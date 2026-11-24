import os
import time
import random
from io import BytesIO
from PIL import Image

_MAX_CAPTURE_HEIGHT = 32000
_MAX_CAPTURE_WIDTH = 1920

_UNIVERSAL_ANIMATION_JS = """() => {
    // 1. Programmatically complete GSAP and ScrollTrigger animations if present
    try {
        if (window.ScrollTrigger) {
            window.ScrollTrigger.getAll().forEach(t => t.progress(1));
            window.ScrollTrigger.refresh();
        }
        if (window.gsap && window.gsap.globalTimeline) {
            window.gsap.globalTimeline.progress(1);
        }
    } catch(e) {}

    // 2. Add active animation classes across all major scroll animation libraries
    try {
        // AOS (Animate on Scroll)
        document.querySelectorAll('[data-aos]').forEach(el => el.classList.add('aos-animate'));
        // WOW.js
        document.querySelectorAll('.wow').forEach(el => el.classList.add('animated'));
        // Sal.js
        document.querySelectorAll('[data-sal]').forEach(el => el.classList.add('sal-animate'));
        // Locomotive Scroll
        document.querySelectorAll('[data-scroll]').forEach(el => el.classList.add('is-inview'));
        // Custom & common scroll classes (.js-scroll, .reveal, etc.)
        document.querySelectorAll('.js-scroll').forEach(el => el.classList.add('scrolled'));
        document.querySelectorAll('.scroll-reveal, .reveal, .in-view, .is-visible, .fade-in').forEach(el => {
            el.classList.add('visible', 'active', 'show', 'scrolled');
        });
        // ScrollReveal.js elements (data-sr-id)
        document.querySelectorAll('[data-sr-id]').forEach(el => {
            el.style.opacity = '1';
            el.style.transform = 'none';
            el.style.visibility = 'visible';
        });

        // Force slide columns, recipe cards, and uncollapsed sliders
        document.querySelectorAll('[class*="slide__column"], .si-slide__column, [class*="recipe-card"], [class*="recipe-slide"], .si-recipe-card').forEach(el => {
            el.style.setProperty('opacity', '1', 'important');
            el.style.setProperty('visibility', 'visible', 'important');
        });
        document.querySelectorAll('#si-product-slider__container, .si-product-slider, .si-product-slide').forEach(el => {
            el.style.setProperty('height', 'auto', 'important');
            el.style.setProperty('min-height', '400px', 'important');
            el.style.setProperty('margin-top', '0px', 'important');
            el.style.setProperty('overflow', 'visible', 'important');
        });
        // Collapse artificial sticky scroll-jack tracks (e.g. Wordsmith, scroll-storytelling tracks)
        document.querySelectorAll('section, div').forEach(el => {
            let st = el.getAttribute('style') || '';
            let hasVh = /height:\s*(\d+)vh/.test(st);
            let valVh = hasVh ? parseInt(st.match(/height:\s*(\d+)vh/)[1]) : 0;
            let valPx = /height:\s*(\d+)px/.test(st) ? parseInt(st.match(/height:\s*(\d+)px/)[1]) : 0;
            let isTrack = el.classList.contains('srs-track') || valVh >= 150 || valPx >= 2000;
            if (isTrack) {
                let stickyChild = Array.from(el.children).find(c => {
                    let cs = window.getComputedStyle(c);
                    return cs.position === 'sticky' || (c.classList && c.classList.contains('sticky'));
                });
                if (stickyChild) {
                    el.style.setProperty('height', 'auto', 'important');
                    el.style.setProperty('min-height', 'auto', 'important');
                    el.style.setProperty('max-height', 'none', 'important');
                    Array.from(el.children).forEach(c => {
                        let cs = window.getComputedStyle(c);
                        if (cs.position === 'sticky' || (c.classList && c.classList.contains('sticky'))) {
                            c.style.setProperty('position', 'relative', 'important');
                            c.style.setProperty('top', '0px', 'important');
                        }
                    });
                }
            }
        });
    } catch(e) {}

    // 3. Inject high-specificity CSS to permanently freeze all animated elements in their 100% visible state
    try {
        if (!document.getElementById('pas-universal-animation-fix')) {
            let style = document.createElement('style');
            style.id = 'pas-universal-animation-fix';
            style.innerHTML = `
                /* Prevent Chromium from skipping off-screen element painting in full-page capture */
                *, *::before, *::after {
                    content-visibility: visible !important;
                }

                /* Dynamic shelves, cards, carousels, and virtualized list items */
                [data-testid*="card"],
                [data-testid*="shelf"],
                [class*="Shelf"],
                [role="group"],
                [class*="Card"],
                [class*="card"] {
                    opacity: 1 !important;
                    visibility: visible !important;
                    content-visibility: visible !important;
                    contain: none !important;
                }

                /* All known scroll-animation frameworks & entrance classes */
                .js-scroll, 
                .js-scroll.fade-in-left, 
                .js-scroll.fade-in-right, 
                .js-scroll.fade-in-bottom, 
                .js-scroll.fade-in-top,
                .scrolled,
                [data-aos], 
                .wow, 
                .animate__animated,
                [data-sal],
                [data-scroll],
                .scroll-reveal,
                .reveal,
                .in-view,
                .is-visible,
                .fade-in,
                .fade-in-up,
                .fade-in-down,
                .fade-in-left,
                .fade-in-right,
                .slide-in,
                .slide-in-up,
                .slide-in-left,
                .slide-in-right {
                    opacity: 1 !important;
                    visibility: visible !important;
                    transform: none !important;
                    animation: none !important;
                    transition: none !important;
                }

                /* Slide columns, product slides, recipe cards, and dynamic showcases */
                [class*="slide__column"],
                [class*="slide__content"],
                [class*="product-slide"],
                [class*="product-slider"],
                [class*="recipe-card"],
                [class*="recipe-slide"],
                .si-slide__column,
                .si-product-slide,
                .si-recipe-card {
                    opacity: 1 !important;
                    visibility: visible !important;
                }

                /* Uncollapse 0-height sliders & fix negative margin collisions */
                #si-product-slider__container,
                .si-product-slider,
                .si-product-slide,
                [class*="product-slider"],
                [class*="product-slide"] {
                    height: auto !important;
                    min-height: 400px !important;
                    margin-top: 0px !important;
                    overflow: visible !important;
                }

                /* Hide blocking fixed animation headers and curtain frame holders */
                .si-factory-animated-header__frame-holder,
                .si-factory-animated-header,
                [class*="animated-header__frame-holder"] {
                    display: none !important;
                }

                /* Collapse artificial sticky scroll tracks */
                .srs-track, [class*="srs-track"] {
                    height: auto !important;
                    min-height: auto !important;
                }

                /* SVG line-drawing animations: force lines fully drawn */
                path[stroke-dasharray], line[stroke-dasharray] {
                    stroke-dashoffset: 0 !important;
                }
            `;
            (document.head || document.documentElement).appendChild(style);
        }
    } catch(e) {}
}"""

