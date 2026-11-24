import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
import os
from PIL import Image
from helper import init, screenshot

ads = [
    {
        "id": 281944,
        "name": "pinterest",
        "url": "https://www.pinterest.com/pinterest/?utm_source=Paid_YouTube&utm_campaign=ConsumerBrand_US_Q22026Anthem60&utm_medium=PaidMedia&gad_source=2&gad_campaignid=23743086863&gclid=EAIaIQobChMIwe2yiK_XlAMVAwzbAR2IQBhnEAEYAiAAEgJkvvD_BwE"
    },
    {
        "id": 281981,
        "name": "spotify",
        "url": "https://open.spotify.com/track/5McmtLnuuUvBvESzMFQ4Yo?utm_source=dv360-united-states-awareness-na-na&utm_medium=olv&utm_campaign=ca7rielandpaco-music-yt-ca7rielandpaco-fans-ca7riel-yt-muero-15s-local-united-states-awareness-nam-cultural-2026q2&utm_content=artistmuero-no&gad_source=2&gad_campaignid=23857090794&gclid=EAIaIQobChMIq7qdvLDXlAMVQDyKAx3SaQDeEAEYASAAEgJpBPD_BwE"
    },
    {
        "id": 43138,
        "name": "wordsmith",
        "url": "https://www.wordsmith.ai/?utm_source=google&utm_medium=cpc&utm_campaign=Youtube-usa&gad_source=2&gad_campaignid=23722270224&gclid=EAIaIQobChMI8ZKDjdCNlwMV8UkrAx11xBcFEAEYASAAEgJlFPD_BwE"
    }
]

for ad in ads:
    ad_id = ad["id"]
    name = ad["name"]
    url = ad["url"]
    print(f"\n========================================================")
    print(f"DIAGNOSING AD {ad_id}: {name}")
    print(f"URL: {url}")
    print(f"========================================================")
    
    page, _ = init.init_dc('in')
    try:
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        
        # Capture using helper.screenshot
        img_path = screenshot.get(page, f"diag_{ad_id}", "scratch")
        if os.path.isfile(img_path):
            img = Image.open(img_path)
            print(f"-> SUCCESS: {img_path} | Size: {os.path.getsize(img_path):,} bytes | Dim: {img.size}")
        else:
            print(f"-> FAILED: {img_path} not found")
    except Exception as e:
        print(f"-> EXCEPTION on ad {ad_id}: {e}")
    finally:
        init.close_browser(page)
