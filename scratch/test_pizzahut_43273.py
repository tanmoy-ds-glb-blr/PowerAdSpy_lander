import sys
sys.path.append('.')
from helper import init, screenshot
from PIL import Image

page, _ = init.init_dc('in')
try:
    url = 'https://www.pizzahut.co.uk/?utm_source=meta&utm_medium=social&utm_campaign=hothoney'
    page.goto(url, timeout=60000, wait_until='domcontentloaded')
    img_path = screenshot.get(page, 'prelander', 'sample_43273_test')
    im = Image.open(img_path)
    print(f"[PASS] Pizza Hut captured: size={im.size}")
    assert im.size[1] < 3000, f"Expected natural height < 3000px, got {im.size[1]}"
finally:
    init.close_browser(page)
