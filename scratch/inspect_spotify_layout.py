import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
from helper import init

page, _ = init.init_dc('in')
url = "https://open.spotify.com/track/5McmtLnuuUvBvESzMFQ4Yo?utm_source=dv360-united-states-awareness-na-na&utm_medium=olv&utm_campaign=ca7rielandpaco-music-yt-ca7rielandpaco-fans-ca7riel-yt-muero-15s-local-united-states-awareness-nam-cultural-2026q2&utm_content=artistmuero-no&gad_source=2&gad_campaignid=23857090794&gclid=EAIaIQobChMIq7qdvLDXlAMVQDyKAx3SaQDeEAEYASAAEgJpBPD_BwE"

page.goto(url, timeout=90000, wait_until='domcontentloaded')
time.sleep(10)

layout_info = page.evaluate('''() => {
    let mainView = document.querySelector('main, [data-testid="main-view"], .main-view-container, [data-overlayscrollbars-viewport]');
    let root = document.querySelector('#main, #root, .Root');
    
    function inspectEl(el) {
        if (!el) return null;
        let cs = window.getComputedStyle(el);
        return {
            tag: el.tagName,
            cls: el.className,
            id: el.id,
            h: el.offsetHeight,
            scrollH: el.scrollHeight,
            overflowY: cs.overflowY,
            position: cs.position
        };
    }
    
    // Find all children of main
    let mainChildren = [];
    if (mainView) {
        Array.from(mainView.children).forEach(c => {
            mainChildren.push(inspectEl(c));
        });
    }
    
    return {
        body: inspectEl(document.body),
        doc: inspectEl(document.documentElement),
        root: inspectEl(root),
        mainView: inspectEl(mainView),
        mainChildren
    };
}''')

import pprint
pprint.pprint(layout_info)
init.close_browser(page)
