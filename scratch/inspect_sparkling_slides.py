import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
from helper import init

page, _ = init.init_dc('in')
url = "https://www.sparklingice.com/?utm_source=DV360&utm_medium=programmatic&utm_campaign=SparklingIce_COREQ126_YT&utm_content=TKR_26_US_SICOREYT_AW_PP_PA_SELI_POSS_YOU_APL_NA_SIX_STD_15_CORE_CD_MRM&gad_source=2&gad_campaignid=23590031968&gclid=EAIaIQobChMIy5qKn67XlAMVJlRvBB1H2zGfEAEYAyAAEgIdqfD_BwE"

page.goto(url, timeout=90000, wait_until='domcontentloaded')
time.sleep(5)

slider_details = page.evaluate('''() => {
    const container = document.querySelector('#si-product-slider__container');
    if (!container) return 'not found';
    
    let slides = Array.from(container.querySelectorAll('.si-product-slide, [class*="product-slide"], [class*="slide"]')).map(s => {
        const cs = window.getComputedStyle(s);
        let imgs = Array.from(s.querySelectorAll('img')).map(i => ({
            src: (i.src || '').slice(0, 80),
            dataSrc: (i.getAttribute('data-src') || i.getAttribute('data-lazy-src') || '').slice(0, 80),
            w: i.offsetWidth,
            h: i.offsetHeight,
            natW: i.naturalWidth,
            natH: i.naturalHeight,
            opacity: window.getComputedStyle(i).opacity,
            visibility: window.getComputedStyle(i).visibility
        }));
        let columns = Array.from(s.querySelectorAll('[class*="column"], [class*="content"]')).map(c => ({
            cls: c.className,
            h: c.offsetHeight,
            opacity: window.getComputedStyle(c).opacity,
            visibility: window.getComputedStyle(c).visibility,
            text: (c.innerText || '').slice(0, 50).replace(/\\n/g, ' ')
        }));
        return {
            cls: s.className,
            h: s.offsetHeight,
            opacity: cs.opacity,
            visibility: cs.visibility,
            display: cs.display,
            imgs,
            columns
        };
    });
    
    return {
        containerH: container.offsetHeight,
        containerMT: window.getComputedStyle(container).marginTop,
        slides
    };
}''')

import pprint
pprint.pprint(slider_details)
init.close_browser(page)
