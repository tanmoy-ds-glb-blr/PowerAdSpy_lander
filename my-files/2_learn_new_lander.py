"""
====================================================================================================
                        LEARNING GUIDE & ANNOTATED CODEBASE: new_lander.py
====================================================================================================
Project Name : PowerAdSpy_landers
File         : learn/2_learn_new_lander.py (Educational replica of new_lander.py)
Author       : Antigravity AI Code Analysis Engine
Target       : Developers & Engineers learning the PowerAdSpy Landing Page Scraper

----------------------------------------------------------------------------------------------------
PURPOSE OF THIS SCRIPT:
----------------------------------------------------------------------------------------------------
This script is the central engine of the PowerAdSpy Landers Scraper. It acts as a high-performance,
multiprocessing coordinator that:
  1. Pulls batches of advertisements from a centralized API (GET_API) for various networks (FB, IG, etc.).
  2. Queues them in an atomic shared file on disk protected by cross-process locks.
  3. Spawns N parallel workers, each managing an automated Playwright Chromium browser.
  4. Routes network traffic through Bright Data geo-targeted proxies matching the target country ISO.
  5. Implements anti-bot evasion (stealth scripts, human scrolling, cookie modal dismissals).
  6. Analyzes pages for dead/404/WAF/login errors (distinguishing Status 2 success vs Status 3 failure).
  7. Captures full-page screenshots (compressed to JPEG < 1MB), localizes HTML/assets, extracts clean text,
     traces redirects, and determines domain registration age via WHOIS.
  8. Uploads media to AWS S3 and posts final structured JSON payloads to the database INSERT API.
  9. Exposes Prometheus metrics on ports 8000-8049 for live Grafana dashboard monitoring.

----------------------------------------------------------------------------------------------------
HOW TO RUN THIS SCRIPT:
----------------------------------------------------------------------------------------------------
  Local Windows Terminal:
    > venv\\Scripts\\activate
    > python new_lander.py

  Linux / VM / Docker:
    $ ./start_process.sh
    # or inside Docker container:
    $ Xvfb :99 -screen 0 1280x800x24 & export DISPLAY=:99; python3 -u new_lander.py

----------------------------------------------------------------------------------------------------
EXPECTED CONSOLE OUTPUT EXAMPLE:
----------------------------------------------------------------------------------------------------
  [Worker 1] Shared queue empty. Fetching new batch from GET_API...
  Taking data from GET_API
  [Worker 1] Ingested 50 ads from GET_API: 50 ready to scrape, 0 in-flight, 0 in cooldown.
  [QUEUE] Worker 1 popped ad_id=1023912 | 49 ads remaining in shared queue
  [PROXY] iso=us   | Playwright & requests proxy set -> brd.superproxy.io:44445
  [PROXY CHECK] iso=us | egress_ip=198.51.100.42 | country=US
  [INFO] Using domain date from Facebook API for example.com: 2021-04-15
  [Worker 1] [SUCCESS STATUS=2] Successfully scraped & inserted ad_id=1023912 | ISO: us
====================================================================================================
"""

import sys

# --------------------------------------------------------------------------------------------------
# 1. CONSOLE ENCODING SAFETY (UTF-8 RECONFIGURATION)
# --------------------------------------------------------------------------------------------------
# Why this is needed:
# Windows command prompts default to legacy code pages like cp1252 or cp437. When printing foreign
# characters (e.g. Japanese, Arabic, Russian emojis, or French accents found in scraped page titles),
# standard Python print() raises 'UnicodeEncodeError: 'charmap' codec can't encode character...'.
# reconfigure(encoding="utf-8", errors="replace") guarantees the script never crashes on stdout prints.
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
from multiprocessing_logging import install_mp_handler
from PIL import Image  # Load Pillow first to prevent C-extension conflicts in Python 3.10
from helper import init, domaindate, screenshot, outgoing_url, redirect, text, html, scrape_ad_category
from logging.handlers import RotatingFileHandler
from prometheus_client import start_http_server, multiprocess, REGISTRY, generate_latest, Counter
from config import Config
import traceback

# --------------------------------------------------------------------------------------------------
# 2. GLOBAL CONFIGURATION & DIRECTORY INITIALIZATION
# --------------------------------------------------------------------------------------------------
# Load configuration from config.yaml via the Config singleton in config.py
config = Config()

# Guarantee all essential scratchpads and logging folders exist before any worker starts
for _dir in ["logs", "er_logs", "images", "zip", "getApi_data", "getApi_data_dev"]:
    os.makedirs(_dir, exist_ok=True)

# Prometheus multiprocess directory:
# When using Python multiprocessing, each worker needs a shared disk location to aggregate metrics.
_tempdir = os.environ.get('prometheus_multiproc_dir')
if not _tempdir or not os.path.isdir(_tempdir):
    _tempdir = os.path.join(tempfile.gettempdir(), "prometheus_multiproc")
    os.makedirs(_tempdir, exist_ok=True)
    os.environ['prometheus_multiproc_dir'] = _tempdir

error_count = 0

