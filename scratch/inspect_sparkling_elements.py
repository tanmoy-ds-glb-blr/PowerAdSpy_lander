import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
from helper import init

page, _ = init.init_dc('in')
url = "https://www.sparklingice.com/?utm_source=DV360&utm_medium=programmatic&utm_campaign=SparklingIce_COREQ126_YT&utm_content=TKR_26_US_SICOREYT_AW_PP_PA_SELI_POSS_YOU_APL_NA_SIX_STD_15_CORE_CD_MRM&gad_source=2&gad_campaignid=23590031968&gclid=EAIaIQobChMIy5qKn67XlAMVJlRvBB1H2zGfEAEYAyAAEgIdqfD_BwE"

print("Navigating to sparklingice...")
page.goto(url, timeout=90000, wait_until='domcontentloaded')
time.sleep(10)

diag = page.evaluate('''() => {
    const elHeader = document.querySelector('.si-factory-animated-header');
    const elFrame = document.querySelector('.si-factory-animated-header__frame-holder');
    const elSlider = document.querySelector('#si-product-slider__container');
    const elRecipe = document.querySelector('.si-recipe-slider-section');
    
    function getInfo(el) {
        if (!el) return null;
        const cs = window.getComputedStyle(el);
        return {
            tag: el.tagName,
            cls: el.className,
            id: el.id,
            pos: cs.position,
            display: cs.display,
            visibility: cs.visibility,
            opacity: cs.opacity,
            h: el.offsetHeight,
            w: el.offsetWidth,
            marginTop: cs.marginTop,
            bg: cs.backgroundColor,
            zIndex: cs.zIndex,
            children: el.children.length
        };
    }
    
    return {
        header: getInfo(elHeader),
        frame: getInfo(elFrame),
        slider: getInfo(elSlider),
        recipe: getInfo(elRecipe)
    };
}''')

import pprint
pprint.pprint(diag)
init.close_browser(page)
