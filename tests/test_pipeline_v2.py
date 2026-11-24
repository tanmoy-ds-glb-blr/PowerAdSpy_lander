import os
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image, ImageDraw

from helper.capture import encode_under_limit
from helper import html as html_archive
from helper.navigation import navigate
from helper.pipeline import ScrapeDeadline, safe_url
from helper import api_client
import new_lander


class FakeRequest:
    def __init__(self, url, redirected_from=None):
        self.url = url
        self.redirected_from = redirected_from
        self.failure = None


class FakeResponse:
    def __init__(self, status, request):
        self.status = status
        self.request = request


class FakePage:
    def __init__(self, score=100, popup=None):
        self.url = "about:blank"
        self.handlers = {}
        self.score = score
        self.popup = popup

    def on(self, event, callback):
        self.handlers[event] = callback

    def goto(self, url, **_kwargs):
        first = FakeRequest("https://example.test/start")
        last = FakeRequest(url, redirected_from=first)
        self.url = url
        if self.popup and "popup" in self.handlers:
            self.handlers["popup"](self.popup)
        return FakeResponse(200, last)

    def evaluate(self, _script):
        return {"text": self.score, "media": 0, "area": 1000}

    def is_closed(self):
        return False


class PipelineV2Tests(unittest.TestCase):
    def test_api_idempotency_key_is_stable_across_retry(self):
        class Response:
            def __init__(self, status):
                self.status_code = status
                self.headers = {}
        class Session:
            def __init__(self):
                self.keys = []
            def request(self, _method, _url, headers=None, **_kwargs):
                self.keys.append(headers["X-Idempotency-Key"])
                return Response(500 if len(self.keys) == 1 else 200)
        session = Session()
        response = api_client.request("POST", "https://example.test", session=session, attempts=2, idempotency_key="run-1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(session.keys, ["run-1", "run-1"])

    def test_retry_after_seconds_is_respected(self):
        class Response:
            headers = {"Retry-After": "2.5"}
        self.assertEqual(api_client.retry_delay(Response(), 1), 2.5)

    def test_login_path_regex_uses_real_word_boundary(self):
        for path in ("/login", "/sign-in", "/signup", "/customer/account/login"):
            self.assertIsNotNone(new_lander.LOGIN_URL_PATH_REGEX.search(path), path)

    def test_safe_url_redacts_secrets_and_fragment(self):
        value = safe_url("https://user:pass@example.test/a?token=abc&x=1#secret")
        self.assertNotIn("user", value)
        self.assertNotIn("pass", value)
        self.assertNotIn("abc", value)
        self.assertNotIn("#secret", value)
        self.assertIn("%5BREDACTED%5D", value)

    def test_navigation_uses_response_and_redirect_chain(self):
        result = navigate(FakePage(), "https://example.test/final", attempts=1)
        self.assertEqual(result.status, 200)
        self.assertEqual(result.final_url, "https://example.test/final")
        self.assertEqual(result.redirects, ["https://example.test/start"])
        self.assertFalse(result.error_code)

    def test_navigation_selects_content_rich_popup(self):
        popup = FakePage(score=1000)
        popup.url = "https://example.test/lander"
        main = FakePage(score=10, popup=popup)
        result = navigate(main, "https://example.test/final", attempts=1)
        self.assertTrue(result.selected_popup)
        self.assertIs(result.selected_page, popup)
        self.assertEqual(result.final_url, popup.url)

    def test_scrape_deadline_is_shared_and_enforced(self):
        deadline = ScrapeDeadline(1)
        deadline.ends = time.monotonic() - 0.01
        with self.assertRaisesRegex(TimeoutError, "unit_stage"):
            deadline.check("unit_stage")

    def test_archive_contains_manifest_and_iframe_document(self):
        class Page:
            def content(self):
                return "<html><body></body></html>"
        class Limits:
            def get_default(self, key):
                return {
                    "HTML_ARCHIVE_ENABLED": True,
                    "HTML_ARCHIVE_MAX_BYTES": 2 * 1024 * 1024,
                    "HTML_ASSET_MAX_COUNT": 5,
                    "HTML_ARCHIVE_TIMEOUT_SECONDS": 2,
                }.get(key)
        source = '<html><body><img src="http://127.0.0.1/not-fetched.png"></body></html>'
        frames = [{"url": "https://frame.test/", "name": "creative", "html": "<p>Frame creative</p>", "saved": True}]
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                archive_path = html_archive.get(Page(), None, "https://page.test/", "run", source, frames, Limits())
                self.assertTrue(os.path.isfile(archive_path))
                with ZipFile(archive_path) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertIn("frames/frame_001.html", archive.namelist())
                    manifest = json.loads(archive.read("archive_manifest.json"))
                    archived_html = archive.read("PowerAdSpy.html").decode("utf-8")
                self.assertTrue(manifest["frames"][0]["saved"])
                self.assertFalse(manifest["assets"][0]["saved"])
                self.assertIn("http://127.0.0.1/not-fetched.png", archived_html)
            finally:
                os.chdir(old_cwd)

    def test_queue_lease_prevents_concurrent_duplicate(self):
        class MetricCounter:
            def labels(self, **_kwargs):
                return self
            def inc(self):
                return None
        class Metric:
            configured_lander_get = MetricCounter()
        class Logger:
            def info(self, *_args, **_kwargs):
                return None
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                queue_path = new_lander._shared_queue_path()
                new_lander._atomic_write_json(queue_path, [{"id": 91, "destination_url": "https://example.test"}])
                lock = threading.Lock()
                leases = {}
                completed = {}
                first = new_lander.pop_next_ad_from_file(lock, "1", Metric(), Logger(), leases, completed)
                new_lander._atomic_write_json(queue_path, [{"id": 91, "destination_url": "https://example.test"}])
                original_hit_api = new_lander.config.hit_get_api
                new_lander.config.hit_get_api = False
                try:
                    with patch.object(new_lander, "get_input_from_file", return_value=([], "fixture.json")):
                        second = new_lander.pop_next_ad_from_file(lock, "2", Metric(), Logger(), leases, completed)
                finally:
                    new_lander.config.hit_get_api = original_hit_api
                self.assertEqual(first["id"], 91)
                self.assertNotIsInstance(second, dict)
                self.assertIn(91, leases)
                self.assertEqual(leases[91][2]["destination_url"], "https://example.test")
            finally:
                os.chdir(old_cwd)

    def test_expired_lease_requeues_persisted_item(self):
        class MetricCounter:
            def labels(self, **_kwargs):
                return self
            def inc(self):
                return None
        class Metric:
            configured_lander_get = MetricCounter()
        class Logger:
            def info(self, *_args, **_kwargs):
                return None
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                item = {"id": 92, "destination_url": "https://expired.test"}
                lease_age = float(new_lander.config.get_default("QUEUE_LEASE_SECONDS") or 300) + 5
                leases = {92: ("dead-worker", time.time() - lease_age, item)}
                recovered = new_lander.pop_next_ad_from_file(
                    threading.Lock(), "3", Metric(), Logger(), leases, {}
                )
                self.assertEqual(recovered, item)
                self.assertEqual(leases[92][2], item)
            finally:
                os.chdir(old_cwd)

    def test_failed_artifacts_are_retained_by_run(self):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                os.makedirs(os.path.join("images", "7"))
                os.makedirs(os.path.join("zip", "7"))
                with open(os.path.join("images", "7", "prelander.jpg"), "wb") as handle:
                    handle.write(b"image")
                with open(os.path.join("zip", "7", "html.zip"), "wb") as handle:
                    handle.write(b"archive")
                retained = new_lander._finalize_artifacts("7", 44, "run-abc", False)
                self.assertTrue(os.path.isfile(os.path.join(retained, "images", "prelander.jpg")))
                self.assertTrue(os.path.isfile(os.path.join(retained, "zip", "html.zip")))
                self.assertTrue(os.path.isfile(os.path.join(retained, "retention.json")))
            finally:
                os.chdir(old_cwd)

    def test_encoder_enforces_exact_byte_limit(self):
        image = Image.new("RGB", (1600, 3200), "white")
        draw = ImageDraw.Draw(image)
        for y in range(0, 3200, 40):
            draw.rectangle((0, y, 1599, y + 20), fill=((y * 3) % 255, (y * 7) % 255, (y * 11) % 255))
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "result.jpg")
            width, height, size, quality = encode_under_limit(image, path, max_bytes=200000, min_width=600)
            self.assertLessEqual(size, 200000)
            self.assertEqual(size, os.path.getsize(path))
            self.assertGreaterEqual(width, 600)
            self.assertGreater(height, width)
            self.assertGreaterEqual(quality, 45)

    def test_encoder_fails_instead_of_returning_oversized_file(self):
        image = Image.effect_noise((1000, 1000), 100).convert("RGB")
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, "COMPRESSION_LIMIT_FAILED"):
                encode_under_limit(image, os.path.join(folder, "x.jpg"), max_bytes=100, min_width=1000)


if __name__ == "__main__":
    unittest.main()
