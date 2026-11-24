import sys
sys.path.append('.')
import time
from helper import init, screenshot

url = "https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB"

def test():
    page, r_session = init.init_dc("in")
    try:
        print("Page opened, navigating to URL...")
        page.goto(url, wait_until="networkidle", timeout=60000)
        
        # Check direct screenshot immediately after goto
        page.screenshot(path="scratch/step1_direct.jpg")
        print("Step 1 direct screenshot saved")
        
        # Check after 5s wait
        time.sleep(5.0)
        page.screenshot(path="scratch/step2_after_5s.jpg")
        print("Step 2 after 5s saved")
        
        # Now call screenshot.get
        screenshot.get(page, "step3_get", "test_culprit")
        print("Step 3 screenshot.get saved")
        
    finally:
        init.close_browser(page)

if __name__ == "__main__":
    test()
