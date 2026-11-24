import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
from helper import init
import time
import pprint

page, _ = init.init_dc('in')
url = "https://open.spotify.com/track/5McmtLnuuUvBvESzMFQ4Yo?utm_source=dv360-united-states-awareness-na-na&utm_medium=olv&utm_campaign=ca7rielandpaco-music-yt-ca7rielandpaco-fans-ca7riel-yt-muero-15s-local-united-states-awareness-nam-cultural-2026q2&utm_content=artistmuero-no&gad_source=2&gad_campaignid=23857090794&gclid=EAIaIQobChMIq7qdvLDXlAMVQDyKAx3SaQDeEAEYASAAEgJpBPD_BwE"
page.goto(url, timeout=90000, wait_until='domcontentloaded')
time.sleep(10)

res = page.evaluate('''() => {
    let all = [];
    document.body.childNodes.forEach(node => {
        if (node.nodeType === 1) { // Element
            let cs = window.getComputedStyle(node);
            all.push({
                tag: node.tagName,
                cls: node.className.toString().slice(0, 50),
                id: node.id,
                h: node.offsetHeight,
                w: node.offsetWidth,
                display: cs.display,
                position: cs.position
            });
        }
    });
    return {
        bodyChildren: all,
        title: document.title,
        bodyH: document.body.scrollHeight,
        docH: document.documentElement.scrollHeight
    };
}''')

pprint.pprint(res)

# Take viewport screenshot
page.screenshot(path="scratch/spotify_test_vp.jpg", full_page=False)
page.screenshot(path="scratch/spotify_test_fp.jpg", full_page=True)

from PIL import Image
vp = Image.open("scratch/spotify_test_vp.jpg")
fp = Image.open("scratch/spotify_test_fp.jpg")
print(f"Viewport screenshot size: {vp.size}")
print(f"Full-page screenshot size: {fp.size}")

init.close_browser(page)
