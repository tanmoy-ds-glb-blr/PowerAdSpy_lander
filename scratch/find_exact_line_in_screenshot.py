import sys
sys.path.append('.')
import time
from helper import init, screenshot

url = "https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB"

def test():
    page, r_session = init.init_dc("in")
    try:
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        print("Waiting 15s for map to load...")
        time.sleep(15.0)
        
        # Check initial map state
        page.screenshot(path="scratch/diag_0_loaded.jpg")
        print("diag_0_loaded.jpg saved")
        
        # Test A1: Unconstrain primary inner scroll container
        page.evaluate("""() => {
            let unconstrained = false;
            document.querySelectorAll('*').forEach(el => {
                const cs = window.getComputedStyle(el);
                const isScrollable = (cs.overflowY === 'auto' || cs.overflowY === 'scroll');
                if (isScrollable && el.scrollHeight > el.clientHeight + 100 && el.clientHeight > 400) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width >= window.innerWidth * 0.4) {
                        unconstrained = true;
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
            if (unconstrained) {
                if (document.body) {
                    document.body.style.overflow = 'auto';
                    document.body.style.height = 'auto';
                    document.body.style.maxHeight = 'none';
                }
                if (document.documentElement) {
                    document.documentElement.style.overflow = 'auto';
                    document.documentElement.style.height = 'auto';
                    document.documentElement.style.maxHeight = 'none';
                }
            }
        }""")
        page.screenshot(path="scratch/diag_1_unconstrain.jpg")
        print("diag_1_unconstrain.jpg saved")
        
        # Test A4: Progressive scroll
        scroll_height = page.evaluate("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)") or 2000
        page.evaluate(f"window.scrollTo(0, 800);")
        page.evaluate("window.dispatchEvent(new Event('scroll'));")
        time.sleep(1.0)
        page.evaluate("window.scrollTo(0, 0);")
        page.evaluate("window.dispatchEvent(new Event('scroll'));")
        time.sleep(1.0)
        page.screenshot(path="scratch/diag_2_scroll.jpg")
        print("diag_2_scroll.jpg saved")
        
        # Test A5: _UNIVERSAL_ANIMATION_JS
        page.evaluate(screenshot._UNIVERSAL_ANIMATION_JS)
        page.screenshot(path="scratch/diag_3_animation_js.jpg")
        print("diag_3_animation_js.jpg saved")
        
        # Test C3: Overlay & backdrop purge
        page.evaluate("""() => {
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
        }""")
        page.screenshot(path="scratch/diag_4_curtain_purge.jpg")
        print("diag_4_curtain_purge.jpg saved")
        
        # Test: native Playwright page.screenshot(full_page=True)
        page.screenshot(path="scratch/diag_5_full_page.jpg", full_page=True)
        print("diag_5_full_page.jpg saved")

    finally:
        init.close_browser(page)

if __name__ == "__main__":
    test()
