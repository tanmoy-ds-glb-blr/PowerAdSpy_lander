import sys
sys.path.append('.')
import time
import os
from helper import init, screenshot

page, _ = init.init_dc('in')
try:
    url = 'https://www.selectumhotels.com/en?utm_source=facebook&utm_medium=cpc&utm_campaign=uk-genel'
    for _ in range(3):
        try:
            page.goto(url, timeout=90000, wait_until='domcontentloaded')
            break
        except Exception:
            time.sleep(2)
            
    time.sleep(10)
    page.screenshot(path='scratch/find_s_0_loaded.jpg')
    print('Loaded at 10s:', os.path.getsize('scratch/find_s_0_loaded.jpg'))
    
    # Check 1: _wake_lazy_images
    screenshot._wake_lazy_images(page)
    page.screenshot(path='scratch/find_s_1_after_wake.jpg')
    print('After wake:', os.path.getsize('scratch/find_s_1_after_wake.jpg'))
    
    # Check 2: Animation JS
    page.evaluate(screenshot._UNIVERSAL_ANIMATION_JS)
    page.screenshot(path='scratch/find_s_2_after_anim.jpg')
    print('After anim:', os.path.getsize('scratch/find_s_2_after_anim.jpg'))
    
    # Check 3: Full page screenshot
    png_bytes = page.screenshot(full_page=True, timeout=60000)
    with open('scratch/find_s_3_fullpage.jpg', 'wb') as f:
        f.write(png_bytes)
    print('Full page:', os.path.getsize('scratch/find_s_3_fullpage.jpg'))
    
    # Check 4: Viewport screenshot
    vp_bytes = page.screenshot(full_page=False, timeout=30000)
    with open('scratch/find_s_4_viewport.jpg', 'wb') as f:
        f.write(vp_bytes)
    print('Viewport:', os.path.getsize('scratch/find_s_4_viewport.jpg'))

finally:
    init.close_browser(page)
