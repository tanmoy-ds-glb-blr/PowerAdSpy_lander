import sys
sys.path.append('.')
import time
import json
from helper import init

page, _ = init.init_dc('in')
try:
    page.goto('https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB', wait_until='networkidle', timeout=60000)
    time.sleep(3)
    
    removed = page.evaluate("""() => {
        let removedElements = [];
        
        // 1. Selector purge
        document.querySelectorAll('#didomi-host, [id*="didomi"], [class*="didomi"], .modal, .modal-backdrop, [class*="modal-popup"], [class*="cookie"], [id*="cookie"], [aria-label*="cookie"], #onetrust-banner-sdk, [class*="onetrust"], #CybotCookiebotDialog').forEach(el => {
            if (el === document.body || el === document.documentElement) return;
            try {
                let cs = window.getComputedStyle(el);
                let cls = (typeof el.className === 'string') ? el.className.toLowerCase() : '';
                let id = (typeof el.id === 'string') ? el.id.toLowerCase() : '';
                let hasBackdropCls = el.classList && el.classList.contains && el.classList.contains('modal-backdrop');
                if (cs.position === 'fixed' || cs.position === 'sticky' || hasBackdropCls || id.includes('didomi') || cls.includes('didomi')) {
                    removedElements.push({
                        rule: 'selector-cookie-modal',
                        tag: el.tagName,
                        cls: el.className,
                        id: el.id,
                        containsCanvas: el.querySelector('canvas') !== null
                    });
                }
            } catch(e) {}
        });

        // 2. Curtain purge
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
                            removedElements.push({
                                rule: 'curtain-known-overlay',
                                tag: el.tagName,
                                cls: el.className,
                                id: el.id,
                                containsCanvas: el.querySelector('canvas') !== null
                            });
                        } else if (hasBg && isCurtain && interactiveCount === 0 && textLen < 50) {
                            removedElements.push({
                                rule: 'curtain-empty-bg',
                                tag: el.tagName,
                                cls: el.className,
                                id: el.id,
                                containsCanvas: el.querySelector('canvas') !== null
                            });
                        }
                    }
                }
            } catch(e) {}
        });

        // 3. Unconstrain container
        document.querySelectorAll('*').forEach(el => {
            const cs = window.getComputedStyle(el);
            const isScrollable = (cs.overflowY === 'auto' || cs.overflowY === 'scroll');
            if (isScrollable && el.scrollHeight > el.clientHeight + 100 && el.clientHeight > 400) {
                const rect = el.getBoundingClientRect();
                if (rect.width >= window.innerWidth * 0.4) {
                    removedElements.push({
                        rule: 'unconstrained-container',
                        tag: el.tagName,
                        cls: el.className,
                        id: el.id,
                        containsCanvas: el.querySelector('canvas') !== null
                    });
                }
            }
        });

        return removedElements;
    }""")
    print("REMOVED ELEMENTS:")
    print(json.dumps(removed, indent=2))
finally:
    init.close_browser(page)
