import sys
sys.path.append('.')
import time
import os
from helper import init, screenshot

def test_ad(ad_id, url, iso='in'):
    print(f"=== Testing Ad {ad_id}: {url} ===")
    page, _ = init.init_dc(iso)
    try:
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        print(f"Page loaded, waiting 10s...")
        time.sleep(10)
        
        # Take a raw screenshot first
        raw_path = f"scratch/raw_{ad_id}.jpg"
        page.screenshot(path=raw_path, full_page=True)
        print(f"Raw screenshot saved to {raw_path}, size: {os.path.getsize(raw_path)}")
        
        # Take standard screenshot with helper/screenshot.py
        target = screenshot.get(page, f"processed_{ad_id}", "scratch")
        print(f"Processed screenshot saved to {target}, size: {os.path.getsize(target)}")
        
    finally:
        init.close_browser(page)

if __name__ == '__main__':
    url_281891 = "https://www.mybobs.com/?utm_source=hxdv360-8924156&utm_medium=progolv&utm_campaign=ps-yt-sales-34684313&utm_content=253527062&dclid=CNKevdTQk5QDFXmvpgQdSlUmYQ&gad_source=7&gad_campaignid=23749426755&gad_source=2&gad_campaignid=23804444849&gbraid=0AAAAACf1fe_lL7w5O1NjW4wZ4TyLnC0gs&gbraid=0AAAAACf1fe_lL7w5O1NjW4wZ4TyLnC0gs&gclid=EAIaIQobChMIz5vNkK7XlAMVYCCKAx3Q3AfbEAEYAiAAEgIxtfD_BwE"
    test_ad(281891, url_281891)
