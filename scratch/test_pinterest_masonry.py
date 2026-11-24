import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
from helper import init
import time
import pprint

page, _ = init.init_dc('in')
url = 'https://www.pinterest.com/pinterest/?utm_source=Paid_YouTube&utm_campaign=ConsumerBrand_US_Q22026Anthem60&utm_medium=PaidMedia&gad_source=2&gad_campaignid=23743086863&gclid=EAIaIQobChMIwe2yiK_XlAMVAwzbAR2IQBhnEAEYAiAAEgJkvvD_BwE'
page.goto(url, timeout=90000, wait_until='domcontentloaded')
time.sleep(5)

def get_m():
    return page.evaluate('''() => {
        let m = document.querySelector('[class*="Masonry"]');
        if (!m) return null;
        let maxChildBottom = 0;
        Array.from(m.children).forEach(c => {
            let r = c.getBoundingClientRect();
            let b = r.bottom - m.getBoundingClientRect().top;
            if (b > maxChildBottom) maxChildBottom = b;
        });
        return {
            styleH: m.style.height,
            offsetH: m.offsetHeight,
            maxChildBottom: Math.round(maxChildBottom),
            childrenCount: m.children.length
        };
    }''')

print("Initial:", get_m())

# Scroll a bit (pos=1000)
page.evaluate('window.scrollTo(0, 1000);')
time.sleep(2)
print("After scroll 1000:", get_m())

# Scroll back to 0
page.evaluate('window.scrollTo(0, 0);')
time.sleep(2)
print("After scroll back to 0:", get_m())

init.close_browser(page)
