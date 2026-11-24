import sys
sys.path.append('.')
import time
from helper import init

def inspect_page(iso='in'):
    print(f"\n--- Inspecting mybobs.com with ISO={iso} ---")
    page, _ = init.init_dc(iso)
    try:
        console_msgs = []
        page_errors = []
        page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        url = "https://www.mybobs.com/?utm_source=hxdv360-8924156&utm_medium=progolv&utm_campaign=ps-yt-sales-34684313&utm_content=253527062"
        resp = page.goto(url, timeout=90000, wait_until='domcontentloaded')
        print(f"Status code: {resp.status if resp else 'None'}, url: {page.url}")
        time.sleep(10)

        dom_info = page.evaluate('''() => {
            const main = document.querySelector('main, #main, [role="main"], .main-content');
            const bodyChildren = Array.from(document.body.children).map(c => ({
                tag: c.tagName,
                id: c.id,
                className: c.className,
                offsetHeight: c.offsetHeight,
                innerTextLen: (c.innerText || '').length,
                innerHTMLSnippet: (c.innerHTML || '').slice(0, 150)
            }));
            return {
                title: document.title,
                bodyHeight: document.body.scrollHeight,
                mainFound: !!main,
                mainHeight: main ? main.offsetHeight : 0,
                mainTextLen: main ? (main.innerText || '').length : 0,
                mainHTMLSnippet: main ? main.innerHTML.slice(0, 300) : '',
                bodyChildren
            };
        }''')
        print("DOM Info:")
        import pprint
        pprint.pprint(dom_info)
        print("\nPage errors:", len(page_errors), page_errors[:5])
        print("Console errors:", [m for m in console_msgs if 'error' in m.lower()][:5])
    finally:
        init.close_browser(page)

if __name__ == '__main__':
    inspect_page('in')
    inspect_page('us')
