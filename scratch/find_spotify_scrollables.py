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

# Run the unconstrain logic from screenshot.py
unconstrained = page.evaluate('''() => {
    let unconstrained = false;
    let list = [];
    document.querySelectorAll('*').forEach(el => {
        const cs = window.getComputedStyle(el);
        const isScrollable = (cs.overflowY === 'auto' || cs.overflowY === 'scroll');
        if (isScrollable && el.scrollHeight > el.clientHeight + 100 && el.clientHeight > 400) {
            list.push({
                tag: el.tagName,
                cls: el.className,
                id: el.id,
                scrollH: el.scrollHeight,
                clientH: el.clientHeight
            });
        }
    });
    return list;
}''')

import pprint
print("Scrollable elements found in Spotify:", flush=True)
pprint.pprint(unconstrained)
init.close_browser(page)
