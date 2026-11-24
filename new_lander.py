import sys

# Ensure UTF-8 output across Windows & Linux consoles to prevent cp1252 charmap encode errors
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    
import random
import multiprocessing
import time
import json
import logging
import requests
import re
import urllib.parse
import tempfile
import os
import shutil
import subprocess
import uuid
import threading

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from PIL import Image  # Load Pillow first for Python 3.10 compatibility
from helper import init, domaindate, outgoing_url, redirect, text, html, scrape_ad_category
from helper import capture, navigation, readiness, page_snapshot, proxy_health
from helper import api_client, daily_logging
from helper.pipeline import ScrapeDeadline
from prometheus_client import start_http_server, multiprocess, REGISTRY, generate_latest, Counter
from config import Config
import traceback

# Load YAML config
config = Config()


def _proxy_check_interval_seconds():
    return proxy_health.clamp_interval(
        config.get_default("PROXY_HEALTH_CHECK_INTERVAL_SECONDS") or 5
    )


def _proxy_check_timeout_seconds():
    return proxy_health.clamp_timeout(
        config.get_default("PROXY_HEALTH_CHECK_TIMEOUT_SECONDS") or 5
    )


def _proxy_stale_seconds():
    configured = config.get_default("PROXY_HEALTH_STALE_SECONDS")
    if configured is not None:
        try:
            return max(1.0, float(configured))
        except (TypeError, ValueError):
            pass
    return _proxy_check_interval_seconds() + _proxy_check_timeout_seconds() + 5.0


def _probe_bright_proxy(
    country_iso=None,
    proxy_state=None,
    stage="proxy_health_check",
    publish_result=True,
    cache_seconds=0.0,
):
    """Run one strict provider probe and publish its result for all workers."""
    if not config.bright_proxies:
        return {}
    country_iso = str(
        country_iso or config.get_default("PROXY_HEALTH_COUNTRY") or "us"
    ).strip().lower()

    def run_probe():
        return init.verify_proxy_egress(
            iso=country_iso,
            required=True,
            timeout_seconds=_proxy_check_timeout_seconds(),
        )

    try:
        egress = proxy_health.run_singleflight_probe(
            proxy_state,
            country_iso,
            run_probe,
            cache_seconds=cache_seconds,
        )
    except proxy_health.ProxyUnavailableError as exc:
        observed_at = getattr(exc, "observed_at", time.time())
        if publish_result:
            proxy_health.mark_unavailable(
                proxy_state,
                exc.reason,
                checked_at=observed_at,
                country_iso=country_iso,
            )
        raise proxy_health.ProxyUnavailableError(
            exc.reason,
            stage=stage,
            observed_at=observed_at,
            country_iso=country_iso,
        ) from exc
    # Worker success never overrides a global DOWN snapshot. Recovery is
    # published by the parent monitor, which is the single authority for UP.
    return egress


def _monitor_bright_proxy(country_iso, timeout_seconds):
    """Run the parent's health check without any worker single-flight lock."""
    return init.verify_proxy_egress(
        iso=country_iso,
        required=True,
        timeout_seconds=timeout_seconds,
    )


def _ensure_proxy_available(
    proxy_state,
    stage,
    country_iso=None,
    force_probe=False,
    outage_since=None,
):
    """Fail closed if the monitor is down/stale, or perform an immediate probe."""
    if not config.bright_proxies:
        return {}
    if force_probe or proxy_state is None:
        # A forced safety-boundary check must never reuse a completed cached
        # success. Concurrent callers that were already waiting on the same
        # in-flight check may still share that one result.
        result = _probe_bright_proxy(
            country_iso,
            proxy_state=proxy_state,
            stage=stage,
            cache_seconds=0.0,
        )
        if proxy_state is not None:
            proxy_health.require_available(
                proxy_state,
                stage=stage,
                stale_after_seconds=_proxy_stale_seconds(),
            )
    else:
        result = proxy_health.require_available(
            proxy_state,
            stage=stage,
            stale_after_seconds=_proxy_stale_seconds(),
        )
    # Even if the provider already recovered, an outage that overlapped this
    # scrape can leave a partially rendered page. Never upload that result.
    if proxy_state is not None and outage_since is not None:
        snapshot = proxy_health.get_snapshot(proxy_state)
        if float(snapshot.get("last_down_at") or 0.0) >= float(outage_since):
            raise proxy_health.ProxyUnavailableError(
                "Bright Data went down during the active scrape; retrying the ad after recovery",
                stage=stage,
                currently_unavailable=not bool(snapshot.get("available")),
            )
    return result


def _wait_for_bright_proxy(proxy_state, instance_no, lander_logger=None):
    """Block a worker before queue acquisition until Bright Data recovers."""
    if not config.bright_proxies:
        return True

    def report_wait(snapshot):
        reason = snapshot.get("reason") or "health check pending"
        message = f"[PROXY PAUSED] Worker {instance_no} waiting for Bright Data: {reason}"
        print(message)
        if lander_logger:
            lander_logger.warning(message)

    if proxy_state is not None:
        return proxy_health.wait_for_available(
            proxy_state,
            stale_after_seconds=_proxy_stale_seconds(),
            poll_seconds=min(1.0, _proxy_check_interval_seconds()),
            on_wait=report_wait,
        )

    # Compatibility fallback for callers that invoke a worker directly rather
    # than through multi_chrome(). Production workers use the shared monitor.
    while True:
        try:
            _probe_bright_proxy(stage="worker_queue_gate")
            return True
        except proxy_health.ProxyUnavailableError as exc:
            report_wait({"reason": exc.reason})
            time.sleep(_proxy_check_interval_seconds())

# Ensure all essential runtime directories exist
for _dir in ["logs", "er_logs", "images", "zip", "getApi_data", "getApi_data_dev"]:
    os.makedirs(_dir, exist_ok=True)

_tempdir = os.environ.get('prometheus_multiproc_dir')
if not _tempdir or not os.path.isdir(_tempdir):
    _tempdir = os.path.join(tempfile.gettempdir(), "prometheus_multiproc")
    os.makedirs(_tempdir, exist_ok=True)
    os.environ['prometheus_multiproc_dir'] = _tempdir
error_count = 0
# ssss
# ── Bot / WAF markers ────────────────────────────────────────────────────────
# These signatures live in raw HTML attributes, iframe src, script IDs, or
# network-level headers — NOT in the visible rendered text.  We still check
# them against the full page source so we don't miss them.
BOT_OR_WAF_MARKERS = (
    "challenges.cloudflare.com",
    "cf-browser-verification",
    "cf-challenge",
    "errors.edgesuite.net",
    "attention required! | cloudflare",
    "just a moment...",
    "checking your browser before accessing",
    "verify you are human",
    "bot detection",
    "security check to continue",
    "this request has been blocked",
    "_incapsula_resource",
    "incapsula incident id",
    "incapsula",
    "imperva",
    "request unsuccessful. incapsula",
    "blocked by our security service",
    "sorry, your access to this site is not possible",
    "perimeterx",
    "datadome",
    "kasada",
)

# ── Dead / error page markers ─────────────────────────────────────────────────
# These are phrases that appear as VISIBLE text on 404 / dead / parked pages.
# They must ONLY be checked against page.inner_text('body') — i.e., the text
# a human actually sees — so that JavaScript translation bundles embedded in
# <script> tags on healthy e-commerce sites (e.g. Puma) never trigger a false
# positive skip.
DEAD_PAGE_TEXT_MARKERS = (
    # Generic error / not-found
    "404 not found",
    "404 page not found",
    "error 404",
    "http error 404",
    "the requested url was not found",
    "page does not exist",
    "this page cannot be found",
    "this page could not be found",
    "oops! that page can't be found",
    "oops! page not found",
    "page no longer available",
    "we couldn't find that page",
    "nothing found",
    # Access denied
    "access denied",
    "you don't have permission to access",
    "request blocked",
    "403 forbidden",
    "http 403",
    # Server errors
    "500 internal server error",
    "502 bad gateway",
    "503 service temporarily unavailable",
    "503 service unavailable",
    "504 gateway time-out",
    "504 gateway timeout",
    # Chrome / network errors (shown as visible text on chrome error pages)
    "dns_probe_finished_nxdomain",
    "err_name_not_resolved",
    "err_connection_refused",
    "err_connection_timed_out",
    "err_connection_reset",
    "err_too_many_redirects",
    "err_empty_response",
    "err_http2_protocol_error",
    "this site can't be reached",
    "server ip address could not be found",
    "check your internet connection",
    # Parked / expired domains
    "this domain is for sale",
    "buy this domain",
    "domain has expired",
    "parked free, courtesy of",
    "domain parked by",
    "this account has been suspended",
    "account has been suspended",
)

# Kept for any legacy references elsewhere in the codebase
BLOCKED_PAGE_MARKERS = BOT_OR_WAF_MARKERS + DEAD_PAGE_TEXT_MARKERS

BLOCKED_TITLE_MARKERS = (
    "404", "not found", "page not found", "site not found",
    "403 forbidden", "access denied", "request blocked",
    "500 internal server", "502 bad gateway", "503 service unavailable",
    "504 gateway time", "attention required", "just a moment",
    "suspended domain", "account suspended", "domain parked",
    "this site can't be reached", "this site can't be reached", "server error"
)

# ── Dynamic Status 3 Keywords File Loader ─────────────────────────────────────
# Reads status_3_keywords.txt from the same directory as new_lander.py.
# Auto-reloads whenever the file is modified on disk so new text phrases
# take effect immediately without restarting workers.
STATUS3_KEYWORDS_FILES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "status_3_keywords.txt"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "status3_keywords.txt"),
]
_cached_status3_keywords = []
_last_status3_mtime = 0

def get_status3_keywords():
    """
    Returns a list of lowercase dead-page / error keywords from status_3_keywords.txt.
    Checks file modification time and auto-refreshes if the file has changed.
    """
    global _cached_status3_keywords, _last_status3_mtime
    try:
        target_file = None
        for candidate in STATUS3_KEYWORDS_FILES:
            if os.path.isfile(candidate):
                target_file = candidate
                break

        if not target_file:
            return _cached_status3_keywords

        current_mtime = os.path.getmtime(target_file)
        if current_mtime != _last_status3_mtime:
            with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                loaded = [
                    line.strip().lower() for line in f
                    if line.strip() and not line.strip().startswith("#")
                ]
            _cached_status3_keywords = loaded
            _last_status3_mtime = current_mtime
    except Exception:
        pass
    return _cached_status3_keywords

SUPPORTED_COUNTRIES = {
    'ae', 'at', 'au', 'be', 'br', 'ca', 'ch', 'cn',
    'de', 'dk', 'es', 'fi', 'fr', 'gb', 'hu', 'id',
    'ie', 'il', 'in', 'it', 'jp', 'kz', 'ma', 'mx',
    'my', 'nl', 'no', 'nz', 'ph', 'pl', 'pt', 'ru',
    'se', 'sg', 'th', 'tr', 'us', 'za',
}
REQUEST_TIMEOUT = (15, 180)


def _request_timeout(deadline=None):
    if deadline is None:
        return REQUEST_TIMEOUT
    deadline.check("external_request")
    remaining = max(1.0, deadline.remaining())
    return (min(10.0, remaining), remaining)


def get_country(single_data):
    raw_iso = single_data.get("iso") or []
    if isinstance(raw_iso, str):
        raw_iso = [raw_iso]

    for value in raw_iso:
        country = str(value).strip().lower()
        if country in SUPPORTED_COUNTRIES:
            return country
    return "us"


