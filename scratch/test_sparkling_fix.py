import sys
sys.path.append('.')
import time
from helper import init

def test_fix():
    page, _ = init.init_dc('in')
    try:
        url = 'https://www.sparklingice.com/?utm_source=DV360&utm_medium=programmatic&utm_campaign=SparklingIce_COREQ126_YT&utm_content=TKR_26_US_SICOREYT_AW_PP_PA_SELI_POSS_YOU_APL_NA_SIX_STD_15_CORE_CD_MRM&gad_source=2&gad_campaignid=23590031968&gclid=EAIaIQobChMIy5qKn67XlAMVJlRvBB1H2zGfEAEYAyAAEgIdqfD_BwE'
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        
        # 10s lead wait as required
        time.sleep(10)
        
        # Apply fix
        page.evaluate('''() => {
            // 1. Unmask images with data: SVG placeholders
            document.querySelectorAll('img, source').forEach(el => {
                if (el.tagName.toLowerCase() === 'img') {
                    if (el.getAttribute('loading') === 'lazy') el.setAttribute('loading', 'eager');
                    el.setAttribute('decoding', 'sync');
                    el.setAttribute('fetchpriority', 'high');

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
                    let src = foundSrc || el.getAttribute('data-lazy-src') || el.getAttribute('data-src') || el.getAttribute('data-original') || el.getAttribute('data-url') || el.getAttribute('data-highres');
                    if (src && (!el.src || el.src.length === 0 || el.naturalWidth === 0 || el.src.startsWith('data:'))) {
                        el.src = src;
                    }
                    
                    let srcset = el.getAttribute('data-lazy-srcset') || el.getAttribute('data-srcset');
                    if (srcset && (!el.srcset || el.srcset.startsWith('data:'))) {
                        el.srcset = srcset;
                    }
                }
            });

            // 2. Uncollapse 0-height sliders / carousels
            document.querySelectorAll('#si-product-slider__container, .si-product-slider, .si-product-slide, [class*="product-slide"]').forEach(el => {
                el.style.setProperty('height', 'auto', 'important');
                el.style.setProperty('min-height', '450px', 'important');
                el.style.setProperty('overflow', 'visible', 'important');
                el.style.setProperty('display', 'block', 'important');
            });

            // 3. Force visibility on recipe slider cards and images
            document.querySelectorAll('.si-recipe-slider img, [class*="recipe-slider"] img, [class*="recipe-card"] img, .si-recipe-card, .si-recipe-slide').forEach(el => {
                el.style.setProperty('opacity', '1', 'important');
                el.style.setProperty('visibility', 'visible', 'important');
            });
            
            // Remove full-height hidden animation headers that block or distort layout
            document.querySelectorAll('.si-factory-animated-header').forEach(el => {
                el.style.setProperty('display', 'none', 'important');
            });
        }''')
        
        # Progressive scroll
        for y in range(0, 5000, 800):
            page.evaluate(f"window.scrollTo(0, {y});")
            time.sleep(0.5)
            
        page.evaluate('''() => {
            // Re-run unmask after scroll
            document.querySelectorAll('img').forEach(el => {
                let src = el.getAttribute('data-lazy-src') || el.getAttribute('data-src') || el.getAttribute('data-original');
                if (src && (!el.src || el.src.startsWith('data:') || el.naturalWidth === 0)) {
                    el.src = src;
                }
                el.style.setProperty('opacity', '1', 'important');
                el.style.setProperty('visibility', 'visible', 'important');
            });
        }''')
        
        page.evaluate("window.scrollTo(0, 0);")
        time.sleep(2)
        
        page.screenshot(path='scratch/fixed_sparklingice.jpg', full_page=True)
        print("Screenshot saved to scratch/fixed_sparklingice.jpg")
    finally:
        init.close_browser(page)

if __name__ == '__main__':
    test_fix()
