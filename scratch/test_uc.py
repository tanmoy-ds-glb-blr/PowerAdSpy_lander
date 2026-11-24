import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
from helper import init
import time
import pprint

page, _ = init.init_dc('in')
url = 'https://www.wordsmith.ai/?utm_source=google&utm_medium=cpc&utm_campaign=Youtube-usa&gad_source=2&gad_campaignid=23722270224&gclid=EAIaIQobChMI8ZKDjdCNlwMV8UkrAx11xBcFEAEYASAAEgJlFPD_BwE'
page.goto(url, timeout=90000, wait_until='domcontentloaded')
time.sleep(5)

uc = page.evaluate('''() => {
    let ucHost = document.querySelector('#usercentrics-root, [id*="usercentrics"], [class*="usercentrics"]');
    let shadowBtns = [];
    if (ucHost && ucHost.shadowRoot) {
        ucHost.shadowRoot.querySelectorAll('button').forEach(b => {
            shadowBtns.push({
                testId: b.getAttribute('data-testid'),
                text: b.innerText
            });
        });
    }
    return {
        ucHost: ucHost ? { id: ucHost.id, tag: ucHost.tagName, hasShadow: !!ucHost.shadowRoot } : null,
        shadowBtns
    };
}''')
pprint.pprint(uc)
init.close_browser(page)