def check_page_status(page):
    """
    Evaluates whether the loaded page is an error, 404, blocked, or dead page.
    Returns (is_bad: bool, reason: str).

    Detection order:
      1. Browser internal error URL  (chrome-error://, about:blank, etc.)
      2. HTTP response status >= 400 via Navigation Timing API
      3. Page <title> matches known error titles
      4. Raw page source matches Bot/WAF signatures (BOT_OR_WAF_MARKERS)
         — these patterns live in script IDs, iframe src, etc., NOT visible text
      5. Visible rendered body text matches dead-page phrases (DEAD_PAGE_TEXT_MARKERS)
         — ONLY visible text so JS translation bundles don't cause false positives
    """
    try:
        current_url = (page.url or "").lower().strip()

        # 1. Browser internal error URLs
        if current_url.startswith(("chrome-error://", "about:blank", "data:text/html,chromewebdata")):
            return True, f"Browser error URL: {current_url[:60]}"

        # 2. Check HTTP status code via Navigation Timing API
        try:
            status = page.evaluate(
                "(() => (window.performance.getEntriesByType('navigation')[0] || {}).responseStatus)()"
            )
            if status and int(status) >= 400:
                return True, f"HTTP Error Status {status}"
        except Exception:
            pass

        # 3. Check Page Title
        title = (page.title() or "").lower().strip()
        for marker in BLOCKED_TITLE_MARKERS:
            if marker in title:
                return True, f"Title indicates error: '{marker}'"

        # 4. Check raw source for Bot/WAF challenge signatures
        # (these are embedded in script IDs, iframe src attributes, hidden divs — not visible text)
        try:
            page_source = (page.content() or "").lower()
            for marker in BOT_OR_WAF_MARKERS:
                if marker in page_source:
                    return True, f"Bot/WAF block detected: '{marker}'"
        except Exception:
            pass

        # 5. Check VISIBLE rendered body text for dead-page phrases
        # Using inner_text() so <script> bundles, JSON dicts, and <style> blocks
        # are ignored — only what a human actually reads on screen is checked.
        # This prevents healthy sites (e.g. Puma, Nykaa) from being falsely
        # skipped because their JS bundle contains a localised 'page not found' string.
        try:
            body_text = page.inner_text("body", timeout=5000).strip().lower()
            
            # Also extract visible text from child frames (e.g. Incapsula, Cloudflare, or WAF block iframes)
            combined_text = body_text
            try:
                if hasattr(page, 'frames'):
                    for frame in page.frames:
                        if frame != getattr(page, 'main_frame', None):
                            try:
                                f_text = frame.inner_text("body", timeout=1000).strip().lower()
                                if f_text:
                                    combined_text += " " + f_text
                            except Exception:
                                pass
            except Exception:
                pass

            for marker in DEAD_PAGE_TEXT_MARKERS:
                if marker in combined_text:
                    return True, f"Page content matched: '{marker}'"

            # Check dynamic status 3 keywords from status_3_keywords.txt
            page_src_lower = ""
            try:
                page_src_lower = (page.content() or "").lower()
            except Exception:
                pass

            for marker in get_status3_keywords():
                if marker and (marker in combined_text or marker in title or (page_src_lower and marker in page_src_lower)):
                    return True, f"Status 3 keyword matched: '{marker}'"

            # Sparse body safety-net: very short body with obvious error keywords
            if len(body_text) < 30 and any(err in body_text for err in ("404", "error", "not found", "forbidden")):
                return True, f"Sparse error body: '{body_text[:60]}'"

            # 6. Completely empty / zero-content page check (HTTP 200 but blank white/empty screen)
            # If a human cannot see anything on the page (zero visible text and zero visual media)
            try:
                def _is_empty_dom():
                    return page.evaluate("""() => {
                        let text = (document.body ? (document.body.innerText || document.body.textContent) : '')
                            .replace(/[\s\u200b\u200c\u200d\ufeff]+/g, '').trim();
                        let mediaCount = document.querySelectorAll('img, iframe, svg, canvas, video, picture, embed, object').length;
                        return text.length === 0 && mediaCount === 0;
                    }""")

                if _is_empty_dom():
                    # Give client-side JS / SPAs (React, Vue, Next.js) 2.5 seconds to mount before confirming
                    page.wait_for_timeout(2500)
                    if _is_empty_dom():
                        return True, "Empty page with zero rendered content (0 visible text and 0 media elements)"
            except Exception:
                pass
        except Exception:
            pass

        return False, "OK"
    except Exception as e:
        return True, f"Exception while inspecting page: {e}"


def is_blocked_page(page):
    is_bad, _ = check_page_status(page)
    return is_bad


# ── Login & Sign-up / Auth Page Detection ─────────────────────────────────────
# Distinguishes TRUE login barriers (status 3) from normal content pages (status 2).
# Pages with actual content (e-commerce catalogs, articles, lead gen) remain status 2.
LOGIN_URL_PATH_REGEX = re.compile(
    r'(^|/)(log-?in|sign-?in|sign-?up|register|registration|customer/account/login|customer/account/create|accounts?/login|users?/login|member-login|portal/login|session/new|checkpoint)(\b|/|\.php|\.html|\.asp|\?|$)',
    re.IGNORECASE
)

LOGIN_AUTH_HOSTS = (
    "accounts.google.com",
    "appleid.apple.com",
    "auth0.com",
    "okta.com",
    "clerk.dev",
)

LOGIN_TITLE_PATTERNS = [
    r'^\s*(log\s?in|sign\s?in|sign\s?up|create\s+(an?\s+)?account|register|registration|member\s+login|customer\s+login|client\s+login|user\s+login)\b',
    r'\b(log\s?into?\s+facebook|login\s*[•·-]\s*instagram|sign\s?in\s*[–—-]\s*google\s*accounts|welcome\s+back\s*[–—-]\s*log\s*in)\b',
    r'[\-\|\:\–\—]\s*(log\s?in|sign\s?in|sign\s?up|create\s+(an?\s+)?account|register)\s*$',
]

LOGIN_TEXT_MARKERS = (
    "please log in to view this page",
    "please sign in to view this page",
    "you must be logged in to view this page",
    "you must be logged in to continue",
    "log in to view this content",
    "sign in to view this content",
    "please log in to access this content",
    "this content is private. please log in",
    "please sign in to access this content",
    "enter your email and password to log in",
    "enter your email and password to sign in",
    "enter your username and password to log in",
)

def is_login_or_signup_page(page, destination_url="", final_url="", ret_text=""):
    """
    Evaluates whether the loaded page is a dedicated login/auth gate (status 3)
    versus a normal page with actual content/products (status 2).
    Returns (is_login: bool, reason: str).
    """
    try:
        if not final_url and page:
            try:
                final_url = page.url or ""
            except Exception:
                final_url = ""

        f_url_lower = (final_url or "").lower().strip()
        dest_url_lower = (destination_url or "").lower().strip()

        # 1. Dedicated Third-Party SSO / Platform Social Login Checkpoints
        if f_url_lower:
            parsed = urllib.parse.urlparse(f_url_lower)
            netloc = parsed.netloc
            path = parsed.path.rstrip("/")
            query = parsed.query

            # Third-party SSO providers (always true auth gate)
            for host in LOGIN_AUTH_HOSTS:
                if host in netloc:
                    return True, f"Redirected to auth provider: {netloc}"

            # Platform social login checkpoints (always true auth gate)
            if "facebook.com" in netloc and ("/login" in path or "/checkpoint" in path):
                return True, f"Facebook login checkpoint: {path}"
            if "instagram.com" in netloc and "/accounts/login" in path:
                return True, f"Instagram login checkpoint: {path}"
            if ("twitter.com" in netloc or "x.com" in netloc) and ("/login" in path or "/i/flow/login" in path):
                return True, f"X/Twitter login checkpoint: {path}"
            if "linkedin.com" in netloc and ("/login" in path or "/checkpoint" in path):
                return True, f"LinkedIn login checkpoint: {path}"

            # Auth redirect query parameter (e.g. redirect_to=...) on dedicated auth paths
            if any(p in query for p in ("redirect_to=", "return_url=", "next=", "continue=", "returnurl=")) and any(k in path for k in ("/login", "/signin", "/auth")):
                return True, f"Auth redirect query parameter: {path}?{query[:50]}"

            # Explicit login URL path pattern when not a marketing content path
            if LOGIN_URL_PATH_REGEX.search(path):
                # Verify it's not a rich content / article / blog / product path
                if not any(k in path for k in ("product", "collection", "shop", "item", "article", "blog", "event", "webinar", "course")):
                    return True, f"Login/Signup URL path detected: {path}"

        # 2. Check word count to distinguish sparse auth barriers from rich content pages
        ret_text_lower = (ret_text or "").lower()
        word_count = len(ret_text_lower.split()) if ret_text_lower else 9999

        # 3. Page Title Check (only on focused pages under 300 words)
        title = ""
        if page:
            try:
                title = (page.title() or "").lower().strip()
            except Exception:
                title = ""

        if title and word_count < 300:
            for pat in LOGIN_TITLE_PATTERNS:
                if re.search(pat, title, re.IGNORECASE):
                    return True, f"Login/Signup title detected on focused page: '{title}'"

        # 4. DOM Structural Check (Visible Password Inputs, Auth Forms on sparse pages)
        # Normal e-commerce stores often have slide-out customer login drawers; only flag
        # if the page is genuinely a login gate with sparse content (< 200 words).
        if page and word_count < 200:
            try:
                dom_auth = page.evaluate("""() => {
                    const pwInputs = Array.from(document.querySelectorAll('input[type="password"]')).filter(el => {
                        const style = window.getComputedStyle(el);
                        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
                    });
                    const hasPassword = pwInputs.length > 0;

                    const authForms = Array.from(document.querySelectorAll('form')).filter(f => {
                        const attrStr = ((f.id || '') + ' ' + (f.className || '') + ' ' + (f.getAttribute('action') || '') + ' ' + (f.getAttribute('name') || '')).toLowerCase();
                        return /login|signin|sign-up|signup|register|auth|password/.test(attrStr);
                    });
                    const hasAuthForm = authForms.length > 0;

                    const headings = Array.from(document.querySelectorAll('h1, h2, h3')).map(h => (h.innerText || '').toLowerCase().trim());
                    const hasAuthHeading = headings.some(h => 
                        /^(log\\s?in|sign\\s?in|sign\\s?up|create\\s+(an?\\s+)?account|register|registration|welcome\\s+back|access\\s+your\\s+account)$/i.test(h)
                    );

                    const buttons = Array.from(document.querySelectorAll('button[type="submit"], input[type="submit"], form button, .btn-login, .btn-signin')).map(b => (b.innerText || b.value || '').toLowerCase().trim());
                    const hasAuthButton = buttons.some(b => 
                        /^(log\\s?in|sign\\s?in|sign\\s?up|create\\s+account|create\\s+my\\s+account|register)$/i.test(b)
                    );

                    return { hasPassword, hasAuthForm, hasAuthHeading, hasAuthButton };
                }""")
                if dom_auth:
                    has_pw = dom_auth.get("hasPassword", False)
                    has_form = dom_auth.get("hasAuthForm", False)
                    has_heading = dom_auth.get("hasAuthHeading", False)
                    has_btn = dom_auth.get("hasAuthButton", False)

                    if has_pw and (has_form or has_heading or has_btn):
                        return True, f"Gated login page (visible password field on sparse page with {word_count} words)"
                    if has_heading and has_btn:
                        return True, f"Dedicated login/signup view (auth heading and submit button on sparse page with {word_count} words)"
            except Exception:
                pass

        # 5. Explicit Gated Text Content Check
        if ret_text_lower:
            for marker in LOGIN_TEXT_MARKERS:
                if marker in ret_text_lower:
                    return True, f"Login text marker matched: '{marker}'"

        return False, None
    except Exception:
        return False, None


class BlockedPageException(Exception):
    pass


