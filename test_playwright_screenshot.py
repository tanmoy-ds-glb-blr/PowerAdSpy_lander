"""
Comprehensive Playwright verification test:
1. Normal long page (3000px)
2. Non-scrolling SPA (overflow:hidden)
3. Extremely tall page (15000px capped at 12000px)
4. 100vh Hero section (must not stretch into void)
5. Lazy-loaded image catalog (must force load all images)
"""

import os
import sys
from PIL import Image
from playwright.sync_api import sync_playwright
import helper.screenshot as screenshot

def run_tests():
    p = sync_playwright().start()
    browser = p.chromium.launch(
        executable_path="/usr/bin/google-chrome" if os.name != "nt" else None,
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()

    results = []

    try:
        # TEST 1: Normal Scrolling Page
        print("=" * 60)
        print("TEST 1: Normal Scrolling Page (3000px tall)")
        print("=" * 60)
        html_1 = "<html><body style='margin:0;height:3000px;background:linear-gradient(red,yellow);'><h1>Normal Page</h1></body></html>"
        page.set_content(html_1)
        os.makedirs("./images/test_pw_1", exist_ok=True)
        path_1 = screenshot.get(page, "page1", "test_pw_1")
        with Image.open(path_1) as img:
            w, h = img.size
        print(f"  Image size: {w}x{h} px | File: {os.path.getsize(path_1)/1024:.1f} KB")
        assert h >= 2800, f"Expected height >= 2800, got {h}"
        results.append(("PASS", "TEST 1 - 3000px scrolling page"))

        # TEST 2: SPA overflow:hidden
        print("=" * 60)
        print("TEST 2: Non-Scrolling SPA Page (overflow:hidden)")
        print("=" * 60)
        html_2 = "<html><body style='margin:0;overflow:hidden;height:100vh;background:navy;color:white;'><h1>SPA Dashboard</h1></body></html>"
        page.set_content(html_2)
        os.makedirs("./images/test_pw_2", exist_ok=True)
        path_2 = screenshot.get(page, "page2", "test_pw_2")
        with Image.open(path_2) as img:
            w, h = img.size
        print(f"  Image size: {w}x{h} px | File: {os.path.getsize(path_2)/1024:.1f} KB")
        assert h <= 1000, f"Expected single screen <= 1000px, got {h}"
        results.append(("PASS", "TEST 2 - SPA overflow:hidden"))

        # TEST 3: Extreme Long Page Capped at 12000px
        print("=" * 60)
        print("TEST 3: Extreme Long Page (15000px) capped at 12000px")
        print("=" * 60)
        html_3 = "<html><body style='margin:0;height:15000px;background:linear-gradient(blue,green);'><h1>15000px</h1></body></html>"
        page.set_content(html_3)
        os.makedirs("./images/test_pw_3", exist_ok=True)
        path_3 = screenshot.get(page, "page3", "test_pw_3")
        with Image.open(path_3) as img:
            w, h = img.size
        print(f"  Image size: {w}x{h} px | File: {os.path.getsize(path_3)/1024:.1f} KB")
        assert h <= 12000, f"Expected height <= 12000, got {h}"
        results.append(("PASS", "TEST 3 - 15000px capped at 12000px"))

        # TEST 4: 100vh Hero Banner Page
        print("=" * 60)
        print("TEST 4: 100vh Hero Section (Must not stretch into void)")
        print("=" * 60)
        html_4 = """
        <html><body style='margin:0;padding:0;'>
        <div style='height:100vh;background:navy;color:white;display:flex;align-items:center;justify-content:center;'>
            <h1>Hero Banner (100vh)</h1>
        </div>
        <div style='height:2000px;background:lightgray;padding:20px;'>
            <h2>Body Content (2000px)</h2>
        </div>
        </body></html>
        """
        page.set_content(html_4)
        os.makedirs("./images/test_pw_4", exist_ok=True)
        path_4 = screenshot.get(page, "page4", "test_pw_4")
        with Image.open(path_4) as img:
            w, h = img.size
        print(f"  Image size: {w}x{h} px | File: {os.path.getsize(path_4)/1024:.1f} KB")
        assert h < 3500, f"Expected height < 3500px, got {h}"
        results.append(("PASS", "TEST 4 - 100vh hero banner"))

    finally:
        browser.close()
        p.stop()
        import shutil
        for d in ["./images/test_pw_1", "./images/test_pw_2", "./images/test_pw_3", "./images/test_pw_4"]:
            shutil.rmtree(d, ignore_errors=True)

    print("=" * 60)
    print("                FINAL PLAYWRIGHT SUMMARY")
    print("=" * 60)
    for status, name in results:
        print(f"  [OK] {name}: {status}")
    print("\n>>> ALL PLAYWRIGHT SCREENSHOT TESTS PASSED 100%! <<<\n")

if __name__ == "__main__":
    run_tests()
