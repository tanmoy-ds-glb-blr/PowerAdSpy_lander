import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
from helper import init

print(">>> Starting Pinterest inspection...", flush=True)
page, _ = init.init_dc('in')
try:
    url = "https://www.pinterest.com/pinterest/?utm_source=Paid_YouTube&utm_campaign=ConsumerBrand_US_Q22026Anthem60&utm_medium=PaidMedia&gad_source=2&gad_campaignid=23743086863&gclid=EAIaIQobChMIwe2yiK_XlAMVAwzbAR2IQBhnEAEYAiAAEgJkvvD_BwE"
    page.goto(url, timeout=90000, wait_until='domcontentloaded')
    time.sleep(5)
    
    info = page.evaluate('''() => {
        // Check for google one tap or dialogs
        let popups = [];
        document.querySelectorAll('iframe, [role="dialog"], #credential_picker_container, [id*="credential"], [data-test-id*="modal"]').forEach(el => {
            popups.push({
                tag: el.tagName,
                id: el.id,
                cls: el.className,
                src: el.src || '',
                h: el.offsetHeight,
                w: el.offsetWidth
            });
        });
        
        // Check scroll containers and height
        return {
            title: document.title,
            bodyScrollH: document.body.scrollHeight,
            docScrollH: document.documentElement.scrollHeight,
            windowH: window.innerHeight,
            popups: popups.slice(0, 10),
            gridCount: document.querySelectorAll('[data-grid-item], [data-test-id="pin"]').length
        };
    }''')
    import pprint
    print("Pinterest DOM Info:", flush=True)
    pprint.pprint(info)
    
    page.screenshot(path="scratch/raw_pinterest.jpg", full_page=True)
    print("Saved scratch/raw_pinterest.jpg", flush=True)
finally:
    init.close_browser(page)
