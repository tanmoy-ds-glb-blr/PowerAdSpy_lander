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

srs_info = page.evaluate('''() => {
    let tracks = [];
    document.querySelectorAll('[class*="srs"], [class*="track"], [class*="sticky"]').forEach(el => {
        let cs = window.getComputedStyle(el);
        tracks.push({
            tag: el.tagName,
            cls: el.className,
            id: el.id,
            h: el.offsetHeight,
            pos: cs.position,
            top: cs.top,
            textLen: (el.innerText || '').length,
            textSample: (el.innerText || '').slice(0, 80).replace(/\\n/g, ' ')
        });
    });
    
    // Also look for cookie elements in shadow DOM or iframes
    let iframes = Array.from(document.querySelectorAll('iframe')).map(i => ({
        src: i.src,
        id: i.id,
        cls: i.className
    }));
    
    return {
        tracks,
        iframes
    };
}''')

import pprint
pprint.pprint(srs_info)
init.close_browser(page)
