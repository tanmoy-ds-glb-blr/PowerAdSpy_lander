import sys
sys.path.append('.')
from helper import init, screenshot
from PIL import Image

page, _ = init.init_dc('in')
try:
    url = 'https://www.gotphoto.co.uk/guides/school-photography-guide/?utm_source=fb&utm_medium=cpc&utm_campaign=UK-FB-IG-PRO-CV-COM-00+%7C+SCH-NUR+I+Lead+I+Dynamic&utm_content=ALL-CV-NA+%7C+UK023+I+Comp+Photog+Interest+Camera_School+Guide+Dynamic+Ad_6316370509468&utm_id=6281896841268&utm_term=6482634880868'
    page.goto(url, timeout=60000, wait_until='domcontentloaded')
    img_path = screenshot.get(page, 'prelander', 'sample_43210_test')
    im = Image.open(img_path)
    print(f"[PASS] GotPhoto captured: size={im.size}")
    assert im.size[1] > 2000, f"Expected height > 2000px, got {im.size[1]}"
finally:
    init.close_browser(page)
