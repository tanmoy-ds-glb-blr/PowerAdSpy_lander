import sys
sys.path.append('.')
import time
from helper import init, screenshot

url = "https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB"

def test():
    page, r_session = init.init_dc("in")
    try:
        t0 = time.time()
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        print(f"Navigation done in {time.time() - t0:.2f}s")
        
        # 10s wait as requested by team lead
        print("Waiting 10s before screenshot...")
        time.sleep(10.0)
        
        # Canvas check buffer
        has_canvas = page.evaluate("() => document.querySelectorAll('canvas').length > 0")
        if has_canvas:
            print("Canvas detected, waiting 3s buffer...")
            time.sleep(3.0)
            
        target = screenshot.get(page, "prelander_test", "sample_43534")
        print("Screenshot saved to:", target)
        
    finally:
        init.close_browser(page)

if __name__ == "__main__":
    test()