class Metrics(object):
    def __init__(self, idx):
        self._tempdir = _tempdir
        self._registry = REGISTRY
        try:
            self._multiprocess_registry = multiprocess.MultiProcessCollector(self._registry, self._tempdir)
        except Exception:
            pass
        net = config.network_name
        self.processed_configured_lander_url = Counter(f'processed_{net}_lander_url_count', f'Number of {net} urls processed',
                                                        ['port', 'status', 'error'], registry=None)
        self.updated_configured_lander = Counter(f'updated_{net}_lander_count', f'Updated {net} Landers based on API response',
                                                  ['port', 'message'], registry=None)
        self.configured_lander_get = Counter(f'{net}_lander_get_count', 'get api not giving data', ['data'], registry=None)

        # Common aliases
        self.processed_lander_url = self.processed_configured_lander_url
        self.updated_lander = self.updated_configured_lander
        self.lander_get = self.configured_lander_get

    def shutdown(self):
        try:
            shutil.rmtree(self._tempdir, ignore_errors=True)
        except Exception:
            pass

    def collect(self):
        return generate_latest(self._registry).decode()

def resolve_ad_redirect(url, timeout=10):
    """
    Pre-resolves ad redirect wrappers (like google.com/goto?url=... or googleadservices.com)
    using direct unproxied HTTP requests before launching Playwright.
    This prevents proxy SERP tunnel blocks (Bright Data 403 Forbidden serp domain / ERR_TUNNEL_CONNECTION_FAILED).
    """
    if not url:
        return url, []

    redirects = []
    curr = url
    if any(marker in curr.lower() for marker in ("google.com/goto", "google.co.in/goto", "googleadservices.com", "googlesyndication.com")):
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36"
                )
            }
            for _ in range(5):
                r = requests.get(curr, headers=headers, timeout=timeout, allow_redirects=False)
                if r.status_code in (301, 302, 303, 307, 308) and "Location" in r.headers:
                    target = r.headers["Location"].strip()
                    if not target.startswith("http"):
                        from urllib.parse import urljoin
                        target = urljoin(curr, target)
                    redirects.append(curr)
                    curr = target
                    if not any(marker in curr.lower() for marker in ("google.com/goto", "google.co.in/goto", "googleadservices.com")):
                        break
                else:
                    break
        except Exception:
            pass

    return curr, redirects


