import sys
sys.path.append('.')
import time
from helper import init

url = "https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB"

def test():
    page, r_session = init.init_dc("in")
    try:
        t0 = time.time()
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        print(f"domcontentloaded in {time.time() - t0:.2f}s")
        
        # Team lead instruction: wait 10 seconds before taking screenshot
        print("Waiting 10 seconds...")
        time.sleep(10.0)
        page.screenshot(path="scratch/after_lead_10s.jpg")
        print("after_lead_10s.jpg taken")
        
        # Check after another 5s (total 15s)
        time.sleep(5.0)
        page.screenshot(path="scratch/after_lead_15s.jpg")
        print("after_lead_15s.jpg taken")
        
        # Check after another 5s (total 20s)
        time.sleep(5.0)
        page.screenshot(path="scratch/after_lead_20s.jpg")
        print("after_lead_20s.jpg taken")

    finally:
        init.close_browser(page)

if __name__ == "__main__":
    test()
