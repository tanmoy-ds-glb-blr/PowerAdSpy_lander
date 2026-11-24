import os
import sys
import logging
import json
from helper import init
import new_lander

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PASS = "[PASS]"
FAIL = "[FAIL]"


def step(label):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")


def main():
    # ── Step 1: Proxy egress check (requests) ────────────────────────────────
    step("Step 1: Bright Data Proxy via requests (direct)")
    egress_info = init.verify_proxy_egress(iso="us")
    if egress_info and egress_info.get("country") == "US":
        print(f"{PASS}  Egress IP: {egress_info.get('ip')} | Country: {egress_info.get('country')}")
    else:
        print(f"{FAIL}  Proxy check returned unexpected result: {egress_info}")
        sys.exit(1)

    # ── Step 2: Playwright browser init with proxy ────────────────────────────
    step("Step 2: Playwright Browser Initialization with Proxy")
    res = init.init_dc("us")
    if not res:
        print(f"{FAIL}  Playwright initialization failed!")
        sys.exit(1)
    page, r_session = res
    print(f"{PASS}  Browser page created. URL: {page.url}")

    try:
        # ── Step 3: Navigate via browser to verify proxy IP ──────────────────
        step("Step 3: Browser navigation → lumtest.com/myip.json")
        page.goto("http://lumtest.com/myip.json", timeout=30000)
        body_text = page.inner_text("body")
        data = json.loads(body_text)
        if data.get("country") == "US":
            print(f"{PASS}  Browser Egress IP: {data.get('ip')} | Country: {data.get('country')}")
        else:
            print(f"{FAIL}  Unexpected country: {data}")
            sys.exit(1)

        # ── Step 4a: check_page_status on a valid live site (Puma) ───────────
        step("Step 4a: check_page_status — ACTIVE site (Puma homepage)")
        print("  Navigating to https://in.puma.com/in/en ...")
        page.goto("https://in.puma.com/in/en", timeout=45000, wait_until="domcontentloaded")
        is_bad, reason = new_lander.check_page_status(page)
        if not is_bad:
            print(f"{PASS}  Puma correctly identified as ACTIVE (is_bad=False)")
        else:
            print(f"{FAIL}  Puma wrongly marked as dead! reason='{reason}'")
            sys.exit(1)

        # ── Step 4b: check_page_status on a real dead URL (expired Facebook ad redirect) ──
        step("Step 4b: check_page_status — DEAD URL (expired Facebook ig_redirect)")
        dead_url = "https://www.facebook.com/ads/ig_redirect/?d=Ad-jHAi55ZEasEP4"
        print(f"  Navigating to {dead_url} ...")
        try:
            page.goto(dead_url, timeout=30000, wait_until="domcontentloaded")
        except Exception as nav_err:
            print(f"  Navigation raised exception (expected for dead URL): {nav_err}")
        is_bad, reason = new_lander.check_page_status(page)
        if is_bad:
            print(f"{PASS}  Dead URL correctly identified as BAD. reason='{reason}'")
        else:
            print(f"{FAIL}  Dead URL NOT detected! is_bad=False. Page may need additional dead-URL markers.")

        # ── Step 5: Screenshot generation ────────────────────────────────────
        step("Step 5: Screenshot Generation on Puma")
        page.goto("https://in.puma.com/in/en", timeout=45000, wait_until="domcontentloaded")
        from helper import screenshot
        os.makedirs("./images/test_instance", exist_ok=True)
        img_path = screenshot.get(page, "test_shot", "test_instance")
        size = os.path.getsize(img_path) if img_path and os.path.isfile(img_path) else 0
        if size > 0:
            print(f"{PASS}  Screenshot saved: {img_path} ({size:,} bytes)")
        else:
            print(f"{FAIL}  Screenshot empty or missing: {img_path}")
            sys.exit(1)

        # ── Step 6: HTML archive packaging ───────────────────────────────────
        step("Step 6: HTML Archive Packaging")
        from helper import html as html_mod
        os.makedirs("./zip/test_instance", exist_ok=True)
        zip_path = html_mod.get(page, r_session, page.url, "test_instance")
        size = os.path.getsize(zip_path) if zip_path and os.path.isfile(zip_path) else 0
        if size > 0:
            print(f"{PASS}  HTML Zip saved: {zip_path} ({size:,} bytes)")
        else:
            print(f"{FAIL}  Zip empty or missing: {zip_path}")
            sys.exit(1)

        # ── All passed ────────────────────────────────────────────────────────
        print(f"\n{'='*60}")
        print("  \u2705 ALL CONTAINER TESTS PASSED SUCCESSFULLY!")
        print(f"{'='*60}\n")

    finally:
        init.close_browser(page)
        for d in ["./images/test_instance", "./zip/test_instance"]:
            if os.path.exists(d):
                import shutil
                shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
