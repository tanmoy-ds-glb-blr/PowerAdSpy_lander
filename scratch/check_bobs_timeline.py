import sys
sys.path.append('.')
import time
from helper import init

def test():
    page, _ = init.init_dc('in')
    responses = []
    page.on('response', lambda res: responses.append((res.status, res.url)))

    url = 'https://www.mybobs.com/?utm_source=hxdv360-8924156&utm_medium=progolv&utm_campaign=ps-yt-sales-34684313&utm_content=253527062&dclid=CNKevdTQk5QDFXmvpgQdSlUmYQ&gad_source=7&gad_campaignid=23749426755&gad_source=2&gad_campaignid=23804444849&gbraid=0AAAAACf1fe_lL7w5O1NjW4wZ4TyLnC0gs&gbraid=0AAAAACf1fe_lL7w5O1NjW4wZ4TyLnC0gs&gclid=EAIaIQobChMIz5vNkK7XlAMVYCCKAx3Q3AfbEAEYAiAAEgIxtfD_BwE'

    print("Navigating...")
    page.goto(url, timeout=90000, wait_until='domcontentloaded')

    for t in [5, 10, 15, 20]:
        time.sleep(5)
        page.screenshot(path=f'scratch/bobs_t_{t}.jpg', full_page=True)
        h = page.evaluate('() => document.body.scrollHeight')
        br = page.evaluate('() => { const el = document.querySelector("cx-page-slot.BloomreachContent"); return el ? el.offsetHeight : 0; }')
        template = page.evaluate('() => { const el = document.querySelector("cx-page-layout"); return el ? el.className : "none"; }')
        print(f"At {t}s: bodyH={h}, bloomreachH={br}, template={template}")

    occ_calls = [r for r in responses if 'api.mybobs.com' in r[1] or 'bloomreach' in r[1]]
    print(f"Total API responses: {len(occ_calls)}")
    for status, u in occ_calls[:15]:
        print(f"  {status} {u[:100]}")

    init.close_browser(page)

if __name__ == '__main__':
    test()
