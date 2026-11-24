import sys
sys.path.append('.')
import time
from helper import init

url = "https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB"

def test():
    page, r_session = init.init_dc("in")
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(3.0)
        
        # Test 1: Just native screenshot with full_page=True
        page.screenshot(path="scratch/step_test1_fullpage.jpg", full_page=True)
        print("Test 1 (full_page=True) taken")
        
        # Test 2: Native screenshot with full_page=False (viewport)
        page.screenshot(path="scratch/step_test2_viewport.jpg", full_page=False)
        print("Test 2 (viewport) taken")
        
        # Test 3: Run unconstrain JS
        # (check if canvas was removed or changed)
        
    finally:
        init.close_browser(page)

if __name__ == "__main__":
    test()