_TRACK_REVEALED_CONTENT_JS = """() => {
    try {
        if (!window.__revealed_content_elements) {
            window.__revealed_content_elements = new Map();
        }
        document.querySelectorAll('div, section, article, main, header, footer').forEach(el => {
            try {
                let cs = window.getComputedStyle(el);
                if (cs.position !== 'fixed' && cs.display !== 'none' && cs.visibility !== 'hidden' && parseFloat(cs.opacity) > 0) {
                    let textLen = (el.innerText || '').trim().length;
                    let hasContent = textLen > 20 || el.querySelector('img, h1, h2, h3, h4, h5, h6, p');
                    if (hasContent && !window.__revealed_content_elements.has(el)) {
                        window.__revealed_content_elements.set(el, cs.display);
                    }
                }
            } catch(e) {}
        });
    } catch(e) {}
}"""

_RESTORE_REVEALED_CONTENT_JS = """() => {
    try {
        if (window.__revealed_content_elements) {
            for (const [el, origDisplay] of window.__revealed_content_elements.entries()) {
                try {
                    if (!document.body.contains(el)) continue;
                    let cs = window.getComputedStyle(el);
                    if (cs.display === 'none') {
                        el.style.setProperty('display', (origDisplay && origDisplay !== 'none') ? origDisplay : 'block', 'important');
                    }
                    if (cs.visibility === 'hidden') {
                        el.style.setProperty('visibility', 'visible', 'important');
                    }
                    let isInactiveSlide = el.classList && (el.classList.contains('opacity-0') || el.classList.contains('pointer-events-none') || el.classList.contains('swiper-slide-duplicate'));
                    if (parseFloat(cs.opacity) === 0 && !isInactiveSlide) {
                        el.style.setProperty('opacity', '1', 'important');
                    }
                } catch(e) {}
            }
        }
    } catch(e) {}
}"""


