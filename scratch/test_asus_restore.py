import sys
sys.path.append('.')
import os
import time
from PIL import Image
from playwright.sync_api import sync_playwright
from helper.screenshot import _wake_lazy_images as _wake_lazy_images_test, _RESTORE_REVEALED_CONTENT_JS

def test_asus():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--disable-web-security"]
        )
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto("https://www.asus.com/in/motherboards-components/motherboards/tuf-gaming/tuf-gaming-z790-pro-wifi/", wait_until="networkidle", timeout=90000)
        _wake_lazy_images_test(page)
        page.screenshot(path="scratch/asus_check_restore.jpg", full_page=True)
        im = Image.open("scratch/asus_check_restore.jpg")
        print("Asus size:", im.size)
        browser.close()

if __name__ == "__main__":
    test_asus()
