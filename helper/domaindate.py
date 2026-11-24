import os
import re
import whois
import datetime
import requests
import tldextract
from bs4 import BeautifulSoup
import yaml
from pathlib import Path


# ----------------------------
# Load YAML config
# ----------------------------
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
if not CONFIG_PATH.is_file():
    CONFIG_PATH = Path("config.yaml")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f) or {}


def log_domain_failure(domain, source, reason):
    """Store why a domain registration date could not be fetched."""
    try:
        safe_reason = str(reason).replace("\n", " ").replace("\r", " ")
        timestamp = datetime.datetime.now().isoformat(timespec="seconds")
        log_dir = Path(__file__).resolve().parent.parent / "logs"
        os.makedirs(log_dir, exist_ok=True)
        with open(log_dir / "domain_date_failures.log", "a", encoding="utf-8") as log_file:
            log_file.write(
                f"{timestamp} | domain={domain} | source={source} | reason={safe_reason}\n"
            )
    except Exception:
        pass


# ----------------------------
# Whitelisted Fallback Networks
# ----------------------------
FALLBACK_NETWORKS = ["instagram", "google", "youtube"]  # only these are allowed as fallback


# ----------------------------
# External API helpers
# ----------------------------
def get_domain_from_api(domain_short: str, network: str, timeout_seconds=95):
    """Fetch domain date from the configured network API."""
    dev_mode = CONFIG.get("default_settings", {}).get("DEV_MODE", False)
    api_key = "DEV_GET_DOMAIN_REG_DATE" if dev_mode else "MAIN_GET_DOMAIN_REG_DATE"
    api_url = CONFIG.get("networks", {}).get(network, {}).get(api_key)

    if not api_url:
        log_domain_failure(domain_short, f"{network}_api", "api_url_not_configured")
        return ""

    try:
        response = requests.get(
            api_url,
            params={"domain": domain_short},
            timeout=max(1.0, float(timeout_seconds))
        )
    except requests.Timeout:
        log_domain_failure(domain_short, f"{network}_api", "request_timeout")
        return ""
    except requests.RequestException as error:
        log_domain_failure(domain_short, f"{network}_api", f"request_error: {error}")
        return ""

    if response.status_code == 429:
        log_domain_failure(domain_short, f"{network}_api", "rate_limited_http_429")
        return ""

    if response.status_code != 200:
        log_domain_failure(
            domain_short,
            f"{network}_api",
            f"http_error_{response.status_code}"
        )
        return ""

    try:
        data = response.json()
    except ValueError:
        log_domain_failure(domain_short, f"{network}_api", "invalid_json_response")
        return ""

    response_data = data.get("data") or {}
    domain_date = ""

    if isinstance(response_data, dict):
        domain_date = response_data.get("domain_registered_date") or ""

        if not domain_date:
            matches = response_data.get("matches") or []
            domain_date = next(
                (
                    item.get("domain_registered_date")
                    for item in matches
                    if isinstance(item, dict)
                    and item.get("domain_registered_date")
                ),
                ""
            )

    domain_date = str(domain_date)[:10] if domain_date else ""

    if not domain_date or domain_date == "0000-00-00":
        log_domain_failure(domain_short, f"{network}_api", "no_date_in_response")
        return ""

    print(f"[INFO] Using domain date from {network.title()} API for {domain_short}: {domain_date}")
    return domain_date


# def update_domain_to_api(domain_short: str, domain_date: str, network: str):
#     """Send scraped domain_date to API via PUT"""
#     try:
#         api_url = CONFIG["networks"][network]["MAIN_UPDATE_DOMAIN_REG_DATE"]
#         payload = {"domain_name": domain_short, "domain_date": domain_date}
#         res = requests.put(api_url, json=payload, timeout=15)
#         if res.status_code == 200:
#             print(f"[INFO] Updated {domain_short} -> {domain_date} in API")
#     except Exception as e:
#         print(f"[WARN] PUT API failed for {domain_short}: {e}")


