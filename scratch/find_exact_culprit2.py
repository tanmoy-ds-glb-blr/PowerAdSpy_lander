import sys
sys.path.append('.')
import time
from helper import init, screenshot

url = "https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB"

def test():
    page, r_session = init.init_dc("in")
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(3.0)
        
        # 1. Run _wake_lazy_images
        screenshot._wake_lazy_images(page)
        page.screenshot(path="scratch/after_wake.jpg", full_page=True)
        print("After _wake_lazy_images saved")
        
        # 2. Run Step 1b purging logic
        page.evaluate("""() => {
            try {
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

                document.querySelectorAll('div, section, aside').forEach(el => {
                    if (el === document.body || el === document.documentElement) return;
                    try {
                        let cs = window.getComputedStyle(el);
                        let hasBackdropCls = el.classList && el.classList.contains && el.classList.contains('modal-backdrop');
                        let zIdx = parseFloat(cs.zIndex);
                        if (cs.position === 'fixed' && (zIdx >= 1 || isNaN(zIdx) || hasBackdropCls)) {
                            let rect = el.getBoundingClientRect();
                            let isFullScreen = rect.width >= window.innerWidth * 0.75 && rect.height >= window.innerHeight * 0.75;
                            if (isFullScreen) {
                                let bg = cs.backgroundColor || '';
                                let hasBg = bg && bg !== 'transparent' && bg !== 'rgba(0, 0, 0, 0)';
                                let isCurtain = (
                                    bg.includes('rgba(') ||
                                    bg.includes('rgb(') ||
                                    parseFloat(cs.opacity) < 0.99 ||
                                    (cs.backdropFilter && cs.backdropFilter !== 'none')
                                );
                                let cls = (typeof el.className === 'string') ? el.className.toLowerCase() : '';
                                let id = (typeof el.id === 'string') ? el.id.toLowerCase() : '';
                                let textLen = (el.innerText || '').trim().length;
                                let interactiveCount = el.querySelectorAll('a, button, input, textarea, select, form').length;
                                let isKnownOverlayCls = (
                                    cls.includes('backdrop') || cls.includes('overlay') || cls.includes('modal') ||
                                    cls.includes('didomi') || cls.includes('transition') || cls.includes('preloader') ||
                                    cls.includes('curtain') || id.includes('backdrop') || id.includes('overlay') ||
                                    id.includes('didomi') || id.includes('transition') || id.includes('preloader') ||
                                    id.includes('curtain')
                                );

                                if (isKnownOverlayCls && (interactiveCount === 0 || cls.includes('backdrop') || cls.includes('didomi') || id.includes('didomi'))) {
                                    el.remove();
                                } else if (hasBg && isCurtain && interactiveCount === 0 && textLen < 50) {
                                    el.remove();
                                }
                            }
                        }
                    } catch(e) {}
                });
            } catch(e) {}
        }""")
        page.screenshot(path="scratch/after_purging.jpg", full_page=True)
        print("After purging saved")
        
    finally:
        init.close_browser(page)

if __name__ == "__main__":
    test()
