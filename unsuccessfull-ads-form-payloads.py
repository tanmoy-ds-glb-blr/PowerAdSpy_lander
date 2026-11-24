import os
import sys
import re
import json
from pathlib import Path

# Ensure UTF-8 output across Windows & Linux consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ==============================================================================
# 🎯 1. LOG FILE CONFIGURATION
# Set the path to the .log file you want to inspect!
# Examples:
#   LOG_FILE = "logs/payloads.log"
#   LOG_FILE = "logs/youtube-payloads.log"
#   LOG_FILE = "logs/facebook-payloads.log"
#   LOG_FILE = "logs/reddit-payloads.log"
#   LOG_FILE = "logs/pinterest-payloads.log"
#   LOG_FILE = "logs/quora-payloads.log"
#   LOG_FILE = "logs/native-payloads.log"
# ==============================================================================
from helper.log_paths import resolve_log_path

LOG_FILE = str(resolve_log_path("logs", "payloads.log"))

# Maximum number of ads to output (set to None for all matching ads)
MAX_ADS = None

# Output file path where the generated Python block will be saved
OUTPUT_FILE = "logs/ads.txt"


# ==============================================================================
# 🎯 2. FILTER BY UNSUCCESSFUL CATEGORY / REASON
# Comment / uncomment the categories below to choose what to extract.
#
# 👉 HOW IT WORKS:
#   - If you comment out all lines except "Connection Error / Unreachable",
#     it will ONLY extract ads that failed due to "Connection Error / Unreachable".
#   - To extract ALL unsuccessful ads regardless of reason, set:
#     SELECTED_CATEGORIES = None
# ==============================================================================
SELECTED_CATEGORIES = [
    # ── Connection & Network ──────────────────────────────────────────────────
    "Connection Error / Unreachable",
    # "Timeout",

    # # ── HTTP Error Status Codes ───────────────────────────────────────────────
    # "HTTP Error Status 400",
    # "HTTP Error Status 401",
    # "HTTP Error Status 403",
    # "HTTP Error Status 404",
    # "HTTP Error Status 429",
    # "HTTP Error Status 500",
    # "HTTP Error Status 502",
    # "HTTP Error Status 503",
    # "HTTP Error Status 504",
    # "HTTP Error Status 520",
    # "HTTP Error Status 522",
    # "HTTP Error Status 523",
    # "HTTP Error Status 526",

    # # ── Bot / WAF Detection & Challenges ──────────────────────────────────────
    # "Bot/WAF block detected: 'challenges.cloudflare.com'",
    # "Bot/WAF block detected: 'challenge-platform'",
    # "Bot/WAF block detected: 'datadome'",
    # "Bot/WAF block detected: 'perimeterx'",
    # "Bot/WAF block detected: '_incapsula_resource'",
    # "Bot/WAF block detected: 'imperva'",
    # "Bot/WAF block detected: 'kasada'",
    # "Bot/WAF block detected: 'verify you are human'",
    # "Bot/WAF block detected: 'checking your browser before accessing'",
    # "Bot/WAF block detected: 'bot detection'",

    # # ── Status 3 Keywords (Dead / Sold / Error / Gated pages) ─────────────────
    # "Status 3 keyword matched: 'page not found'",
    # "Status 3 keyword matched: '404 not found'",
    # "Status 3 keyword matched: 'access denied'",
    # "Status 3 keyword matched: 'item not found'",
    # "Status 3 keyword matched: 'product not found'",
    # "Status 3 keyword matched: 'product no longer available'",
    # "Status 3 keyword matched: 'this product is no longer available'",
    # "Status 3 keyword matched: 'this page is not available'",
    # "Status 3 keyword matched: 'robot or human'",
    # "Status 3 keyword matched: 'prove your humanity'",
    # "Status 3 keyword matched: 'request blocked'",
    # "Status 3 keyword matched: 'this domain is for sale'",
    # "Status 3 keyword matched: 'click the button below to continue shopping'",

    # # ── Content, Rendering, & API Errors ──────────────────────────────────────
    # "Empty page with zero rendered content",
    # "Empty HTML content",
    # "Screenshot error",
    # "Upload API failed",
    # "Insert API failed",
    # "Chrome initialization failed",
    # "Title indicates error",
    # "Browser error URL",
]


