import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
import os
from PIL import Image
from helper import init, screenshot

page, _ = init.init_dc('in')
url = "https://www.pinterest.com/pinterest/?utm_source=Paid_YouTube&utm_campaign=ConsumerBrand_US_Q22026Anthem60&utm_medium=PaidMedia&gad_source=2&gad_campaignid=23743086863&gclid=EAIaIQobChMIwe2yiK_XlAMVAwzbAR2IQBhnEAEYAiAAEgJkvvD_BwE"

try:
    page.goto(url, timeout=90000, wait_until='domcontentloaded')
    img_path = screenshot.get(page, "test_pinterest", "scratch")
    if os.path.isfile(img_path):
        im = Image.open(img_path)
        print(f"Captured: {img_path} | Size: {im.size} | File bytes: {os.path.getsize(img_path)}")
except Exception as e:
    print(f"Error: {e}")
finally:
    init.close_browser(page)