# --------------------------------------------------------------------------------------------------
# 3. WAF & ANTI-BOT SIGNATURES (Raw HTML & Frame Inspection)
# --------------------------------------------------------------------------------------------------
# These signatures appear inside <script> IDs, <iframe> sources, hidden divs, or WAF challenge pages.
# Unlike visible text, these must be checked against page.content() (the full raw DOM).
BOT_OR_WAF_MARKERS = (
    "challenges.cloudflare.com",
    "cf-browser-verification",
    "cf-challenge",
    "challenge-platform",
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

# --------------------------------------------------------------------------------------------------
# 4. DEAD & ERROR PAGE MARKERS (Visible Text Only)
# --------------------------------------------------------------------------------------------------
# CRITICAL ARCHITECTURAL DECISION:
# These phrases are checked ONLY against page.inner_text('body') — the text a human actually sees.
# Why? Healthy e-commerce sites (e.g. Puma, Nike, Amazon) often embed translation bundles inside
# <script> tags that contain every possible error string ("404 not found", "page does not exist").
# If checked against page.content(), healthy stores would be falsely skipped!
DEAD_PAGE_TEXT_MARKERS = (
    # 404 / Missing pages
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
    # 403 Forbidden / Access denied
    "access denied",
    "you don't have permission to access",
    "request blocked",
    "403 forbidden",
    "http 403",
    # 5xx Server errors
    "500 internal server error",
    "502 bad gateway",
    "503 service temporarily unavailable",
    "503 service unavailable",
    "504 gateway time-out",
    "504 gateway timeout",
    # Chrome internal error messages
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
    # Expired / parked domains
    "this domain is for sale",
    "buy this domain",
    "domain has expired",
    "parked free, courtesy of",
    "domain parked by",
    "this account has been suspended",
    "account has been suspended",
)

BLOCKED_PAGE_MARKERS = BOT_OR_WAF_MARKERS + DEAD_PAGE_TEXT_MARKERS

BLOCKED_TITLE_MARKERS = (
    "404", "not found", "page not found", "site not found",
    "403 forbidden", "access denied", "request blocked",
    "500 internal server", "502 bad gateway", "503 service unavailable",
    "504 gateway time", "attention required", "just a moment",
    "suspended domain", "account suspended", "domain parked",
    "this site can't be reached", "server error"
)

# --------------------------------------------------------------------------------------------------
# 5. DYNAMIC STATUS 3 KEYWORDS AUTO-RELOADER
# --------------------------------------------------------------------------------------------------
# Allows operations and QA teams to add new blocked/dead-page phrases to status_3_keywords.txt on disk.
# The function checks os.path.getmtime() and automatically refreshes in-memory cache without needing
# to restart 20-50 running worker processes!
STATUS3_KEYWORDS_FILES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "status_3_keywords.txt"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "status3_keywords.txt"),
]
_cached_status3_keywords = []
_last_status3_mtime = 0