# ----------------------------
# Scraping methods (as you wrote them)
# ----------------------------
def scrape_domain_date(domain_short: str):
    customer = os.environ.get("BRIGHT_DATA_CUSTOMER", "")
    password = os.environ.get("BRIGHT_DATA_PASSWORD", "")
    if customer and password:
        p = f"http://{customer}-country-us:{password}@brd.superproxy.io:22225"
        proxies = {'http': p, 'https': p}
    else:
        proxies = {}
    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/60.0.3112.50 Safari/537.36'
    }

    # Method 1: whois lib
    try:
        w = whois.whois(domain_short)
        domain_date = w.creation_date
        # print(f"[DEBUG][WHOIS] Raw creation_date for {domain_short}: {domain_date}")

        if domain_date is None:
            raise ValueError("No creation date found")

        # Handle list case safely
        if isinstance(domain_date, list):
            domain_date = next((d for d in domain_date if d is not None), None)

        if not domain_date:
            raise ValueError("No valid date in WHOIS result")

        # Normalize to date only
        if isinstance(domain_date, datetime.datetime):
            domain_date = domain_date.date()

        # print(f"[DEBUG][WHOIS] Picked date: {domain_date}")

        td = datetime.date.today() - domain_date
        domain_age = 1 if td.days > 0 else 0
        return domain_date.strftime("%Y-%m-%d"), domain_age

    except Exception as e:
        print(f"[WARN][WHOIS] Failed for {domain_short}: {e}")
        log_domain_failure(domain_short, "python_whois", e)

    # Method 2: whois.com
    try:
        res = requests.get(f"https://www.whois.com/whois/{domain_short}", headers=headers, proxies=proxies, timeout=30)
        soup = BeautifulSoup(res.content, "html.parser")
        div_label = soup.find("div", text=re.compile("Registered On:"), attrs={'class': 'df-label'})
        if div_label:
            val = div_label.parent.find("div", attrs={'class': 'df-value'}).get_text()
            dt_obj = datetime.datetime.strptime(val, '%Y-%m-%d')
            td = datetime.datetime.now() - dt_obj
            domain_age = 1 if td.days > 0 else 0
            return val, domain_age
    except:
        pass

    # Method 3: domaintools.com
    try:
        res = requests.get(f"http://whois.domaintools.com/{domain_short}", headers=headers, proxies=proxies, timeout=30)
        soup = BeautifulSoup(res.content, "html.parser")
        div_label = soup.find("span", text=re.compile("Created on .+"))
        if div_label:
            date = div_label.get_text().split()[-1]
        else:
            div_label = soup.find("div", text=re.compile("Registered On:"), attrs={'class': 'df-label'})
            val = div_label.parent.find("div", attrs={'class': 'df-value'}).get_text()
            date = val
        dt_obj = datetime.datetime.strptime(date, '%Y-%m-%d')
        td = datetime.datetime.now() - dt_obj
        domain_age = 1 if td.days > 0 else 0
        return date, domain_age
    except:
        pass

    # Method 4: whoxy.com (HTML fallback)
    try:
        res = requests.get(f"https://www.whoxy.com/{domain_short}#json", headers=headers, timeout=30, proxies=proxies)
        soup = BeautifulSoup(res.content, 'html.parser')
        date = soup.find_all("span", class_="hljs-string")[4].text.strip('"')
        dt_obj = datetime.datetime.strptime(date, '%Y-%m-%d')
        td = datetime.datetime.now() - dt_obj
        domain_age = 1 if td.days > 0 else 0
        return date, domain_age
    except:
        pass

    # Method 5: who.is
    try:
        res = requests.get(f"https://who.is/whois/{domain_short}", headers=headers, timeout=30)
        soup = BeautifulSoup(res.content, 'html.parser')
        date = soup.find("div", string="Registered On").nextSibling.nextSibling.text
        dt_obj = datetime.datetime.strptime(date, '%Y-%m-%d')
        td = datetime.datetime.now() - dt_obj
        domain_age = 1 if td.days > 0 else 0
        return date, domain_age
    except:
        pass

    # Method 6: RDAP
    try:
        res = requests.get(f"https://rdap.org/domain/{domain_short}", headers=headers, proxies=proxies, timeout=30)
        if res.status_code == 200 and 'application/json' in res.headers.get('Content-Type', ''):
            data = res.json()
            if 'events' in data:
                for event in data['events']:
                    if event.get('eventAction') == 'registration':
                        date = event.get('eventDate')[:10]
                        dt_obj = datetime.datetime.strptime(date, '%Y-%m-%d')
                        td = datetime.datetime.now() - dt_obj
                        domain_age = 1 if td.days > 0 else 0
                        return date, domain_age
    except:
        pass

    # Method 7: WhoisXML API
    try:
        res = requests.get(f"https://www.whoisxmlapi.com/whoisserver/WhoisService?domainName={domain_short}&outputFormat=JSON",
                           headers=headers, proxies=proxies, timeout=30)
        if res.status_code == 200 and 'application/json' in res.headers.get('Content-Type', ''):
            data = res.json()
            if 'WhoisRecord' in data and 'createdDate' in data['WhoisRecord']:
                date = data['WhoisRecord']['createdDate'][:10]
                dt_obj = datetime.datetime.strptime(date, '%Y-%m-%d')
                td = datetime.datetime.now() - dt_obj
                domain_age = 1 if td.days > 0 else 0
                return date, domain_age
    except:
        pass

    # Method 8: whoisrequest.org (scraped)
    try:
        res = requests.get(f"https://www.whoisrequest.org/whois/{domain_short}",
                           headers=headers, proxies=proxies, timeout=30)
        soup = BeautifulSoup(res.content, 'html.parser')
        textblock = soup.get_text()
        match = re.search(r'Creation Date:\s*(\d{4}-\d{2}-\d{2})', textblock)
        if match:
            date = match.group(1)
            dt_obj = datetime.datetime.strptime(date, '%Y-%m-%d')
            td = datetime.datetime.now() - dt_obj
            domain_age = 1 if td.days > 0 else 0
            return date, domain_age
    except:
        pass

    # Final fallback
    log_domain_failure(
        domain_short,
        "all_fallbacks",
        "registration_date_not_found_after_all_methods"
    )
    return "", 0


