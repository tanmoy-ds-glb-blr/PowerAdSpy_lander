import os
import shutil
import tempfile
import requests
import traceback
import csv
import logging
from playwright.sync_api import sync_playwright
from config import Config
from helper.proxy_health import ProxyUnavailableError, sanitize_error

_log = logging.getLogger("lander")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SETUP_DIR = os.path.join(_BASE_DIR, "setup")
_BRD_CSV = os.path.join(_BASE_DIR, "helper", "ips-pas2026-02-05T07_41_53.550Z.csv")

_BRD_SUPERPROXY = "brd.superproxy.io"
_BRD_PORT = "44445"
_BRD_CUSTOMER = os.environ.get("BRIGHT_DATA_CUSTOMER", "")
_BRD_PASS = os.environ.get("BRIGHT_DATA_PASSWORD", "")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

# Comprehensive stealth script to mock human desktop browser and remove webdriver flags
STEALTH_JS = """
// 1. Mask navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
});

// 2. Mock window.chrome runtime
window.chrome = {
    app: { isInstalled: false },
    webstore: { onInstallStageChanged: {}, onDownloadProgress: {} },
    runtime: {
        PlatformOs: { MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' },
        PlatformArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64', MIPS: 'mips', MIPS64: 'mips64' },
        PlatformNaclArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64', MIPS: 'mips', MIPS64: 'mips64' },
        RequestUpdateCheckStatus: { THROTTLED: 'throttled', NO_UPDATE: 'no_update', UPDATE_AVAILABLE: 'update_available' },
        OnInstalledReason: { INSTALL: 'install', UPDATE: 'update', CHROME_UPDATE: 'chrome_update', SHARED_MODULE_UPDATE: 'shared_module_update' },
        OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' }
    },
    csi: function() {},
    loadTimes: function() {}
};

// 3. Mock languages and plugins
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
});
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});
"""

_COUNTRY_NAME_TO_ISO = {
    "united states": "us",
    "united kingdom": "gb",
    "great britain": "gb",
    "germany": "de",
    "france": "fr",
    "spain": "es",
    "italy": "it",
    "canada": "ca",
    "australia": "au",
    "netherlands": "nl",
    "belgium": "be",
    "switzerland": "ch",
    "austria": "at",
    "sweden": "se",
    "norway": "no",
    "denmark": "dk",
    "finland": "fi",
    "poland": "pl",
    "portugal": "pt",
    "brazil": "br",
    "mexico": "mx",
    "japan": "jp",
    "india": "in",
    "singapore": "sg",
    "russia": "ru",
    "turkey": "tr",
    "israel": "il",
    "united arab emirates": "ae",
    "hungary": "hu",
    "indonesia": "id",
    "ireland": "ie",
    "kazakhstan": "kz",
    "morocco": "ma",
    "malaysia": "my",
    "new zealand": "nz",
    "philippines": "ph",
    "thailand": "th",
    "south africa": "za",
}

def _geo_to_iso(geo: str) -> str:
    geo = geo.strip()
    if len(geo) == 2:
        return geo.lower()
    base = geo.split("(")[0].strip().lower()
    return _COUNTRY_NAME_TO_ISO.get(base, base[:2].lower())