def scraping(single_data, metric, lander_logger, port, instance_no, count, error_logger, proxy_state=None):
    global error_count
    page = None
    r_session = None
    scrape_run_id = None
    scrape_started_at = time.time()
    ad_id = single_data.get("id", 0) if isinstance(single_data, dict) else 0

    if isinstance(single_data, dict):
        single_data.pop("_proxy_unavailable", None)
        single_data.pop("_proxy_unavailable_reason", None)

    def _abort_for_proxy_outage(error):
        reason = getattr(error, "reason", str(error))
        if isinstance(single_data, dict):
            single_data["_proxy_unavailable"] = True
            single_data["_proxy_unavailable_reason"] = reason
            single_data.pop("_terminal_reported", None)
        if getattr(error, "currently_unavailable", True):
            proxy_health.mark_unavailable(
                proxy_state,
                reason,
                checked_at=getattr(error, "observed_at", None),
                country_iso=getattr(error, "country_iso", None),
            )
        message = (
            f"[PROXY OUTAGE] Worker {instance_no} paused ad_id={ad_id}; "
            f"no final payload sent: {reason}"
        )
        print(message)
        lander_logger.warning(message)
        if scrape_run_id:
            # This is infrastructure interruption, not a terminal scrape. The
            # ad will be fully re-scraped after recovery, so discard partial
            # worker artifacts instead of retaining them as failed evidence.
            _finalize_artifacts(instance_no, ad_id, scrape_run_id, True, lander_logger)
        init.close_browser(page)
        return False

    try:
        scrape_run_id = single_data.setdefault("_scrape_run_id", uuid.uuid4().hex)
        deadline = ScrapeDeadline(float(config.get_default("OVERALL_SCRAPE_TIMEOUT_SECONDS") or 240))
        def _report_status3(ad_id_value, country_value, destination_value, reason_value):
            # A target failure may be reported only while Bright Data is
            # independently confirmed healthy. This distinguishes a dead
            # destination from a provider outage.
            _ensure_proxy_available(
                proxy_state,
                stage="before_status3_payload",
                country_iso=country_value,
                force_probe=True,
                outage_since=scrape_started_at,
            )
            confirmed = send_status3_payload(
                ad_id_value, country_value, destination_value, reason_value,
                lander_logger, scrape_run_id, deadline=deadline,
                pre_send_guard=lambda: _ensure_proxy_available(
                    proxy_state,
                    stage="status3_insert_dispatch",
                    country_iso=country_value,
                    outage_since=scrape_started_at,
                ),
            )
            if confirmed:
                single_data["_terminal_reported"] = True
            return confirmed
        country = get_country(single_data)
        countries = [country]
        ad_id = single_data.get('id', 0)
        destination_url = str(single_data.get('destination_url') or "").replace("\\", "").strip()
        initial_egress = _ensure_proxy_available(
            proxy_state,
            stage="scrape_start",
            country_iso=countries[0],
            force_probe=True,
            outage_since=scrape_started_at,
        )
        if not destination_url:
            lander_logger.warning(f"[SKIPPED] ad_id={ad_id} has empty destination_url")
            metric.processed_configured_lander_url.labels(port=port, status="skipped", error="Empty destination_url").inc()
            log_unsuccessful_ad(single_data, "Empty destination_url")
            _report_status3(ad_id, countries[0], destination_url, "Empty destination_url")
            return False

        payload_list = []
        init_result = init.init_dc(
            countries[0],
            verify_egress=not config.bright_proxies,
        )
        if init_result is None:
            print(f"[Chrome Init] Retry after 5 seconds for country={countries[0]}")
            time.sleep(5)
            init_result = init.init_dc(
                countries[0],
                verify_egress=not config.bright_proxies,
            )
        if init_result is None:
            log_unsuccessful_ad(single_data, "Chrome initialization failed")
            raise RuntimeError(f"Chrome initialization failed for country={countries[0]}")
        page, r_session = init_result
        deadline.check("browser_initialized")
        egress_info = initial_egress or getattr(r_session, "_egress_info", None)
        if config.bright_proxies and egress_info:
            r_session._egress_info = egress_info
            page._egress_info = egress_info

        # Log proxy info linked to this ad object into logs/proxy.log
        log_proxy_ad(single_data, r_session, countries[0])

        # Browser-native navigation is authoritative. It preserves the configured egress,
        # records the actual response status/redirect chain, and retries only transient errors.
        nav_url = destination_url
        nav_result = navigation.navigate(
            page, nav_url, timeout_ms=int(min(90.0, deadline.remaining()) * 1000), attempts=2,
            logger=lander_logger, deadline=deadline,
            abort_check=lambda: _ensure_proxy_available(
                proxy_state,
                stage="navigation",
                country_iso=countries[0],
                outage_since=scrape_started_at,
            ),
        )
        selected_page = nav_result.selected_page
        if selected_page is not None and selected_page is not page:
            original_page = page
            for attr in ("_pw_context", "_pw_browser", "_pw_instance", "_egress_info"):
                if hasattr(original_page, attr):
                    setattr(selected_page, attr, getattr(original_page, attr))
            page = selected_page
            lander_logger.info(f"[POPUP SELECTED] ad_id={ad_id} | url={page.url}")
        initial_redirects = nav_result.redirects
        if nav_result.error_code:
            # Navigation errors can be destination-specific. Probe the proxy
            # now; only a healthy probe permits the existing status=3 path.
            _ensure_proxy_available(
                proxy_state,
                stage="navigation_failed",
                country_iso=countries[0],
                force_probe=True,
                outage_since=scrape_started_at,
            )
            nav_err_str = nav_result.error
            reason = "Timeout" if nav_result.error_code == "NAV_TIMEOUT" else "Connection Error / Unreachable"
            print(f"[Worker {instance_no}] [WARN] Skipped unreachable ad_id={ad_id} | reason={reason}")
            lander_logger.warning(f"[SKIPPED UNREACHABLE] ad_id={ad_id} | reason={reason} | url={nav_url}")
            skipped_entry = json.dumps({
                "skipped": True,
                "ad_id": ad_id,
                "reason": reason,
                "destination_url": destination_url,
                "final_url": nav_url,
                "error": nav_err_str[:150],
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            payload_logger.info(skipped_entry)
            log_unsuccessful_ad(single_data, reason)
            _report_status3(ad_id, countries[0], destination_url, reason)
            metric.processed_configured_lander_url.labels(port=port, status="skipped", error=reason).inc()
            init.close_browser(page)
            return False

        _ensure_proxy_available(
            proxy_state,
            stage="navigation_complete",
            country_iso=countries[0],
            outage_since=scrape_started_at,
        )

        ready_result = readiness.wait_for_ready(
            page,
            timeout_seconds=min(float(config.get_default("PAGE_READY_TIMEOUT_SECONDS") or 30), deadline.remaining()),
            stable_samples=int(config.get_default("CAPTURE_LAYOUT_STABLE_SAMPLES") or 3),
            frame_timeout_ms=int((config.get_default("FRAME_READY_TIMEOUT_SECONDS") or 2) * 1000),
            abort_check=lambda: _ensure_proxy_available(
                proxy_state,
                stage="page_readiness",
                country_iso=countries[0],
                outage_since=scrape_started_at,
            ),
        )
        lander_logger.info(f"[READINESS] ad_id={ad_id} | {json.dumps(ready_result.to_dict(), ensure_ascii=False)}")
        snapshot = page_snapshot.capture_snapshot(page, ready_result.frames)
        deadline.check("immutable_snapshot")
        _ensure_proxy_available(
            proxy_state,
            stage="page_snapshot_complete",
            country_iso=countries[0],
            outage_since=scrape_started_at,
        )
        f_url = snapshot.url or page.url

        # Check for 404, blocked, or error pages immediately before doing any heavy processing
        is_bad, reason = check_page_status(page)
        if is_bad:
            print(f"[Worker {instance_no}] [WARN] Skipped blocked/error ad_id={ad_id} | reason={reason}")
            lander_logger.warning(f"[SKIPPED BAD/BLOCKED PAGE] ad_id={ad_id} | reason={reason} | url={f_url}")
            skipped_entry = json.dumps({
                "skipped": True,
                "ad_id": ad_id,
                "reason": reason,
                "destination_url": destination_url,
                "final_url": f_url,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            payload_logger.info(skipped_entry)
            log_unsuccessful_ad(single_data, reason, final_url=f_url)
            metric.processed_configured_lander_url.labels(port=port, status="skipped", error=reason).inc()
            terminal_confirmed = _report_status3(ad_id, countries[0], destination_url, reason)
            _finalize_artifacts(instance_no, ad_id, scrape_run_id, terminal_confirmed, lander_logger)
            init.close_browser(page)
            return False

        # Login/block classification is intentionally performed before screenshot capture,
        # so any later consent dismissal or capture repair cannot erase the evidence.
        snapshot_text = " ".join(x for x in (snapshot.text, snapshot.frame_text) if x).strip()
        pre_is_login, pre_login_reason = is_login_or_signup_page(page, destination_url, f_url, snapshot_text)

        ret_status = 2

        try:
            ret_redirects, final_url, ret_screenshot, ret_text, ret_outgoing, ret_html, category_list = controller(
                page,
                nav_url,
                instance_no,
                r_session,
                f_url,
                snapshot,
                deadline,
                abort_check=lambda: _ensure_proxy_available(
                    proxy_state,
                    stage="content_capture",
                    country_iso=countries[0],
                    outage_since=scrape_started_at,
                ),
            )
            if initial_redirects:
                ret_redirects = initial_redirects + [r for r in ret_redirects if r not in initial_redirects]
            # Run slow domain metadata lookup only after visual capture is complete.
            deadline.check("before_domain_metadata")
            ret_domain_date, ret_domain_age = domaindate.get(
                f_url, network=config.network_name, timeout_seconds=min(20.0, deadline.remaining())
            ) or ("", None)
            if not ret_domain_date:
                ret_domain_date = "1970-01-01"
            _ensure_proxy_available(
                proxy_state,
                stage="content_capture_complete",
                country_iso=countries[0],
                outage_since=scrape_started_at,
            )
        except BlockedPageException as b_err:
            reason = str(b_err)
            print(f"[Worker {instance_no}] [WARN] Skipped blocked/error ad_id={ad_id} | reason={reason}")
            lander_logger.warning(f"[SKIPPED BAD/BLOCKED PAGE] ad_id={ad_id} | reason={reason} | url={f_url}")
            log_unsuccessful_ad(single_data, reason, final_url=f_url)
            metric.processed_configured_lander_url.labels(port=port, status="skipped", error=reason).inc()
            terminal_confirmed = _report_status3(ad_id, countries[0], destination_url, reason)
            _finalize_artifacts(instance_no, ad_id, scrape_run_id, terminal_confirmed, lander_logger)
            init.close_browser(page)
            return False

        if not isinstance(ret_text, str) or not ret_text.strip():
            if final_url.lower().split('?')[0].endswith('.pdf'):
                reason = "Direct PDF / document download"
            else:
                reason = f"Empty HTML content -- ad_id={ad_id}, url={final_url}"
            print(f"[Worker {instance_no}] [WARN] Skipped ad_id={ad_id} | reason={reason}")
            lander_logger.warning(f"[SKIPPED EMPTY/PDF] ad_id={ad_id} | reason={reason} | url={final_url}")
            log_unsuccessful_ad(single_data, reason, final_url=final_url)
            metric.processed_configured_lander_url.labels(port=port, status="skipped", error=reason).inc()
            terminal_confirmed = _report_status3(ad_id, countries[0], destination_url, reason)
            _finalize_artifacts(instance_no, ad_id, scrape_run_id, terminal_confirmed, lander_logger)
            init.close_browser(page)
            return False

        # Post-scrape classification: check for Login / Sign-up page or Status 3 Keywords
        is_login, login_reason = pre_is_login, pre_login_reason

        matched_status3_kw = None
        ret_text_lower = ret_text.lower()
        for kw in get_status3_keywords():
            if kw in ret_text_lower:
                matched_status3_kw = kw
                break

        # Also check page content / frames in case text was rendered in an iframe or WAF markup
        if not matched_status3_kw:
            try:
                ps = (page.content() or "").lower()
                for kw in get_status3_keywords():
                    if kw in ps:
                        matched_status3_kw = kw
                        break
                if not matched_status3_kw:
                    for w in BOT_OR_WAF_MARKERS:
                        if w in ret_text_lower or w in ps:
                            matched_status3_kw = f"WAF marker: {w}"
                            break
            except Exception:
                pass

        if is_login or matched_status3_kw:
            ret_status = 3
            reason = login_reason if is_login else f"Status 3 keyword matched: '{matched_status3_kw}'"
            print(f"[Worker {instance_no}] [STATUS 3 DETECTED] ad_id={ad_id} | reason={reason} | url={final_url}")
            lander_logger.warning(f"[STATUS 3 SCRAPED] ad_id={ad_id} | reason={reason} | url={final_url}")
            log_unsuccessful_ad(single_data, reason, final_url=final_url)
            metric.processed_configured_lander_url.labels(port=port, status="status_3", error=reason).inc()
        else:
            ret_status = 2

        # This strict pre-upload probe prevents a partial/outage page from
        # reaching either the media API or the final insert API.
        _ensure_proxy_available(
            proxy_state,
            stage="before_media_upload",
            country_iso=countries[0],
            force_probe=True,
            outage_since=scrape_started_at,
        )
        try:
            pay = make_payload(ad_id, countries[0], instance_no, ret_redirects, final_url, ret_screenshot, ret_text,
                               ret_outgoing, ret_domain_date, ret_domain_age, ret_status, ret_html, category_list, lander_logger,
                               scrape_run_id=scrape_run_id, deadline=deadline,
                               abort_check=lambda: _ensure_proxy_available(
                                   proxy_state,
                                   stage="media_upload",
                                   country_iso=countries[0],
                                   outage_since=scrape_started_at,
                               ))
            payload_list.append(pay)
        except proxy_health.ProxyUnavailableError:
            raise
        except Exception as upload_err:
            reason = f"Upload API failed: {upload_err}"
            print(f"[Worker {instance_no}] [WARN] Upload API failed for ad_id={ad_id} | reason={upload_err}")
            lander_logger.warning(f"[UPLOAD API FAILED] ad_id={ad_id} | reason={upload_err} | url={final_url}")
            log_unsuccessful_ad(single_data, reason, final_url=final_url)
            metric.processed_configured_lander_url.labels(port=port, status="fail", error="Upload API failed").inc()
            _report_status3(ad_id, countries[0], destination_url, str(upload_err)[:120])
            _finalize_artifacts(instance_no, ad_id, scrape_run_id, False, lander_logger)
            init.close_browser(page)
            return False

        # The upload can take long enough for provider health to change. Check
        # once more immediately before the final status=2/status=3 insert.
        _ensure_proxy_available(
            proxy_state,
            stage="before_final_payload",
            country_iso=countries[0],
            force_probe=True,
            outage_since=scrape_started_at,
        )
        if not send_payload(
            payload_list,
            lander_logger,
            port,
            metric,
            scrape_run_id=scrape_run_id,
            deadline=deadline,
            pre_send_guard=lambda: _ensure_proxy_available(
                proxy_state,
                stage="final_insert_dispatch",
                country_iso=countries[0],
                outage_since=scrape_started_at,
            ),
        ):
            reason = "Insert API failed"
            print(f"[Worker {instance_no}] [WARN] Insert API failed for ad_id={ad_id}")
            lander_logger.warning(f"[INSERT API FAILED] ad_id={ad_id} | url={final_url}")
            log_unsuccessful_ad(single_data, reason, final_url=final_url)
            metric.processed_configured_lander_url.labels(port=port, status="fail", error=reason).inc()
            _report_status3(ad_id, countries[0], destination_url, reason)
            _finalize_artifacts(instance_no, ad_id, scrape_run_id, False, lander_logger)
            init.close_browser(page)
            return False

        if ret_status == 3:
            print(f"[Worker {instance_no}] [SUCCESS STATUS=3] Scraped and inserted ad_id={ad_id} with status=3 (login/gate) | ISO: {countries[0]}")
        else:
            print(f"[Worker {instance_no}] [SUCCESS STATUS=2] Successfully scraped & inserted ad_id={ad_id} | ISO: {countries[0]}")
        metric.processed_configured_lander_url.labels(port=port, status="pass", error="None").inc()
        error_count = 0

        if isinstance(single_data, dict):
            single_data["_result_status"] = ret_status
            single_data["_result_reason"] = reason if ret_status == 3 else "Scraped full lander"

        _finalize_artifacts(instance_no, ad_id, scrape_run_id, True, lander_logger)
        init.close_browser(page)
        return True


    except proxy_health.ProxyUnavailableError as proxy_error:
        return _abort_for_proxy_outage(proxy_error)

    except Exception as error:
        error_str = str(error)
        try:
            _ensure_proxy_available(
                proxy_state,
                stage="scrape_exception",
                country_iso=(countries[0] if 'countries' in locals() and countries else None),
                force_probe=proxy_health.looks_like_proxy_error(error_str),
                outage_since=scrape_started_at,
            )
        except proxy_health.ProxyUnavailableError as proxy_error:
            return _abort_for_proxy_outage(proxy_error)
        known_expected = any(k in error_str for k in [
            "Blocked page", "Empty HTML content", "Insert API failed", "Upload API failed",
            "Connection Error", "Timeout", "Timed out"
        ])
        if not known_expected:
            print("[Multiprocessing error]", type(error).__name__, error_str)
            traceback.print_exc()
        else:
            _aid = ad_id if 'ad_id' in locals() else 'unknown'
            print(f"[Worker {instance_no}] [WARN] Handled error for ad_id={_aid}: {error_str[:80]}")

        if "Empty HTML content" in error_str:
            metric.processed_configured_lander_url.labels(
                port=port,
                status="fail",
                error="Empty HTML content"
            ).inc()
            error_logger.error(error_str)
        elif "Blocked page detected" in error_str:
            if count < 1:
                error_logger.warning(
                    f"Blocked page detected; retrying once -- ad_id={ad_id}, url={destination_url}"
                )
                init.close_browser(page)
                return scraping(
                    single_data,
                    metric,
                    lander_logger,
                    port,
                    instance_no,
                    count + 1,
                    error_logger,
                    proxy_state=proxy_state,
                )

            metric.processed_configured_lander_url.labels(
                port=port,
                status="fail",
                error="Blocked page"
            ).inc()
            error_logger.error(
                f"Blocked after retry -- ad_id={ad_id}, url={destination_url}"
            )
            try:
                _report_status3(ad_id, countries[0], destination_url, "Blocked page after retry")
            except proxy_health.ProxyUnavailableError as proxy_error:
                return _abort_for_proxy_outage(proxy_error)
            init.close_browser(page)
            return False

        elif "invalid argument" in error_str:
            metric.processed_configured_lander_url.labels(
                port=port,
                status="fail",
                error="invalid argument"
            ).inc()
            error_logger.error("invalid argument -- " + error_str)
        elif "Timed out receiving" in error_str:
            metric.processed_configured_lander_url.labels(port=port, status="fail", error="Timed out receiving").inc()
            error_logger.error("timed out -- " + error_str)
        elif "'NoneType' object has no attribute 'replace'" in error_str:
            metric.processed_configured_lander_url.labels(port=port, status="fail", error="None Destination URL").inc()
            error_logger.error("None type -- " + error_str)
        elif "net::ERR" in error_str:
            metric.processed_configured_lander_url.labels(port=port, status="fail", error="Connection Error").inc()
            error_logger.error("net Err -- " + error_str)
        elif "MaxRetryError" in error_str:
            metric.processed_configured_lander_url.labels(port=port, status="fail", error="MaxRetryError").inc()
            error_logger.error("max retry error -- " + error_str)
        elif "Expecting value:" in error_str:
            metric.processed_configured_lander_url.labels(port=port, status="fail", error="Blank response Error").inc()
            error_logger.error("blank response -- " + error_str)
        elif "cannot determine loading status" in error_str:
            count += 1
            if count <= 2:
                init.close_browser(page)
                return scraping(
                    single_data, metric, lander_logger, port, instance_no,
                    count, error_logger, proxy_state=proxy_state,
                )
            else:
                metric.processed_configured_lander_url.labels(port=port, status="fail", error="Loading Status Error").inc()
                error_logger.error("loading status error -- " + error_str)
        elif "No such file or directory" in error_str or "The system cannot find the file specified" in error_str:
            metric.processed_configured_lander_url.labels(port=port, status="fail", error="0 byte file").inc()
            folder = './zip/' + str(instance_no)
            if os.path.exists(folder):
                try:
                    shutil.rmtree(folder, ignore_errors=True)
                    os.makedirs(folder, exist_ok=True)
                except Exception as err:
                    print(f"Failed to reset {folder}: {err}")
        else:
            metric.processed_configured_lander_url.labels(port=port, status="fail", error="other error").inc()
            error_logger.error("other error -- " + error_str)

        error_count += 1
        if error_count > 25:
            if os.name != "nt" and os.path.exists("./stop_process.sh"):
                try:
                    sub = subprocess.Popen(["bash", "./stop_process.sh"])
                    time.sleep(2)
                    sub.kill()
                except Exception:
                    pass

        # Post status=3 to INSERT API so backend marks this ad as failed/blocked
        try:
            _ad_id_s3 = ad_id if 'ad_id' in locals() else single_data.get('id', 0)
            _country_s3 = countries[0] if 'countries' in locals() and countries else get_country(single_data)
            _dest_s3 = destination_url if 'destination_url' in locals() else single_data.get('destination_url', '')
            log_unsuccessful_ad(single_data, error_str[:120])
            _report_status3(_ad_id_s3, _country_s3, _dest_s3, error_str[:120])
        except proxy_health.ProxyUnavailableError as proxy_error:
            return _abort_for_proxy_outage(proxy_error)
        except Exception as _e:
            lander_logger.error(f"[STATUS=3 fallback failed] {_e}")

        if 'scrape_run_id' in locals() and 'ad_id' in locals():
            _finalize_artifacts(instance_no, ad_id, scrape_run_id, False, lander_logger)
        init.close_browser(page)
        return False



def setup_logger(name, filename, level=logging.INFO, max_bytes=52_428_800, backups=50, raw=False):
    return daily_logging.configure_logger(
        name,
        filename,
        level=level,
        max_bytes=int(config.get_default("LOG_MAX_BYTES") or max_bytes),
        backups=int(config.get_default("LOG_BACKUP_COUNT") if config.get_default("LOG_BACKUP_COUNT") is not None else backups),
        raw=raw,
        timezone=str(config.get_default("LOG_TIMEZONE") or "Asia/Kolkata"),
        date_format=str(config.get_default("LOG_DATE_FORMAT") or "%d-%m-%Y"),
        idle_seconds=float(config.get_default("LOG_HANDLER_IDLE_SECONDS") or 3600),
        daily_folders=bool(config.get_default("LOG_DAILY_FOLDERS") is not False),
    )

# Dedicated loggers
payload_logger = setup_logger("payload_logger", "logs/payloads.log", level=logging.INFO)
successful_payload_logger = setup_logger("successful_payload_logger", "logs/successful_payloads.json", level=logging.INFO, raw=True)
unsuccessful_ad_logger = setup_logger("unsuccessful_ad_logger", "logs/unsuccessful_ads.json", level=logging.INFO, raw=True)
proxy_ad_logger = setup_logger("proxy_ad_logger", "logs/proxy.log", level=logging.INFO, raw=True)
proxy_health_logger = setup_logger(
    "proxy_health_logger", "logs/proxy_health.log", level=logging.INFO, raw=True
)

def log_unsuccessful_ad(single_data, reason, final_url=None):
    """Logs the original ad object dictionary from the GET API into logs/unsuccessful_ads.json"""
    try:
        if isinstance(single_data, dict):
            single_data["_result_status"] = 3
            single_data["_result_reason"] = str(reason or "")
        entry = {
            "ad_id": single_data.get("id") or single_data.get("ad_id", 0),
            "reason": reason,
            "destination_url": single_data.get("destination_url", ""),
            "final_url": final_url or single_data.get("destination_url", ""),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "raw_ad": single_data
        }
        unsuccessful_ad_logger.info(json.dumps(entry, ensure_ascii=False))
    except Exception as e:
        print(f"[Logging Warning] Failed to log unsuccessful ad: {e}")

def log_proxy_ad(single_data, r_session, country_iso):
    """Logs active Bright Data proxy info paired with the ad object into logs/proxy.log"""
    try:
        egress = getattr(r_session, "_egress_info", {}) or {}
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ad_id": single_data.get("id") or single_data.get("ad_id", 0),
            "proxy": {
                "host": init._get_brd_host(country_iso),
                "country_iso": country_iso,
                "egress_ip": egress.get("ip", "unknown"),
                "egress_country": egress.get("country", country_iso.upper()),
            },
            "ad": single_data
        }
        proxy_ad_logger.info(json.dumps(entry, ensure_ascii=False))
    except Exception as e:
        print(f"[Logging Warning] Failed to log proxy ad: {e}")

import json

def make_payload(ad_id, iso, instance_no, ret_redirects, final_url, ret_screenshot,
                 ret_text, ret_outgoing, ret_domain_date, ret_domain_age,
                 ret_status, ret_html, category_list, lander_logger, scrape_run_id=None,
                 deadline=None, abort_check=None):
    # print(f"[DEBUG] make_payload called for ad_id={ad_id}, iso={iso}")
    payload = {
        "ad_id": ad_id,
        "redirects": ret_redirects,
        "outgoing_url": ret_outgoing,
        "destinations": final_url,
        "country_iso": iso,
        "html_path": "",
        "html_content": (ret_text or "")[:25000],


        "screen_shot": "",
        "status": ret_status,
        "domain_age": ret_domain_age,
        "domain_registered_date": ret_domain_date,

        "IsDataCenterProxy": 1,
        "crawled_by": "python",
        "ad_category": category_list
    }
    if abort_check:
        abort_check()

    # Facebook's upload API accepts the screenshot as `media` and returns `image_path`.
    # `html_path` is optional for this endpoint; the extracted text is sent at insert time.
    try:
        if not os.path.isfile(ret_screenshot) or os.path.getsize(ret_screenshot) == 0:
            raise RuntimeError(f"Screenshot is missing or empty -- ad_id={ad_id}")

        if str(instance_no).startswith("sample_"):
            try:
                os.makedirs("./images/saved_samples", exist_ok=True)
                shutil.copy2(ret_screenshot, f"./images/saved_samples/{instance_no}.jpg")
            except Exception:
                pass

        zip_file = None
        with open(ret_screenshot, 'rb') as img:
            # Note: The backend S3 upload endpoint requires status '2' to store the media
            # and generate/return the S3 image_path. The final payload still carries status=3.
            s3_upload_status = '2' if ret_status == 3 else str(ret_status)
            form_data_payload = {
                'media': ('img.jpg', img, 'image/jpeg'),
                'ad_id': (None, str(ad_id)),
                'status': (None, s3_upload_status),
                'country': (None, str(iso)),
            }

            # Facebook's uploadFileToServer endpoint only handles a single file ('media').
            # Attaching 'zip' causes the backend to overwrite image_path with the .zip file path!
            if config.network_name != "facebook" and ret_html and os.path.isfile(ret_html) and os.path.getsize(ret_html) > 0:
                zip_size_bytes = os.path.getsize(ret_html)
                # Safe Zip Size Check: If html.zip is larger than 15 MB, skip attaching it to avoid Cloudflare 413
                if zip_size_bytes <= 15 * 1024 * 1024:
                    zip_file = open(ret_html, 'rb')
                    form_data_payload['zip'] = ('file.zip', zip_file, 'application/zip')
                else:
                    lander_logger.warning(
                        f"[S3 UPLOAD] ad_id={ad_id} | html.zip ({round(zip_size_bytes / (1024*1024), 2)}MB) exceeds 15MB limit; uploading screenshot only to prevent 413 Payload Too Large"
                    )

            try:
                api_url = config.get_api("DEV_S3_API") if config.dev_mode else config.get_api("MAIN_S3_API")
                payload_logger.info(f"[S3 UPLOAD REQUEST] ad_id={ad_id} | instance={instance_no} | url={api_url}")
                res = None
                media_operation_key = f"media-{scrape_run_id or uuid.uuid4().hex}"
                upload_attempts = int(config.get_default("API_MAX_ATTEMPTS") or 3)
                for upload_attempt in range(1, upload_attempts + 1):
                    if abort_check:
                        abort_check()
                    if deadline:
                        deadline.check("media_upload")
                    img.seek(0)
                    if zip_file:
                        zip_file.seek(0)
                    try:
                        res = requests.post(
                            api_url, files=form_data_payload, timeout=_request_timeout(deadline),
                            headers={"X-Idempotency-Key": media_operation_key},
                        )
                        if abort_check:
                            abort_check()
                    except (requests.Timeout, requests.ConnectionError):
                        if abort_check:
                            abort_check()
                        if upload_attempt >= upload_attempts:
                            raise
                        time.sleep(min(8, 2 ** (upload_attempt - 1)))
                        continue
                    if res.status_code not in api_client.RETRYABLE_STATUS or upload_attempt >= upload_attempts:
                        break
                    if abort_check:
                        abort_check()
                    time.sleep(api_client.retry_delay(res, upload_attempt))
            finally:
                if zip_file:
                    zip_file.close()

            # HTTP 413 Auto-Retry: If the S3 upload endpoint still returns HTTP 413 (Payload Too Large),
            # immediately retry with ONLY the screenshot (media)
            if res.status_code == 413 and 'zip' in form_data_payload:
                if abort_check:
                    abort_check()
                if deadline:
                    deadline.check("media_upload_without_archive")
                lander_logger.warning(f"[S3 UPLOAD RETRY] ad_id={ad_id} | HTTP 413 received. Retrying upload with screenshot only...")
                payload_logger.warning(f"[S3 UPLOAD RETRY] ad_id={ad_id} | Retrying with screenshot only due to HTTP 413")
                img.seek(0)
                form_retry = {
                    'media': ('img.jpg', img, 'image/jpeg'),
                    'ad_id': (None, str(ad_id)),
                    'status': (None, s3_upload_status),
                    'country': (None, str(iso)),
                }
                res = requests.post(
                    api_url, files=form_retry, timeout=_request_timeout(deadline),
                    headers={"X-Idempotency-Key": media_operation_key + "-without-archive"},
                )
                if abort_check:
                    abort_check()

            try:
                x = res.json()
            except Exception:
                x = {"raw": res.text}

            lander_logger.info(json.dumps(x, ensure_ascii=False))
            payload_logger.info(f"[S3 UPLOAD RESPONSE] ad_id={ad_id} | instance={instance_no} | HTTP {res.status_code} | response={json.dumps(x, ensure_ascii=False)}")
            if not res.ok or str(x.get("code")) != "200":
                raise RuntimeError(f"Upload API failed: HTTP={res.status_code}, response={x}")

            payload["screen_shot"] = x.get("image_path", "")
            payload["html_path"] = x.get("html_path", "")
            if not payload["screen_shot"] and ret_status != 3:
                raise RuntimeError(f"Upload API returned missing image_path -- ad_id={ad_id}, response={x}")

        lander_logger.info(json.dumps([payload], ensure_ascii=False))
    finally:
        # Artifact lifecycle is finalized only after the insert API outcome is known.
        pass

    return payload


def _finalize_artifacts(instance_no, ad_id, scrape_run_id, success, lander_logger=None):
    """Delete confirmed artifacts, or retain failures in a run-scoped recovery folder."""
    sources = [
        (os.path.join("images", str(instance_no)), "images"),
        (os.path.join("zip", str(instance_no)), "zip"),
    ]
    if success:
        for source, _label in sources:
            if os.path.isdir(source):
                shutil.rmtree(source, ignore_errors=True)
        return None
    safe_ad = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(ad_id))[:80] or "unknown"
    safe_run = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(scrape_run_id))[:80] or uuid.uuid4().hex
    destination = os.path.join("failed_artifacts", config.network_name, f"ad_{safe_ad}_{safe_run}")
    os.makedirs(destination, exist_ok=True)
    moved = False
    for source, label in sources:
        if not os.path.isdir(source):
            continue
        target = os.path.join(destination, label)
        try:
            if os.path.exists(target):
                shutil.rmtree(target, ignore_errors=True)
            shutil.move(source, target)
            moved = True
        except Exception as exc:
            if lander_logger:
                lander_logger.warning(f"[ARTIFACT RETENTION FAILED] source={source} error={exc}")
    if moved:
        metadata = {
            "ad_id": ad_id,
            "scrape_run_id": scrape_run_id,
            "retained_at": time.time(),
            "reason": "terminal API operation was not confirmed",
        }
        _atomic_write_json(os.path.join(destination, "retention.json"), metadata)
        if lander_logger:
            lander_logger.warning(f"[ARTIFACTS RETAINED] ad_id={ad_id} path={destination}")
        return destination
    try:
        if os.path.isdir(destination) and not os.listdir(destination):
            os.rmdir(destination)
    except Exception:
        pass
    return None

def send_payload(
    payload_list,
    lander_logger,
    port,
    metric,
    scrape_run_id=None,
    deadline=None,
    pre_send_guard=None,
):
    try:
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        api_url = config.get_api("DEV_INSERT_API") if config.dev_mode else config.get_api("MAIN_INSERT_API")

        res_json = {}
        for p in payload_list:
            if deadline:
                deadline.check("insert_api")
            if pre_send_guard is not None:
                pre_send_guard()
            body = {"ad_id": p["ad_id"], "insertData": p}
            status_val = p.get("status", 2)
            if status_val == 2:
                # Log status=2 payload into logs/successful_payloads.json
                successful_payload_logger.info(json.dumps(body, ensure_ascii=False))
                payload_logger.info(f"[SUCCESSFUL PAYLOAD status=2] {json.dumps(body, ensure_ascii=False)}")
            else:
                payload_logger.info(f"[SCRAPED PAYLOAD status={status_val}] {json.dumps(body, ensure_ascii=False)}")

            payload_logger.info(f"[INSERT API REQUEST] ad_id={p['ad_id']} | status={status_val} | url={api_url}")
            lander_logger.info(f"[DEBUG SEND] status={status_val} {json.dumps(body, ensure_ascii=False)}")
            res = api_client.post_json(
                api_url, body,
                attempts=int(config.get_default("API_MAX_ATTEMPTS") or 3),
                timeout=_request_timeout(deadline),
                idempotency_key=f"insert-{scrape_run_id or uuid.uuid4().hex}-{status_val}",
                before_attempt=pre_send_guard,
            )

            try:
                res_json = res.json()
            except Exception:
                res_json = {"raw": res.text}

            lander_logger.info(json.dumps(res_json, ensure_ascii=False))
            payload_logger.info(f"[INSERT API RESPONSE] ad_id={p['ad_id']} | HTTP {res.status_code} | response={json.dumps(res_json, ensure_ascii=False)}")
            if not res.ok or str(res_json.get("code")) != "200":
                # Fallback: If INSERT_API failed due to ER_DATA_TOO_LONG on white_ad_lander / html_path or white_ad_screenshot
                if "ER_DATA_TOO_LONG" in str(res_json) or "white_ad_lander" in str(res_json) or "white_ad_screenshot" in str(res_json):
                    lander_logger.warning(f"[RETRY INSERT API] ad_id={p['ad_id']} retrying with trimmed fields due to DB column length limit...")
                    p_retry = dict(p)
                    if "white_ad_lander" in str(res_json):
                        p_retry["html_path"] = ""
                    if "white_ad_screenshot" in str(res_json):
                        orig_shot = p_retry.get("screen_shot", "")
                        # Staging DB white_ad_screenshot column limit is ~45-50 chars; send filename (<= 45 chars)
                        base_shot = os.path.basename(orig_shot)
                        p_retry["screen_shot"] = base_shot[:45]
                    body_retry = {"ad_id": p["ad_id"], "insertData": p_retry}
                    res_retry = api_client.post_json(
                        api_url, body_retry, attempts=int(config.get_default("API_MAX_ATTEMPTS") or 3),
                        timeout=_request_timeout(deadline), idempotency_key=f"insert-trimmed-{scrape_run_id or uuid.uuid4().hex}-{status_val}",
                        before_attempt=pre_send_guard,
                    )
                    try:
                        res_json_retry = res_retry.json()
                    except Exception:
                        res_json_retry = {"raw": res_retry.text}
                    payload_logger.info(f"[INSERT API RETRY RESPONSE] ad_id={p['ad_id']} | HTTP {res_retry.status_code} | response={json.dumps(res_json_retry, ensure_ascii=False)}")
                    if res_retry.ok and str(res_json_retry.get("code")) == "200":
                        p.update(p_retry)
                        res_json = res_json_retry
                        continue
                raise RuntimeError(f"Insert API failed: HTTP={res.status_code}, response={res_json}")

        ad_ids = " ".join(str(p['ad_id']) for p in payload_list)
        ip_hit_count = sum(len(p['outgoing_url']) + len(p['redirects']) + 2 for p in payload_list)
        lander_logger.info(f"IP hit count : {ip_hit_count} ad_ids: {ad_ids}")

        metric.updated_configured_lander.labels(port=port, message=res_json.get('message', 'no message')).inc()
        return True

    except proxy_health.ProxyUnavailableError:
        raise
    except Exception as e:
        lander_logger.info(json.dumps({"error": str(e)}, ensure_ascii=False))
        metric.updated_configured_lander.labels(port=port, message="insertion error").inc()
        return False


def send_status3_payload(
    ad_id,
    country_iso,
    destination_url,
    reason,
    lander_logger,
    scrape_run_id=None,
    deadline=None,
    pre_send_guard=None,
):
    """
    Posts a minimal payload with status=3 to MAIN_INSERT_API / DEV_INSERT_API
    to inform the backend that this ad was blocked, skipped, or errored.
    status = 3 -> Error / Blocked / Cannot scrape
    """
    try:
        if pre_send_guard is not None:
            pre_send_guard()
        payload = {
            "ad_id": ad_id,
            "redirects": [],
            "outgoing_url": [],
            "destinations": destination_url,
            "country_iso": country_iso,
            "html_path": "",
            "html_content": "N/A",
            "screen_shot": "N/A",
            "status": 3,
            "domain_age": None,
            "domain_registered_date": "1970-01-01",
            "IsDataCenterProxy": 1,
            "crawled_by": "python",
            "ad_category": []
        }
        body = {"ad_id": ad_id, "insertData": payload}
        payload_logger.info(f"[STATUS 3 PAYLOAD] ad_id={ad_id} | reason={reason} | payload={json.dumps(body, ensure_ascii=False)}")
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        api_url = config.get_api("DEV_INSERT_API") if config.dev_mode else config.get_api("MAIN_INSERT_API")
        payload_logger.info(f"[STATUS 3 INSERT REQUEST] ad_id={ad_id} | url={api_url}")
        lander_logger.warning(
            f"[STATUS=3] Posting blocked/skipped ad to INSERT_API | ad_id={ad_id} | reason={reason} | url={destination_url}"
        )
        res = api_client.post_json(
            api_url, body, attempts=int(config.get_default("API_MAX_ATTEMPTS") or 3),
            timeout=_request_timeout(deadline), idempotency_key=f"status3-{scrape_run_id or uuid.uuid4().hex}",
            before_attempt=pre_send_guard,
        )
        try:
            res_json = res.json()
        except Exception:
            res_json = {"raw": res.text}
        lander_logger.info(f"[STATUS=3 API Response] {json.dumps(res_json, ensure_ascii=False)}")
        payload_logger.info(f"[STATUS 3 INSERT RESPONSE] ad_id={ad_id} | HTTP {res.status_code} | response={json.dumps(res_json, ensure_ascii=False)}")
        return bool(res.ok and str(res_json.get("code")) == "200")
    except proxy_health.ProxyUnavailableError:
        raise
    except Exception as e:
        lander_logger.error(f"[STATUS=3] Failed to post status=3 for ad_id={ad_id}: {e}")
        return False
def controller(
    page,
    destination_url,
    instance_no,
    r_session,
    f_url,
    snapshot=None,
    deadline=None,
    abort_check=None,
):
    # print(f"[DEBUG] Controller loading {destination_url}")
    final_url = page.url
    is_bad, block_reason = check_page_status(page)
    if is_bad:
        raise BlockedPageException(block_reason or f"Blocked page detected: {final_url}")

    # Ensure required directories exist before html/screenshot
    os.makedirs(f'./zip/{instance_no}', exist_ok=True)
    os.makedirs(f'./images/{instance_no}', exist_ok=True)

    if abort_check:
        abort_check()
    try:
        ret_redirects = redirect.get(destination_url, final_url, r_session, page)
        if not ret_redirects:
            print(f"[Redirect] Empty for: {destination_url}")
    except Exception as e:
        ret_redirects = []
        print(f"[Redirect] Error for {destination_url}: {e}")

    if deadline:
        deadline.check("before_capture")
    if abort_check:
        abort_check()
    capture_result = capture.capture_page(
        page,
        "prelander",
        instance_no,
        config=config,
        deadline=deadline,
        abort_check=abort_check,
    )
    ret_screenshot = capture_result.image_path
    print(
        f"[Capture] state={capture_result.state} mode={capture_result.mode} "
        f"size={capture_result.width}x{capture_result.height} bytes={capture_result.final_bytes} "
        f"truncated={capture_result.truncated}"
    )

    if abort_check:
        abort_check()
    original_html = snapshot.html if snapshot is not None else None
    ret_html = html.get(
        page,
        r_session,
        final_url,
        instance_no,
        html_source=original_html,
        frame_documents=snapshot.frame_documents if snapshot is not None else None,
        config=config,
        deadline=deadline,
    )
    if abort_check:
        abort_check()

    try:
        ret_text = " ".join(x for x in (
            snapshot.text if snapshot is not None else "",
            snapshot.frame_text if snapshot is not None else "",
        ) if x).strip() if snapshot is not None else text.get(page)
        if not ret_text:
            print(f"[Text] Empty for: {final_url}")
            ret_text = ""
    except Exception as e:
        print(f"[Text] Error for {final_url}: {e}")
        ret_text = ""

    if abort_check:
        abort_check()
    try:
        ret_outgoing = outgoing_url.get_from_html(original_html, final_url, r_session) if original_html is not None else outgoing_url.get(page, final_url, r_session)
        if not ret_outgoing:
            print(f"[Outgoing URL] Empty for: {final_url}")
    except Exception as e:
        ret_outgoing = []
        print(f"[Outgoing URL] Error for {final_url}: {e}")

    try:
        category_list = []
    except Exception as e:
        category_list = []
        print(f"[Category] Error for {f_url}: {e}")

    if abort_check:
        abort_check()
    return ret_redirects, final_url, ret_screenshot, ret_text, ret_outgoing, ret_html, category_list



def get_input(instance_no):
    print("Taking data from GET_API")
    try:
        api_key = "DEV_GET_API" if config.dev_mode else "MAIN_GET_API"
        api_url = config.get_api(api_key)
        inp = api_client.request(
            "GET", api_url, attempts=int(config.get_default("API_MAX_ATTEMPTS") or 3),
            timeout=REQUEST_TIMEOUT, idempotency_key=f"get-{config.network_name}-{instance_no}",
        )
        if inp.status_code != 200:
            print(f"[GET INPUT ERROR] HTTP status code {inp.status_code}")
            return None
        try:
            data = inp.json()
        except Exception:
            data = json.loads(inp.text)
        li_of_data = data.get('data', []) if isinstance(data, dict) else []
        if not isinstance(li_of_data, list):
            li_of_data = []

        folder = "getApi_data_dev" if config.dev_mode else "getApi_data"
        os.makedirs(folder, exist_ok=True)
        filename = os.path.join(folder, f"temp_getapi_data_{config.network_name}_{instance_no}.json")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(li_of_data, f)

        return li_of_data
    except Exception as e:
        print("[GET INPUT ERROR]", e)
        return None


def get_input_from_file(instance_no):
    print("### HIT_GET_API is False -> Taking data from file")
    folder = "getApi_data_dev" if config.dev_mode else "getApi_data"
    filename = f"{folder}/temp_getapi_data_{config.network_name}_{instance_no}.json"

    try:
        with open(filename, "r") as f:
            li_of_data = json.load(f)
        if not li_of_data:
            raise ValueError("Empty file content.")
    except Exception as e:
        print(f"[File Read Error] {e} -> Re-fetching from GET API")
        li_of_data = get_input(instance_no)
        if li_of_data is None:
            return [], filename
    return li_of_data, filename


# ─────────────────────────────────────────────────────────────────────────────────
# Shared disk-based ad queue helpers (Option B: JSON file + multiprocessing.Lock)
# ─────────────────────────────────────────────────────────────────────────────────

def _shared_queue_path():
    """Returns the path to the single shared ad queue file used by all workers."""
    folder = "getApi_data_dev" if config.dev_mode else "getApi_data"
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"shared_ad_queue_{config.network_name}.json")


