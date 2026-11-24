import sys
sys.path.append('.')
from PIL import Image
from playwright.sync_api import sync_playwright
from helper.screenshot import _wake_lazy_images as _wake_lazy_images_test

def test_flipkart():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--disable-web-security"]
        )
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto("https://www.flipkart.com/wd-blue-nvme-sn550-250-gb-desktop-laptop-internal-solid-state-drive-ssd-wds250g2b0c/p/itm490aff88d3a73", wait_until="networkidle", timeout=90000)
        _wake_lazy_images_test(page)
        page.screenshot(path="scratch/flipkart_check_restore.jpg", full_page=True)
        im = Image.open("scratch/flipkart_check_restore.jpg")
        print("Flipkart size:", im.size)
        browser.close()

if __name__ == "__main__":
    test_flipkart()
