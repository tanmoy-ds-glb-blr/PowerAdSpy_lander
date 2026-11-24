import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
from helper import init

page, _ = init.init_dc('in')
url = "https://www.pinterest.com/pinterest/?utm_source=Paid_YouTube&utm_campaign=ConsumerBrand_US_Q22026Anthem60&utm_medium=PaidMedia&gad_source=2&gad_campaignid=23743086863&gclid=EAIaIQobChMIwe2yiK_XlAMVAwzbAR2IQBhnEAEYAiAAEgJkvvD_BwE"
page.goto(url, timeout=90000, wait_until='domcontentloaded')
time.sleep(5)

# Check elements before and after progressive scroll
before_h = page.evaluate("document.body.scrollHeight")
print("Before scroll bodyH:", before_h)

# Scroll down
for pos in range(0, 5000, 800):
    page.evaluate(f"window.scrollTo(0, {pos});")
    time.sleep(0.5)

after_h = page.evaluate("document.body.scrollHeight")
print("After scroll bodyH:", after_h)

# Inspect what is at the bottom
bottom_info = page.evaluate('''() => {
    let elements = [];
    document.querySelectorAll('*').forEach(el => {
        let rect = el.getBoundingClientRect();
        let top = rect.top + window.scrollY;
        if (top > 2000) {
            elements.push({
                tag: el.tagName,
                cls: (typeof el.className === 'string') ? el.className.slice(0, 50) : '',
                id: el.id,
                h: el.offsetHeight,
                w: el.offsetWidth,
                top: Math.round(top),
                text: (el.innerText || '').slice(0, 50).replace(/\\n/g, ' ')
            });
        }
    });
    return {
        count: elements.length,
        elements: elements.slice(-20)
    };
}''')

import pprint
print("Bottom elements count:", bottom_info["count"])
pprint.pprint(bottom_info["elements"])
init.close_browser(page)