def _atomic_write_json(path, data, strict=False):
    """Write data to path atomically via a .tmp file so no corruption on crash."""
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    tmp_path = f"{path}.tmp_{os.getpid()}_{int(time.time() * 1000) % 100000}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp_path, path)  # atomic rename on Linux & Windows
    except Exception as atomic_error:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as fallback_error:
            if strict:
                raise OSError(
                    f"Failed to persist JSON at {path}: atomic={atomic_error}; fallback={fallback_error}"
                ) from fallback_error
            return False
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
    return True


AD_COOLDOWN_SECONDS = 300  # 5 minutes cooldown to avoid DB lag duplicates while allowing re-scrapes for updates


def _completed_tracker_path():
    """Returns the path to the completed ad IDs cache file."""
    folder = "getApi_data_dev" if config.dev_mode else "getApi_data"
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"completed_ad_ids_{config.network_name}.json")


def _lease_tracker_path():
    folder = "getApi_data_dev" if config.dev_mode else "getApi_data"
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"active_leases_{config.network_name}.json")


def _persist_leases(in_flight_dict):
    data = {str(k): list(v) if isinstance(v, (list, tuple)) else v for k, v in in_flight_dict.items()}
    _atomic_write_json(_lease_tracker_path(), data)


class _LeaseHeartbeat:
    def __init__(self, file_lock, in_flight_dict, ad_id, instance_no):
        self.file_lock = file_lock
        self.in_flight_dict = in_flight_dict
        self.ad_id = ad_id
        self.instance_no = instance_no
        self.interval = max(10.0, float(config.get_default("QUEUE_LEASE_SECONDS") or 300) / 3.0)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name=f"lease-{ad_id}", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=2)

    def _run(self):
        while not self.stop_event.wait(self.interval):
            try:
                with self.file_lock:
                    if self.ad_id not in self.in_flight_dict:
                        return
                    existing = self.in_flight_dict.get(self.ad_id)
                    payload = existing[2] if isinstance(existing, (list, tuple)) and len(existing) >= 3 else None
                    self.in_flight_dict[self.ad_id] = (self.instance_no, time.time(), payload)
                    _persist_leases(self.in_flight_dict)
            except Exception:
                return