def get_status3_keywords():
    """
    Returns list of lowercase keywords from status_3_keywords.txt.
    Auto-refreshes if the modification time on disk changes.
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


def get_country(single_data):
    """
    Extracts the two-letter ISO country code from the API ad object.
    
    Sample Input single_data:
        {"id": 101, "iso": ["US", "CA"], "destination_url": "https://example.com"}
    Output:
        'us' (or fallback 'us' if no supported code matched)
    """
    raw_iso = single_data.get("iso") or []
    if isinstance(raw_iso, str):
        raw_iso = [raw_iso]

    for value in raw_iso:
        country = str(value).strip().lower()
        if country in SUPPORTED_COUNTRIES:
            return country
    return "us"


# --------------------------------------------------------------------------------------------------
# 6. COMPREHENSIVE PAGE STATUS EVALUATOR
# --------------------------------------------------------------------------------------------------
def check_page_status(page):
    """
    Evaluates whether the loaded page is an error, 404, blocked, or dead page.
    Returns: (is_bad: bool, reason: str)

    Execution Sequence:
      1. Browser internal error URL (chrome-error://, about:blank, chromewebdata).
      2. HTTP response status >= 400 using Navigation Timing API.
      3. <title> text matching known error titles.
      4. Raw page HTML matching Bot/WAF challenge signatures.
      5. Rendered visible body text matching dead page markers.
      6. Child iframe visible text inspection.
      7. Dynamic keywords from status_3_keywords.txt.
      8. Completely empty DOM check (0 text, 0 images after SPA wait).
    """
    try:
        current_url = (page.url or "").lower().strip()

        # Step 1: Chrome internal error URLs
        if current_url.startswith(("chrome-error://", "about:blank", "data:text/html,chromewebdata")):
            return True, f"Browser error URL: {current_url[:60]}"

        # Step 2: HTTP status code via Navigation Timing API (catches 404, 500, etc.)
        try:
            status = page.evaluate(
                "(() => (window.performance.getEntriesByType('navigation')[0] || {}).responseStatus)()"
            )
            if status and int(status) >= 400:
                return True, f"HTTP Error Status {status}"
        except Exception:
            pass

        # Step 3: Check Page Title
        title = (page.title() or "").lower().strip()
        for marker in BLOCKED_TITLE_MARKERS:
            if marker in title:
                return True, f"Title indicates error: '{marker}'"

        # Step 4: Check raw HTML source for Bot/WAF challenge signatures
        try:
            page_source = (page.content() or "").lower()
            for marker in BOT_OR_WAF_MARKERS:
                if marker in page_source:
                    return True, f"Bot/WAF block detected: '{marker}'"
        except Exception:
            pass

        # Step 5: Check VISIBLE rendered body text (avoids JS script false positives)
        try:
            body_text = page.inner_text("body", timeout=5000).strip().lower()
            
            # Step 5b: Also extract text from child frames (e.g. Incapsula/Cloudflare challenge iframes)
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

            # Step 5c: Check dynamic status_3_keywords.txt
            page_src_lower = ""
            try:
                page_src_lower = (page.content() or "").lower()
            except Exception:
                pass

            for marker in get_status3_keywords():
                if marker and (marker in combined_text or marker in title or (page_src_lower and marker in page_src_lower)):
                    return True, f"Status 3 keyword matched: '{marker}'"

            # Step 5d: Sparse body safety net (very short body with error words)
            if len(body_text) < 30 and any(err in body_text for err in ("404", "error", "not found", "forbidden")):
                return True, f"Sparse error body: '{body_text[:60]}'"

            # Step 6: Empty page check (HTTP 200 returned but blank white screen)
            try:
                def _is_empty_dom():
                    return page.evaluate("""() => {
                        let text = (document.body ? (document.body.innerText || document.body.textContent) : '')
                            .replace(/[\\s\\u200b\\u200c\\u200d\\ufeff]+/g, '').trim();
                        let mediaCount = document.querySelectorAll('img, iframe, svg, canvas, video, picture, embed, object').length;
                        return text.length === 0 && mediaCount === 0;
                    }""")

                if _is_empty_dom():
                    # Give client-side SPAs (React, Next.js) 2.5s to mount before confirming blank
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
    """Convenience boolean wrapper around check_page_status."""
    is_bad, _ = check_page_status(page)
    return is_bad


# --------------------------------------------------------------------------------------------------
# 7. AUTH & LOGIN WALL DETECTION (Status 2 vs Status 3 Gating)
# --------------------------------------------------------------------------------------------------
# Distinguishes genuine auth gates (which must be marked Status 3) from normal product pages that
# simply have a small "Login" button in their navbar (which must remain Status 2).
LOGIN_URL_PATH_REGEX = re.compile(
    r'(^|/)(log-?in|sign-?in|sign-?up|register|registration|customer/account/login|customer/account/create|accounts?/login|users?/login|member-login|portal/login|session/new|checkpoint)( |/|\.php|\.html|\.asp|\?|$)',
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
    r'^\s*(log\s?in|sign\s?in|sign\s?up|create\s+(an?\s+)?account|register|registration|member\s+login|customer\s+login|client\s+login|user\s+login) ',
    r' (log\s?into?\s+facebook|login\s*[•·-]\s*instagram|sign\s?in\s*[–—-]\s*google\s*accounts|welcome\s*back\s*[–—-]\s*log\s*in) ',
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
    Evaluates whether the destination page is a dedicated login/auth gate (status 3).
    Returns: (is_login: bool, reason: str)
    """
    try:
        if not final_url and page:
            try:
                final_url = page.url or ""
            except Exception:
                final_url = ""

        f_url_lower = (final_url or "").lower().strip()

        # Check 1: Dedicated SSO / OAuth redirect domains (Google Accounts, Okta, Clerk)
        if f_url_lower:
            parsed = urllib.parse.urlparse(f_url_lower)
            netloc = parsed.netloc
            path = parsed.path.rstrip("/")
            query = parsed.query

            for host in LOGIN_AUTH_HOSTS:
                if host in netloc:
                    return True, f"Redirected to auth provider: {netloc}"

            # Platform social login checkpoints
            if "facebook.com" in netloc and ("/login" in path or "/checkpoint" in path):
                return True, f"Facebook login checkpoint: {path}"
            if "instagram.com" in netloc and "/accounts/login" in path:
                return True, f"Instagram login checkpoint: {path}"
            if ("twitter.com" in netloc or "x.com" in netloc) and ("/login" in path or "/i/flow/login" in path):
                return True, f"X/Twitter login checkpoint: {path}"
            if "linkedin.com" in netloc and ("/login" in path or "/checkpoint" in path):
                return True, f"LinkedIn login checkpoint: {path}"

            # Query parameters indicating auth redirects (e.g. redirect_to=...)
            if any(p in query for p in ("redirect_to=", "return_url=", "next=", "continue=")) and any(k in path for k in ("/login", "/signin", "/auth")):
                return True, f"Auth redirect query parameter: {path}?{query[:50]}"

            # Explicit login URL path pattern
            if LOGIN_URL_PATH_REGEX.search(path):
                if not any(k in path for k in ("product", "collection", "shop", "item", "article", "blog")):
                    return True, f"Login/Signup URL path detected: {path}"

        # Check 2: Word count filter (e-commerce catalogs have > 500 words; login gates are sparse < 200)
        ret_text_lower = (ret_text or "").lower()
        word_count = len(ret_text_lower.split()) if ret_text_lower else 9999

        # Check 3: Page Title on sparse pages
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

        # Check 4: Visible DOM Password input on sparse pages
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
                        /^(log\\s?in|sign\\s?in|sign\\s?up|create\\s+(an?\\s+)?account|register|registration|welcome\\s+back)$/i.test(h)
                    );

                    const buttons = Array.from(document.querySelectorAll('button[type="submit"], input[type="submit"], form button')).map(b => (b.innerText || b.value || '').toLowerCase().trim());
                    const hasAuthButton = buttons.some(b => 
                        /^(log\\s?in|sign\\s?in|sign\\s?up|create\\s+account|register)$/i.test(b)
                    );

                    return { hasPassword, hasAuthForm, hasAuthHeading, hasAuthButton };
                }""")
                if dom_auth:
                    if dom_auth.get("hasPassword") and (dom_auth.get("hasAuthForm") or dom_auth.get("hasAuthHeading") or dom_auth.get("hasAuthButton")):
                        return True, f"Gated login page (visible password field on sparse page with {word_count} words)"
            except Exception:
                pass

        # Check 5: Explicit text markers
        if ret_text_lower:
            for marker in LOGIN_TEXT_MARKERS:
                if marker in ret_text_lower:
                    return True, f"Login text marker matched: '{marker}'"

        return False, None
    except Exception:
        return False, None


class BlockedPageException(Exception):
    """Raised when a blocked, 404, or dead landing page is encountered."""
    pass


# --------------------------------------------------------------------------------------------------
# 8. PROMETHEUS METRICS CLASS
# --------------------------------------------------------------------------------------------------
class Metrics(object):
    """
    Manages Prometheus counters for Grafana monitoring.
    Each worker exposes its metrics on its assigned port (8000 to 8049).
    """
    def __init__(self, idx):
        self._tempdir = _tempdir
        self._registry = REGISTRY
        try:
            self._multiprocess_registry = multiprocess.MultiProcessCollector(self._registry, self._tempdir)
        except Exception:
            pass
        net = config.network_name
        self.processed_configured_lander_url = Counter(
            f'processed_{net}_lander_url_count', f'Number of {net} urls processed',
            ['port', 'status', 'error'], registry=None
        )
        self.updated_configured_lander = Counter(
            f'updated_{net}_lander_count', f'Updated {net} Landers based on API response',
            ['port', 'message'], registry=None
        )
        self.configured_lander_get = Counter(
            f'{net}_lander_get_count', 'get api not giving data', ['data'], registry=None
        )
        # Aliases
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


# --------------------------------------------------------------------------------------------------
# 9. SERP REDIRECT RESOLVER
# --------------------------------------------------------------------------------------------------
def resolve_ad_redirect(url, timeout=10):
    """
    Pre-resolves ad redirect wrappers (e.g. google.com/goto?url=... or googleadservices.com)
    using direct unproxied HTTP requests BEFORE launching Playwright.
    
    Why: Bright Data proxies reject crawling Google SERP domains (returns 403 Forbidden SERP Domain /
    ERR_TUNNEL_CONNECTION_FAILED). Pre-resolving via Python direct HTTP bypasses this restriction!
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
                        target = urllib.parse.urljoin(curr, target)
                    redirects.append(curr)
                    curr = target
                    if not any(marker in curr.lower() for marker in ("google.com/goto", "google.co.in/goto", "googleadservices.com")):
                        break
                else:
                    break
        except Exception:
            pass

    return curr, redirects


