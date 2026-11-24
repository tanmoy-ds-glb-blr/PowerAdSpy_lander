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

details = page.evaluate('''() => {
    let results = [];
    document.querySelectorAll('*').forEach(el => {
        let st = el.getAttribute('style') || '';
        let m = st.match(/height:\\s*(\\d+)vh/);
        if (m && parseInt(m[1]) > 150) {
            results.push({
                tag: el.tagName,
                cls: el.className,
                style: st,
                h: el.offsetHeight,
                children: Array.from(el.children).map(c => {
                    let cs = window.getComputedStyle(c);
                    return {
                        tag: c.tagName,
                        cls: c.className.slice(0, 50),
                        pos: cs.position,
                        top: cs.top,
                        h: c.offsetHeight
                    };
                })
            });
        }
    });
    return results;
}''')

pprint.pprint(details)
init.close_browser(page)