def _record_ad_completed(file_lock, ad_id, in_flight_dict, completed_dict):
    """Marks an ad as finished: removes from in_flight and adds to completed_dict with 5m cooldown."""
    if ad_id is None:
        return
    now = time.time()
    with file_lock:
        in_flight_dict.pop(ad_id, None)
        _persist_leases(in_flight_dict)
        completed_dict[ad_id] = now
        try:
            completed_path = _completed_tracker_path()
            # Retain only entries within 5-minute cooldown window
            current_dict = {str(k): ts for k, ts in completed_dict.items() if now - ts < AD_COOLDOWN_SECONDS}
            _atomic_write_json(completed_path, current_dict)
        except Exception:
            pass


def _release_ad_for_retry(file_lock, single_data, in_flight_dict, lander_logger):
    """Release a failed lease and requeue it without losing the ad on worker/process failure."""
    if not isinstance(single_data, dict):
        return
    ad_id = single_data.get("id")
    max_attempts = int(config.get_default("QUEUE_MAX_ATTEMPTS") or 3)
    next_attempt = int(single_data.get("_queue_attempt", 0)) + 1
    with file_lock:
        in_flight_dict.pop(ad_id, None)
        _persist_leases(in_flight_dict)
        if next_attempt >= max_attempts:
            dead_path = os.path.join(
                "getApi_data_dev" if config.dev_mode else "getApi_data",
                f"dead_letter_{config.network_name}.json",
            )
            dead = []
            if os.path.isfile(dead_path):
                try:
                    with open(dead_path, "r", encoding="utf-8") as handle:
                        dead = json.load(handle)
                except Exception:
                    dead = []
            failed = dict(single_data)
            failed["_queue_attempt"] = next_attempt
            failed["_dead_lettered_at"] = time.time()
            dead.append(failed)
            _atomic_write_json(dead_path, dead)
            lander_logger.error(f"[QUEUE DEAD LETTER] ad_id={ad_id} attempts={next_attempt}")
            return
        queue_path = _shared_queue_path()
        queued = []
        if os.path.isfile(queue_path):
            try:
                with open(queue_path, "r", encoding="utf-8") as handle:
                    queued = json.load(handle)
            except Exception:
                queued = []
        retry_item = dict(single_data)
        retry_item["_queue_attempt"] = next_attempt
        if not any(item.get("id") == ad_id for item in queued if isinstance(item, dict)):
            queued.append(retry_item)
            _atomic_write_json(queue_path, queued)
        lander_logger.warning(f"[QUEUE RETRY] ad_id={ad_id} attempt={next_attempt}/{max_attempts}")


