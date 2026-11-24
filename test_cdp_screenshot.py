"""
Docker container test: validates CDP full-page screenshot on 4 page types.
Run inside container with:  python3 test_cdp_screenshot.py
"""
import os
import sys
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from helper import screenshot


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,800")
    return webdriver.Chrome(options=opts)


def report(label, path, viewport_h):
    with Image.open(path) as img:
        w, h = img.size
    size_kb = os.path.getsize(path) / 1024
    print(f"  Image size : {w} x {h} px")
    print(f"  File size  : {size_kb:.1f} KB")
    assert size_kb <= 1024, f"File exceeds 1 MB! ({size_kb:.1f} KB)"
    return w, h, size_kb


def run_tests():
    driver = make_driver()
    results = []
    try:
        viewport_h = driver.execute_script("return window.innerHeight")
        print(f"\nViewport height inside container: {viewport_h}px\n")

        # TEST 1: Normal long scrollable page (3000px tall)
        print("=" * 60)
        print("TEST 1: Normal Scrolling Page (3000px tall)")
        print("=" * 60)
        long_html = ("<html><body style=\'margin:0;height:3000px;"
                     "background:linear-gradient(red,yellow,blue);\'>"
                     "<h1>Top</h1>"
                     "<div style=\'position:absolute;top:1400px\'><h1>Middle</h1></div>"
                     "<div style=\'position:absolute;top:2800px\'><h1>Bottom</h1></div>"
                     "</body></html>")
        driver.get("data:text/html;charset=utf-8," + long_html)
        os.makedirs("./images/test_cdp_long", exist_ok=True)
        path = screenshot.get(driver, "long_page", "test_cdp_long")
        w, h, kb = report("long", path, viewport_h)
        assert h > viewport_h, f"Expected h > {viewport_h}, got {h}"
        assert h > 1000, f"Expected tall page, got {h}px"
        print("[TEST 1 PASSED] Full-page capture is taller than single viewport!\n")
        results.append(("PASS", "TEST 1 - 3000px long page"))

        # TEST 2: Non-scrolling SPA page (overflow:hidden)
        print("=" * 60)
        print("TEST 2: Non-Scrolling SPA Page (overflow:hidden)")
        print("=" * 60)
        spa_html = ("<html><body style=\'margin:0;height:100vh;"
                    "overflow:hidden;background:lime;\'>"
                    "<h1>Single-screen SPA</h1></body></html>")
        driver.get("data:text/html;charset=utf-8," + spa_html)
        os.makedirs("./images/test_cdp_spa", exist_ok=True)
        path = screenshot.get(driver, "spa_page", "test_cdp_spa")
        w, h, kb = report("spa", path, viewport_h)
        assert h <= viewport_h + 50, f"Expected ~{viewport_h}px, got {h}"
        print("[TEST 2 PASSED] SPA captured cleanly as single screen!\n")
        results.append(("PASS", "TEST 2 - SPA overflow:hidden"))

        # TEST 3: Very long page capped at 12000px
        print("=" * 60)
        print("TEST 3: Extremely Long Page (15000px) capped at 12000px")
        print("=" * 60)
        huge_html = ("<html><body style=\'margin:0;height:15000px;"
                     "background:linear-gradient(purple,orange);\'>"
                     "<h1>Top of Huge Page</h1>"
                     "<div style=\'position:absolute;top:13000px\'><h1>Near Bottom</h1></div>"
                     "</body></html>")
        driver.get("data:text/html;charset=utf-8," + huge_html)
        os.makedirs("./images/test_cdp_huge", exist_ok=True)
        path = screenshot.get(driver, "huge_page", "test_cdp_huge")
        w, h, kb = report("huge", path, viewport_h)
        assert h <= 12000 + 50, f"Expected height <= 12000, got {h}"
        assert h > 8000, f"Expected capture taller than 8000px, got {h}px"
        print("[TEST 3 PASSED] Huge page capped safely at <=12000px!\n")
        results.append(("PASS", "TEST 3 - 15000px page capped at 12000px"))

        # TEST 4: 100vh Hero section must NOT stretch into a void
        print("=" * 60)
        print("TEST 4: 100vh Hero Section (Must not stretch into void)")
        print("=" * 60)
        vh_html = (
            "<html><body style=\'margin:0;padding:0;\'>"
            "<div style=\'height:100vh;background:navy;color:white;display:flex;"
            "align-items:center;justify-content:center;\'>"
            "<h1>Hero Banner (100vh)</h1>"
            "</div>"
            "<div style=\'height:2000px;background:lightgray;padding:20px;\'>"
            "<h2>Body Content (2000px)</h2>"
            "</div>"
            "</body></html>"
        )
        driver.get("data:text/html;charset=utf-8," + vh_html)
        os.makedirs("./images/test_cdp_vh", exist_ok=True)
        path = screenshot.get(driver, "vh_page", "test_cdp_vh")
        w, h, kb = report("vh", path, viewport_h)
        # The expected total height is viewport_h (hero) + 2000px body, NOT a 12000px void!
        expected_h = viewport_h + 2000
        assert abs(h - expected_h) < 150, f"Hero banner stretched! Expected ~{expected_h}px, got {h}px"
        print(f"[TEST 4 PASSED] 100vh hero section rendered at natural size ({h}px total)!\n")
        results.append(("PASS", "TEST 4 - 100vh hero banner"))

    finally:
        driver.quit()
        import shutil
        for d in ["./images/test_cdp_long", "./images/test_cdp_spa", "./images/test_cdp_huge", "./images/test_cdp_vh"]:
            shutil.rmtree(d, ignore_errors=True)

    print("=" * 60)
    print("                FINAL SUMMARY")
    print("=" * 60)
    all_pass = True
    for status, name in results:
        mark = "OK" if status == "PASS" else "FAIL"
        print(f"  [{mark}] {name}: {status}")
        if status != "PASS":
            all_pass = False
    print()
    if all_pass:
        print(">>> ALL 4 CDP SCREENSHOT TESTS PASSED 100%! <<<")
        sys.exit(0)
    else:
        print(">>> SOME TESTS FAILED <<<")
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