_UNCONSTRAIN_CONTAINERS_JS = """() => {
    try {
        let unconstrained = false;

        // 1. Unconstrain html & body
        if (document.documentElement) {
            document.documentElement.style.setProperty('overflow', 'visible', 'important');
            document.documentElement.style.setProperty('height', 'auto', 'important');
            document.documentElement.style.setProperty('max-height', 'none', 'important');
        }
        if (document.body) {
            if (document.body.classList) {
                document.body.classList.remove('modal-open', 'didomi-popup-open');
            }
            document.body.style.setProperty('overflow', 'visible', 'important');
            document.body.style.setProperty('height', 'auto', 'important');
            document.body.style.setProperty('max-height', 'none', 'important');
            if (document.body.clientHeight === 0) {
                document.body.style.setProperty('min-height', '100vh', 'important');
            }
        }

        // 2. Unconstrain top-level SPA root and view containers (Spotify, Next.js, React/Angular apps)
        // Avoid generic [class*="Root"] / [class*="root"] which matches hundreds of Material-UI / BEM subcomponents!
        document.querySelectorAll('body > #main, body > #root, body > #__next, body > #app, body > [class*="Root"], body > [class*="root"], .Root__main-view, [data-testid="main-view-container"]').forEach(el => {
            unconstrained = true;
            el.style.setProperty('overflow', 'visible', 'important');
            el.style.setProperty('height', 'auto', 'important');
            el.style.setProperty('max-height', 'none', 'important');
            if (el.clientHeight === 0) {
                el.style.setProperty('min-height', '100vh', 'important');
            }
        });

        // Specific to Spotify desktop web player root grid:
        document.querySelectorAll('.Root__top-container, [data-testid="root-container"]').forEach(el => {
            let cs = window.getComputedStyle(el);
            if (cs.display === 'grid') {
                el.style.setProperty('grid-template-rows', 'auto auto auto', 'important');
            }
        });

        // 3. Find scrollable elements (including OverlayScrollbars & SPAs)
        document.querySelectorAll('*').forEach(el => {
            try {
                const cs = window.getComputedStyle(el);
                const isScrollable = (cs.overflowY === 'auto' || cs.overflowY === 'scroll' || cs.overflow === 'auto' || cs.overflow === 'scroll');
                const isOverlay = el.hasAttribute('data-overlayscrollbars-viewport') || (el.classList && el.classList.contains('os-viewport'));
                if ((isScrollable && el.scrollHeight > el.clientHeight + 100 && el.clientHeight > 300) || isOverlay) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width >= window.innerWidth * 0.3 || isOverlay) {
                        unconstrained = true;
                        el.style.setProperty('overflow', 'visible', 'important');
                        el.style.setProperty('overflow-y', 'visible', 'important');
                        el.style.setProperty('max-height', 'none', 'important');
                        el.style.setProperty('height', 'auto', 'important');

                        // Walk up parent chain: only unconstrain overflow and height/max-height.
                        // NEVER overwrite grid-template-rows or position on parents (preserves multi-row grids like Squarespace Fluid Engine)!
                        let p = el.parentElement;
                        while (p && p !== document.body && p !== document.documentElement) {
                            p.style.setProperty('overflow', 'visible', 'important');
                            p.style.setProperty('overflow-y', 'visible', 'important');
                            p.style.setProperty('max-height', 'none', 'important');
                            p.style.setProperty('height', 'auto', 'important');
                            p = p.parentElement;
                        }
                    }
                }
            } catch(e) {}
        });

        // 4. In Spotify / custom scrollbar apps: unconstrain OverlayScrollbars host, content, and player bar
        document.querySelectorAll('[data-overlayscrollbars-viewport], .os-viewport, .os-host, .os-content').forEach(os => {
            os.style.setProperty('overflow', 'visible', 'important');
            os.style.setProperty('height', 'auto', 'important');
            os.style.setProperty('max-height', 'none', 'important');
        });

        // If bottom now-playing / signup bar is fixed, ensure it flows naturally after content
        document.querySelectorAll('[data-testid="now-playing-bar"], footer[class*="now-playing"]').forEach(bar => {
            bar.style.setProperty('position', 'relative', 'important');
            bar.style.setProperty('top', 'auto', 'important');
            bar.style.setProperty('bottom', 'auto', 'important');
        });

        // 5. Force content-visibility: visible on all elements so Chromium paints all off-screen content
        document.querySelectorAll('*').forEach(el => {
            try {
                let cs = window.getComputedStyle(el);
                if (cs.contentVisibility && cs.contentVisibility !== 'visible') {
                    el.style.setProperty('content-visibility', 'visible', 'important');
                }
                if (cs.contain === 'strict' || cs.contain === 'paint') {
                    el.style.setProperty('contain', 'none', 'important');
                }
            } catch(e) {}
        });
        document.querySelectorAll('[data-testid*="card"], [data-testid*="shelf"], [class*="Shelf"], [role="group"], [class*="Card"], [class*="card"]').forEach(el => {
            el.style.setProperty('content-visibility', 'visible', 'important');
            el.style.setProperty('visibility', 'visible', 'important');
            el.style.setProperty('opacity', '1', 'important');
            el.style.setProperty('contain', 'none', 'important');
        });

        return unconstrained;
    } catch(e) {
        return false;
    }
}"""


