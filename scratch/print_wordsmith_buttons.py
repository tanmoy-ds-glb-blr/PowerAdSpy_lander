import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
from helper import init

page, _ = init.init_dc('in')
page.goto('https://www.wordsmith.ai/?utm_source=google&utm_medium=cpc&utm_campaign=Youtube-usa&gad_source=2&gad_campaignid=23722270224&gclid=EAIaIQobChMI8ZKDjdCNlwMV8UkrAx11xBcFEAEYASAAEgJlFPD_BwE', timeout=60000, wait_until='domcontentloaded')
time.sleep(5)
btns = page.evaluate('''() => Array.from(document.querySelectorAll('button, a')).map(b => ({
    tag: b.tagName,
    cls: b.className,
    id: b.id,
    txt: (b.innerText||'').trim()
})).filter(b => b.txt.length > 0 && b.txt.length < 50)''')
import pprint
pprint.pprint(btns)
init.close_browser(page)