# --------------------------------------------------------------------------------------------------
# 10. SCRAPING PIPELINE (Single Ad Execution)
# --------------------------------------------------------------------------------------------------
def scraping(single_data, metric, lander_logger, port, instance_no, count, error_logger):
    """
    Core scraping worker execution for a single ad dictionary.
    Coordinates browser launch -> navigation -> verification -> extraction -> S3 -> database insert.
    """
    global error_count
    page = None
    r_session = None

    try:
        country = get_country(single_data)
        countries = [country]
        ad_id = single_data.get('id', 0)
        destination_url = str(single_data.get('destination_url') or "").replace("\\", "").strip()

        # Guard: Check for empty destination URL
        if not destination_url:
            lander_logger.warning(f"[SKIPPED] ad_id={ad_id} has empty destination_url")
            metric.processed_configured_lander_url.labels(port=port, status="skipped", error="Empty destination_url").inc()
            log_unsuccessful_ad(single_data, "Empty destination_url")
            send_status3_payload(ad_id, countries[0], destination_url, "Empty destination_url", lander_logger)
            return False

        payload_list = []

        # 1. Initialize Playwright Chrome + Bright Data proxy for the ad's country ISO
        init_result = init.init_dc(countries[0])
        if init_result is None:
            time.sleep(5)
            init_result = init.init_dc(countries[0])
        if init_result is None:
            log_unsuccessful_ad(single_data, "Chrome initialization failed")
            raise RuntimeError(f"Chrome initialization failed for country={countries[0]}")
        page, r_session = init_result

        # Log active proxy info linked to this ad into logs/proxy.log
        log_proxy_ad(single_data, r_session, countries[0])

        # 2. Pre-resolve ad redirect wrappers
        nav_url, initial_redirects = resolve_ad_redirect(destination_url)
        if initial_redirects:
            lander_logger.info(f"[REDIRECT PRE-RESOLVED] ad_id={ad_id} | {destination_url[:80]} -> {nav_url[:80]}")

        # 3. Navigate with retry for transient proxy tunnel blips
        nav_success = False
        nav_err = None
        for nav_attempt in range(2):
            try:
                page.goto(nav_url.strip(), timeout=90000, wait_until='domcontentloaded')
                time.sleep(random.uniform(1.0, 2.0))
                nav_success = True
                break
            except Exception as e:
                nav_err = e
                err_str = str(e)
                if nav_attempt == 0 and any(k in err_str for k in ["ERR_TUNNEL_CONNECTION_FAILED", "ERR_PROXY_CONNECTION_FAILED", "ERR_CONNECTION_RESET"]):
                    lander_logger.warning(f"[PROXY RETRY] ad_id={ad_id} | retrying page.goto after proxy blip")
                    time.sleep(2.0)
                    continue
                break

        if not nav_success:
            nav_err_str = str(nav_err)
            reason = "Timeout" if "Timed out" in nav_err_str else "Connection Error / Unreachable"
            lander_logger.warning(f"[SKIPPED UNREACHABLE] ad_id={ad_id} | reason={reason} | url={nav_url}")
            log_unsuccessful_ad(single_data, reason)
            send_status3_payload(ad_id, countries[0], destination_url, reason, lander_logger)
            metric.processed_configured_lander_url.labels(port=port, status="skipped", error=reason).inc()
            init.close_browser(page)
            return False

        f_url = page.url

        # 4. Immediate page status check (catches 404s, WAF challenges immediately)
        is_bad, reason = check_page_status(page)
        if is_bad:
            lander_logger.warning(f"[SKIPPED BAD/BLOCKED PAGE] ad_id={ad_id} | reason={reason} | url={f_url}")
            log_unsuccessful_ad(single_data, reason, final_url=f_url)
            metric.processed_configured_lander_url.labels(port=port, status="skipped", error=reason).inc()
            send_status3_payload(ad_id, countries[0], destination_url, reason, lander_logger)
            init.close_browser(page)
            return False

        # 5. Domain registration date lookup (WHOIS)
        ret_domain_date, ret_domain_age = domaindate.get(f_url, network=config.network_name) or ("", None)
        if not ret_domain_date:
            ret_domain_date = "1970-01-01"
        ret_status = 2

        # 6. Execute controller to capture screenshot, HTML, text, and outgoing links
        try:
            ret_redirects, final_url, ret_screenshot, ret_text, ret_outgoing, ret_html, category_list = controller(
                page, nav_url, instance_no, r_session, f_url
            )
            if initial_redirects:
                ret_redirects = initial_redirects + [r for r in ret_redirects if r not in initial_redirects]
        except BlockedPageException as b_err:
            reason = str(b_err)
            lander_logger.warning(f"[SKIPPED BAD/BLOCKED PAGE] ad_id={ad_id} | reason={reason} | url={f_url}")
            log_unsuccessful_ad(single_data, reason, final_url=f_url)
            metric.processed_configured_lander_url.labels(port=port, status="skipped", error=reason).inc()
            send_status3_payload(ad_id, countries[0], destination_url, reason, lander_logger)
            init.close_browser(page)
            return False

        # Guard: Check for empty text or PDF download
        if not isinstance(ret_text, str) or not ret_text.strip():
            reason = "Direct PDF download" if final_url.lower().endswith('.pdf') else f"Empty HTML content -- ad_id={ad_id}"
            lander_logger.warning(f"[SKIPPED EMPTY/PDF] ad_id={ad_id} | reason={reason} | url={final_url}")
            log_unsuccessful_ad(single_data, reason, final_url=final_url)
            metric.processed_configured_lander_url.labels(port=port, status="skipped", error=reason).inc()
            send_status3_payload(ad_id, countries[0], destination_url, reason, lander_logger)
            init.close_browser(page)
            return False

        # 7. Post-scrape status classification (Login wall or Status 3 keywords)
        is_login, login_reason = is_login_or_signup_page(page, destination_url, final_url, ret_text)

        matched_status3_kw = None
        ret_text_lower = ret_text.lower()
        for kw in get_status3_keywords():
            if kw in ret_text_lower:
                matched_status3_kw = kw
                break

        if is_login or matched_status3_kw:
            ret_status = 3
            reason = login_reason if is_login else f"Status 3 keyword matched: '{matched_status3_kw}'"
            lander_logger.warning(f"[STATUS 3 SCRAPED] ad_id={ad_id} | reason={reason} | url={final_url}")
            log_unsuccessful_ad(single_data, reason, final_url=final_url)
            metric.processed_configured_lander_url.labels(port=port, status="status_3", error=reason).inc()
        else:
            ret_status = 2

        # 8. S3 media upload (screenshot & html zip)
        try:
            pay = make_payload(ad_id, countries[0], instance_no, ret_redirects, final_url, ret_screenshot, ret_text,
                               ret_outgoing, ret_domain_date, ret_domain_age, ret_status, ret_html, category_list, lander_logger)
            payload_list.append(pay)
        except Exception as upload_err:
            reason = f"Upload API failed: {upload_err}"
            lander_logger.warning(f"[UPLOAD API FAILED] ad_id={ad_id} | reason={upload_err}")
            log_unsuccessful_ad(single_data, reason, final_url=final_url)
            metric.processed_configured_lander_url.labels(port=port, status="fail", error="Upload API failed").inc()
            send_status3_payload(ad_id, countries[0], destination_url, str(upload_err)[:120], lander_logger)
            init.close_browser(page)
            return False

        # 9. Database insert via INSERT API
        if not send_payload(payload_list, lander_logger, port, metric):
            reason = "Insert API failed"
            lander_logger.warning(f"[INSERT API FAILED] ad_id={ad_id} | url={final_url}")
            log_unsuccessful_ad(single_data, reason, final_url=final_url)
            metric.processed_configured_lander_url.labels(port=port, status="fail", error=reason).inc()
            send_status3_payload(ad_id, countries[0], destination_url, reason, lander_logger)
            init.close_browser(page)
            return False

        metric.processed_configured_lander_url.labels(port=port, status="pass", error="None").inc()
        error_count = 0
        init.close_browser(page)
        return True

    except Exception as error:
        error_str = str(error)
        lander_logger.error(f"[Worker {instance_no} Exception] ad_id={single_data.get('id')}: {error_str}")
        error_logger.error(error_str)
        try:
            _aid = single_data.get('id', 0)
            _iso = get_country(single_data)
            _dest = single_data.get('destination_url', '')
            send_status3_payload(_aid, _iso, _dest, error_str[:120], lander_logger)
        except Exception:
            pass
        init.close_browser(page)
        return False


