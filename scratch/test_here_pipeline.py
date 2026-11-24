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
        
        # Check WebGL support
        gl_info = page.evaluate("""() => {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            return {
                has_gl: !!gl,
                renderer: gl ? gl.getParameter(gl.getExtension('WEBGL_debug_renderer_info')?.UNMASKED_RENDERER_WEBGL || 0x1F01) : null
            };
        }""")
        print("WebGL in Chrome:", gl_info)
        
        # Check map canvas
        canvases = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('canvas')).map(c => ({
                w: c.width,
                h: c.height,
                style: c.getAttribute('style')
            }));
        }""")
        print("Canvases:", canvases)
        
        # Take screenshot via screenshot.get
        target_path = screenshot.get(page, "test_here", "test_43534")
        print("Screenshot saved to:", target_path)
    finally:
        init.close_browser(page)

if __name__ == "__main__":
    test()
