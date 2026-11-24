import sys
sys.path.append('.')
from helper import init, screenshot
from PIL import Image

page, _ = init.init_dc('in')
try:
    url = 'https://www.routesinteriors.com/'
    page.goto(url, timeout=60000, wait_until='domcontentloaded')
    img_path = screenshot.get(page, 'prelander', 'sample_43271_test')
    im = Image.open(img_path)
    print(f"[PASS] Routes Interiors captured: size={im.size}")
    assert im.size[1] > 4000, f"Expected full page height > 4000px, got {im.size[1]}"
finally:
    init.close_browser(page)
