import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
from helper import init

page, _ = init.init_dc('in')
responses = []
page.on('response', lambda r: responses.append((r.status, r.request.resource_type, r.url)))

url = 'https://www.mybobs.com/?utm_source=hxdv360-8924156&utm_medium=progolv&utm_campaign=ps-yt-sales-34684313&utm_content=253527062&dclid=CNKevdTQk5QDFXmvpgQdSlUmYQ&gad_source=7&gad_campaignid=23749426755&gad_source=2&gad_campaignid=23804444849&gbraid=0AAAAACf1fe_lL7w5O1NjW4wZ4TyLnC0gs&gbraid=0AAAAACf1fe_lL7w5O1NjW4wZ4TyLnC0gs&gclid=EAIaIQobChMIz5vNkK7XlAMVYCCKAx3Q3AfbEAEYAiAAEgIxtfD_BwE'

for attempt in range(3):
    try:
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        break
    except Exception as e:
        print(f"Goto attempt {attempt+1} failed: {e}")
        time.sleep(2)

time.sleep(12)

print(f'Total responses: {len(responses)}')
xhr_fetch = [r for r in responses if r[1] in ('xhr', 'fetch')]
print(f'Total XHR/Fetch: {len(xhr_fetch)}')
for status, rtype, u in xhr_fetch:
    print(f"[{status}] {rtype:5} {u[:120]}")

page_layout = page.evaluate('''() => {
    return Array.from(document.querySelectorAll('cx-page-layout')).map(p => ({
        cls: p.className,
        h: p.offsetHeight,
        slotCount: p.querySelectorAll('cx-page-slot').length
    }));
}''')
print("Page layouts:", page_layout)

init.close_browser(page)
