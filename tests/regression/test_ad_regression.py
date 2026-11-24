"""Unit and offline regression tests for PowerAdSpy ad-scraping defect cases.

Tests all previously encountered defects and scraping edge cases from
regression_cases.json using offline mock fixtures and real headless Chromium DOM
evaluations, avoiding external network/proxy dependencies for fast pre-push execution.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from helper.init import _resolve_chrome_paths
from helper.capture import capture_page, encode_under_limit
from PIL import Image, ImageDraw
import new_lander
from tests.regression.regression_runner import (
    DummyMetric,
    load_regression_cases,
    get_regression_case_by_id,
    evaluate_mock_page_status,
    evaluate_mock_login_gate,
)


class MockSimplePage:
    """Lightweight mock of Playwright Page for fast URL/title/content unit tests."""
    def __init__(
        self,
        url="https://example.test/landing-page",
        title="Valid Page",
        content="<html><body>Hello World</body></html>",
        inner_text="Hello World",
        response_status=200,
    ):
        self.url = url
        self._title = title
        self._content = content
        self._inner_text = inner_text
        self._response_status = response_status
        self.frames = []

    def title(self):
        return self._title

    def content(self):
        return self._content

    def inner_text(self, selector="body", timeout=5000):
        return self._inner_text

    def evaluate(self, script):
        if "responseStatus" in script:
            return self._response_status
        if "mediaCount" in script:
            return False
        return None

    def wait_for_timeout(self, ms):
        pass


class AdScrapingRegressionTests(unittest.TestCase):
    """Regression test suite for previously encountered defects in ad scraping."""

    @classmethod
    def setUpClass(cls):
        """Initialise headless Chromium for real DOM tests."""
        try:
            from playwright.sync_api import sync_playwright
            cls._playwright = sync_playwright().start()
            executable = _resolve_chrome_paths()
            kwargs = {"headless": True}
            if executable:
                kwargs["executable_path"] = executable
            cls._browser = cls._playwright.chromium.launch(**kwargs)
        except Exception as exc:
            cls._browser = None
            print(f"[Warning] Headless browser unavailable for DOM regression: {exc}")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_browser", None):
            try:
                cls._browser.close()
            except Exception:
                pass
        if getattr(cls, "_playwright", None):
            try:
                cls._playwright.stop()
            except Exception:
                pass

    def _render_in_browser(self, html_content: str):
        """Helper to render HTML via a file:// URL in Playwright for genuine DOM checks."""
        if not self._browser:
            raise unittest.SkipTest("Playwright browser unavailable")
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html_content)
            temp_path = f.name

        try:
            page = self._browser.new_page()
            page.goto(f"file:///{temp_path.replace(os.sep, '/')}")
            return page, temp_path
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    # ──────────────────────────────────────────────────────────────────────────
    # Catalog Integrity Tests
    # ──────────────────────────────────────────────────────────────────────────

    def test_regression_cases_catalog_integrity(self):
        """Verifies regression_cases.json is well-formed with unique IDs and required keys."""
        cases = load_regression_cases()
        self.assertGreaterEqual(len(cases), 5, "Regression catalog must contain at least 5 baseline cases")

        seen_ids = set()
        seen_codes = set()
        for case in cases:
            ad_id = case.get("id")
            code = case.get("case_code")
            self.assertIsNotNone(ad_id, f"Case missing 'id': {case}")
            self.assertIsNotNone(code, f"Case missing 'case_code': {case}")
            self.assertNotIn(ad_id, seen_ids, f"Duplicate ad id in catalog: {ad_id}")
            self.assertNotIn(code, seen_codes, f"Duplicate case_code in catalog: {code}")
            seen_ids.add(ad_id)
            seen_codes.add(code)

            self.assertIn("category", case)
            self.assertIn("defect_history", case)
            self.assertIn("ad_data", case)
            self.assertIn("expected", case)
            self.assertIn(case["expected"]["status"], (2, 3))

    # ──────────────────────────────────────────────────────────────────────────
    # Defect Scenario: Empty / Missing Destination URL (REG-010 / Ad 99903)
    # ──────────────────────────────────────────────────────────────────────────

    def test_empty_destination_url_defect(self):
        """Ad with empty destination_url must be rejected safely with Status 3 without crashing."""
        case = get_regression_case_by_id(99903)
        self.assertIsNotNone(case)

        ad_data = dict(case["ad_data"])
        metric = DummyMetric()
        logger = new_lander.setup_logger("test_empty_url", "logs/test_empty.log")

        result = new_lander.scraping(
            single_data=ad_data,
            metric=metric,
            lander_logger=logger,
            port="test_port",
            instance_no="test_empty",
            count=0,
            error_logger=logger,
        )
        self.assertFalse(result)
        self.assertEqual(ad_data.get("_result_status"), 3)
        self.assertEqual(ad_data.get("_result_reason"), "Empty destination_url")

    # ──────────────────────────────────────────────────────────────────────────
    # Defect Scenario: Facebook Login Checkpoint Redirect (REG-002 / Ad 134235)
    # ──────────────────────────────────────────────────────────────────────────

    def test_facebook_login_checkpoint_defect(self):
        """Ads redirecting to Facebook /login or /checkpoint must be flagged as Status 3 (Login Gate)."""
        case = get_regression_case_by_id(134235)
        self.assertIsNotNone(case)

        mock_page = MockSimplePage(
            url="https://www.facebook.com/login/?next=https%3A%2F%2Fwww.facebook.com",
            title="Log in to Facebook",
            inner_text="Log In. Recent logins. Click your picture or add an account.",
        )
        is_gate, reason = evaluate_mock_login_gate(
            mock_page,
            destination_url=case["ad_data"]["destination_url"],
            final_url=mock_page.url,
            body_text=mock_page.inner_text(),
        )
        self.assertTrue(is_gate, "Facebook /login redirect must be classified as login wall")
        self.assertIn("Facebook login checkpoint", reason)

    # ──────────────────────────────────────────────────────────────────────────
    # Defect Scenario: HTTP 403 Forbidden Detection (REG-003 / REG-004)
    # ──────────────────────────────────────────────────────────────────────────

    def test_http_403_status_code_defect(self):
        """Pages returning HTTP 403 Forbidden must be caught by Navigation Timing status check."""
        page_403 = MockSimplePage(
            url="https://store.reliancedigital.in/",
            title="Online Shopping",
            response_status=403,
            inner_text="Forbidden",
        )
        is_bad, reason = evaluate_mock_page_status(page_403)
        self.assertTrue(is_bad)
        self.assertIn("403", reason)

    def test_access_denied_title_defect(self):
        """Akamai/EdgeSuite 403 pages with 'Access Denied' or '403 Forbidden' title must be caught."""
        page_denied = MockSimplePage(
            url="https://www.saksfifthavenue.com/",
            title="403 Forbidden - Access Denied",
            response_status=200,  # Even if status code is masked
            inner_text="You don't have permission to access on this server.",
        )
        is_bad, reason = evaluate_mock_page_status(page_denied)
        self.assertTrue(is_bad)
        self.assertTrue("403" in reason or "Title" in reason or "content matched" in reason)

    # ──────────────────────────────────────────────────────────────────────────
    # Defect Scenario: Bot / WAF Cloudflare Challenges (REG-005 / REG-006)
    # ──────────────────────────────────────────────────────────────────────────

    def test_cloudflare_turnstile_marker_defect(self):
        """Pages embedding 'challenges.cloudflare.com' must be caught as Bot/WAF blocks."""
        page_turnstile = MockSimplePage(
            url="https://www.sofi.com/",
            title="Security Verification",  # Non-triggering title to verify source check
            content="<html><head><script src='https://challenges.cloudflare.com/turnstile/v0/api.js'></script></head><body>Verification in progress</body></html>",
            inner_text="Verification in progress",
        )
        is_bad, reason = evaluate_mock_page_status(page_turnstile)
        self.assertTrue(is_bad)
        self.assertIn("Bot/WAF block detected", reason)
        self.assertIn("challenges.cloudflare.com", reason)

    def test_cloudflare_challenge_platform_marker_defect(self):
        """Pages embedding 'cf-browser-verification' or 'cf-challenge' must be caught."""
        page_cf = MockSimplePage(
            url="https://www.groupon.com/deals/n-c",
            title="Site Access",  # Non-triggering title to verify source check
            content="<html><body><div id='cf-challenge'>Checking browser</div></body></html>",
            inner_text="Checking browser",
        )
        is_bad, reason = evaluate_mock_page_status(page_cf)
        self.assertTrue(is_bad)
        self.assertIn("Bot/WAF block detected", reason)
        self.assertIn("cf-challenge", reason)

    # ──────────────────────────────────────────────────────────────────────────
    # False-Positive Prevention: Rich E-Commerce with Slide-Out Login (REG-008)
    # ──────────────────────────────────────────────────────────────────────────

    def test_rich_ecommerce_store_not_flagged_as_login_gate(self):
        """Rich store pages with login drawers must NOT be falsely marked as Status 3 login walls."""
        case = get_regression_case_by_id(99901)
        self.assertIsNotNone(case)
        scenario = case["mock_scenario"]

        page = MockSimplePage(
            url=scenario["final_url"],
            title=scenario["title"],
            inner_text=scenario["body_text"],
        )
        is_gate, reason = evaluate_mock_login_gate(
            page,
            destination_url=case["ad_data"]["destination_url"],
            final_url=scenario["final_url"],
            body_text=scenario["body_text"],
        )
        self.assertFalse(is_gate, f"Rich e-commerce page was falsely flagged as login gate: {reason}")

    # ──────────────────────────────────────────────────────────────────────────
    # False-Positive Prevention: i18n Translation Bundles in Script (REG-009)
    # ──────────────────────────────────────────────────────────────────────────

    def test_i18n_script_bundle_not_flagged_as_dead_page(self):
        """Strings like 'page not found' inside <script> JSON must NOT trigger dead page status."""
        case = get_regression_case_by_id(99902)
        self.assertIsNotNone(case)
        scenario = case["mock_scenario"]

        page, temp_path = self._render_in_browser(scenario["page_source"])
        try:
            is_bad, reason = new_lander.check_page_status(page)
            self.assertFalse(
                is_bad,
                f"Page was falsely classified as dead due to script tag contents: {reason}"
            )
        finally:
            page.close()
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # ──────────────────────────────────────────────────────────────────────────
    # Defect Scenario: Genuine Visible 404 Not Found (REG-011)
    # ──────────────────────────────────────────────────────────────────────────

    def test_genuine_404_body_detected_as_dead_page(self):
        """A page displaying '404 Page Not Found' in visible body must be caught as Status 3."""
        case = get_regression_case_by_id(99904)
        self.assertIsNotNone(case)
        scenario = case["mock_scenario"]

        page, temp_path = self._render_in_browser(scenario["page_source"])
        try:
            is_bad, reason = new_lander.check_page_status(page)
            self.assertTrue(is_bad, "Genuine 404 page was not detected as dead")
            self.assertTrue(
                "404" in reason or "content matched" in reason or "keyword matched" in reason,
                f"Unexpected reason: {reason}"
            )
        finally:
            page.close()
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # ──────────────────────────────────────────────────────────────────────────
    # Defect Scenario: Browser Internal Error URLs
    # ──────────────────────────────────────────────────────────────────────────

    def test_browser_internal_error_urls_detected(self):
        """chrome-error:// and about:blank must be detected immediately."""
        for error_url in [
            "chrome-error://chromewebdata/",
            "about:blank",
            "data:text/html,chromewebdata",
        ]:
            page = MockSimplePage(url=error_url)
            is_bad, reason = evaluate_mock_page_status(page)
            self.assertTrue(is_bad, f"Failed to catch error URL: {error_url}")
            self.assertIn("Browser error URL", reason)

    # ──────────────────────────────────────────────────────────────────────────
    # Dynamic Status 3 Keywords File Verification
    # ──────────────────────────────────────────────────────────────────────────

    def test_dynamic_status3_keywords_reloading(self):
        """Ensures get_status3_keywords() loads phrases from status_3_keywords.txt."""
        keywords = new_lander.get_status3_keywords()
        self.assertIsInstance(keywords, list)
        self.assertGreater(len(keywords), 0, "status_3_keywords.txt should contain keywords")


    # ──────────────────────────────────────────────────────────────────────────
    # Defect Scenario: Screenshot Full-Height Capture & 1MB Limit Regression
    # ──────────────────────────────────────────────────────────────────────────

    def test_screenshot_tall_page_full_capture_not_clamped_to_viewport(self):
        """Tall landing pages must be captured at full document height, never clamped to viewport."""
        html = """
        <!doctype html><html><body style="margin:0;padding:0;background:#f5f5f7">
          <header style="height:200px;background:#333;color:#fff;padding:20px"><h1>Top Header</h1></header>
          <section style="height:1500px;background:linear-gradient(#fff, #0071e3);padding:20px">
            <h2>Product Specs</h2><p>Feature details section 1</p>
          </section>
          <section style="height:1500px;background:linear-gradient(#0071e3, #333);color:#fff;padding:20px">
            <h2>Deep Specs</h2><p>Feature details section 2</p>
          </section>
          <footer style="height:1000px;background:#111;color:#fff;padding:20px">
            <p>Copyright 2026 Legal Footer</p>
          </footer>
        </body></html>
        """
        page, temp_path = self._render_in_browser(html)
        old_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as folder:
                try:
                    os.chdir(folder)
                    class FullPageConfig:
                        def get_default(self, key):
                            return {
                                "CAPTURE_MAX_HEIGHT": 32000,
                                "CAPTURE_MAX_WIDTH": 1920,
                                "SCREENSHOT_MAX_BYTES": 1048576,
                            }.get(key)

                    result = capture_page(page, "tall_test", "reg_instance", config=FullPageConfig())
                    self.assertEqual(result.state, "full")
                    self.assertFalse(result.truncated)
                    # Must capture full document (> 4000 px), strictly NOT clamped to viewport (720 px)
                    self.assertGreaterEqual(result.height, 4000, "Screenshot was truncated to viewport height!")
                    self.assertLessEqual(result.final_bytes, 1048576, "Screenshot exceeded 1.0 MB limit!")
                    self.assertTrue(os.path.exists(result.image_path))
                    self.assertEqual(os.path.getsize(result.image_path), result.final_bytes)
                finally:
                    os.chdir(old_cwd)
        finally:
            page.close()
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_screenshot_bounded_clip_captures_full_bound_not_viewport(self):
        """When CAPTURE_MAX_HEIGHT is reached, Playwright clip must capture up to limit, not viewport."""
        html = """
        <!doctype html><html><body style="margin:0;padding:0">
          <div style="height:6000px;background:linear-gradient(#fff, #111);padding:20px">
            <h1>Long Webpage</h1>
            <div style="position:absolute;top:2000px">Midway Marker</div>
            <div style="position:absolute;top:4000px">Lower Marker</div>
          </div>
        </body></html>
        """
        page, temp_path = self._render_in_browser(html)
        old_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as folder:
                try:
                    os.chdir(folder)
                    class BoundedConfig:
                        def get_default(self, key):
                            return {
                                "CAPTURE_MAX_HEIGHT": 2500,
                                "CAPTURE_MAX_WIDTH": 1920,
                                "SCREENSHOT_MAX_BYTES": 1048576,
                            }.get(key)

                    result = capture_page(page, "bounded_test", "reg_instance", config=BoundedConfig())
                    self.assertEqual(result.state, "partial")
                    self.assertTrue(result.truncated)
                    # Height must equal the bounded limit (2500 px), NOT viewport height (~720 px)
                    self.assertEqual(result.height, 2500, "Bounded clip failed to capture full bound!")
                    self.assertGreater(result.height, 1000, "Bounded clip was erroneously clamped to viewport!")
                    self.assertLessEqual(result.final_bytes, 1048576)
                finally:
                    os.chdir(old_cwd)
        finally:
            page.close()
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_screenshot_compression_and_1mb_limit_guarantee(self):
        """Image encoder must reliably compress large/tall screenshots strictly under 1 MB."""
        with tempfile.TemporaryDirectory() as folder:
            # Create a very tall synthetic image: 1920 x 25000 px
            tall_image = Image.new("RGB", (1920, 25000), color=(245, 245, 247))
            draw = ImageDraw.Draw(tall_image)
            for y in range(0, 25000, 500):
                draw.rectangle([(50, y), (1870, y + 200)], fill=(y % 255, (y * 2) % 255, (y * 3) % 255))
                draw.text((100, y + 50), f"Section marker at y={y} px", fill=(255, 255, 255))

            out_path = os.path.join(folder, "test_tall_compressed.jpg")
            w, h, size, quality = encode_under_limit(tall_image, out_path, max_bytes=1048576)

            self.assertTrue(os.path.exists(out_path))
            self.assertLessEqual(size, 1048576, f"Compressed file size {size} exceeded 1.0 MB (1048576 bytes)!")
            self.assertEqual(size, os.path.getsize(out_path))
            self.assertGreater(h, 5000, "Encoded image height should remain substantial")
            self.assertGreaterEqual(quality, 45, "Quality dropped below minimum 45")


if __name__ == "__main__":
    unittest.main()