def _wake_lazy_images(page):
    """
    Robust lazy image and dynamic content loader that guarantees 100% image,
    animation, and widget rendering identically across Windows and Linux (Docker/Xvfb).
    """
    try:
        # 1. Unmask initial data attributes and force eager loading
        _unmask_js = """() => {
            document.querySelectorAll('img, source').forEach(el => {
                if (el.tagName.toLowerCase() === 'img') {
                    if (el.getAttribute('loading') === 'lazy') {
                        el.setAttribute('loading', 'eager');
                    }
                    el.setAttribute('decoding', 'sync');
                    el.setAttribute('fetchpriority', 'high');

                    // If sizes is 'auto' or starts with 'auto' (e.g. Squarespace lazy images), give concrete hint
                    let sizes = el.getAttribute('sizes') || '';
                    if (sizes.startsWith('auto') || sizes === 'auto') {
                        el.setAttribute('sizes', '100vw');
                    }

                    if (el.naturalWidth === 0 && el.getAttribute('srcset')) {
                        const parts = el.getAttribute('srcset').split(',');
                        const last = parts[parts.length - 1].trim().split(' ')[0];
                        if (last && (last.startsWith('http') || last.startsWith('//') || last.startsWith('/'))) {
                            el.src = last;
                        }
                    }

                    let foundSrc = null;
                    if (el.dataset) {
                        for (let k in el.dataset) {
                            let v = el.dataset[k];
                            if (typeof v === 'string' && (v.startsWith('http') || v.startsWith('//') || v.startsWith('/') || v.startsWith('./'))) {
                                foundSrc = v;
                                break;
                            }
                        }
                    }
                    let src = foundSrc || el.getAttribute('data-src') || el.getAttribute('data-original') || el.getAttribute('data-lazy-src') || el.getAttribute('data-url') || el.getAttribute('data-highres') || el.getAttribute('data-lazy') || el.getAttribute('data-full-url');
                    if (src && (!el.src || el.src.length === 0 || el.naturalWidth === 0 || el.src.startsWith('data:'))) {
                        el.src = src;
                    }
                }
                let srcset = el.getAttribute('data-lazy-srcset') || el.getAttribute('data-srcset');
                if (srcset && (!el.srcset || el.srcset.startsWith('data:'))) {
                    el.srcset = srcset;
                }
            });
            document.querySelectorAll('img').forEach(el => {
                if (el.style.opacity === '0' || window.getComputedStyle(el).opacity === '0') {
                    el.style.setProperty('opacity', '1', 'important');
                    el.style.setProperty('visibility', 'visible', 'important');
                }
            });
            // Ensure dynamic shelf cards, album carousels, and grid items are fully visible
            document.querySelectorAll('[data-testid*="card"], [data-testid*="shelf"], [class*="Shelf"], [role="group"]').forEach(el => {
                el.style.setProperty('visibility', 'visible', 'important');
                if (window.getComputedStyle(el).opacity === '0') {
                    el.style.setProperty('opacity', '1', 'important');
                }
            });
            document.querySelectorAll('[data-bg], [data-background], [data-background-image], [data-lazy-bg]').forEach(el => {
                let bg = el.getAttribute('data-bg') || el.getAttribute('data-background') || el.getAttribute('data-background-image') || el.getAttribute('data-lazy-bg');
                if (bg) {
                    el.style.backgroundImage = 'url("' + bg + '")';
                }
            });

            // Unmask iframes (Google Ads iframes, embedded maps, video players, ad widgets)
            document.querySelectorAll('iframe').forEach(el => {
                if (el.getAttribute('loading') === 'lazy') {
                    el.setAttribute('loading', 'eager');
                }
                let src = el.getAttribute('data-src') || el.getAttribute('data-lazy-src') || el.getAttribute('data-original') || el.getAttribute('data-url');
                if (src && (!el.src || el.src === 'about:blank' || el.src.length === 0)) {
                    el.src = src;
                }
            });
        }"""
        page.evaluate(_unmask_js)
        page.evaluate(_TRACK_REVEALED_CONTENT_JS)

        # Trigger user interaction listeners (e.g. WP Rocket rocketlazyloadscript, dynamic HubSpot forms, lazy widget inits)
        try:
            page.mouse.move(100, 100)
            page.evaluate("""() => {
                ['mousemove', 'scroll', 'keydown', 'click', 'touchstart'].forEach(evt => {
                    window.dispatchEvent(new Event(evt, { bubbles: true }));
                    document.dispatchEvent(new Event(evt, { bubbles: true }));
                });
            }""")
        except Exception:
            pass

        # 2. Progressive scroll down across the entire unconstrained page and internal scroll containers
        scroll_height = page.evaluate("""() => {
            let maxH = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
            document.querySelectorAll('*').forEach(el => {
                let cs = window.getComputedStyle(el);
                if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll' || el.hasAttribute('data-overlayscrollbars-viewport') || (el.classList && el.classList.contains('os-viewport'))) && el.scrollHeight > maxH) {
                    maxH = el.scrollHeight;
                }
            });
            return maxH;
        }""") or 2000
        max_height = min(scroll_height, _MAX_CAPTURE_HEIGHT)
        viewport_step = 800

        pos = 0
        while pos < max_height:
            pos += viewport_step
            page.evaluate(f"""() => {{
                window.scrollTo(0, {pos});
                document.querySelectorAll('*').forEach(el => {{
                    let cs = window.getComputedStyle(el);
                    if (cs.overflowY === 'auto' || cs.overflowY === 'scroll' || el.hasAttribute('data-overlayscrollbars-viewport') || (el.classList && el.classList.contains('os-viewport'))) {{
                        if (el.scrollHeight > el.clientHeight + 50) {{
                            el.scrollTop = {pos};
                            el.dispatchEvent(new Event('scroll'));
                        }}
                    }}
                }});
            }}""")
            page.evaluate("window.dispatchEvent(new Event('scroll'));")
            page.evaluate(_TRACK_REVEALED_CONTENT_JS)
            # Team lead requirement: wait 2 seconds at each scroll step for dynamic widgets/iframes/ads to load
            time.sleep(2.0)

            # Check dynamic height and detect guest/auth walls on virtualized infinite feeds (e.g. Pinterest)
            scroll_status = page.evaluate("""() => {
                let maxB = 0;
                let innerScroll = 0;
                document.querySelectorAll('*').forEach(c => { if (c.scrollTop > innerScroll) innerScroll = c.scrollTop; });
                let effectiveScrollY = Math.max(window.scrollY, innerScroll);

                document.querySelectorAll('img, p, h1, h2, h3, a, [role="listitem"]').forEach(el => {
                    let r = el.getBoundingClientRect();
                    if (r.height > 20 && r.width > 20) {
                        let b = r.bottom + effectiveScrollY;
                        if (b > maxB) maxB = b;
                    }
                });
                // Genuine content walls (e.g. Pinterest unauth wall modal) - do NOT match Google One Tap credential_picker or reCAPTCHA badges
                let isWall = !!document.querySelector('[data-test-id*="unauth-wall"]');
                let curH = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
                document.querySelectorAll('*').forEach(el => {
                    let cs = window.getComputedStyle(el);
                    if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll' || el.hasAttribute('data-overlayscrollbars-viewport') || (el.classList && el.classList.contains('os-viewport'))) && el.scrollHeight > curH) {
                        curH = el.scrollHeight;
                    }
                });
                return {
                    maxB: Math.round(maxB),
                    isWall: isWall,
                    scrollHeight: curH
                };
            }""")
            cur_sh = (scroll_status and scroll_status.get("scrollHeight")) or 0
            if cur_sh > 0:
                max_height = max(max_height, min(cur_sh, _MAX_CAPTURE_HEIGHT))

            # If an auth/guest wall is present and scroll has progressed well beyond all visible content,
            # stop progressive scroll early to avoid inflating empty virtual space
            if scroll_status and scroll_status.get("isWall") and pos > scroll_status.get("maxB", 0) + 1200:
                break

        # Final bottom flush: Ensure internal scroll containers reach their absolute bottom
        page.evaluate("""() => {
            document.querySelectorAll('*').forEach(el => {
                let cs = window.getComputedStyle(el);
                if (cs.overflowY === 'auto' || cs.overflowY === 'scroll' || el.hasAttribute('data-overlayscrollbars-viewport') || (el.classList && el.classList.contains('os-viewport'))) {
                    if (el.scrollHeight > el.clientHeight + 50) {
                        el.scrollTop = el.scrollHeight;
                        el.dispatchEvent(new Event('scroll'));
                    }
                }
            });
        }""")
        time.sleep(2.0)

        # 3. At bottom: re-run unmask for dynamically mounted elements and wait for dynamic widgets
        page.evaluate(_unmask_js)
        page.evaluate(_TRACK_REVEALED_CONTENT_JS)
        time.sleep(2.0)

        # 4. NOW UNCONSTRAIN ALL CONTAINERS:
        # After scrolling has mounted all dynamic sections (e.g. Spotify Recommended releases, Fans also like),
        # unconstrain so the full height is visible in document flow without clipping or virtualization unmounting.
        page.evaluate(_UNCONSTRAIN_CONTAINERS_JS)

        # 5. Freeze & Reveal Phase 1: Lock all scroll-triggered animations (.js-scroll, AOS, WOW, etc.)
        # so they do NOT disappear or revert to opacity:0 when scrolling back to top
        page.evaluate(_UNIVERSAL_ANIMATION_JS)

        # 6. Smoothly return to top without firing scroll events that re-trigger React unmounting
        page.evaluate("window.scrollTo(0, 0);")
        time.sleep(1.0)

        # Restore content elements that were revealed during scrolling but re-hidden by scroll listeners
        page.evaluate(_RESTORE_REVEALED_CONTENT_JS)
        page.evaluate(_unmask_js)

        # 7. Smart wait: wait until images actually have naturalWidth > 0
        start = time.time()
        while time.time() - start < 5.0:
            unloaded = page.evaluate("""() => {
                let imgs = Array.from(document.querySelectorAll('img'));
                return imgs.filter(img => img.src && !img.src.startsWith('data:') && img.naturalWidth === 0 && img.clientHeight > 0).length;
            }""")
            if unloaded == 0:
                break
            time.sleep(0.5)

        # 8. Smart wait for dynamic forms / HubSpot iframes if present on page
        form_start = time.time()
        while time.time() - form_start < 4.0:
            has_pending_form = page.evaluate("""() => {
                let hasHsScript = !!document.querySelector('script[src*="hsforms"], script[data-rocket-src*="hsforms"], script#hubspot-forms-js');
                let formWrapper = document.querySelector('.form-wrapper, [class*="hs-form"], [id*="hs_form"]');
                let hasIframe = !!document.querySelector('.hs-form-iframe, iframe[id*="hs-form"]');
                return (hasHsScript && formWrapper && !hasIframe);
            }""")
            if not has_pending_form:
                break
            time.sleep(0.5)

    except Exception:
        pass