# ----------------------------
# Master function
# ----------------------------
def get(url: str, network: str = None, timeout_seconds=None):
    """
    Main entrypoint:
    1. Try GET API for domain date
    2. If not found, scrape
    3. If scraped successfully, send to PUT API
    """
    if not network:
        network = CONFIG.get("default_settings", {}).get("NETWORK")

    if not network:
        raise ValueError(
            "Network not specified for domain date. Please define 'NETWORK' under default_settings in config.yaml."
        )

    domain = tldextract.extract(url)
    domain_short = domain.domain + "." + domain.suffix

    # Step 1: External GET API
    domain_date = get_domain_from_api(domain_short, network, timeout_seconds or 95)
    if domain_date:
        dt_obj = datetime.datetime.strptime(domain_date, "%Y-%m-%d")
        td = datetime.datetime.now() - dt_obj
        domain_age = 1 if td.days > 0 else 0
        return domain_date, domain_age

    # A bounded pipeline call deliberately avoids the multi-provider WHOIS fallback:
    # several third-party libraries do not expose a reliable cancellation mechanism.
    if timeout_seconds is not None:
        return "", 0

    # Step 2: Scrape if API failed
    domain_date, domain_age = scrape_domain_date(domain_short)
    # if domain_date:
    #     # Step 3: Update API with scraped date
    #     # update_domain_to_api(domain_short, domain_date, network)
    return domain_date, domain_age
