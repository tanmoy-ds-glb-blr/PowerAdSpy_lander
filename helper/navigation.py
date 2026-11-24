import random
import time

from helper.pipeline import NavigationResult, safe_url


TRANSIENT_MARKERS = (
    "ERR_TUNNEL_CONNECTION_FAILED", "ERR_PROXY_CONNECTION_FAILED", "ERR_CONNECTION_RESET",
    "ERR_CONNECTION_CLOSED", "ERR_TIMED_OUT", "ERR_NAME_NOT_RESOLVED", "Timeout",
    "HTTP2_PROTOCOL_ERROR",
)


def navigate(
    page,
    url: str,
    timeout_ms: int = 90000,
    attempts: int = 2,
    logger=None,
    deadline=None,
    abort_check=None,
):
    started = time.monotonic()
    failures = []
    redirects = []
    popup_pages = []

    def on_popup(popup):
        popup_pages.append(popup)

    try:
        page.on("popup", on_popup)
    except Exception:
        pass

    def on_failed(request):
        try:
            failures.append({"url": safe_url(request.url), "error": str(request.failure or "")[:160]})
        except Exception:
            pass

    page.on("requestfailed", on_failed)
    result = NavigationResult(requested_url=safe_url(url))
    last_error = None
    for attempt in range(1, max(1, attempts) + 1):
        result.attempts = attempt
        try:
            if abort_check:
                abort_check()
            if deadline:
                deadline.check("navigation")
            attempt_timeout = min(timeout_ms, int(deadline.remaining() * 1000)) if deadline else timeout_ms
            response = page.goto(url.strip(), timeout=max(1000, attempt_timeout), wait_until="domcontentloaded")
            if abort_check:
                abort_check()
            result.final_url = page.url or url
            result.status = response.status if response else None
            if response:
                request = response.request
                chain = []
                while getattr(request, "redirected_from", None):
                    request = request.redirected_from
                    chain.append(safe_url(request.url))
                redirects = list(reversed(chain))
            break
        except Exception as exc:
            if abort_check:
                abort_check()
            last_error = exc
            message = str(exc)
            if attempt >= attempts or not any(marker.lower() in message.lower() for marker in TRANSIENT_MARKERS):
                result.error_code = "NAV_TIMEOUT" if "timeout" in message.lower() else "NAV_CONNECTION_ERROR"
                result.error = message[:300]
                break
            if logger:
                logger.warning("[NAV_RETRY] attempt=%s url=%s error=%s", attempt, safe_url(url), message[:120])
            delay = min(5.0, (2 ** (attempt - 1)) + random.uniform(0, 0.5))
            if deadline:
                delay = min(delay, deadline.remaining())
            if delay > 0:
                time.sleep(delay)
                if abort_check:
                    abort_check()
    result.redirects = redirects
    result.request_failures = failures[-50:]
    if popup_pages:
        time.sleep(min(0.5, deadline.remaining()) if deadline else 0.5)
    candidates = [page] + [p for p in popup_pages if not getattr(p, "is_closed", lambda: True)()]

    def score(candidate):
        try:
            if not (candidate.url or "").lower().startswith(("http://", "https://")):
                return -1
            state = candidate.evaluate("""() => ({
              text:(document.body?(document.body.innerText||'').trim().length:0),
              media:document.querySelectorAll('img,iframe,svg,canvas,video').length,
              area:document.body?document.body.getBoundingClientRect().width*document.body.getBoundingClientRect().height:0
            })""")
            return int(state.get("text") or 0) + int(state.get("media") or 0) * 100 + min(1000, int(state.get("area") or 0) // 1000)
        except Exception:
            return -1

    selected = max(candidates, key=score) if candidates else page
    result.popup_urls = [safe_url(p.url or "") for p in popup_pages]
    result.selected_popup = selected is not page
    result.selected_page = selected
    if result.selected_popup:
        result.final_url = selected.url or result.final_url
    result.elapsed_ms = int((time.monotonic() - started) * 1000)
    if not result.final_url and last_error is None:
        result.error_code = "NAV_NO_RESPONSE"
    return result
