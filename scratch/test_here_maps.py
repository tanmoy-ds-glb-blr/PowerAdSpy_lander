import time
from playwright.sync_api import sync_playwright

url = "https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB"

def test_map():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--allow-insecure-localhost",
            ]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-GB"
        )
        page = context.new_page()
        
        console_msgs = []
        page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))
        
        failed_requests = []
        page.on("requestfailed", lambda req: failed_requests.append(f"{req.url}: {req.failure}"))
        
        print("Navigating to URL...")
        page.goto(url, wait_until="networkidle", timeout=60000)
        
        # Take initial screenshot
        page.screenshot(path="scratch/here_initial.jpg")
        
        print("Waiting 10 seconds...")
        time.sleep(10.0)
        page.screenshot(path="scratch/here_after_10s.jpg")
        
        # Check canvas elements
        canvases = page.evaluate("""() => {
            const els = Array.from(document.querySelectorAll('canvas'));
            return els.map(c => ({
                width: c.width,
                height: c.height,
                clientWidth: c.clientWidth,
                clientHeight: c.clientHeight,
                style: c.getAttribute('style'),
                className: c.className
            }));
        }""")
        print("Canvases:", canvases)
        
        # Check webgl support
        webgl_info = page.evaluate("""() => {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            if (!gl) return { webgl: false };
            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            return {
                webgl: true,
                vendor: debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : 'unknown',
                renderer: debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : 'unknown'
            };
        }""")
        print("WebGL Info:", webgl_info)
        
        print(f"Console messages ({len(console_msgs)}):")
        for m in console_msgs[-10:]:
            print(" ", m)
            
        print(f"Failed requests ({len(failed_requests)}):")
        for f in failed_requests[:10]:
            print(" ", f)

        browser.close()

if __name__ == "__main__":
    test_map()
