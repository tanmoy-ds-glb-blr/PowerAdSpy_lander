import sys
sys.path.append('.')
import time
from helper import init

def inspect():
    page, _ = init.init_dc('in')
    try:
        url = 'https://www.sparklingice.com/?utm_source=DV360&utm_medium=programmatic&utm_campaign=SparklingIce_COREQ126_YT&utm_content=TKR_26_US_SICOREYT_AW_PP_PA_SELI_POSS_YOU_APL_NA_SIX_STD_15_CORE_CD_MRM&gad_source=2&gad_campaignid=23590031968&gclid=EAIaIQobChMIy5qKn67XlAMVJlRvBB1H2zGfEAEYAyAAEgIdqfD_BwE'
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        time.sleep(10)

        hidden_elements = page.evaluate('''() => {
            let list = [];
            document.querySelectorAll('section, [class*="slide"], [class*="slider"], [class*="product"], [class*="recipe"]').forEach(el => {
                let cs = window.getComputedStyle(el);
                if (cs.opacity === '0' || cs.visibility === 'hidden' || cs.display === 'none' || el.offsetHeight === 0) {
                    list.push({
                        tag: el.tagName,
                        cls: el.className,
                        id: el.id,
                        h: el.offsetHeight,
                        w: el.offsetWidth,
                        display: cs.display,
                        visibility: cs.visibility,
                        opacity: cs.opacity,
                        childCount: el.children.length
                    });
                }
            });
            return list;
        }''')
        import pprint
        print('Hidden/0-height elements count:', len(hidden_elements))
        pprint.pprint(hidden_elements[:25])
        
        # Also check what sliders/carousels exist
        sliders = page.evaluate('''() => {
            return Array.from(document.querySelectorAll('[class*="slick"], [class*="swiper"], [class*="slider"], [class*="carousel"]')).map(el => ({
                tag: el.tagName,
                cls: el.className,
                id: el.id,
                h: el.offsetHeight,
                display: window.getComputedStyle(el).display,
                childCount: el.children.length
            }));
        }''')
        print('\nSliders/Carousels count:', len(sliders))
        pprint.pprint(sliders[:20])

    finally:
        init.close_browser(page)

if __name__ == '__main__':
    inspect()
