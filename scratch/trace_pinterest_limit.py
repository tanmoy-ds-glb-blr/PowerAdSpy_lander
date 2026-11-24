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

for pos in range(1000, 9000, 1000):
    page.evaluate(f'window.scrollTo(0, {pos});')
    time.sleep(2)
    res = page.evaluate('''() => {
        let maxImgBottom = 0;
        let imgCount = 0;
        document.querySelectorAll('img').forEach(el => {
            let rect = el.getBoundingClientRect();
            let bottom = rect.bottom + window.scrollY;
            if (rect.height > 50 && rect.width > 50) {
                imgCount++;
                if (bottom > maxImgBottom) maxImgBottom = bottom;
            }
        });
        return {
            maxImgBottom: Math.round(maxImgBottom),
            imgCount,
            bodyH: document.body.scrollHeight,
            windowY: window.scrollY
        };
    }''')
    print(f"At pos={pos}: {res}")

init.close_browser(page)
