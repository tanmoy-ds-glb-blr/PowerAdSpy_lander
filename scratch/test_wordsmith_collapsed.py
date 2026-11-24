import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
from helper import init
import time
import os
from PIL import Image

page, _ = init.init_dc('in')
url = "https://www.wordsmith.ai/?utm_source=google&utm_medium=cpc&utm_campaign=Youtube-usa&gad_source=2&gad_campaignid=23722270224&gclid=EAIaIQobChMI8ZKDjdCNlwMV8UkrAx11xBcFEAEYASAAEgJlFPD_BwE"
page.goto(url, timeout=90000, wait_until='domcontentloaded')
time.sleep(5)

# Run collapse on scroll tracks
page.evaluate('''() => {
    document.querySelectorAll('*').forEach(el => {
        let st = el.getAttribute('style') || '';
        let hasVh = /height:\\s*(\\d+)vh/.test(st);
        let hasHugePx = /height:\\s*(\\d+)px/.test(st);
        let valVh = hasVh ? parseInt(st.match(/height:\\s*(\\d+)vh/)[1]) : 0;
        let valPx = hasHugePx ? parseInt(st.match(/height:\\s*(\\d+)px/)[1]) : 0;
        
        let hasStickyChild = Array.from(el.children).some(c => {
            let cs = window.getComputedStyle(c);
            return cs.position === 'sticky';
        });
        
        if ((valVh >= 150 || valPx >= 2000 || el.classList.contains('srs-track')) && hasStickyChild) {
            el.style.setProperty('height', 'auto', 'important');
            el.style.setProperty('min-height', 'auto', 'important');
            el.style.setProperty('max-height', 'none', 'important');
            
            Array.from(el.children).forEach(c => {
                let cs = window.getComputedStyle(c);
                if (cs.position === 'sticky') {
                    c.style.setProperty('position', 'relative', 'important');
                    c.style.setProperty('top', '0px', 'important');
                }
            });
        }
    });
}''')

bodyH = page.evaluate("document.body.scrollHeight")
print("After collapsing scroll tracks, bodyH =", bodyH)

path = "scratch/test_wordsmith_collapsed.jpg"
page.screenshot(path=path, full_page=True)
im = Image.open(path)
print(f"Captured: {path} | Size: {im.size} | File bytes: {os.path.getsize(path)}")
init.close_browser(page)
