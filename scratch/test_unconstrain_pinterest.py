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

res = page.evaluate('''() => {
    let list = [];
    document.querySelectorAll('*').forEach(el => {
        const cs = window.getComputedStyle(el);
        const isScrollable = (cs.overflowY === 'auto' || cs.overflowY === 'scroll');
        if (isScrollable && el.scrollHeight > el.clientHeight + 100 && el.clientHeight > 400) {
            const rect = el.getBoundingClientRect();
            list.push({
                tag: el.tagName,
                cls: el.className,
                id: el.id,
                scrollH: el.scrollHeight,
                clientH: el.clientHeight,
                rectW: rect.width
            });
        }
    });
    return list;
}''')

print("Scrollables matching unconstrain on Pinterest:")
pprint.pprint(res)
init.close_browser(page)
