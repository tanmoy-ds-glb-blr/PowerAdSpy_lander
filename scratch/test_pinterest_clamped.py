import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
from helper import init
import time
import os
from PIL import Image

page, _ = init.init_dc('in')
url = 'https://www.pinterest.com/pinterest/?utm_source=Paid_YouTube&utm_campaign=ConsumerBrand_US_Q22026Anthem60&utm_medium=PaidMedia&gad_source=2&gad_campaignid=23743086863&gclid=EAIaIQobChMIwe2yiK_XlAMVAwzbAR2IQBhnEAEYAiAAEgJkvvD_BwE'
page.goto(url, timeout=90000, wait_until='domcontentloaded')
time.sleep(5)

# Scroll down
for pos in range(0, 4000, 800):
    page.evaluate(f'window.scrollTo(0, {pos});')
    time.sleep(0.5)

# Scroll back to 0
page.evaluate('window.scrollTo(0, 0);')
time.sleep(1.5)

# Purge Google One Tap & recaptcha badge
page.evaluate('''() => {
    document.querySelectorAll('#credential_picker_container, #credential_picker_iframe, iframe[src*="accounts.google.com/gsi"], iframe[id*="gsi_"], .grecaptcha-badge, [class*="grecaptcha-badge"]').forEach(el => el.remove());
    
    // Clamp Masonry container
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

path = "scratch/test_pinterest_clamped.jpg"
page.screenshot(path=path, full_page=True)
im = Image.open(path)
print(f"Captured clamped: {path} | Size: {im.size} | File bytes: {os.path.getsize(path)}")
init.close_browser(page)
