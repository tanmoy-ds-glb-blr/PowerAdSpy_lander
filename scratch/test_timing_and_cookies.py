import sys
sys.path.append('.')
import time
from helper import init

url = "https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB"

def test():
    page, r_session = init.init_dc("in")
    try:
        # Navigate just like new_lander.py: wait_until='domcontentloaded'
        t0 = time.time()
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        print(f"Navigation domcontentloaded took: {time.time() - t0:.2f}s")
        
        # Immediate capture (like old new_lander without wait)
        page.screenshot(path="scratch/timing_0s.jpg")
        print("timing_0s.jpg taken")
        
        # After 3s
        time.sleep(3.0)
        page.screenshot(path="scratch/timing_3s.jpg")
        print("timing_3s.jpg taken")
        
        # After another 7s (total 10s wait)
        time.sleep(7.0)
        page.screenshot(path="scratch/timing_10s.jpg")
        print("timing_10s.jpg taken")
        
    finally:
        init.close_browser(page)

if __name__ == "__main__":
    test()
