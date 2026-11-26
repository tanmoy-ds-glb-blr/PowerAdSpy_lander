import os
import sys
import json
import time
import logging
from pathlib import Path

# Ensure UTF-8 output across Windows & Linux consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import new_lander
from helper import init
from tests.regression.regression_runner import DummyMetric, load_regression_cases, get_regression_case_by_id

# ==============================================================================
# BROWSER DISPLAY MODE:
# Set HEADLESS = False -> Shows visual browser popup (for Windows desktop testing)
# Set HEADLESS = True  -> Runs silently in background (for Linux servers / Docker / CI)
# ==============================================================================
HEADLESS = False

# CLI argument overrides (optional: python test_sample_ads.py --headless or --headed)
if "--headless" in sys.argv:
    HEADLESS = True
elif "--headed" in sys.argv:
    HEADLESS = False

if not HEADLESS:
    os.environ["HEADLESS"] = "false"
    _orig_init_dc = init.init_dc
    def _headed_init_dc(iso, *args, **kwargs):
        kwargs["headless"] = False
        return _orig_init_dc(iso, *args, **kwargs)
    init.init_dc = _headed_init_dc

    _orig_close_browser = init.close_browser
    def _patient_close_browser(page):
        if page:
            try:
                print("\n  [VISUAL INSPECTION] Waiting 5 seconds before closing browser popup...")
                time.sleep(5)
            except Exception:
                pass
        return _orig_close_browser(page)
    init.close_browser = _patient_close_browser
    init.close_driver = _patient_close_browser
    if hasattr(new_lander, "init"):
        new_lander.init.close_browser = _patient_close_browser
        new_lander.init.close_driver = _patient_close_browser
else:
    os.environ["HEADLESS"] = "true"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("test_sample_ads")
error_logger = logging.getLogger("test_sample_ads_error")

# ==============================================================================
# MANUALLY CONFIGURE YOUR SAMPLE ADS HERE
# Add, remove, or edit any ad dictionaries you want to test specifically.
# To run all regression cases instead, run: python test_sample_ads.py --all
# ==============================================================================

SAMPLE_ADS = [
    {
        "id": 277734,
        "destination_url": "https://www.myhomequote.com/home-quote/gutterquote?a=280&api_key=z4fcR0ywuT2QeKgF&cp=1&t10=yt&googlepixelid=AW-16510757587/ZXynCPae2NIZENPV-MA9&s1=G468_37_169&s4=807055279863&gad_source=2&gad_campaignid=23797465410&gclid=EAIaIQobChMI6JLAv_aklAMVe2AeAh3UJguPEAEYASAAEgIFK_D_BwE",
    }
]


def run_ad(ad_data, index=1, total=1):
    if "id" not in ad_data and "ad_id" in ad_data:
        ad_data["id"] = ad_data["ad_id"]
    ad_id = ad_data.get("id", 0)
    destination_url = ad_data.get("destination_url", "")
    iso = ad_data.get("iso", ["us"])

    case_info = get_regression_case_by_id(ad_id)
    case_label = f"[{case_info.get('case_code')}] {case_info.get('title')}" if case_info else f"Ad ID: {ad_id}"

    print("\n" + "=" * 76)
    print(f"  [{index}/{total}] PROCESSING SAMPLE AD: {case_label}")
    print(f"   Destination URL : {destination_url}")
    print(f"   Country ISO     : {iso}")
    if case_info and case_info.get("defect_history"):
        print(f"   Defect Context  : {case_info['defect_history'][:70]}...")
    print("=" * 76)

    metric = DummyMetric()
    t0 = time.time()
    try:
        success = new_lander.scraping(
            single_data=ad_data,
            metric=metric,
            lander_logger=logger,
            port="test",
            instance_no=f"sample_{ad_id}",
            count=0,
            error_logger=error_logger
        )
    except Exception as e:
        print(f"  [ERROR] Scraping raised unexpected exception: {e}")
        success = False

    elapsed = round(time.time() - t0, 2)
    res_status = ad_data.get("_result_status", 2 if success else 3)
    res_reason = ad_data.get("_result_reason", "")

    print(f"\n  [RESULT for ad_id={ad_id} in {elapsed}s]:")
    if res_status == 2 and success:
        print(f"  [PASS] SUCCESS (status: 2) -> Full lander scraped. Payload in: logs/<YYYY-MM-DD>/successful_payloads.json")
    elif res_status == 3 and success:
        print(f"  [GATE] STATUS 3 (Login Gate / Authentication Wall) -> Scraped & inserted as status: 3 ({res_reason})")
    else:
        print(f"  [SKIP] SKIPPED / BLOCKED (status: 3) -> Logged in: logs/<YYYY-MM-DD>/unsuccessful_ads.json ({res_reason})")

    return {
        "ad_id": ad_id,
        "destination_url": destination_url,
        "success": success,
        "status": res_status,
        "reason": res_reason,
        "elapsed_seconds": elapsed,
    }