# --------------------------------------------------------------------------------------------------
# 11. DEDICATED LOGGERS SETUP
# --------------------------------------------------------------------------------------------------
def setup_logger(name, filename, level=logging.INFO, max_bytes=52_428_800, backups=50, raw=False):
    """Initializes a rotating file logger (50 MB per file, 50 backups)."""
    dir_name = os.path.dirname(filename)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        try:
            handler = RotatingFileHandler(filename, encoding="utf-8", maxBytes=max_bytes, backupCount=backups)
            formatter = logging.Formatter("%(message)s") if raw else logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        except Exception as e:
            fallback = logging.StreamHandler()
            logger.addHandler(fallback)
    return logger

payload_logger = setup_logger("payload_logger", "logs/payloads.log", level=logging.INFO)
successful_payload_logger = setup_logger("successful_payload_logger", "logs/successful_payloads.json", level=logging.INFO, raw=True)
unsuccessful_ad_logger = setup_logger("unsuccessful_ad_logger", "logs/unsuccessful_ads.json", level=logging.INFO, raw=True)
proxy_ad_logger = setup_logger("proxy_ad_logger", "logs/proxy.log", level=logging.INFO, raw=True)

def log_unsuccessful_ad(single_data, reason, final_url=None):
    """Logs raw ad object with reason to logs/unsuccessful_ads.json."""
    try:
        entry = {
            "ad_id": single_data.get("id") or single_data.get("ad_id", 0),
            "reason": reason,
            "destination_url": single_data.get("destination_url", ""),
            "final_url": final_url or single_data.get("destination_url", ""),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "raw_ad": single_data
        }
        unsuccessful_ad_logger.info(json.dumps(entry, ensure_ascii=False))
    except Exception:
        pass

def log_proxy_ad(single_data, r_session, country_iso):
    """Logs egress IP and proxy parameters to logs/proxy.log."""
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
    except Exception:
        pass


