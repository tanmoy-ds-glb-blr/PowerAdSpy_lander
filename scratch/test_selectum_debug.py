import sys
sys.path.append('.')
import time
import os
from helper import init, screenshot

page, _ = init.init_dc('in')
try:
    url = 'https://www.selectumhotels.com/en?utm_source=facebook&utm_medium=cpc&utm_campaign=uk-genel'
    for attempt in range(3):
        try:
            page.goto(url, timeout=90000, wait_until='domcontentloaded')
            break
        except Exception as e:
            print(f"Attempt {attempt} failed: {e}")
            time.sleep(2)
            
    time.sleep(3)
    target = screenshot.get(page, 'test_selectum', 'test_sel')
    print('Selectum target size:', os.path.getsize(target))
    from PIL import Image
    im = Image.open(target)
    print('Selectum image dimensions:', im.size)
finally:
    init.close_browser(page)
