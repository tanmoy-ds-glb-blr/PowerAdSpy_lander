import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
from helper import init

print(">>> Starting Wordsmith inspection...", flush=True)
page, _ = init.init_dc('in')
try:
    url = "https://www.wordsmith.ai/?utm_source=google&utm_medium=cpc&utm_campaign=Youtube-usa&gad_source=2&gad_campaignid=23722270224&gclid=EAIaIQobChMI8ZKDjdCNlwMV8UkrAx11xBcFEAEYASAAEgJlFPD_BwE"
    page.goto(url, timeout=90000, wait_until='domcontentloaded')
    time.sleep(5)
    
    info = page.evaluate('''() => {
        // Find cookie banner
        let banners = [];
        document.querySelectorAll('button, [class*="cookie"], [id*="cookie"], [class*="banner"]').forEach(b => {
            let txt = (b.innerText || '').trim();
            if (txt.toLowerCase().includes('cookie') || txt.toLowerCase().includes('accept') || txt.toLowerCase().includes('reject')) {
                banners.push({
                    tag: b.tagName,
                    cls: b.className,
                    id: b.id,
                    txt: txt.slice(0, 50)
                });
            }
        });
        
        // Find huge empty sections or sticky/pinned elements
        let sections = [];
        document.querySelectorAll('section, main > div, div[class*="section"]').forEach(s => {
            const cs = window.getComputedStyle(s);
            sections.push({
                tag: s.tagName,
                cls: s.className,
                id: s.id,
                h: s.offsetHeight,
                pos: cs.position,
                textLen: (s.innerText || '').trim().length,
                textSample: (s.innerText || '').slice(0, 80).replace(/\\n/g, ' ')
            });
        });
        
        return {
            title: document.title,
            bodyScrollH: document.body.scrollHeight,
            banners: banners.slice(0, 10),
            sections
        };
    }''')
    import pprint
    print("Wordsmith DOM Info:", flush=True)
    pprint.pprint(info)
    page.screenshot(path="scratch/raw_wordsmith.jpg", full_page=True)
    print("Saved scratch/raw_wordsmith.jpg", flush=True)
finally:
    init.close_browser(page)