def _release_ad_for_proxy_wait(file_lock, single_data, in_flight_dict, lander_logger):
    """Requeue infrastructure-interrupted work without consuming an ad retry."""
    if not isinstance(single_data, dict):
        return
    ad_id = single_data.get("id")
    with file_lock:
        queue_path = _shared_queue_path()
        queued = []
        if os.path.isfile(queue_path):
            try:
                with open(queue_path, "r", encoding="utf-8") as handle:
                    queued = json.load(handle)
                if not isinstance(queued, list):
                    queued = []
            except Exception:
                queued = []

        retry_item = dict(single_data)
        for transient_key in (
            "_proxy_unavailable",
            "_proxy_unavailable_reason",
            "_terminal_reported",
            "_result_status",
            "_result_reason",
            "_scrape_run_id",
        ):
            retry_item.pop(transient_key, None)
        # Preserve _queue_attempt exactly: a provider outage must never move an
        # ad toward the dead-letter threshold.
        if not any(item.get("id") == ad_id for item in queued if isinstance(item, dict)):
            queued.insert(0, retry_item)
            # Persist the queue before releasing its durable lease. If both
            # atomic and fallback writes fail, the lease remains recoverable.
            _atomic_write_json(queue_path, queued, strict=True)
        in_flight_dict.pop(ad_id, None)
        _persist_leases(in_flight_dict)
    lander_logger.warning(
        f"[QUEUE PROXY PAUSE] ad_id={ad_id} requeued without retry increment"
    )


def pop_next_ad_from_file(file_lock, instance_no, metric, lander_logger, in_flight_dict, completed_dict):
    """
    Atomically pop exactly one valid ad from the shared disk queue.
    Guarantees zero duplicate scraping while allowing legitimate re-scrapes for updates:
      1. Immediate atomic pop under multiprocessing.Lock.
      2. Tracking currently in-flight ads across all workers (in_flight_dict).
      3. Short 5-minute cooldown window for completed ads (completed_dict).
         - Completed < 5 mins ago -> skipped (DB lag protection).
         - Completed > 5 mins ago -> permitted to be re-scraped for lander updates!
      4. Smart backoff if all ads returned by GET_API are currently in-flight or in cooldown.
    """
    queue_path = _shared_queue_path()
    now = time.time()

    with file_lock:
        lease_seconds = float(config.get_default("QUEUE_LEASE_SECONDS") or 300)
        # Clean stale in-flight leases.
        expired_ads = []
        for aid, info in list(in_flight_dict.items()):
            if isinstance(info, (list, tuple)) and len(info) >= 2:
                if now - info[1] > lease_seconds:
                    if len(info) >= 3 and isinstance(info[2], dict):
                        expired_ads.append(dict(info[2]))
                    in_flight_dict.pop(aid, None)
        _persist_leases(in_flight_dict)

        # Clean completed entries older than 5 minutes (300 seconds)
        # Once an ad is past cooldown, it is pruned so future GET_API deliveries will be scraped as updates!
        for aid, ts in list(completed_dict.items()):
            if now - ts >= AD_COOLDOWN_SECONDS:
                completed_dict.pop(aid, None)

        # 1. Read current queue from disk
        ads = []
        if os.path.isfile(queue_path):
            try:
                with open(queue_path, "r", encoding="utf-8") as f:
                    ads = json.load(f)
                if not isinstance(ads, list):
                    ads = []
            except Exception:
                ads = []
        queued_ids = {item.get("id") for item in ads if isinstance(item, dict)}
        for expired in expired_ads:
            if expired.get("id") not in queued_ids:
                ads.insert(0, expired)
                queued_ids.add(expired.get("id"))

        # Filter out anything in the queue that is currently in-flight or within 5-min cooldown
        valid_ads = []
        for item in ads:
            aid = item.get("id")
            if aid is not None and item.get("destination_url"):
                if aid not in in_flight_dict and aid not in completed_dict:
                    valid_ads.append(item)
        ads = valid_ads

        # 2. Refill if empty
        if not ads:
            print(f"[Worker {instance_no}] Shared queue empty. Fetching new batch from GET_API...")
            batch = get_input(instance_no) if config.hit_get_api else get_input_from_file(instance_no)[0]
            if not batch:
                metric.configured_lander_get.labels(data='empty').inc()
                _atomic_write_json(queue_path, [])
                return None

            startfrom = config.skip_ads_till or 0
            raw_candidates = [
                item for item in batch[startfrom:]
                if item.get("id") is not None and item.get("destination_url")
            ]

            fresh_ads = []
            in_flight_count = 0
            cooldown_count = 0
            for item in raw_candidates:
                aid = item.get("id")
                if aid in in_flight_dict:
                    in_flight_count += 1
                elif aid in completed_dict:
                    cooldown_count += 1
                else:
                    fresh_ads.append(item)

            if fresh_ads:
                ads = fresh_ads
                print(
                    f"[Worker {instance_no}] Ingested {len(raw_candidates)} ads from GET_API: "
                    f"{len(fresh_ads)} ready to scrape, {in_flight_count} in-flight by other workers, {cooldown_count} in 5-min cooldown."
                )
            else:
                print(
                    f"[Worker {instance_no}] All {len(raw_candidates)} ads from GET_API are currently in-flight "
                    f"({in_flight_count}) or in 5-min cooldown ({cooldown_count}). Waiting 10s for workers to finish..."
                )
                _atomic_write_json(queue_path, [])
                return "WAIT"

        # 3. Pop exactly one ad
        if not ads:
            _atomic_write_json(queue_path, [])
            return None

        target_ad = ads.pop(0)
        target_id = target_ad.get("id")
        in_flight_dict[target_id] = (instance_no, time.time(), dict(target_ad))
        _persist_leases(in_flight_dict)

        # 4. Write remaining ads back to disk atomically
        _atomic_write_json(queue_path, ads)
        remaining = len(ads)

    lander_logger.info(
        f"[QUEUE] Worker {instance_no} popped ad_id={target_ad.get('id')} | "
        f"{remaining} ads remaining in shared queue | in_flight={len(in_flight_dict)} | active_cooldown={len(completed_dict)}"
    )
    return target_ad


