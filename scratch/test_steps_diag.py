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
    
    # Check canvas before
    c_before = page.evaluate('() => document.querySelectorAll("canvas").length')
    print('Initial canvas count:', c_before)
    page.screenshot(path='scratch/test_0_initial.jpg')
    
    # Step 1: _wake_lazy_images
    print("Running _wake_lazy_images...")
    screenshot._wake_lazy_images(page)
    print('After wake canvas count:', page.evaluate('() => document.querySelectorAll("canvas").length'))
    page.screenshot(path='scratch/test_1_wake.jpg')
    
    # Step 2: Modal / curtain purging
    print("Running modal / curtain purging...")
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
    print('After purge canvas count:', page.evaluate('() => document.querySelectorAll("canvas").length'))
    page.screenshot(path='scratch/test_2_purge.jpg')
    
    # Step 3: page.screenshot(full_page=True) vs page.screenshot(full_page=False)
    page.screenshot(path='scratch/test_3_fullpage.jpg', full_page=True)
    page.screenshot(path='scratch/test_3_viewport.jpg', full_page=False)
    
    # Step 4: Now call screenshot.get directly to see final result
    screenshot.get(page, "test_4_screenshot_get", "test_diag")
    print("Done all!")

finally:
    init.close_browser(page)
