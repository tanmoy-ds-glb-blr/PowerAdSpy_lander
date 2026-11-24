import sys
sys.path.append('.')
import time
from helper import init

url = "https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB"

def test():
    page, r_session = init.init_dc("in")
    try:
        req_urls = []
        page.on("request", lambda req: req_urls.append(req.url))
        
        page.goto(url, timeout=90000, wait_until='networkidle')
        print(f"Total requests after networkidle: {len(req_urls)}")
        for u in req_urls[:30]:
            print(" ", u[:100])
            
        page.screenshot(path="scratch/networkidle_shot.jpg")
    finally:
        init.close_browser(page)

if __name__ == "__main__":
    test()