def main(instances):
    global payload_logger, successful_payload_logger, unsuccessful_ad_logger, proxy_ad_logger
    if len(instances) >= 6:
        instance_no, port, file_lock, in_flight_dict, completed_dict, proxy_state = instances[:6]
    else:
        instance_no, port, file_lock, in_flight_dict, completed_dict = instances
        proxy_state = None
    os.makedirs(f'./images/{instance_no}', exist_ok=True)
    os.makedirs(f'./zip/{instance_no}', exist_ok=True)
    metric = Metrics(idx=instance_no)
    try:
        start_http_server(int(port))
    except Exception as port_err:
        print(f"[Metrics Server Warning] Port {port}: {port_err}")

    payload_logger = setup_logger("payload_logger", "logs/payloads.log", level=logging.INFO)
    successful_payload_logger = setup_logger("successful_payload_logger", "logs/successful_payloads.json", level=logging.INFO, raw=True)
    unsuccessful_ad_logger = setup_logger("unsuccessful_ad_logger", "logs/unsuccessful_ads.json", level=logging.INFO, raw=True)
    proxy_ad_logger = setup_logger("proxy_ad_logger", "logs/proxy.log", level=logging.INFO, raw=True)
    lander_logger = setup_logger(f"{instance_no}_lander_logger", f"logs/{instance_no}_{config.network_name}_lander_logger.log")
    error_logger = setup_logger(f"{instance_no}_error_logger", f"er_logs/{instance_no}_{config.network_name}_error_logger.log")

    # Staggered start
    time.sleep(config.time_gap * (int(instance_no) - 1))

    while True:
        # Fail closed before the GET queue is read or an ad lease is created.
        _wait_for_bright_proxy(proxy_state, instance_no, lander_logger)
        single_data = pop_next_ad_from_file(file_lock, instance_no, metric, lander_logger, in_flight_dict, completed_dict)
        if single_data == "WAIT":
            time.sleep(10)
            continue
        if single_data is None:
            print(f"[Worker {instance_no}] No data available from GET_API. Waiting 1 minute...")
            time.sleep(60)
            continue

        ad_id = single_data.get("id")
        heartbeat = _LeaseHeartbeat(file_lock, in_flight_dict, ad_id, instance_no)
        heartbeat.start()
        scrape_succeeded = False
        try:
            scrape_succeeded = bool(
                scraping(
                    single_data, metric, lander_logger, port, instance_no, 0,
                    error_logger, proxy_state=proxy_state,
                )
            )
        except proxy_health.ProxyUnavailableError as proxy_error:
            single_data["_proxy_unavailable"] = True
            single_data["_proxy_unavailable_reason"] = proxy_error.reason
            if getattr(proxy_error, "currently_unavailable", True):
                proxy_health.mark_unavailable(
                    proxy_state,
                    proxy_error.reason,
                    checked_at=getattr(proxy_error, "observed_at", None),
                    country_iso=getattr(proxy_error, "country_iso", None),
                )
            lander_logger.warning(
                f"[PROXY OUTAGE] Worker {instance_no} paused ad_id={ad_id}: {proxy_error.reason}"
            )
        except Exception as loop_err:
            error_logger.error(f"[Worker {instance_no} Loop Crash] {loop_err}: {traceback.format_exc()}")
            time.sleep(5)
        finally:
            heartbeat.stop()
            if bool(single_data.get("_proxy_unavailable")):
                _release_ad_for_proxy_wait(file_lock, single_data, in_flight_dict, lander_logger)
            elif scrape_succeeded or bool(single_data.get("_terminal_reported")):
                _record_ad_completed(file_lock, ad_id, in_flight_dict, completed_dict)
            else:
                _release_ad_for_retry(file_lock, single_data, in_flight_dict, lander_logger)


def multi_chrome():
    for _dir in ["logs", "er_logs", "images", "zip", "getApi_data", "getApi_data_dev"]:
        os.makedirs(_dir, exist_ok=True)
    if os.path.isdir(_tempdir):
        for _f in os.listdir(_tempdir):
            if _f.endswith('.db'):
                try:
                    os.remove(os.path.join(_tempdir, _f))
                except Exception:
                    pass
    ins_no = [
    ("1", "8000"), ("2", "8001"), ("3", "8002"), ("4", "8003"),
    ("5", "8004"), ("6", "8005"), ("7", "8006"), ("8", "8007"),
    ("9", "8008"), ("10", "8009"), ("11", "8010"), ("12", "8011"),
    ("13", "8012"), ("14", "8013"), ("15", "8014"), ("16", "8015"),
    ("17", "8016"), ("18", "8017"), ("19", "8018"), ("20", "8019"),
    ("21", "8020"), ("22", "8021"), ("23", "8022"), ("24", "8023"),
    ("25", "8024"), ("26", "8025"), ("27", "8026"), ("28", "8027"),
    ("29", "8028"), ("30", "8029"), ("31", "8030"), ("32", "8031"),
    ("33", "8032"), ("34", "8033"), ("35", "8034"), ("36", "8035"),
    ("37", "8036"), ("38", "8037"), ("39", "8038"), ("40", "8039"),
    ("41", "8040"), ("42", "8041"), ("43", "8042"), ("44", "8043"),
    ("45", "8044"), ("46", "8045"), ("47", "8046"), ("48", "8047"),
    ("49", "8048"), ("50", "8049")
]
    # Create a single cross-process file lock shared by all workers.
    # This ensures only one worker at a time can read/pop/write the shared ad queue.
    manager = multiprocessing.Manager()
    file_lock = manager.Lock()
    in_flight_dict = manager.dict()
    completed_dict = manager.dict()
    proxy_state = manager.dict()
    proxy_state["_write_lock"] = manager.RLock()
    proxy_state["_probe_lock"] = manager.RLock()
    proxy_state["_probe_cache"] = {}
    proxy_health.initialize_state(proxy_state, enabled=config.bright_proxies)

    # Pre-load completed ads from disk if available
    completed_path = _completed_tracker_path()
    if os.path.isfile(completed_path):
        try:
            with open(completed_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    now = time.time()
                    for k, ts in saved.items():
                        if now - ts < AD_COOLDOWN_SECONDS:
                            completed_dict[int(k) if str(k).isdigit() else k] = ts
        except Exception:
            pass

    # Restore unexpired leases after a supervisor restart. Expired leases are ignored
    # and their ads may be acquired again from the API/queue.
    lease_path = _lease_tracker_path()
    expired_saved_ads = []
    if os.path.isfile(lease_path):
        try:
            with open(lease_path, "r", encoding="utf-8") as f:
                saved_leases = json.load(f)
            now = time.time()
            lease_seconds = float(config.get_default("QUEUE_LEASE_SECONDS") or 300)
            for key, info in saved_leases.items():
                if isinstance(info, (list, tuple)) and len(info) >= 2 and now - float(info[1]) < lease_seconds:
                    normalized = int(key) if str(key).isdigit() else key
                    payload = info[2] if len(info) >= 3 and isinstance(info[2], dict) else None
                    in_flight_dict[normalized] = (info[0], float(info[1]), payload)
                elif isinstance(info, (list, tuple)) and len(info) >= 3 and isinstance(info[2], dict):
                    expired_saved_ads.append(info[2])
        except Exception:
            pass
    if expired_saved_ads:
        queue_path = _shared_queue_path()
        queued = []
        if os.path.isfile(queue_path):
            try:
                with open(queue_path, "r", encoding="utf-8") as handle:
                    queued = json.load(handle)
                if not isinstance(queued, list):
                    queued = []
            except Exception:
                queued = []
        queued_ids = {item.get("id") for item in queued if isinstance(item, dict)}
        for item in expired_saved_ads:
            if item.get("id") not in queued_ids:
                queued.append(item)
                queued_ids.add(item.get("id"))
        _atomic_write_json(queue_path, queued)
    _persist_leases(in_flight_dict)

    # Every worker consumes the same proxy health snapshot. Immediate worker
    # validations are serialized and simultaneous checks are coalesced; only
    # the parent publishes UP.
    worker_args = [
        (instance_no, port, file_lock, in_flight_dict, completed_dict, proxy_state)
        for instance_no, port in ins_no[:config.instances]
    ]
    # A manager-backed queue writes synchronously through the manager process,
    # avoiding the per-worker feeder buffers that can lose their tail when a
    # long-running Pool is terminated during shutdown.
    log_queue = None
    listener = None
    proxy_monitor = None
    proxy_probe_runner = None
    p = None
    try:
        log_queue = manager.Queue(maxsize=int(config.get_default("LOG_QUEUE_MAX_RECORDS") or 20000))
        listener = daily_logging.LoggingListener(
            log_queue,
            base_dir=os.getcwd(),
            timezone=str(config.get_default("LOG_TIMEZONE") or "Asia/Kolkata"),
            date_format=str(config.get_default("LOG_DATE_FORMAT") or "%d-%m-%Y"),
            idle_seconds=float(config.get_default("LOG_HANDLER_IDLE_SECONDS") or 3600),
            daily_folders=bool(config.get_default("LOG_DAILY_FOLDERS") is not False),
        )
        p = multiprocessing.Pool(
            config.instances,
            initializer=daily_logging.install_worker_queue,
            initargs=(log_queue, float(config.get_default("LOG_QUEUE_PUT_TIMEOUT_SECONDS") or 2)),
        )
        if config.bright_proxies:
            # Keep the monitor's network call in one reusable spawn-process.
            # If DNS or the socket stack wedges, the process is terminated at
            # a hard deadline and recreated on the next health cycle.
            proxy_probe_runner = proxy_health.IsolatedProbeRunner()
            proxy_probe_runner.start()
        # Start the listener thread only after Pool workers have been forked/spawned.
        # Forking a process while a parent thread is already active is unsafe on Linux.
        listener.start()

        if config.bright_proxies:
            def _monitor_transition(current, _previous):
                event = "PROXY RECOVERED" if current.get("available") else "PROXY DOWN"
                message = f"[{event}] Bright Data health: {current.get('reason', 'unknown')}"
                print(message)
                try:
                    # Keep parent monitor writes separate from worker proxy.log
                    # rotation to avoid independent handlers racing on Windows.
                    proxy_health_logger.info(json.dumps({
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "event": event.lower().replace(" ", "_"),
                        "available": bool(current.get("available")),
                        "reason": current.get("reason", ""),
                        "egress_ip": current.get("egress_ip", ""),
                        "egress_country": current.get("egress_country", ""),
                        "checked_country": current.get("checked_country", ""),
                        "down_country": current.get("down_country", ""),
                    }, ensure_ascii=False))
                except Exception:
                    pass

            proxy_monitor = proxy_health.ProxyHealthMonitor(
                proxy_state,
                # This isolated checker is independent of worker probe locks, so
                # worker country checks cannot delay the <=10-second cadence.
                checker=proxy_probe_runner,
                country_iso=config.get_default("PROXY_HEALTH_COUNTRY") or "us",
                interval_seconds=_proxy_check_interval_seconds(),
                timeout_seconds=_proxy_check_timeout_seconds(),
                on_transition=_monitor_transition,
            )
            proxy_monitor.start()
        p.map(main, worker_args, chunksize=1)
    except KeyboardInterrupt:
        print("\n[Shutdown] Terminating scraper workers...")
    finally:
        if proxy_monitor is not None:
            proxy_monitor.stop(timeout=_proxy_check_timeout_seconds() + 2.0)
        if proxy_probe_runner is not None:
            proxy_probe_runner.close()
        if p is not None:
            p.terminate()
            p.join()
        if listener is not None and listener.thread.is_alive():
            try:
                listener.stop(timeout=30)
            except Exception as log_shutdown_error:
                print(f"[Logging Shutdown Warning] {log_shutdown_error}", file=sys.stderr)
        elif listener is not None:
            listener.router.close()
        if log_queue is not None:
            try:
                log_queue.close()
                log_queue.join_thread()
            except Exception:
                pass
        manager.shutdown()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    multi_chrome()
