import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
from helper import init

page, _ = init.init_dc('in')
url = "https://www.wordsmith.ai/?utm_source=google&utm_medium=cpc&utm_campaign=Youtube-usa&gad_source=2&gad_campaignid=23722270224&gclid=EAIaIQobChMI8ZKDjdCNlwMV8UkrAx11xBcFEAEYASAAEgJlFPD_BwE"

page.goto(url, timeout=90000, wait_until='domcontentloaded')
time.sleep(5)

info = page.evaluate('''() => {
    // 1. Find cookie banner and its buttons
    let cookieBtns = [];
    document.querySelectorAll('button, a, div[role="dialog"]').forEach(b => {
        let txt = (b.innerText || '').trim();
        if (txt.toLowerCase() === 'accept' || txt.toLowerCase() === 'reject' || txt.toLowerCase().includes('cookie')) {
            cookieBtns.push({
                tag: b.tagName,
                cls: b.className,
                id: b.id,
                txt: txt.slice(0, 50),
                h: b.offsetHeight,
                w: b.offsetWidth
            });
        }
    });

    // 2. Find the 5400px section and its children
    let bigSection = null;
    document.querySelectorAll('section, div').forEach(el => {
        if (el.offsetHeight > 3000) {
            let cs = window.getComputedStyle(el);
            let children = Array.from(el.children).map(c => {
                let ccs = window.getComputedStyle(c);
                return {
                    tag: c.tagName,
                    cls: c.className.slice(0, 50),
                    id: c.id,
                    h: c.offsetHeight,
                    pos: ccs.position,
                    top: ccs.top,
                    text: (c.innerText || '').slice(0, 50).replace(/\\n/g, ' ')
                };
            });
            bigSection = {
                tag: el.tagName,
                cls: el.className,
                id: el.id,
                h: el.offsetHeight,
                pos: cs.position,
                children
            };
        }
    });

    return {
        cookieBtns,
        bigSection
    };
}''')

import pprint
pprint.pprint(info)
init.close_browser(page)
