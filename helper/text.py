from bs4 import BeautifulSoup
from bs4.element import Comment

def get(page):
    try:
        html_src = ""
        try:
            if hasattr(page, 'content'):
                html_src = page.content()
            elif hasattr(page, 'page_source'):
                html_src = page.page_source
        except Exception:
            html_src = ""

        if not html_src:
            return ""

        soup = BeautifulSoup(html_src, 'html.parser')
        
        def tag_visible(element):
            if element.parent.name in ['style', 'script', 'head', 'title', 'meta', '[document]']:
                return False
            if isinstance(element, Comment):
                return False
            return True
            
        texts = soup.find_all(string=True)
        visible_texts = filter(tag_visible, texts)
        text_in_page = " ".join(t.strip() for t in visible_texts)

        # Include visible text from child frames (e.g. WAF block pages or error iframes)
        try:
            if hasattr(page, 'frames'):
                for frame in page.frames:
                    if frame != getattr(page, 'main_frame', None):
                        try:
                            f_text = frame.inner_text('body', timeout=1000).strip()
                            if f_text:
                                text_in_page += " " + f_text
                        except Exception:
                            pass
        except Exception:
            pass

        return " ".join(text_in_page.split())

    except Exception as err:
        print(f"[Text Extraction Warning] {err}")
        return ""
