import sys
sys.path.append('.')
from helper import init, screenshot
from PIL import Image

page, _ = init.init_dc('in')
try:
    url = 'https://www.eventbrite.co.uk/e/hatching-dragons-city-nursery-school-open-house-tickets-828264801317?aff=oddtdtcreator&utm_campaign=Event%3A+Hatching+Dragons+City+-+Nursery+School+Open+House&utm_source=facebook&utm_medium=paid&hsa_acc=556544545849589&hsa_cam=120209102687610387&hsa_grp=120209102687650387&hsa_ad=120209102688240387&hsa_src=fb&hsa_net=facebook&hsa_ver=3'
    page.goto(url, timeout=60000, wait_until='domcontentloaded')
    img_path = screenshot.get(page, 'prelander', 'sample_43016_test')
    im = Image.open(img_path)
    print(f"[PASS] Eventbrite captured: size={im.size}")
    assert im.size[1] < 3500, f"Expected height < 3500px, got {im.size[1]}"
finally:
    init.close_browser(page)
