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

dom_tree = page.evaluate('''() => {
    function getTree(el, depth) {
        if (!el || depth > 5) return null;
        let cs = window.getComputedStyle(el);
        let children = Array.from(el.children).map(c => getTree(c, depth + 1)).filter(Boolean);
        return {
            tag: el.tagName,
            cls: el.className.toString().slice(0, 40),
            id: el.id,
            h: el.offsetHeight,
            scrollH: el.scrollHeight,
            overflowY: cs.overflowY,
            children
        };
    }
    return getTree(document.body, 0);
}''')

import pprint
pprint.pprint(dom_tree)
init.close_browser(page)
