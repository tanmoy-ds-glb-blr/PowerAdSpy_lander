import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
from helper import init

def test():
    page, _ = init.init_dc('in')
    try:
        url = 'https://www.mybobs.com/?utm_source=hxdv360-8924156&utm_medium=progolv&utm_campaign=ps-yt-sales-34684313&utm_content=253527062&dclid=CNKevdTQk5QDFXmvpgQdSlUmYQ&gad_source=7&gad_campaignid=23749426755&gad_source=2&gad_campaignid=23804444849&gbraid=0AAAAACf1fe_lL7w5O1NjW4wZ4TyLnC0gs&gbraid=0AAAAACf1fe_lL7w5O1NjW4wZ4TyLnC0gs&gclid=EAIaIQobChMIz5vNkK7XlAMVYCCKAx3Q3AfbEAEYAiAAEgIxtfD_BwE'
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        time.sleep(10)
        
        main_info = page.evaluate('''() => {
            const m = document.querySelector('main');
            if (!m) return 'No main';
            return {
                h: m.offsetHeight,
                children: Array.from(m.children).map(c => ({
                    tag: c.tagName,
                    cls: c.className,
                    h: c.offsetHeight,
                    childCount: c.children.length,
                    html: c.innerHTML.slice(0, 300)
                }))
            };
        }''')
        import pprint
        pprint.pprint(main_info)
    finally:
        init.close_browser(page)

if __name__ == '__main__':
    test()
