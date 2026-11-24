import requests
import json
import sys
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_CUSTOMER = os.environ.get("BRIGHT_DATA_CUSTOMER", "")
_PASSWORD = os.environ.get("BRIGHT_DATA_PASSWORD", "")


def _proxy_url(port):
    if not _CUSTOMER or not _PASSWORD:
        return ""
    return f"http://{_CUSTOMER}-country-us:{_PASSWORD}@brd.superproxy.io:{port}"


PROXIES_TO_TEST = [
    {"name": "1. Main Crawler Proxy (Port 44445)", "url": _proxy_url(44445)},
    {"name": "2. Alternate Proxy (Port 22225)", "url": _proxy_url(22225)},
]

def main():
    if not _CUSTOMER or not _PASSWORD:
        raise SystemExit("Set BRIGHT_DATA_CUSTOMER and BRIGHT_DATA_PASSWORD before running this check.")
    print("=" * 65)
    print("        BRIGHT DATA PROXY HEALTH CHECK")
    print("=" * 65)

    for item in PROXIES_TO_TEST:
        name = item["name"]
        p_url = item["url"]

        print(f"\n[+] Testing: {name}")
        print("    Proxy URL: http://brd.superproxy.io (credentials hidden)")
        print("-" * 65)

        try:
            res = requests.get(
                "https://lumtest.com/myip.json",
                proxies={"http": p_url, "https": p_url},
                timeout=12
            )
            if res.status_code == 200:
                data = res.json()
                print("    RESULT:  [ACTIVE / WORKING] (HTTP 200) OK")
                print(f"    IP:      {data.get('ip')}")
                print(f"    Country: {data.get('country')}")
                geo = data.get("geo") or {}
                print(f"    City:    {geo.get('city') or 'N/A'}, {geo.get('region_name') or 'N/A'}")
                asn = data.get("asn") or {}
                print(f"    ISP/ASN: {asn.get('org_name') or 'N/A'} (AS{asn.get('asnum') or 'N/A'})")
            else:
                print(f"    RESULT:  [FAILED] (HTTP {res.status_code})")
                print(f"    Details: {res.text.strip()[:200]}")

        except requests.exceptions.ConnectTimeout:
            print("    RESULT:  [FAILED - CONNECTION TIMED OUT]")
            print("    REASON:  The proxy port is unreachable or blocked by Proxmox/network firewall.")
        except requests.exceptions.ProxyError as e:
            err_str = str(e)
            if "407" in err_str:
                print("    RESULT:  [FAILED - 407 AUTHENTICATION ERROR]")
                print("    REASON:  Proxy credentials or zone subscription is EXPIRED/INVALID in Bright Data.")
            else:
                print(f"    RESULT:  [FAILED - PROXY ERROR]: {err_str[:250]}")
        except Exception as e:
            print(f"    RESULT:  [FAILED - ERROR]: {type(e).__name__}: {str(e)[:250]}")

    print("\n" + "=" * 65)

if __name__ == "__main__":
    main()