def _trim_trailing_blank_void(image, min_void_px=300, padding_px=100):
    """
    Trims trailing massive empty voids (e.g. 300+ px of pure uniform blank background)
    at the bottom of full-page screenshots using pure PIL, with no external dependencies.
    Preserves real content and provides a clean 100px bottom padding.
    """
    try:
        w, h = image.size
        if h <= min_void_px:
            return image

        rgb_img = image.convert("RGB")
        # Sample background color from the very bottom row across 5 sample points
        samples = [rgb_img.getpixel((x, h - 1)) for x in [0, w // 4, w // 2, 3 * w // 4, w - 1]]
        r_vals = [s[0] for s in samples]
        g_vals = [s[1] for s in samples]
        b_vals = [s[2] for s in samples]
        # If the bottom edge has varied colors, it's real content/footer artwork, do not trim
        if max(r_vals) - min(r_vals) > 15 or max(g_vals) - min(g_vals) > 15 or max(b_vals) - min(b_vals) > 15:
            return image

        bg_r = sum(r_vals) // len(r_vals)
        bg_g = sum(g_vals) // len(g_vals)
        bg_b = sum(b_vals) // len(b_vals)

        step = 5
        last_content_y = None
        tolerance = 8

        for y in range(h - 1, 0, -step):
            is_empty = True
            for x in range(0, w, max(1, w // 20)):
                pr, pg, pb = rgb_img.getpixel((x, y))
                if abs(pr - bg_r) > tolerance or abs(pg - bg_g) > tolerance or abs(pb - bg_b) > tolerance:
                    is_empty = False
                    break
            if not is_empty:
                last_content_y = y
                for refine_y in range(y, min(h, y + step)):
                    row_has_content = False
                    for rx in range(0, w, max(1, w // 30)):
                        pr, pg, pb = rgb_img.getpixel((rx, refine_y))
                        if abs(pr - bg_r) > tolerance or abs(pg - bg_g) > tolerance or abs(pb - bg_b) > tolerance:
                            row_has_content = True
                            break
                    if row_has_content:
                        last_content_y = refine_y
                break

        if last_content_y is not None:
            void_height = h - 1 - last_content_y
            if void_height >= min_void_px:
                new_h = min(h, last_content_y + padding_px)
                return image.crop((0, 0, w, new_h))

        return image
    except Exception:
        return image


def _save_with_size_limit(image, img_name, max_mb=1.0):
    """Save a PIL Image as an optimised JPEG, compressing progressively under max_mb."""
    os.makedirs(os.path.dirname(img_name), exist_ok=True)

    if image.mode != "RGB":
        image = image.convert("RGB")

    quality = 85
    image.save(img_name, format="JPEG", quality=quality, optimize=True)

    file_size_mb = os.path.getsize(img_name) / (1024 * 1024)
    attempts = 0
    while file_size_mb > max_mb and attempts < 10:
        attempts += 1
        w, h = image.size
        new_w = max(100, int(w * 0.9))
        new_h = max(100, int(h * 0.9))
        image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        quality = max(50, quality - 5)
        image.save(img_name, format="JPEG", quality=quality, optimize=True)
        file_size_mb = os.path.getsize(img_name) / (1024 * 1024)


def get(page, img_name, instance_no):
    """Capture a full-page screenshot using Playwright, capped at max dimensions and < 1.0 MB."""
    target_path = "./images/" + str(instance_no) + "/" + img_name + ".jpg"

    try:
        # Step 0: Team lead requirement - wait 10 seconds before taking screenshot
        # During the 10-second wait, periodically dismiss blocking cookie/consent banners
        # so SPAs (like Angular/Spartacus, React) immediately start unblocking & hydrating content
        wait_start = time.time()
        while time.time() - wait_start < 10.0:
            try:
                page.mouse.move(50, 50)
                page.evaluate("""() => {
                    ['mousemove', 'scroll', 'keydown', 'click', 'touchstart'].forEach(evt => {
                        window.dispatchEvent(new Event(evt, { bubbles: true }));
                        document.dispatchEvent(new Event(evt, { bubbles: true }));
                    });
                    const consentBtn = document.querySelector(
                        '#onetrust-accept-btn-handler, #onetrust-reject-all-handler, #CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, [data-testid="cookie-accept-all"], [data-testid*="cookie-policy-manage-dialog-accept"], aside#consent-banner button, [id*="consent-banner"] button'
                    );
                    if (consentBtn && consentBtn.offsetHeight > 0) {
                        consentBtn.click();
                        return;
                    }
                    const ucUi = document.getElementById('usercentrics-cmp-ui');
                    if (ucUi && ucUi.shadowRoot) {
                        const ucBtn = ucUi.shadowRoot.querySelector('button[data-testid="uc-accept-all-button"], button[data-testid*="accept"]');
                        if (ucBtn) ucBtn.click();
                    }
                    document.querySelectorAll('#onetrust-banner-sdk button, [id*="cookie"] button, [class*="cookie"] button, [id*="consent"] button, [class*="consent"] button, aside#consent-banner button, [role="dialog"] button, .modal button').forEach(b => {
                        let txt = (b.innerText || '').trim().toLowerCase();
                        if (['accept', 'reject', 'accept all', 'allow all', 'accept cookies', 'agree and proceed', 'reject all', 'i agree', 'allow selection', 'accept all cookies', 'close', 'got it'].includes(txt)) {
                            b.click();
                        }
                    });
                }""")
            except Exception:
                pass
            time.sleep(2.0)

        # For heavy SPAs / map applications, wait for network tile streams to settle
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        # Step 1: Wake lazy images with robust progressive scroll
        _wake_lazy_images(page)

        # Safety buffer: wait 3 seconds after progressive scroll so all assets settle
        time.sleep(3.0)

        # Step 1b: Final Freeze & Reveal + Modal / Dialog Dismissal + Font readiness check
        try:
            page.evaluate(_UNIVERSAL_ANIMATION_JS)

            # 1. Dismiss standard modals & ARIA dialogs (e.g. Instagram guest walls)
            try:
                close_btn = page.query_selector(
                    '[role="dialog"] [aria-label="Close"], [role="dialog"] button.close, svg[aria-label="Close"], .modal .close'
                )
                if close_btn:
                    close_btn.click(timeout=1000)
                    time.sleep(0.5)
            except Exception:
                pass

            # 2. Purge remaining backdrops, modals, cookie popups, consent overlays, sticky auth dialogs, and hanging preloaders
            page.evaluate("""() => {
                try {
                    // Remove fixed animated header frame holders
                    document.querySelectorAll('.si-factory-animated-header__frame-holder, .si-factory-animated-header').forEach(el => el.remove());

                    // Hide hanging preloaders / page loader screens
                    document.querySelectorAll('.preloader, #preloader, [class*="preloader"], [id*="preloader"], .page-loader, #page-loader, .loading-screen, #loading-screen').forEach(el => {
                        if (el === document.body || el === document.documentElement) return;
                        try {
                            let cs = window.getComputedStyle(el);
                            if (cs.position === 'fixed' || cs.position === 'absolute') {
                                el.style.setProperty('display', 'none', 'important');
                                el.style.setProperty('opacity', '0', 'important');
                                el.style.setProperty('visibility', 'hidden', 'important');
                            }
                        } catch(e) {}
                    });

                    // Purge generic modals, backdrops, and cookie/consent overlays without triggering reload handlers
                    const host = document.getElementById('didomi-host');
                    if (host) host.remove();
                    const uc = document.getElementById('usercentrics-cmp-ui');
                    if (uc) uc.remove();
                    document.querySelectorAll('#usercentrics-cmp-ui, #usercentrics-root, [id*="usercentrics"], [class*="usercentrics"], #didomi-host, [id*="didomi"], [class*="didomi"], .modal, .modal-backdrop, [class*="modal-popup"], [class*="cookie"], [id*="cookie"], [aria-label*="cookie"], #onetrust-banner-sdk, [class*="onetrust"], #CybotCookiebotDialog, [id*="consent"], [class*="consent"], aside#consent-banner, [id*="consent-banner"]').forEach(el => {
                        if (el === document.body || el === document.documentElement) return;
                        try {
                            let cs = window.getComputedStyle(el);
                            let cls = (typeof el.className === 'string') ? el.className.toLowerCase() : '';
                            let id = (typeof el.id === 'string') ? el.id.toLowerCase() : '';
                            let hasBackdropCls = el.classList && el.classList.contains && el.classList.contains('modal-backdrop');
                            if (cs.position === 'fixed' || cs.position === 'sticky' || hasBackdropCls || id.includes('didomi') || cls.includes('didomi') || id.includes('usercentrics') || cls.includes('usercentrics')) {
                                el.remove();
                            }
                        } catch(e) {}
                    });

                    // Scan for buttons/links containing consent action text and remove their fixed/high-z overlay container
                    document.querySelectorAll('button, a').forEach(btn => {
                        try {
                            const txt = (btn.innerText || '').trim().toLowerCase();
                            if (['accept', 'reject', 'accept all', 'allow all', 'accept cookies', 'agree and proceed', 'reject all', 'allow selection', 'accept all cookies', 'reject non-essential'].includes(txt)) {
                                try { btn.click(); } catch(e) {}
                                let p = btn.parentElement;
                                let overlay = null;
                                while (p && p !== document.body && p !== document.documentElement) {
                                    const cs = window.getComputedStyle(p);
                                    let z = parseInt(cs.zIndex, 10);
                                    if (cs.position === 'fixed' || (!isNaN(z) && z >= 50)) {
                                        overlay = p;
                                    }
                                    p = p.parentElement;
                                }
                                if (overlay && overlay !== document.body && overlay !== document.documentElement) {
                                    overlay.remove();
                                }
                            }
                        } catch(e) {}
                    });

                    // Purge Google One Tap & floating reCAPTCHA badges
                    document.querySelectorAll('#credential_picker_container, #credential_picker_iframe, iframe[src*="accounts.google.com/gsi"], iframe[id*="gsi_"], [id*="credential_picker"], .grecaptcha-badge, [class*="grecaptcha-badge"]').forEach(el => el.remove());

                    // Purge auth dialogs & floating sign-in prompts (Instagram, Pinterest, Spotify, etc.)
                    document.querySelectorAll('[role="dialog"], [class*="unauth"], div').forEach(el => {
                        if (el === document.body || el === document.documentElement) return;
                        try {
                            let cs = window.getComputedStyle(el);
                            let isFixed = cs.position === 'fixed' || cs.position === 'sticky';
                            if (isFixed || el.getAttribute('role') === 'dialog') {
                                let txt = (el.innerText || '');
                                if (txt.includes('Sign up') || txt.includes('Log In') || txt.includes('Log in') || 
                                    txt.includes('You are signed out') || (txt.includes('Sign in') && txt.includes('best experience')) ||
                                    txt.includes('Save your password with Google')) {
                                    if (el.offsetHeight > 100 || isFixed) {
                                        el.remove();
                                    }
                                }
                            }
                        } catch(e) {}
                    });

                    // Clamp masonry/virtualized containers where style.height was stretched but children only occupy a fraction
                    document.querySelectorAll('[class*="Masonry"], [class*="masonry"], [data-test-id*="masonry"]').forEach(m => {
                        let maxChildBottom = 0;
                        Array.from(m.children).forEach(c => {
                            let r = c.getBoundingClientRect();
                            let b = r.bottom - m.getBoundingClientRect().top;
                            if (b > maxChildBottom) maxChildBottom = b;
                        });
                        if (maxChildBottom > 200 && m.offsetHeight > maxChildBottom + 100) {
                            m.style.setProperty('height', maxChildBottom + 'px', 'important');
                        }
                    });

                    // Collapse artificial sticky scroll tracks (Wordsmith)
                    document.querySelectorAll('section, div').forEach(el => {
                        let st = el.getAttribute('style') || '';
                        let hasVh = /height:\s*(\d+)vh/.test(st);
                        let valVh = hasVh ? parseInt(st.match(/height:\s*(\d+)vh/)[1]) : 0;
                        let valPx = /height:\s*(\d+)px/.test(st) ? parseInt(st.match(/height:\s*(\d+)px/)[1]) : 0;
                        let isTrack = el.classList.contains('srs-track') || valVh >= 150 || valPx >= 2000;
                        if (isTrack) {
                            let stickyChild = Array.from(el.children).find(c => {
                                let cs = window.getComputedStyle(c);
                                return cs.position === 'sticky' || (c.classList && c.classList.contains('sticky'));
                            });
                            if (stickyChild) {
                                el.style.setProperty('height', 'auto', 'important');
                                el.style.setProperty('min-height', 'auto', 'important');
                                el.style.setProperty('max-height', 'none', 'important');
                                Array.from(el.children).forEach(c => {
                                    let cs = window.getComputedStyle(c);
                                    if (cs.position === 'sticky' || (c.classList && c.classList.contains('sticky'))) {
                                        c.style.setProperty('position', 'relative', 'important');
                                        c.style.setProperty('top', '0px', 'important');
                                    }
                                });
                            }
                        }
                    });

                    // Remove full-screen curtains, transition overlays, and backdrops (dark, white, grey, blur-filtered, or off-screen transition sheets)
                    document.querySelectorAll('div, section, aside').forEach(el => {
                        if (el === document.body || el === document.documentElement) return;
                        // Never remove ad containers, iframes, or Google Ad components
                        if (el.querySelector('iframe, ins, [id*="google"], [class*="google"], [id*="gpt"], [class*="gpt"], [class*="ad-"]')) return;
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

                                    // Purge if:
                                    // 1) Known overlay/backdrop/transition/curtain with no complex text content
                                    // 2) Any full-screen fixed element with background that is completely devoid of interactive controls & text (< 50 chars)
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

            # Unconstrain primary inner scroll container & SPAs (Spotify, Flipkart, etc.)
            page.evaluate(_UNCONSTRAIN_CONTAINERS_JS)
            page.evaluate("document.fonts ? document.fonts.ready : Promise.resolve()")
            page.evaluate(_RESTORE_REVEALED_CONTENT_JS)
        except Exception:
            pass

        # Step 1c: Video elements max-height lock (prevents distorted video containers)
        try:
            page.evaluate("""() => {
                document.querySelectorAll('video').forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if (rect.height > 0 && rect.height <= 1200) {
                        el.style.maxHeight = rect.height + 'px';
                        if (el.parentElement) {
                            el.parentElement.style.maxHeight = rect.height + 'px';
                        }
                    }
                });
            }""")
        except Exception:
            pass

        # Step 2: Native Playwright full_page screenshot
        try:
            png_bytes = page.screenshot(full_page=True, timeout=60000)
        except Exception as e:
            print(f"[Screenshot] Full page screenshot failed ({e}), falling back to viewport capture.")
            png_bytes = page.screenshot(full_page=False, timeout=30000)

        image = Image.open(BytesIO(png_bytes))

        # Step 3: Hard-crop bounds safety net
        if image.height > _MAX_CAPTURE_HEIGHT:
            image = image.crop((0, 0, image.width, _MAX_CAPTURE_HEIGHT))
        if image.width > _MAX_CAPTURE_WIDTH:
            image = image.crop((0, 0, _MAX_CAPTURE_WIDTH, image.height))

        # Step 3b: Universal trailing blank void trimmer
        # Removes trailing massive empty voids (e.g. 300+ px of pure uniform blank background)
        # caused by overstretched document heights, virtualized feeds (Pinterest), or SPAs (Spotify)
        image = _trim_trailing_blank_void(image, min_void_px=300, padding_px=100)

        # Step 4: Progressively compress to JPEG < 1.0 MB
        _save_with_size_limit(image, target_path)
        if "sample_" in str(instance_no):
            _save_with_size_limit(image, f"./images/saved_samples/{instance_no}.jpg")
        return target_path

    except Exception as err:
        raise Exception(f"Screenshot error: {err}") from err
