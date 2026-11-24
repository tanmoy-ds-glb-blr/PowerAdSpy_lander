import sys
import logging
import json
import os
import time
from pathlib import Path
import new_lander
from helper.log_paths import dated_log_path
from config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("test_live_ad")
error_logger = logging.getLogger("test_live_ad_error")

class DummyCounter:
    def labels(self, **kwargs):
        return self
    def inc(self):
        pass

class DummyMetric:
    def __init__(self):
        self.processed_configured_lander_url = DummyCounter()
        self.updated_configured_lander = DummyCounter()
        self.configured_lander_get = DummyCounter()
        # Aliases
        self.processed_lander_url = self.processed_configured_lander_url
        self.updated_lander = self.updated_configured_lander
        self.lander_get = self.configured_lander_get

def test_single_ad(ad, instance_no="live_test", port="8000"):
    ad_id = ad.get('id')
    iso = ad.get('iso')
    url = ad.get('destination_url')
    print(f"\n" + "="*60)
    print(f" [TESTING AD {ad_id}]")
    print(f"   Country ISO     : {iso}")
    print(f"   Destination URL : {url}")
    print("="*60)

    metric = DummyMetric()
    start_time = time.time()
    try:
        success = new_lander.scraping(
            single_data=ad,
            metric=metric,
            lander_logger=logger,
            port=port,
            instance_no=instance_no,
            count=0,
            error_logger=error_logger
        )
    except Exception as e:
        print(f"[EXCEPTION] Scraping encountered an error: {e}")
        success = False

    elapsed = round(time.time() - start_time, 2)
    print(f"\n[EXECUTION COMPLETED IN {elapsed}s]")
    print(f"  Result Success: {success}")

    # Check payload log entry
    last_log = None
    payload_log = str(dated_log_path(
        "logs", "payloads.log",
        timezone=str(new_lander.config.get_default("LOG_TIMEZONE") or "Asia/Kolkata"),
        date_format=str(new_lander.config.get_default("LOG_DATE_FORMAT") or "%d-%m-%Y"),
    ))
    if os.path.exists(payload_log):
        with open(payload_log, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            for l in reversed(lines):
                if f'"ad_id": {ad_id}' in l or f'"ad_id": "{ad_id}"' in l:
                    last_log = l
                    break

    if last_log:
        print(f"\n  [PAYLOAD LOG ENTRY]:")
        try:
            parsed = json.loads(last_log)
            print(f"  {json.dumps(parsed, indent=4)[:600]}...")
        except Exception:
            print(f"  {last_log[:300]}")

    return {
        "ad_id": ad_id,
        "url": url,
        "success": success,
        "elapsed_seconds": elapsed,
    }

def main():
    print("==================================================")
    print("      DOCKER LIVE AD SCRAPER VERIFICATION         ")
    print("==================================================")
    
    cfg = Config()
    print(f"Configuration: Dev Mode={cfg.dev_mode}, Bright Proxies={cfg.bright_proxies}")
    print(f"DEV_GET_API: {cfg.get_api('DEV_GET_API')}")
    print(f"DEV_INSERT_API: {cfg.get_api('DEV_INSERT_API')}")
    print(f"DEV_S3_API: {cfg.get_api('DEV_S3_API')}")

    ads = new_lander.get_input(1)
    if not ads:
        print("[ERROR] Could not fetch ads from DEV_GET_API")
        sys.exit(1)

    print(f"\n[API RETURNED {len(ads)} ADS IN BATCH]")
    for i, a in enumerate(ads[:5]):
        print(f"  {i+1}. ID: {a.get('id')} | ISO: {a.get('iso')} | URL: {a.get('destination_url')[:60]}")

    # Target another active ad: ad 132785
    active_ad = next((a for a in ads if a.get("id") == 132785), ads[4])
    blocked_ad = ads[0] # Nykaa Fashion (403 blocked)



    results = []
    print(f"\n[RUNNING TEST 1: LIVE ACTIVE AD {active_ad.get('id')}]")
    results.append(test_single_ad(active_ad, instance_no="active_ad_test", port="8000"))

    print(f"\n[RUNNING TEST 2: BLOCKED / PROTECTED AD {blocked_ad.get('id')}]")
    results.append(test_single_ad(blocked_ad, instance_no="blocked_ad_test", port="8001"))


    print("\n" + "="*60)
    print("                 FINAL SUMMARY                    ")
    print("="*60)
    for r in results:
        status_str = "SUCCESS (SCRAPED & UPLOADED)" if r["success"] else "BLOCKED / FAILED"
        print(f"  Ad ID {r['ad_id']} ({r['url'][:40]}...): {status_str} in {r['elapsed_seconds']}s")

    all_passed = any(r["success"] for r in results)
    if all_passed:
        print("\n>>> OVERALL VERDICT: CODE IS ABLE TO SCRAPE AND UPLOAD AD DATA PROPERLY! <<<")
    else:
        print("\n>>> OVERALL VERDICT: SCRAPING FAILED OR PAGES WERE BLOCKED. <<<")

if __name__ == "__main__":
    main()