def _load_brd_ip_map() -> dict:
    ip_map = {}
    if not os.path.isfile(_BRD_CSV):
        _log.warning("[BRD] CSV not found at %s. Will use superproxy gateway.", _BRD_CSV)
        return ip_map
    with open(_BRD_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ip = (row.get("ip") or row.get("IP") or "").strip()
            geo = (row.get("geolocation") or row.get("Geolocation") or "").strip()
            if not ip or not geo:
                continue
            iso = _geo_to_iso(geo)
            ip_map.setdefault(iso, []).append(ip)
    return ip_map

_BRD_IP_MAP = _load_brd_ip_map()

def _get_brd_host(iso: str = None) -> str:
    # Always route through the official Bright Data superproxy gateway.
    # Bright Data dynamically routes to the correct country via the username: -country-{iso}
    return f"{_BRD_SUPERPROXY}:{_BRD_PORT}"

def _get_brd_credentials():
    """Read credentials at call time so a restarted worker sees env changes."""
    return (
        os.environ.get("BRIGHT_DATA_CUSTOMER", "").strip(),
        os.environ.get("BRIGHT_DATA_PASSWORD", ""),
    )

def _get_proxy_url(iso: str) -> str:
    host_port = _get_brd_host(iso)
    customer, password = _get_brd_credentials()
    user = f"{customer}-country-{iso}"
    return f"http://{user}:{password}@{host_port}"

def _resolve_chrome_paths():
    """Detect available Google Chrome executable."""
    if os.name != "nt":
        for path in ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser"]:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return None

    # Windows resolution
    local_chrome = os.path.join(_SETUP_DIR, "chrome-for-testing-149", "chrome.exe")
    if os.path.isfile(local_chrome):
        return local_chrome

    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None

def verify_proxy_egress(session=None, iso=None, required=False, timeout_seconds=10):
    """Verify egress and optionally fail closed when Bright Data is unavailable."""
    owned_session = None
    try:
        if session:
            client = session
        elif iso:
            customer, password = _get_brd_credentials()
            if not customer or not password:
                raise ProxyUnavailableError(
                    "BRIGHT_DATA_CUSTOMER/BRIGHT_DATA_PASSWORD are not set",
                    stage="proxy_health_check",
                )
            owned_session = requests.Session()
            owned_session.trust_env = False
            client = owned_session
            p_url = _get_proxy_url(iso)
            client.proxies = {"http": p_url, "https": p_url}
        else:
            client = requests
        timeout_seconds = min(10.0, max(0.1, float(timeout_seconds or 10)))
        # Requests applies a scalar timeout independently to connect and read,
        # which can double the intended wall time. Split a bounded total budget
        # and reject redirects so the continuous monitor can start another
        # probe within the configured <=10 second interval.
        connect_timeout = min(3.0, max(0.1, timeout_seconds / 2.0))
        read_timeout = min(3.0, max(0.1, timeout_seconds - connect_timeout))
        res = client.get(
            "https://lumtest.com/myip.json",
            timeout=(connect_timeout, read_timeout),
            allow_redirects=False,
        )
        if not res.ok:
            provider_message = (
                res.headers.get("x-brd-err-msg")
                or res.headers.get("X-Brd-Error")
                or (res.text or "")[:200]
            )
            if res.status_code == 407:
                reason = f"Bright Data rejected proxy access (HTTP 407): {provider_message}"
            else:
                reason = f"proxy health endpoint returned HTTP {res.status_code}: {provider_message}"
            raise ProxyUnavailableError(sanitize_error(reason), stage="proxy_health_check")
        try:
            data = res.json()
        except Exception as exc:
            raise ProxyUnavailableError(
                f"proxy health endpoint returned invalid JSON: {type(exc).__name__}",
                stage="proxy_health_check",
            ) from exc
        if not isinstance(data, dict) or not data.get("ip"):
            raise ProxyUnavailableError(
                "proxy health endpoint returned no egress IP",
                stage="proxy_health_check",
            )
        asn = data.get("asn") if isinstance(data.get("asn"), dict) else {}
        _log.info("[PROXY CHECK] iso=%s | egress_ip=%s | country=%s | asn=%s",
                  iso or "N/A", data.get("ip"), data.get("country"),
                  data.get("org", asn.get("org", asn.get("org_name", "N/A"))))
        return data
    except ProxyUnavailableError as exc:
        _log.warning("[PROXY CHECK] iso=%s | unavailable: %s", iso or "N/A", sanitize_error(exc))
        if required:
            raise
    except Exception as exc:
        unavailable = ProxyUnavailableError(
            f"{type(exc).__name__}: {sanitize_error(exc)}",
            stage="proxy_health_check",
        )
        _log.warning("[PROXY CHECK] iso=%s | unavailable: %s", iso or "N/A", unavailable)
        if required:
            raise unavailable from exc
    finally:
        if owned_session is not None:
            try:
                owned_session.close()
            except Exception:
                pass
    return None

def init_dc(iso, headless=None, verify_egress=True):
    """Initialize Playwright browser and requests session using Bright Data proxy."""
    user_agent = os.environ.get("BROWSER_USER_AGENT", "").strip()
    _cfg = Config()
    
    use_proxy = getattr(_cfg, "bright_proxies", True)
    p = None
    browser = None
    context = None
    try:
        chrome_bin = _resolve_chrome_paths()
        p = sync_playwright().start()

        if headless is None:
            headless = os.environ.get("HEADLESS", "true").lower() not in ("false", "0", "no")
        
        launch_kwargs = {
            "headless": headless,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--allow-insecure-localhost",
            ],
        }
        if use_proxy:
            brd_customer, brd_password = _get_brd_credentials()
            if not brd_customer or not brd_password:
                raise ProxyUnavailableError(
                    "BRIGHT_PROXIES is enabled but BRIGHT_DATA_CUSTOMER/BRIGHT_DATA_PASSWORD are not set",
                    stage="browser_initialization",
                )
            host_port = _get_brd_host(iso)
            host, port = host_port.rsplit(":", 1)
            brd_user = f"{brd_customer}-country-{iso}"
            bypass_list = "localhost,127.0.0.1"
            launch_kwargs["proxy"] = {
                "server": f"http://{host}:{port}",
                "username": brd_user,
                "password": brd_password,
                "bypass": bypass_list,
            }
            launch_kwargs["args"].append("--proxy-bypass-list=<-loopback>")
        if chrome_bin:
            launch_kwargs["executable_path"] = chrome_bin
            _log.info("[PLAYWRIGHT] Using Chrome executable: %s", chrome_bin)
        
        browser = p.chromium.launch(**launch_kwargs)
        context_kwargs = dict(
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
            locale="en-US",
            timezone_id="America/New_York",
        )
        if user_agent:
            context_kwargs["user_agent"] = user_agent
        context = browser.new_context(**context_kwargs)
        context.add_init_script(STEALTH_JS)
        page = context.new_page()
        page.set_default_timeout(180000)
        page.set_default_navigation_timeout(180000)
        
        # Attach references for clean teardown
        page._pw_context = context
        page._pw_browser = browser
        page._pw_instance = p
        
        r_session = requests.Session()
        try:
            effective_user_agent = page.evaluate("navigator.userAgent")
        except Exception:
            effective_user_agent = user_agent or DEFAULT_USER_AGENT
        r_session.headers.update({"user-agent": effective_user_agent})
        if use_proxy:
            proxy_url = _get_proxy_url(iso)
            no_proxy_domains = "localhost,127.0.0.1"
            r_session.proxies = {"http": proxy_url, "https": proxy_url, "no": no_proxy_domains}
            masked = proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url
            _log.info("[PROXY] iso=%-4s | Playwright & requests proxy set -> %s", iso, masked)
            egress_info = (
                verify_proxy_egress(r_session, iso, required=True, timeout_seconds=5)
                if verify_egress
                else None
            )
        else:
            _log.info("[PROXY] iso=%-4s | BRIGHT_PROXIES disabled -> direct connection", iso)
            egress_info = verify_proxy_egress(r_session, None)

        r_session._egress_info = egress_info
        page._egress_info = egress_info
        return page, r_session
        
    except Exception as e:
        if context:
            try:
                context.close()
            except Exception:
                pass
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if p:
            try:
                p.stop()
            except Exception:
                pass
        if isinstance(e, ProxyUnavailableError):
            _log.warning("[PROXY] iso=%-4s | init_dc paused: %s", iso, sanitize_error(e))
        else:
            _log.error("[PROXY] iso=%-4s | init_dc FAILED: %s", iso, sanitize_error(e))
        _log.debug(traceback.format_exc())
        if isinstance(e, ProxyUnavailableError):
            raise
        return None

def init_residential(iso, headless=None):
    """Fallback residential init using Playwright."""
    return init_dc(iso, headless=headless)

def close_browser(page):
    """Safely shut down the Playwright page, context, browser, and runtime."""
    if not page:
        return
    try:
        if hasattr(page, "_pw_context") and page._pw_context:
            page._pw_context.close()
    except Exception:
        pass
    try:
        if hasattr(page, "_pw_browser") and page._pw_browser:
            page._pw_browser.close()
    except Exception:
        pass
    try:
        if hasattr(page, "_pw_instance") and page._pw_instance:
            page._pw_instance.stop()
    except Exception:
        pass

# Backward compatibility alias
close_driver = close_browser
