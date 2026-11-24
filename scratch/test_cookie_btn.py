import sys
sys.path.append('.')
import time
from helper import init

page, _ = init.init_dc('in')
try:
    page.goto('https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB', wait_until='networkidle', timeout=60000)
    time.sleep(2)
    btns = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button')).map(x => ({
            text: x.innerText,
            cls: x.className,
            id: x.id,
            outer: x.outerHTML.substring(0, 100)
        }));
    }""")
    for b in btns:
        if 'cookie' in b['text'].lower() or 'accept' in b['text'].lower():
            print(b)
finally:
    init.close_browser(page)
