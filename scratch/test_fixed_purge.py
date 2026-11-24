import sys
sys.path.append('.')
import time
import os
from helper import init

page, _ = init.init_dc('in')
try:
    print("Navigating...")
    page.goto('https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB', wait_until='networkidle', timeout=60000)
    time.sleep(3)
    
    # Run purge WITHOUT the destructive body.style.height = 'auto'
    page.evaluate("""() => {
        const host = document.getElementById('didomi-host');
        if (host) host.remove();
        document.querySelectorAll('#didomi-host, [id*="didomi"], [class*="didomi"], .modal, .modal-backdrop, [class*="modal-popup"], [class*="cookie"], [id*="cookie"], [aria-label*="cookie"], #onetrust-banner-sdk, [class*="onetrust"], #CybotCookiebotDialog').forEach(el => {
            if (el === document.body || el === document.documentElement) return;
            try {
                let cs = window.getComputedStyle(el);
                let cls = (typeof el.className === 'string') ? el.className.toLowerCase() : '';
                let id = (typeof el.id === 'string') ? el.id.toLowerCase() : '';
                let hasBackdropCls = el.classList && el.classList.contains && el.classList.contains('modal-backdrop');
                if (cs.position === 'fixed' || cs.position === 'sticky' || hasBackdropCls || id.includes('didomi') || cls.includes('didomi')) {
                    el.remove();
                }
            } catch(e) {}
        });

        document.querySelectorAll('[role="dialog"]').forEach(el => {
            if (el === document.body || el === document.documentElement) return;
            try {
                if (el.innerText && (el.innerText.includes('Sign up') || el.innerText.includes('Log In') || el.innerText.includes('Log in'))) {
                    el.remove();
                }
            } catch(e) {}
        });

        if (document.body && document.body.classList) {
            document.body.classList.remove('modal-open', 'didomi-popup-open');
        }
    }""")
    
    page.screenshot(path='scratch/fixed_purge_test.jpg', full_page=True)
    print('Fixed screenshot size:', os.path.getsize('scratch/fixed_purge_test.jpg'))
finally:
    init.close_browser(page)
