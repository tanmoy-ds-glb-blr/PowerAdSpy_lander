import re
import tldextract
from bs4 import BeautifulSoup
from helper import redirect

def is_socialmedia(url):
    patterns = [
        r"http(s)?://(.*\.)?twitter\.com/[A-z0-9_]+/?",
        r"http(s)?://(www\.)?github\.com/[A-z0-9_-]+/?",
        r"http(s)?://([\w]+\.)?linkedin\.com/[A-z0-9_-]+/?",
        r"http(s)?://(www\.)?(facebook|fb)\.com/[A-z0-9_\-.]+/?",
        r"https?://(www\.)?instagram\.com/([A-Za-z0-9_]{1,30})",
        r"https?://(t(elegram)?\.me|telegram\.org)/([a-z0-9_]{5,32})/?",
    ]
    return 1 if any(re.search(p, url) for p in patterns) else 0

def get(page, url, r_session):
    """Extract up to 3 non-social external outgoing links with Playwright."""
    try:
        link_list = dict()
        outgoing_url = []
        base = tldextract.extract(url)
        
        # Extract all anchor hrefs directly from DOM
        try:
            hrefs = page.evaluate("""
                Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(h => h.startsWith('http://') || h.startsWith('https://'))
            """)
        except Exception:
            hrefs = []

        outgoing_count = 0
        for href in hrefs[:50]:
            if outgoing_count >= 3:
                break
            try:
                destn = tldextract.extract(href)
                if destn.domain and base.domain != destn.domain and destn.domain not in link_list and not is_socialmedia(href):
                    outgoing_count += 1
                    link_list[destn.domain] = ""
                    link_list[href] = ""
                    redirects = redirect.get(href, href, r_session, page)
                    outgoing_url.append({
                        "start_url": href,
                        "destination_url": href,
                        "redirect_urls": redirects
                    })
            except Exception:
                continue
                
        return outgoing_url
    except Exception as err:
        print(f"[Outgoing URL Error] {err}")
        return []


def get_from_html(html_source, url, r_session):
    """Extract outgoing links from an immutable HTML snapshot."""
    try:
        soup = BeautifulSoup(html_source or "", "html.parser")
        hrefs = [a.get("href") for a in soup.select("a[href]")]
        base = tldextract.extract(url)
        seen = set()
        result = []
        from urllib.parse import urljoin
        for raw in hrefs[:100]:
            href = urljoin(url, raw)
            dest = tldextract.extract(href)
            if not dest.domain or dest.domain == base.domain or dest.domain in seen or is_socialmedia(href):
                continue
            seen.add(dest.domain)
            result.append({"start_url": href, "destination_url": href, "redirect_urls": redirect.get(href, href, r_session)})
            if len(result) >= 3:
                break
        return result
    except Exception as err:
        print(f"[Outgoing URL Snapshot Error] {err}")
        return []