# --------------------------------------------------------------------------------------------------
# 12. S3 UPLOAD & PAYLOAD CONSTRUCTION
# --------------------------------------------------------------------------------------------------
def make_payload(ad_id, iso, instance_no, ret_redirects, final_url, ret_screenshot,
                 ret_text, ret_outgoing, ret_domain_date, ret_domain_age,
                 ret_status, ret_html, category_list, lander_logger):
    """
    Constructs the final ad payload dictionary and uploads media files to AWS S3 via S3_API.
    
    Sample Resulting Payload Structure:
    {
        "ad_id": 1023912,
        "redirects": ["https://ad.link", "https://store.com/promo"],
        "outgoing_url": [{"start_url": "https://privacy.org", "destination_url": "...", "redirect_urls": []}],
        "destinations": "https://store.com/product/123",
        "country_iso": "us",
        "html_path": "https://s3.amazonaws.com/.../html.zip",
        "html_content": "Extracted visible text...",
        "screen_shot": "https://s3.amazonaws.com/.../screenshot.jpg",
        "status": 2,
        "domain_age": 1,
        "domain_registered_date": "2021-04-15",
        "IsDataCenterProxy": 1,
        "crawled_by": "python",
        "ad_category": []
    }
    """
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

    try:
        if not os.path.isfile(ret_screenshot) or os.path.getsize(ret_screenshot) == 0:
            raise RuntimeError(f"Screenshot is missing or empty -- ad_id={ad_id}")

        zip_file = None
        with open(ret_screenshot, 'rb') as img:
            s3_upload_status = '2' if ret_status == 3 else str(ret_status)
            form_data_payload = {
                'media': ('img.jpg', img, 'image/jpeg'),
                'ad_id': (None, str(ad_id)),
                'status': (None, s3_upload_status),
                'country': (None, str(iso)),
            }

            # Facebook upload endpoint only takes a single file ('media').
            # Attaching 'zip' on Facebook causes the backend to overwrite image_path with the zip path!
            if config.network_name != "facebook" and ret_html and os.path.isfile(ret_html) and os.path.getsize(ret_html) > 0:
                zip_file = open(ret_html, 'rb')
                form_data_payload['zip'] = ('file.zip', zip_file, 'application/zip')

            try:
                api_url = config.get_api("DEV_S3_API") if config.dev_mode else config.get_api("MAIN_S3_API")
                payload_logger.info(f"[S3 UPLOAD REQUEST] ad_id={ad_id} | instance={instance_no} | url={api_url}")
                res = requests.post(api_url, files=form_data_payload, timeout=REQUEST_TIMEOUT)
            finally:
                if zip_file:
                    zip_file.close()

            try:
                x = res.json()
            except Exception:
                x = {"raw": res.text}

            payload_logger.info(f"[S3 UPLOAD RESPONSE] ad_id={ad_id} | HTTP {res.status_code} | response={json.dumps(x, ensure_ascii=False)}")
            if not res.ok or str(x.get("code")) != "200":
                raise RuntimeError(f"Upload API failed: HTTP={res.status_code}, response={x}")

            payload["screen_shot"] = x.get("image_path", "")
            payload["html_path"] = x.get("html_path", "")
            if not payload["screen_shot"] and ret_status != 3:
                raise RuntimeError(f"Upload API returned missing image_path -- ad_id={ad_id}, response={x}")

    finally:
        # Clean up ephemeral instance images and zips from disk
        for folder_path in [f'./images/{instance_no}', f'./zip/{instance_no}']:
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path, ignore_errors=True)

    return payload


# --------------------------------------------------------------------------------------------------
# 13. DATABASE INSERT API DISPATCHER
# --------------------------------------------------------------------------------------------------
def send_payload(payload_list, lander_logger, port, metric):
    """
    Submits structured JSON payload to DEV_INSERT_API or MAIN_INSERT_API.
    Includes smart fallback: if the staging database throws ER_DATA_TOO_LONG on columns like
    white_ad_screenshot or white_ad_lander, it trims fields to column limits and retries!
    """
    try:
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        api_url = config.get_api("DEV_INSERT_API") if config.dev_mode else config.get_api("MAIN_INSERT_API")

        res_json = {}
        for p in payload_list:
            body = {"ad_id": p["ad_id"], "insertData": p}
            status_val = p.get("status", 2)
            if status_val == 2:
                successful_payload_logger.info(json.dumps(body, ensure_ascii=False))
            payload_logger.info(f"[INSERT API REQUEST] ad_id={p['ad_id']} | status={status_val} | url={api_url}")

            res = requests.post(api_url, data=json.dumps(body), headers=headers, timeout=REQUEST_TIMEOUT)

            try:
                res_json = res.json()
            except Exception:
                res_json = {"raw": res.text}

            payload_logger.info(f"[INSERT API RESPONSE] ad_id={p['ad_id']} | HTTP {res.status_code} | response={json.dumps(res_json, ensure_ascii=False)}")
            
            # Fallback for database column length overflow
            if not res.ok or str(res_json.get("code")) != "200":
                if "ER_DATA_TOO_LONG" in str(res_json) or "white_ad_lander" in str(res_json) or "white_ad_screenshot" in str(res_json):
                    lander_logger.warning(f"[RETRY INSERT API] ad_id={p['ad_id']} retrying with trimmed fields...")
                    p_retry = dict(p)
                    if "white_ad_lander" in str(res_json):
                        p_retry["html_path"] = ""
                    if "white_ad_screenshot" in str(res_json):
                        orig_shot = p_retry.get("screen_shot", "")
                        base_shot = os.path.basename(orig_shot)
                        p_retry["screen_shot"] = base_shot[:45]
                    body_retry = {"ad_id": p["ad_id"], "insertData": p_retry}
                    res_retry = requests.post(api_url, data=json.dumps(body_retry), headers=headers, timeout=REQUEST_TIMEOUT)
                    try:
                        res_json_retry = res_retry.json()
                    except Exception:
                        res_json_retry = {"raw": res_retry.text}
                    if res_retry.ok and str(res_json_retry.get("code")) == "200":
                        p.update(p_retry)
                        res_json = res_json_retry
                        continue
                raise RuntimeError(f"Insert API failed: HTTP={res.status_code}, response={res_json}")

        metric.updated_configured_lander.labels(port=port, message=res_json.get('message', 'no message')).inc()
        return True

    except Exception as e:
        lander_logger.info(json.dumps({"error": str(e)}, ensure_ascii=False))
        metric.updated_configured_lander.labels(port=port, message="insertion error").inc()
        return False


