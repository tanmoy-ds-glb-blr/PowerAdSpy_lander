import tldextract
from urllib.request import urlparse

def is_validurl(url):
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)

def get(url1, url2, r_session, page=None):
    """Returns redirect URLs between starting URL and destination URL."""
    unique_redirects = dict()
    destination = tldextract.extract(url2)
    
    # Check via requests session history
    try:
        if r_session is not None:
            res = r_session.get(url1, timeout=30)
            if len(res.history) > 0:
                for x in res.history:
                    redirect = tldextract.extract(x.url)
                    if is_validurl(x.url) and redirect.domain not in destination.domain and not (any([x1 for x1 in list(unique_redirects.keys()) if tldextract.extract(x.url).domain in tldextract.extract(x1).domain])):
                        unique_redirects[x.url] = ""
    except Exception:
        pass

    return list(unique_redirects.keys())
