import sys
sys.path.append('.')
import time
import os
from helper import init, screenshot

page, _ = init.init_dc('in')
try:
    url = 'https://www.selectumhotels.com/en?utm_source=facebook&utm_medium=cpc&utm_campaign=uk-genel'
    loaded = False
    for attempt in range(5):
        try:
            print(f"Connecting attempt {attempt+1}...")
            page.goto(url, timeout=90000, wait_until='domcontentloaded')
            loaded = True
            break
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            time.sleep(3)
    if not loaded:
        print("Failed all attempts to connect to selectumhotels.com")
        sys.exit(1)
    time.sleep(10)
    
    # 0. Before
    page.screenshot(path='scratch/sel_diag_0.jpg', full_page=True)
    print('sel_diag_0 (before):', os.path.getsize('scratch/sel_diag_0.jpg'))
    
    # 1. Cookie button click
    btn = page.query_selector('button:has-text("Accept All")')
    if btn:
        print('Found Accept All btn, clicking...')
        btn.click()
        time.sleep(1)
    page.screenshot(path='scratch/sel_diag_1_after_btn.jpg', full_page=True)
    print('sel_diag_1_after_btn:', os.path.getsize('scratch/sel_diag_1_after_btn.jpg'))
    
    # 2. Call screenshot.get
    target = screenshot.get(page, 'sel_diag_final', 'test_sel_diag')
    print('sel_diag_final from screenshot.get:', os.path.getsize(target))

finally:
    init.close_browser(page)
