import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
from helper import init

page, _ = init.init_dc('in')
url = 'https://www.mybobs.com/?utm_source=hxdv360-8924156&utm_medium=progolv&utm_campaign=ps-yt-sales-34684313&utm_content=253527062&dclid=CNKevdTQk5QDFXmvpgQdSlUmYQ&gad_source=7&gad_campaignid=23749426755&gad_source=2&gad_campaignid=23804444849&gbraid=0AAAAACf1fe_lL7w5O1NjW4wZ4TyLnC0gs&gbraid=0AAAAACf1fe_lL7w5O1NjW4wZ4TyLnC0gs&gclid=EAIaIQobChMIz5vNkK7XlAMVYCCKAx3Q3AfbEAEYAiAAEgIxtfD_BwE'

print("Navigating to mybobs...")
page.goto(url, timeout=90000, wait_until='domcontentloaded')
time.sleep(3)

print("Dismissing cookie banner immediately...")
dismissed = page.evaluate('''() => {
    // Try finding and clicking Accept / Reject / Close button
    let clicked = false;
    document.querySelectorAll('button, a').forEach(b => {
        let txt = (b.innerText || '').trim().toLowerCase();
        if (txt === 'accept' || txt === 'reject' || txt === 'accept all' || txt === 'allow all') {
            b.click();
            clicked = true;
        }
    });
    return clicked;
}''')
print("Cookie banner clicked:", dismissed)

# Wait 7 seconds (total 10s wait)
time.sleep(7)

res = page.evaluate('''() => {
    return {
        title: document.title,
        bodyH: document.body.scrollHeight,
        layouts: Array.from(document.querySelectorAll('cx-page-layout')).map(p => ({
            cls: p.className,
            h: p.offsetHeight,
            slots: Array.from(p.querySelectorAll('cx-page-slot')).map(s => ({
                pos: s.getAttribute('position') || s.className,
                children: s.children.length,
                h: s.offsetHeight
            }))
        }))
    };
}''')
import pprint
pprint.pprint(res)
page.screenshot(path='scratch/bobs_after_cookie_dismiss.jpg', full_page=True)
print("Saved scratch/bobs_after_cookie_dismiss.jpg")
init.close_browser(page)
