import os
import sys
sys.path.append('.')
import time
from helper import init, screenshot

page, _ = init.init_dc('in')
try:
    print("Navigating...")
    page.goto('https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB', wait_until='networkidle', timeout=60000)
    time.sleep(3)
    
    # Check baseline
    page.screenshot(path='scratch/iso_0_base.jpg')
    
    # 1. Check animation js
    print("Testing animation js...")
    page.evaluate(screenshot._UNIVERSAL_ANIMATION_JS)
    page.screenshot(path='scratch/iso_1_anim.jpg')
    
    # 2. Check close btn
    print("Testing close btn...")
    try:
        close_btn = page.query_selector(
            '[role="dialog"] [aria-label="Close"], [role="dialog"] button.close, svg[aria-label="Close"], .modal .close'
        )
        if close_btn:
            print('Found close btn:', close_btn)
            close_btn.click(timeout=1000)
            time.sleep(0.5)
    except Exception as e:
        print('Close btn exc:', e)
    page.screenshot(path='scratch/iso_2_closebtn.jpg')
    
    # 3. Check Step 1b purging
    print("Testing modal purge...")
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

            document.querySelectorAll('*').forEach(el => {
                const cs = window.getComputedStyle(el);
                const isScrollable = (cs.overflowY === 'auto' || cs.overflowY === 'scroll');
                if (isScrollable && el.scrollHeight > el.clientHeight + 100 && el.clientHeight > 400) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width >= window.innerWidth * 0.4) {
                        el.style.overflow = 'visible';
                        el.style.overflowY = 'visible';
                        el.style.maxHeight = 'none';
                        el.style.height = 'auto';

                        let p = el.parentElement;
                        while (p && p !== document.body && p !== document.documentElement) {
                            const pcs = window.getComputedStyle(p);
                            if (pcs.maxHeight !== 'none' || pcs.overflowY === 'hidden' || pcs.overflow === 'hidden') {
                                p.style.maxHeight = 'none';
                                p.style.overflow = 'visible';
                                p.style.overflowY = 'visible';
                                p.style.height = 'auto';
                            }
                            p = p.parentElement;
                        }
                    }
                }
            });

            if (document.body) {
                if (document.body.classList) {
                    document.body.classList.remove('modal-open', 'didomi-popup-open');
                }
                document.body.style.overflow = 'auto';
                document.body.style.height = 'auto';
                document.body.style.maxHeight = 'none';
            }
            if (document.documentElement) {
                document.documentElement.style.overflow = 'auto';
                document.documentElement.style.height = 'auto';
                document.documentElement.style.maxHeight = 'none';
            }
        } catch(e) {}
    }""")
    page.screenshot(path='scratch/iso_3_purge.jpg')
    
    # 4. fonts and restore
    print("Testing fonts and restore...")
    page.evaluate("document.fonts ? document.fonts.ready : Promise.resolve()")
    page.evaluate(screenshot._RESTORE_REVEALED_CONTENT_JS)
    page.screenshot(path='scratch/iso_4_restore.jpg')
    
    # 5. _wake_lazy_images
    print("Testing _wake_lazy_images...")
    screenshot._wake_lazy_images(page)
    page.screenshot(path='scratch/iso_5_wake.jpg')
    
    # 6. full_page vs viewport
    print("Testing screenshot full_page vs viewport...")
    b1 = page.screenshot(full_page=True)
    with open('scratch/iso_6_fp.jpg', 'wb') as f:
        f.write(b1)
    b2 = page.screenshot(full_page=False)
    with open('scratch/iso_6_vp.jpg', 'wb') as f:
        f.write(b2)
        
    for k in [
        'scratch/iso_0_base.jpg',
        'scratch/iso_1_anim.jpg',
        'scratch/iso_2_closebtn.jpg',
        'scratch/iso_3_purge.jpg',
        'scratch/iso_4_restore.jpg',
        'scratch/iso_5_wake.jpg',
        'scratch/iso_6_fp.jpg',
        'scratch/iso_6_vp.jpg',
    ]:
        print(k, os.path.getsize(k))

finally:
    init.close_browser(page)