def read_log_lines(filepath):
    """Safely reads log lines supporting UTF-8, UTF-16 (with or without BOM), and fallback encodings."""
    # 1. Check for UTF-16 Byte Order Mark (BOM) first (common in Windows PowerShell output)
    try:
        with open(filepath, "rb") as f:
            header = f.read(2)
        if header in (b"\xff\xfe", b"\xfe\xff"):
            with open(filepath, "r", encoding="utf-16", errors="replace") as f:
                return [line.strip() for line in f if line.strip()]
    except Exception:
        pass

    # 2. Try standard UTF-8 without errors="replace" so genuine UnicodeDecodeError can trigger fallback
    for enc in ("utf-8", "utf-16", "latin1"):
        try:
            with open(filepath, "r", encoding=enc) as f:
                return [line.strip() for line in f if line.strip()]
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"[Error] Failed to read {filepath} with {enc}: {e}")
            break

    # 3. Last-resort fallback with error replacement
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []


def parse_unsuccessful_ads(lines):
    """
    Parses all status 3 and skipped ad entries from payloads.log lines.
    Returns: dict of {ad_id: {'id': int, 'destination_url': str, 'reason': str}}
    """
    ads = {}

    for line in lines:
        # Pattern 1: {"skipped": true, "ad_id": 474, "reason": "...", "destination_url": "..."}
        if "skipped" in line and ("true" in line or "True" in line):
            m = re.search(r"\{.*\}", line)
            if m:
                try:
                    d = json.loads(m.group(0))
                    aid = d.get("ad_id")
                    reason = d.get("reason", "").strip()
                    url = d.get("destination_url") or d.get("final_url", "")
                    if aid:
                        if aid not in ads:
                            ads[aid] = {"id": aid, "reason": reason, "destination_url": url}
                        else:
                            if url and not ads[aid].get("destination_url"):
                                ads[aid]["destination_url"] = url
                            if reason and not ads[aid].get("reason"):
                                ads[aid]["reason"] = reason
                except Exception:
                    pass

        # Pattern 2: [STATUS 3 PAYLOAD] ad_id=474 | reason=... | payload={...}
        elif "[STATUS 3 PAYLOAD]" in line:
            m_ad = re.search(r"ad_id=(\d+)", line)
            m_reason = re.search(r"reason=([^|]+)", line)
            aid = int(m_ad.group(1)) if m_ad else None
            reason = m_reason.group(1).strip() if m_reason else ""
            
            dest = ""
            p_str = line.split("payload=")[-1]
            try:
                pdata = json.loads(p_str)
                dest = pdata.get("insertData", {}).get("destinations", "")
            except Exception:
                pass

            if aid:
                if aid not in ads:
                    ads[aid] = {"id": aid, "reason": reason, "destination_url": dest}
                else:
                    if dest and not ads[aid].get("destination_url"):
                        ads[aid]["destination_url"] = dest
                    if reason and not ads[aid].get("reason"):
                        ads[aid]["reason"] = reason

        # Pattern 3: [SCRAPED PAYLOAD status=3]
        elif "[SCRAPED PAYLOAD status=3]" in line:
            p_str = line.split("[SCRAPED PAYLOAD status=3] ")[-1]
            try:
                pdata = json.loads(p_str)
                aid = pdata.get("ad_id")
                dest = pdata.get("insertData", {}).get("destinations", "")
                if aid and aid not in ads:
                    ads[aid] = {"id": aid, "reason": "Scraped with status=3 (login gate/auth checkpoint)", "destination_url": dest}
            except Exception:
                pass

    return ads


def matches_filter(reason, selected_categories):
    """Checks if the ad reason matches any selected category (flexible substring match)."""
    if selected_categories is None:
        return True  # No filter: accept all
    if not selected_categories:
        return False

    r_lower = (reason or "").strip().lower()
    for cat in selected_categories:
        c_lower = cat.strip().lower()
        if not c_lower:
            continue
        # Exact match or substring containment in either direction
        if c_lower == r_lower or c_lower in r_lower or r_lower.startswith(c_lower):
            return True
    return False


def format_ads_code(ad_list):
    """Formats the list of ads into ready-to-copy Python code matching test_sample_ads.py."""
    lines = ["[\n"]
    for i, ad in enumerate(ad_list):
        aid = ad["id"]
        reason = ad.get("reason", "").replace("\n", " ").replace("\r", "").strip()
        url = ad.get("destination_url", "").replace('"', '\\"')
        
        comment = f"  # {reason}" if reason else ""
        lines.append(f'    {{\n        "id": {aid},{comment}\n        "destination_url": "{url}",\n    }}')
        if i < len(ad_list) - 1:
            lines.append(",\n")
        else:
            lines.append("\n")
    lines.append("]\n")
    return "".join(lines)


