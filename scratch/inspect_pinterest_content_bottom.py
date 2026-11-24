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

def get_lowest():
    return page.evaluate('''() => {
        let maxBottom = 0;
        let lowestElem = null;
        let count = 0;
        document.querySelectorAll('img, p, h1, h2, h3, a').forEach(el => {
            let rect = el.getBoundingClientRect();
            let bottom = rect.bottom + window.scrollY;
            if (rect.height > 10 && rect.width > 10 && bottom > 100) {
                count++;
                if (bottom > maxBottom) {
                    maxBottom = bottom;
                    lowestElem = {
                        tag: el.tagName,
                        cls: (typeof el.className === 'string') ? el.className.slice(0, 40) : '',
                        bottom: Math.round(bottom),
                        h: Math.round(rect.height),
                        w: Math.round(rect.width),
                        text: (el.innerText || '').slice(0, 40)
                    };
                }
            }
        });
        return { maxBottom, lowestElem, count, bodyH: document.body.scrollHeight };
    }''')

print("Initial:")
pprint.pprint(get_lowest())

page.evaluate('window.scrollTo(0, 1000);')
time.sleep(2)
print("After scrollTo(1000):")
pprint.pprint(get_lowest())

page.evaluate('window.scrollTo(0, 2000);')
time.sleep(2)
print("After scrollTo(2000):")
pprint.pprint(get_lowest())

page.evaluate('window.scrollTo(0, 3000);')
time.sleep(2)
print("After scrollTo(3000):")
pprint.pprint(get_lowest())

init.close_browser(page)
