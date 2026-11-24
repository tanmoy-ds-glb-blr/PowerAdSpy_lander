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

# Progressive scroll
for pos in range(0, 5000, 800):
    page.evaluate(f'window.scrollTo(0, {pos});')
    time.sleep(0.5)

# Scroll back to top
page.evaluate('window.scrollTo(0, 0);')
time.sleep(2)

tall_elements = page.evaluate('''() => {
    let list = [];
    document.querySelectorAll('*').forEach(el => {
        if (el.offsetHeight > 3000) {
            list.push({
                tag: el.tagName,
                cls: (typeof el.className === 'string') ? el.className.slice(0, 50) : '',
                id: el.id,
                h: el.offsetHeight,
                scrollH: el.scrollHeight,
                style: el.getAttribute('style')
            });
        }
    });
    return list;
}''')

print("Tall elements after scrolling back to top:")
pprint.pprint(tall_elements)
init.close_browser(page)
