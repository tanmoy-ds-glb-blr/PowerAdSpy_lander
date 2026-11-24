import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
from helper import init, screenshot
import time
import os
from PIL import Image

page, _ = init.init_dc('in')
url = "https://www.wordsmith.ai/?utm_source=google&utm_medium=cpc&utm_campaign=Youtube-usa&gad_source=2&gad_campaignid=23722270224&gclid=EAIaIQobChMI8ZKDjdCNlwMV8UkrAx11xBcFEAEYASAAEgJlFPD_BwE"
page.goto(url, timeout=90000, wait_until='domcontentloaded')

# Now run get() after updating screenshot.py with the fix
# First let's test if uc.remove() in evaluate works
page.evaluate('''() => {
    const uc = document.getElementById('usercentrics-cmp-ui');
    if (uc) uc.remove();
}''')
time.sleep(2)

path = "scratch/test_wordsmith_clean.jpg"
page.screenshot(path=path, full_page=True)
im = Image.open(path)
print(f"Captured: {path} | Size: {im.size} | bytes: {os.path.getsize(path)}")
init.close_browser(page)