def send_status3_payload(ad_id, country_iso, destination_url, reason, lander_logger):
    """
    Submits a minimal status=3 error payload to INSERT_API.
    Informs backend to mark ad as blocked/skipped so it is NOT fetched again indefinitely.
    """
    try:
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
        res = requests.post(api_url, data=json.dumps(body), headers=headers, timeout=REQUEST_TIMEOUT)
        try:
            res_json = res.json()
        except Exception:
            res_json = {"raw": res.text}
        payload_logger.info(f"[STATUS 3 INSERT RESPONSE] ad_id={ad_id} | HTTP {res.status_code} | response={json.dumps(res_json, ensure_ascii=False)}")
    except Exception as e:
        lander_logger.error(f"[STATUS=3] Failed to post status=3 for ad_id={ad_id}: {e}")


# --------------------------------------------------------------------------------------------------
# 14. HELPER CONTROLLER DISPATCHER
# --------------------------------------------------------------------------------------------------
def controller(page, destination_url, instance_no, r_session, f_url):
    """
    Orchestrates the individual helper components for a loaded page:
      1. Verify page status is still valid.
      2. Trace HTTP redirects via helper/redirect.py.
      3. Capture full-page screenshot via helper/screenshot.py.
      4. Archive HTML and assets via helper/html.py.
      5. Extract clean visible text via helper/text.py.
      6. Discover outgoing links via helper/outgoing_url.py.
    """
    final_url = page.url
    is_bad, block_reason = check_page_status(page)
    if is_bad:
        raise BlockedPageException(block_reason or f"Blocked page detected: {final_url}")

    os.makedirs(f'./zip/{instance_no}', exist_ok=True)
    os.makedirs(f'./images/{instance_no}', exist_ok=True)

    # Redirects
    try:
        ret_redirects = redirect.get(destination_url, final_url, r_session, page)
    except Exception:
        ret_redirects = []

    # Screenshot
    ret_screenshot = screenshot.get(page, "prelander", instance_no)

    # HTML Archive
    ret_html = html.get(page, r_session, final_url, instance_no)

    # Visible Text
    try:
        ret_text = text.get(page)
    except Exception:
        ret_text = ""

    # Outgoing links
    try:
        ret_outgoing = outgoing_url.get(page, final_url, r_session)
    except Exception:
        ret_outgoing = []

    # Category classification (empty list; legacy sitereview bypassed)
    category_list = []

    return ret_redirects, final_url, ret_screenshot, ret_text, ret_outgoing, ret_html, category_list


# --------------------------------------------------------------------------------------------------
# 15. INPUT BATCH FETCHER (GET_API)
# --------------------------------------------------------------------------------------------------
def get_input(instance_no):
    """Fetches a fresh batch of ads from DEV_GET_API or MAIN_GET_API."""
    try:
        api_key = "DEV_GET_API" if config.dev_mode else "MAIN_GET_API"
        api_url = config.get_api(api_key)
        inp = requests.get(api_url, timeout=REQUEST_TIMEOUT)
        if inp.status_code != 200:
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
    except Exception:
        return None

def get_input_from_file(instance_no):
    """Fallback: reads cached batch from local disk file if HIT_GET_API is False."""
    folder = "getApi_data_dev" if config.dev_mode else "getApi_data"
    filename = f"{folder}/temp_getapi_data_{config.network_name}_{instance_no}.json"
    try:
        with open(filename, "r") as f:
            li_of_data = json.load(f)
        if not li_of_data:
            raise ValueError("Empty file content.")
    except Exception:
        li_of_data = get_input(instance_no)
        if li_of_data is None:
            return [], filename
    return li_of_data, filename


# --------------------------------------------------------------------------------------------------
# 16. ATOMIC SHARED QUEUE & COOLDOWN TRACKING (Multi-Worker Coordination)
# --------------------------------------------------------------------------------------------------
def _shared_queue_path():
    folder = "getApi_data_dev" if config.dev_mode else "getApi_data"
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"shared_ad_queue_{config.network_name}.json")

def _atomic_write_json(path, data):
    """
    Writes data to disk atomically by writing to a .tmp file first, then performing os.replace().
    Guarantees no file corruption if a process crashes mid-write!
    """
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    tmp_path = f"{path}.tmp_{os.getpid()}_{int(time.time() * 1000) % 100000}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

AD_COOLDOWN_SECONDS = 300  # 5-minute cooldown prevents DB lag duplicate scraping

def _completed_tracker_path():
    folder = "getApi_data_dev" if config.dev_mode else "getApi_data"
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"completed_ad_ids_{config.network_name}.json")

def _record_ad_completed(file_lock, ad_id, in_flight_dict, completed_dict):
    """Marks an ad as finished: removes from in_flight and adds to completed_dict with 5m cooldown."""
    if ad_id is None:
        return
    now = time.time()
    with file_lock:
        in_flight_dict.pop(ad_id, None)
        completed_dict[ad_id] = now
        try:
            completed_path = _completed_tracker_path()
            current_dict = {str(k): ts for k, ts in completed_dict.items() if now - ts < AD_COOLDOWN_SECONDS}
            _atomic_write_json(completed_path, current_dict)
        except Exception:
            pass

