import sys
sys.path.append('.')
import time
from helper import init

url = "https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB"

def test():
    page, r_session = init.init_dc("in")
    try:
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        
        for sec in range(1, 25):
            time.sleep(1.0)
            status = page.evaluate("""() => {
                // Check canvas pixel or WebGL status
                const canvas = document.querySelector('canvas');
                let hasData = false;
                if (canvas) {
                    try {
                        const ctx = canvas.getContext('2d');
                        if (ctx) {
                            const pixel = ctx.getImageData(canvas.width / 2, canvas.height / 2, 1, 1).data;
                            hasData = pixel[3] > 0;
                        }
                    } catch(e) {}
                }
                
                // Check route / directions status or destination card
                const inputDest = document.querySelector('input[placeholder*="destination"], [aria-label*="destination"]');
                const spinners = document.querySelectorAll('[class*="spinner"], [class*="loading"], [aria-busy="true"]');
                const addr = document.body.innerText.includes('Tong Road');
                
                return {
                    url: window.location.href,
                    title: document.title,
                    canvasCount: document.querySelectorAll('canvas').length,
                    spinnersCount: spinners.length,
                    hasTongRoad: addr
                };
            }""")
            print(f"Sec {sec}: {status}")
            
            # If map has loaded or URL redirected
            if "Tong Road" in status.get('url', '') or status.get('hasTongRoad'):
                print("Found destination resolved!")

        page.screenshot(path="scratch/sec25_result.jpg")
    finally:
        init.close_browser(page)

if __name__ == "__main__":
    test()
