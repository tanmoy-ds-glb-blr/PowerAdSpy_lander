import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
from helper import init
import time
import os
from PIL import Image
import numpy as np

def trim_trailing_blank_void(im, min_void_px=300, padding_px=100):
    w, h = im.size
    if h <= min_void_px:
        return im
    rgb = np.array(im.convert("RGB"))
    bottom_row = rgb[-1, :, :]
    bg_color = np.median(bottom_row, axis=0)
    corners = np.array([rgb[-1, 0], rgb[-1, -1], rgb[-1, w // 2]])
    corner_std = np.std(corners, axis=0)
    if np.max(corner_std) > 15:
        return im
    diff = np.max(np.abs(rgb.astype(np.int16) - bg_color.astype(np.int16)), axis=2)
    row_empty = np.mean(diff <= 8, axis=1) >= 0.995
    non_empty_rows = np.where(~row_empty)[0]
    if len(non_empty_rows) == 0:
        return im
    last_content_y = non_empty_rows[-1]
    void_height = h - 1 - last_content_y
    if void_height >= min_void_px:
        new_h = min(h, last_content_y + padding_px)
        return im.crop((0, 0, w, new_h))
    return im

page, _ = init.init_dc('in')
url = "https://www.pinterest.com/pinterest/?utm_source=Paid_YouTube&utm_campaign=ConsumerBrand_US_Q22026Anthem60&utm_medium=PaidMedia&gad_source=2&gad_campaignid=23743086863&gclid=EAIaIQobChMIwe2yiK_XlAMVAwzbAR2IQBhnEAEYAiAAEgJkvvD_BwE"
page.goto(url, timeout=90000, wait_until='domcontentloaded')
time.sleep(5)

# Progressive scroll with stop if pos > maxContentBottom + 1200
scroll_height = page.evaluate("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)") or 2000
pos = 0
while pos < min(scroll_height, 12000):
    pos += 800
    page.evaluate(f"window.scrollTo(0, {pos});")
    time.sleep(2.0)
    
    # Check max content bottom
    status = page.evaluate('''() => {
        let maxB = 0;
        document.querySelectorAll('img, p, h1, h2, h3, a, [role="listitem"]').forEach(el => {
            let r = el.getBoundingClientRect();
            if (r.height > 20 && r.width > 20) {
                let b = r.bottom + window.scrollY;
                if (b > maxB) maxB = b;
            }
        });
        return {
            maxB,
            bodyH: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight),
            hasGuestWall: !!document.querySelector('.grecaptcha-badge, [id*="credential_picker"], [class*="unauth"]') || (document.body.innerText || '').includes('signed out')
        };
    }''')
    sh = status['bodyH']
    print(f"pos={pos}, maxB={status['maxB']}, bodyH={sh}")
    if status['hasGuestWall'] and pos > status['maxB'] + 1000:
        print(f"Reached guest wall end at pos={pos}, stopping scroll!")
        break
    scroll_height = sh

# Scroll back to 0
page.evaluate("window.scrollTo(0, 0);")
time.sleep(1.5)

# Step 1b: Purge One Tap + Badge, and Clamp Masonry
page.evaluate('''() => {
    document.querySelectorAll('#credential_picker_container, #credential_picker_iframe, iframe[src*="accounts.google.com/gsi"], iframe[id*="gsi_"], .grecaptcha-badge, [class*="grecaptcha-badge"]').forEach(el => el.remove());
    
    document.querySelectorAll('[class*="Masonry"], [class*="masonry"]').forEach(m => {
        let maxChildBottom = 0;
        Array.from(m.children).forEach(c => {
            let r = c.getBoundingClientRect();
            let b = r.bottom - m.getBoundingClientRect().top;
            if (b > maxChildBottom) maxChildBottom = b;
        });
        if (maxChildBottom > 200 && m.offsetHeight > maxChildBottom + 100) {
            m.style.setProperty('height', maxChildBottom + 'px', 'important');
        }
    });
}''')

raw_path = "scratch/pinterest_fixed_raw.jpg"
page.screenshot(path=raw_path, full_page=True)
im_raw = Image.open(raw_path)
print(f"Raw captured: {im_raw.size}")

im_trimmed = trim_trailing_blank_void(im_raw)
trimmed_path = "scratch/pinterest_fixed_trimmed.jpg"
im_trimmed.save(trimmed_path)
print(f"Trimmed: {im_trimmed.size}")

init.close_browser(page)