def pop_next_ad_from_file(file_lock, instance_no, metric, lander_logger, in_flight_dict, completed_dict):
    """
    Atomically pops exactly ONE ad from shared disk queue under multiprocessing.Lock.
    Guarantees zero duplicate scraping while allowing re-scrapes after cooldown expires:
      1. Immediate atomic pop under file_lock.
      2. Tracks currently in-flight ads across all workers.
      3. Skips ads in 5-minute cooldown (protection against database replication lag).
      4. Auto-refills queue from GET_API when empty.
    """
    queue_path = _shared_queue_path()
    now = time.time()

    with file_lock:
        # Prune stale in-flight (older than 20 mins)
        for aid, info in list(in_flight_dict.items()):
            if isinstance(info, (list, tuple)) and len(info) >= 2:
                if now - info[1] > 1200:
                    in_flight_dict.pop(aid, None)

        # Prune completed entries past 5-min cooldown
        for aid, ts in list(completed_dict.items()):
            if now - ts >= AD_COOLDOWN_SECONDS:
                completed_dict.pop(aid, None)

        # Read current queue from disk
        ads = []
        if os.path.isfile(queue_path):
            try:
                with open(queue_path, "r", encoding="utf-8") as f:
                    ads = json.load(f)
                if not isinstance(ads, list):
                    ads = []
            except Exception:
                ads = []

        # Filter valid ads not currently in-flight or in cooldown
        valid_ads = []
        for item in ads:
            aid = item.get("id")
            if aid is not None and item.get("destination_url"):
                if aid not in in_flight_dict and aid not in completed_dict:
                    valid_ads.append(item)
        ads = valid_ads

        # Refill if empty
        if not ads:
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
            for item in raw_candidates:
                aid = item.get("id")
                if aid not in in_flight_dict and aid not in completed_dict:
                    fresh_ads.append(item)

            if fresh_ads:
                ads = fresh_ads
            else:
                _atomic_write_json(queue_path, [])
                return "WAIT"

        if not ads:
            _atomic_write_json(queue_path, [])
            return None

        # Pop target ad and mark in-flight
        target_ad = ads.pop(0)
        target_id = target_ad.get("id")
        in_flight_dict[target_id] = (instance_no, time.time())

        # Write remaining ads back to disk atomically
        _atomic_write_json(queue_path, ads)
        remaining = len(ads)

    lander_logger.info(f"[QUEUE] Worker {instance_no} popped ad_id={target_ad.get('id')} | {remaining} ads remaining in shared queue")
    return target_ad


# --------------------------------------------------------------------------------------------------
# 17. WORKER PROCESS ENTRYPOINT
# --------------------------------------------------------------------------------------------------
def main(instances):
    """Main execution loop for an individual multiprocessing worker instance."""
    global payload_logger, successful_payload_logger, unsuccessful_ad_logger, proxy_ad_logger
    instance_no, port, file_lock, in_flight_dict, completed_dict = instances

    os.makedirs(f'./images/{instance_no}', exist_ok=True)
    os.makedirs(f'./zip/{instance_no}', exist_ok=True)
    metric = Metrics(idx=instance_no)

    # Start Prometheus metrics HTTP server for this worker
    try:
        start_http_server(int(port))
    except Exception as port_err:
        print(f"[Metrics Server Warning] Port {port}: {port_err}")

    # Set up dedicated per-worker loggers
    lander_logger = setup_logger(f"{instance_no}_lander_logger", f"logs/{instance_no}_{config.network_name}_lander_logger.log")
    error_logger = setup_logger(f"{instance_no}_error_logger", f"er_logs/{instance_no}_{config.network_name}_error_logger.log")

    # Staggered startup delay: instance 1 starts at 0s, instance 2 at 30s, instance 3 at 60s, etc.
    time.sleep(config.time_gap * (int(instance_no) - 1))

    # Infinite polling & scraping loop
    while True:
        single_data = pop_next_ad_from_file(file_lock, instance_no, metric, lander_logger, in_flight_dict, completed_dict)
        if single_data == "WAIT":
            time.sleep(10)
            continue
        if single_data is None:
            time.sleep(60)
            continue

        ad_id = single_data.get("id")
        try:
            scraping(single_data, metric, lander_logger, port, instance_no, 0, error_logger)
        except Exception as loop_err:
            error_logger.error(f"[Worker {instance_no} Loop Crash] {loop_err}: {traceback.format_exc()}")
            time.sleep(5)
        finally:
            _record_ad_completed(file_lock, ad_id, in_flight_dict, completed_dict)


# --------------------------------------------------------------------------------------------------
# 18. MULTIPROCESSING POOL MANAGER
# --------------------------------------------------------------------------------------------------
def multi_chrome():
    """Spawns the pool of N parallel scraper workers and coordinates shared state."""
    logging.Formatter.converter = time.gmtime
    try:
        install_mp_handler()
    except Exception:
        pass

    for _dir in ["logs", "er_logs", "images", "zip", "getApi_data", "getApi_data_dev"]:
        os.makedirs(_dir, exist_ok=True)

    # Clean stale Prometheus DB files
    if os.path.isdir(_tempdir):
        for _f in os.listdir(_tempdir):
            if _f.endswith('.db'):
                try:
                    os.remove(os.path.join(_tempdir, _f))
                except Exception:
                    pass

    # Worker port assignments (instance 1 -> 8000, instance 2 -> 8001, ..., up to 50 workers)
    ins_no = [(str(i), str(8000 + i - 1)) for i in range(1, 51)]

    # Cross-process synchronization structures
    manager = multiprocessing.Manager()
    file_lock = manager.Lock()
    in_flight_dict = manager.dict()
    completed_dict = manager.dict()

    # Preload completed ads cache from disk if available
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

    # Spawn worker pool up to config.instances
    worker_args = [(instance_no, port, file_lock, in_flight_dict, completed_dict) for instance_no, port in ins_no[:config.instances]]
    p = multiprocessing.Pool(config.instances)
    try:
        p.map(main, worker_args, chunksize=1)
    except KeyboardInterrupt:
        print("\n[Shutdown] Terminating scraper workers...")
    finally:
        p.terminate()
        p.join()
        manager.shutdown()

if __name__ == '__main__':
    multi_chrome()
