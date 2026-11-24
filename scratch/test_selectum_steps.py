import sys
sys.path.append('.')
import time
import os
from helper import init, screenshot

page, _ = init.init_dc('in')
try:
    url = 'https://www.selectumhotels.com/en?utm_source=facebook&utm_medium=cpc&utm_campaign=uk-genel'
    for attempt in range(3):
        try:
            page.goto(url, timeout=90000, wait_until='domcontentloaded')
            break
        except Exception:
            time.sleep(2)
            
    time.sleep(5)
    page.screenshot(path='scratch/sel_step0.jpg')
    print('sel_step0:', os.path.getsize('scratch/sel_step0.jpg'))
    
    # 1. Unmask JS
    page.evaluate("""() => {
        document.querySelectorAll('img, source').forEach(el => {
            if (el.tagName.toLowerCase() === 'img') {
                if (el.getAttribute('loading') === 'lazy') el.setAttribute('loading', 'eager');
            }
        });
    }""")
    page.screenshot(path='scratch/sel_step1.jpg')
    print('sel_step1:', os.path.getsize('scratch/sel_step1.jpg'))
    
    # 2. Scroll
    page.evaluate("window.scrollTo(0, 1000);")
    time.sleep(1)
    page.evaluate("window.scrollTo(0, 0);")
    time.sleep(1)
    page.screenshot(path='scratch/sel_step2_scroll.jpg')
    print('sel_step2_scroll:', os.path.getsize('scratch/sel_step2_scroll.jpg'))
    
    # 3. Universal animation JS
    page.evaluate(screenshot._UNIVERSAL_ANIMATION_JS)
    page.screenshot(path='scratch/sel_step3_anim.jpg')
    print('sel_step3_anim:', os.path.getsize('scratch/sel_step3_anim.jpg'))
    
    # 4. Modals and overlays purge
    page.evaluate("""() => {
        try {
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
        } catch(e) {}
    }""")
    page.screenshot(path='scratch/sel_step4_purge1.jpg')
    print('sel_step4_purge1:', os.path.getsize('scratch/sel_step4_purge1.jpg'))
    
    # 5. Curtain purge
    page.evaluate("""() => {
        try {
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
    page.screenshot(path='scratch/sel_step5_curtain.jpg')
    print('sel_step5_curtain:', os.path.getsize('scratch/sel_step5_curtain.jpg'))
    
    # 6. full_page=True screenshot
    page.screenshot(path='scratch/sel_step6_fullpage.jpg', full_page=True)
    print('sel_step6_fullpage:', os.path.getsize('scratch/sel_step6_fullpage.jpg'))
    
finally:
    init.close_browser(page)
