import sys
sys.path.append('.')
import time
from helper import init

def run_test():
    page, _ = init.init_dc('in')
    try:
        url = 'https://www.mybobs.com/?utm_source=hxdv360-8924156&utm_medium=progolv&utm_campaign=ps-yt-sales-34684313&utm_content=253527062&dclid=CNKevdTQk5QDFXmvpgQdSlUmYQ&gad_source=7&gad_campaignid=23749426755&gad_source=2&gad_campaignid=23804444849&gbraid=0AAAAACf1fe_lL7w5O1NjW4wZ4TyLnC0gs&gbraid=0AAAAACf1fe_lL7w5O1NjW4wZ4TyLnC0gs&gclid=EAIaIQobChMIz5vNkK7XlAMVYCCKAx3Q3AfbEAEYAiAAEgIxtfD_BwE'
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        
        # Wait 10s as standard
        time.sleep(10)
        
        # Check initial state
        state1 = page.evaluate('''() => {
            const nav = document.querySelector('header nav, .navigation, cx-category-navigation');
            const main = document.querySelector('main');
            const br = document.querySelector('cx-page-slot.BloomreachContent');
            return {
                nav: !!nav && nav.offsetHeight > 0,
                mainH: main ? main.offsetHeight : 0,
                brChildren: br ? br.children.length : 0,
                brH: br ? br.offsetHeight : 0,
                bodyH: document.body.scrollHeight,
                pageTemplate: document.querySelector('cx-page-layout') ? document.querySelector('cx-page-layout').className : ''
            };
        }''')
        print("Initial state after 10s:", state1)
        
        # Now let's see: what happens if we scroll cx-storefront or window?
        # Let's inspect the scroll container of mybobs!
        scroll_info = page.evaluate('''() => {
            let scrollables = [];
            document.querySelectorAll('*').forEach(el => {
                const cs = window.getComputedStyle(el);
                if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 50) {
                    scrollables.push({
                        tag: el.tagName,
                        cls: el.className,
                        id: el.id,
                        scrollH: el.scrollHeight,
                        clientH: el.clientHeight,
                        overflowY: cs.overflowY
                    });
                }
            });
            return {
                docScrollH: document.documentElement.scrollHeight,
                bodyScrollH: document.body.scrollHeight,
                windowInnerH: window.innerHeight,
                scrollables
            };
        }''')
        print("Scroll info:", scroll_info)
        
    finally:
        init.close_browser(page)

if __name__ == '__main__':
    run_test()