def main():
    target_log = LOG_FILE
    list_only = False
    show_all = False
    custom_filters = []
    custom_limit = None
    skip_next = False

    args = sys.argv[1:]
    for idx, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg in ("--all", "-a"):
            show_all = True
        elif arg in ("--categories", "--list-categories", "-c"):
            list_only = True
        elif arg in ("--filter", "-f") and idx + 1 < len(args):
            custom_filters.append(args[idx + 1])
            skip_next = True
        elif arg in ("--limit", "-n") and idx + 1 < len(args):
            try:
                custom_limit = int(args[idx + 1])
            except ValueError:
                pass
            skip_next = True
        elif not arg.startswith("-"):
            target_log = arg

    # Search candidates if default path is relative
    if not os.path.isfile(target_log):
        candidates = [
            target_log,
            os.path.join("logs", os.path.basename(target_log)),
            os.path.join("..", "logs", os.path.basename(target_log)),
            "logs/payloads.log",
            "logs/youtube-payloads.log",
        ]
        for c in candidates:
            if c and os.path.isfile(c):
                target_log = c
                break

    if not os.path.isfile(target_log):
        print(f"\n[Error] Log file not found: '{target_log}'")
        print("Please check LOG_FILE variable at the top of this script or pass the path via CLI:")
        print("  python unsuccessfull-ads-form-payloads.py logs/my-log.log\n")
        sys.exit(1)

    print("=" * 80)
    print("           POWERADSPY UNSUCCESSFUL ADS EXTRACTOR FROM LOG")
    print(f"  Target Log File : {target_log}")
    print("=" * 80)

    lines = read_log_lines(target_log)
    if not lines:
        print("[Warning] Log file is empty or could not be decoded.")
        sys.exit(0)

    all_unsuccessful = parse_unsuccessful_ads(lines)
    print(f"Found {len(all_unsuccessful)} total unique unsuccessful ads in log.\n")

    # Group counts by detected reason
    category_counts = {}
    for ad in all_unsuccessful.values():
        r = ad.get("reason", "Unknown")
        # Simplify dynamic upload/empty HTML messages for aggregation
        clean_r = r
        if clean_r.startswith("Empty HTML content --"):
            clean_r = "Empty HTML content"
        elif clean_r.startswith("Upload API failed: HTTP="):
            clean_r = clean_r.split(",")[0]
        category_counts[clean_r] = category_counts.get(clean_r, 0) + 1

    # If --categories flag was passed, list all found reasons and exit
    if list_only:
        print("Discovered Categories in this Log File:")
        print("-" * 80)
        for cat, cnt in sorted(category_counts.items(), key=lambda x: -x[1]):
            print(f"  {cnt:>5} ads  |  {cat}")
        print("-" * 80)
        return

    if custom_filters:
        active_filters = custom_filters
    elif show_all:
        active_filters = None
    else:
        active_filters = SELECTED_CATEGORIES

    if active_filters is not None and len(active_filters) == 0:
        print("=" * 80)
        print("  [NOTICE] All categories in SELECTED_CATEGORIES are currently commented out!")
        print("  Uncomment the categories you want to extract at the top of the file,")
        print("  or pass --all to extract everything.")
        print("=" * 80)
        print("\nAvailable Categories in this Log File:")
        for cat, cnt in sorted(category_counts.items(), key=lambda x: -x[1]):
            print(f"  {cnt:>5} ads  |  {cat}")
        print()
        return

    # Filter ads
    filtered_ads = []
    for ad in all_unsuccessful.values():
        if matches_filter(ad.get("reason", ""), active_filters):
            filtered_ads.append(ad)

    # Sort deterministically by ad ID
    filtered_ads.sort(key=lambda x: x["id"])

    effective_limit = custom_limit or MAX_ADS
    if effective_limit and len(filtered_ads) > effective_limit:
        filtered_ads = filtered_ads[:effective_limit]

    filter_desc = "ALL (no filter)" if active_filters is None else f"{len(active_filters)} selected category/categories"
    print(f"Active Filter      : {filter_desc}")
    print(f"Matching Ads Found : {len(filtered_ads)}\n")

    if not filtered_ads:
        print("No ads matched your selected categories. Available categories in log:")
        for cat, cnt in sorted(category_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  - {cat} ({cnt} ads)")
        return

    # Generate Python code output
    code_output = format_ads_code(filtered_ads)

    print("-" * 80)
    print("COPY-PASTE READY OUTPUT FOR test_sample_ads.py (SAMPLE_ADS = [...]):")
    print("-" * 80)
    print(code_output)
    print("-" * 80)

    # Save to file if configured
    if OUTPUT_FILE:
        try:
            out_dir = os.path.dirname(OUTPUT_FILE)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
                out.write(code_output)
            print(f"\n[SUCCESS] Saved {len(filtered_ads)} ads to: {OUTPUT_FILE}\n")
        except Exception as e:
            print(f"[Warning] Failed to save output to {OUTPUT_FILE}: {e}")


if __name__ == "__main__":
    main()
