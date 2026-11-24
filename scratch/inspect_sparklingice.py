import sys
sys.path.append('.')
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import time
from helper import init

def inspect_sparklingice():
    print("\n--- Inspecting sparklingice.com ---")
    page, _ = init.init_dc('in')
    try:
        url = "https://www.sparklingice.com/?utm_source=DV360&utm_medium=programmatic&utm_campaign=SparklingIce_COREQ126_YT&utm_content=TKR_26_US_SICOREYT_AW_PP_PA_SELI_POSS_YOU_APL_NA_SIX_STD_15_CORE_CD_MRM&gad_source=2&gad_campaignid=23590031968&gclid=EAIaIQobChMIy5qKn67XlAMVJlRvBB1H2zGfEAEYAyAAEgIdqfD_BwE"
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        time.sleep(10)

        info = page.evaluate('''() => {
            const sections = Array.from(document.querySelectorAll('section, main > div, body > div')).map(s => {
                const cs = window.getComputedStyle(s);
                return {
                    tag: s.tagName,
                    id: s.id,
                    className: s.className,
                    height: s.offsetHeight,
                    width: s.offsetWidth,
                    display: cs.display,
                    visibility: cs.visibility,
                    opacity: cs.opacity,
                    position: cs.position,
                    transform: cs.transform,
                    hasImages: s.querySelectorAll('img').length,
                    images: Array.from(s.querySelectorAll('img')).map(i => ({
                        src: (i.src || '').slice(0, 100),
                        dataSrc: (i.getAttribute('data-src') || i.getAttribute('data-lazy-src') || '').slice(0, 100),
                        w: i.offsetWidth,
                        h: i.offsetHeight,
                        natW: i.naturalWidth,
                        natH: i.naturalHeight,
                        display: window.getComputedStyle(i).display,
                        opacity: window.getComputedStyle(i).opacity,
                        visibility: window.getComputedStyle(i).visibility
                    })).slice(0, 5),
                    textLen: (s.innerText || '').length,
                    textSample: (s.innerText || '').slice(0, 100).replace(/\\n/g, ' ')
                };
            }).filter(s => s.height > 50 || s.hasImages > 0 || s.textLen > 10);

            return { sections };
        }''')
        print(f"Total sections: {len(info['sections'])}")
        for i, sec in enumerate(info['sections']):
            print(f"\n--- Section {i}: {sec['tag']} #{sec['id']} .{sec['className'][:40]} (h={sec['height']}, pos={sec['position']}, op={sec['opacity']}, vis={sec['visibility']}, imgs={sec['hasImages']}) ---")
            print(f"Text: {sec['textSample']}")
            if sec['images']:
                print(f"Images ({len(sec['images'])}):")
                for img in sec['images']:
                    print("  ", img)
    finally:
        init.close_browser(page)

if __name__ == '__main__':
    inspect_sparklingice()
