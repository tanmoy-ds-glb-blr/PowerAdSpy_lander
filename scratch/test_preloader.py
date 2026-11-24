import sys
sys.path.append('.')
import time
from helper import init

page, _ = init.init_dc('in')
try:
    url = 'https://www.selectumhotels.com/en?utm_source=facebook&utm_medium=cpc&utm_campaign=uk-genel'
    page.goto(url, timeout=90000, wait_until='domcontentloaded')
    time.sleep(5)
    
    preloader = page.evaluate("""() => {
        let els = document.querySelectorAll('[class*="loader"], [class*="preload"], [id*="loader"], [id*="preload"]');
        return Array.from(els).map(e => ({
            tag: e.tagName,
            cls: e.className,
            id: e.id,
            display: window.getComputedStyle(e).display,
            opacity: window.getComputedStyle(e).opacity,
            visibility: window.getComputedStyle(e).visibility
        }));
    }""")
    print('Preloaders found:', preloader)
finally:
    init.close_browser(page)
