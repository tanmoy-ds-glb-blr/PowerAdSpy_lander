import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
from helper import init
import time
import pprint

page, _ = init.init_dc('in')
url = "https://www.wordsmith.ai/?utm_source=google&utm_medium=cpc&utm_campaign=Youtube-usa&gad_source=2&gad_campaignid=23722270224&gclid=EAIaIQobChMI8ZKDjdCNlwMV8UkrAx11xBcFEAEYASAAEgJlFPD_BwE"
page.goto(url, timeout=90000, wait_until='domcontentloaded')
time.sleep(5)

# Check heights before scroll
h0 = page.evaluate("document.body.scrollHeight")
print("Before scroll bodyH:", h0)

for pos in range(0, 8000, 800):
    page.evaluate(f'window.scrollTo(0, {pos});')
    time.sleep(0.5)

h1 = page.evaluate("document.body.scrollHeight")
print("After scroll bodyH:", h1)

tracks = page.evaluate('''() => {
    let list = [];
    document.querySelectorAll('*').forEach(el => {
        let cs = window.getComputedStyle(el);
        if (el.offsetHeight > 1500) {
            list.push({
                tag: el.tagName,
                cls: el.className.toString().slice(0, 60),
                id: el.id,
                h: el.offsetHeight,
                scrollH: el.scrollHeight,
                styleAttr: el.getAttribute('style') || '',
                pos: cs.position
            });
        }
    });
    return list;
}''')

print("Elements with offsetHeight > 1500 after scrolling:")
pprint.pprint(tracks)

init.close_browser(page)
