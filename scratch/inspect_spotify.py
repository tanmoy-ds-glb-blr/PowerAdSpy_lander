import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
from helper import init

print(">>> Starting Spotify inspection...", flush=True)
page, _ = init.init_dc('in')
try:
    url = "https://open.spotify.com/track/5McmtLnuuUvBvESzMFQ4Yo?utm_source=dv360-united-states-awareness-na-na&utm_medium=olv&utm_campaign=ca7rielandpaco-music-yt-ca7rielandpaco-fans-ca7riel-yt-muero-15s-local-united-states-awareness-nam-cultural-2026q2&utm_content=artistmuero-no&gad_source=2&gad_campaignid=23857090794&gclid=EAIaIQobChMIq7qdvLDXlAMVQDyKAx3SaQDeEAEYASAAEgJpBPD_BwE"
    page.goto(url, timeout=90000, wait_until='domcontentloaded')
    time.sleep(5)
    
    info = page.evaluate('''() => {
        // Find all scrollable containers in Spotify
        let scrollables = [];
        document.querySelectorAll('*').forEach(el => {
            const cs = window.getComputedStyle(el);
            if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 50) {
                scrollables.push({
                    tag: el.tagName,
                    cls: el.className,
                    id: el.id,
                    dataTestId: el.getAttribute('data-testid') || '',
                    scrollHeight: el.scrollHeight,
                    clientHeight: el.clientHeight,
                    offsetHeight: el.offsetHeight,
                    overflowY: cs.overflowY,
                    htmlSnippet: (el.innerHTML || '').slice(0, 100)
                });
            }
        });
        
        return {
            title: document.title,
            bodyScrollH: document.body.scrollHeight,
            bodyH: document.body.clientHeight,
            docScrollH: document.documentElement.scrollHeight,
            scrollables
        };
    }''')
    import pprint
    print("Spotify DOM Info:", flush=True)
    pprint.pprint(info)
    page.screenshot(path="scratch/raw_spotify.jpg", full_page=True)
    print("Saved scratch/raw_spotify.jpg", flush=True)
finally:
    init.close_browser(page)