def main():
    print("=" * 76)
    print("        POWERADSPY MANUAL SAMPLE ADS RUNNER (NO GET_API CALLS)")
    if not HEADLESS:
        print("   [VISUAL POPUP ACTIVE] Browser window will appear to show live scrolling")
    else:
        print("   [HEADLESS ACTIVE] Running silently in background (HEADLESS=True)")
    print("=" * 76)

    ads_to_run = list(SAMPLE_ADS)

    # Optional CLI support:
    #   python test_sample_ads.py --all (run all regression cases)
    #   python test_sample_ads.py --ad <id> (run specific ad)
    if "--all" in sys.argv:
        try:
            cases = load_regression_cases()
            ads_to_run = [c["ad_data"] for c in cases if c.get("ad_data", {}).get("destination_url")]
            print(f"Loaded all {len(ads_to_run)} regression cases from catalog.")
        except Exception as e:
            print(f"[Warning] Failed to load regression catalog: {e}. Using inline SAMPLE_ADS.")
            ads_to_run = list(SAMPLE_ADS)
    elif "--ad" in sys.argv:
        try:
            ad_idx = sys.argv.index("--ad") + 1
            target_id = sys.argv[ad_idx]
            case = get_regression_case_by_id(target_id)
            if case:
                ads_to_run = [case["ad_data"]]
            else:
                ads_to_run = [a for a in ads_to_run if str(a.get("id")) == str(target_id)]
        except Exception:
            pass
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        custom_file = Path(sys.argv[1])
        if custom_file.is_file():
            try:
                content = json.loads(custom_file.read_text(encoding="utf-8"))
                if isinstance(content, list):
                    ads_to_run = content
                    print(f"Loaded {len(ads_to_run)} ads from: {custom_file}")
                elif isinstance(content, dict):
                    ads_to_run = [content]
                    print(f"Loaded single ad from: {custom_file}")
            except Exception as e:
                print(f"[Warning] Failed to read {custom_file}: {e}. Using regression catalog.")

    print(f"Total ads to process: {len(ads_to_run)}\n")

    results = []
    for i, ad in enumerate(ads_to_run, 1):
        res = run_ad(ad, index=i, total=len(ads_to_run))
        results.append(res)

    print("\n" + "=" * 76)
    print("                             EXECUTION SUMMARY")
    print("=" * 76)
    for r in results:
        if r["status"] == 2:
            status_label = "[PASS] SUCCESS (status: 2)"
        elif r["status"] == 3 and r["success"]:
            status_label = "[GATE] LOGIN WALL (status: 3)"
        else:
            status_label = "[SKIP] BLOCKED/FAIL (status: 3)"
        print(f"  Ad ID: {r['ad_id']:<8} | {status_label:<30} | {r['elapsed_seconds']:>5}s | {r['destination_url'][:30]}")
    print("=" * 76)
    print("Logs generated:")
    print("  - Successful Payloads (status 2)  : logs/<YYYY-MM-DD>/successful_payloads.json")
    print("  - Unsuccessful Ads (status 3)     : logs/<YYYY-MM-DD>/unsuccessful_ads.json")
    print("  - All Transactions & API Requests : logs/<YYYY-MM-DD>/payloads.log")
    print("  - Proxy Connections               : logs/<YYYY-MM-DD>/proxy.log")
    print("=" * 76 + "\n")


if __name__ == "__main__":
    main()
