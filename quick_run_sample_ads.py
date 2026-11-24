import os
import sys
import ast
import json
import time
import logging
import argparse
from pathlib import Path
import multiprocessing as mp

# Ensure UTF-8 output across Windows & Linux consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Always enforce HEADLESS mode by default for speed and background execution
os.environ["HEADLESS"] = "true"

import new_lander
from helper import init
from config import Config

# ==============================================================================
# MANUALLY CONFIGURE YOUR SAMPLE ADS HERE
# You can paste any ad dictionaries here, or pass an external file via CLI:
#   python quick_run_sample_ads.py logs/ads.txt
#   python quick_run_sample_ads.py logs/ads.txt --limit 5
#   python quick_run_sample_ads.py logs/ads.txt --instances 5
# ==============================================================================

SAMPLE_ADS = [
{
        "id": 63,  # Connection Error / Unreachable
        "destination_url": "https://coffee-sensor.com/?oppref=gAAAAABqw0DpaoKQDn5zFBLXRyQ8PyCJzT0Meet7iz1gNmvbrH0gyCeOjCoqWmK4qd7fJL6xzRRPNVwAWMU9Y_XZl5Jzizdl6aiZdJy1pU2WqkcEAEZfp5Uw&olref=gAAAAABqw0DpjmLH-HRnLOwQ0jLxkvjWb0qx6o-P7WisFMu0WQ5On1PtzipjrXW__XaruwvzFqYrhtTE0K8lxJmlvDn8-1yPvVq5FLre0foQsI92XwOmhUh2OPtTmP9tNVsRUvsitcDOwVWuJ3FK_zAFksGSKGZDEQw",
    },
    {
        "id": 64,  # Connection Error / Unreachable
        "destination_url": "https://theartment.com/products/the-retro-chair?utm_source=chatgpt&utm_medium=cpc&utm_campaign=cmpn_6aa10895d3248193801da75e14a9ef9c&utm_content=ad_6aa1089de8588195bb7b4b8421306003&utm_term=adgrp_38259c3085bc81938c96473546698b56&oppref=gAAAAABqw0EYwM8NM8XSU00TWZdvyrR9bQ-S-fsW3mXHl54ArJJ_lMW10skxm4_W3mtvfxyR0E0MT_VYo7z_pVhq-iGyHTjDSWVcP52SSS_9Sm18DvoIyR8w&olref=gAAAAABqw0EY19HmyYI62y7Q0pB886-niqAAx3JvOYg9jyrIL4duARa32_o5nyPz_rXDSVVYrKxP_50l8TrbadXzK_5R8VBkH06vcBc0eo3LgOvLBSAXlCYTRUa_HAgThZryFxYZ25G02-GXjmkxpF8e1ASOGh5LEQw",
    },
    {
        "id": 65,  # Connection Error / Unreachable
        "destination_url": "https://www.letsbeco.com/?https://www.letsbeco.com/collections/buy-more-save-more?utm_source=Chatgpt&utm_medium=GPTADS&utm_campaign=B2G1_Festive&utm_id=OpenAI_B2G1_Festive&oppref=gAAAAABqw0E8kDDn_L9NzJq42RyAeqA_8V33wovixCL5gf7gQn0OvH9wLylu13yl5BOSwM0Md0BW_Peb-TPd2U5Dt_acQjH7atxSNfi2VKBK2ZCkNfwh2uUw&olref=gAAAAABqw0E8n1Sg3CmFzMXfR1-9GPHyzM8LdQkMYj75LtPtY9H63gOKt0a7i57lgLfWsnNhADWqZvFZM2G5Kbzz7U3tSJ9O0naxQ8754ufJWVDSJSTQSVepKr-67WCXBo7ZDForlhTfN1BQTLVT_z_vp-0HrdgoFQw",
    },
    {
        "id": 66,  # Connection Error / Unreachable
        "destination_url": "https://www.nestleprofessional.in/portfolio-campaign?utm_source=openai&utm_medium=cpc&utm_campaign=Brand_Traffic_Ad_Group&utm_content=Brand_Ad5?utm_source%3Dopenai&utm_medium=cpc&utm_campaign=Generic_Traffic_Ad_Group&utm_content=Generic_Ad3&oppref=gAAAAABqw3xMb8-VTOX14M-s3f65IwXq89BvwnsCe27BxgLK8q8W5ZdRo4ap_Sm8HBctFm0x7QKvP0JzCVT884KlG1EJS3bcdTeih9keA8QHb2CSnD7JDYkw&olref=gAAAAABqw3xMFXPX6Jh0DGzKZiXmGw6ldEzp4C9BSO1OdVHa39pde7r2gB8FBBf87xQBEHml9C8aiuZurl_dbZ6QMnAhSlcioO3AjFTFtgM11_sAcIN2Xw0AVzNdK7n4N9PqPo2vcT4nxpdK4p5gv9_yRa2mxEr-Pww",
    },
    {
        "id": 67,  # Connection Error / Unreachable
        "destination_url": "https://cat.as.criteo.com/delivery/ckwcaoa.aspx?r=http://www.myntra.com/Vacuum-Cleaner/ILIFE/ILIFE-A80-Pro-Vacuum--Mop-Robot/28426732/buy&rs=1-nn3BM1ojO7c4HRja74B9CUU6BbsNBRC8AGl1tGk8-ww&r_he=6643770773786196205&cat=216400169&cto_ca=726362&cto_b=12444626&cto_cc=1&cto_ad=3220904&cto_co=IN&cto_z=1834262&cto_oac=%7Bcampaign.id%7D&oppref=gAAAAABqw3xjiEfces7mkB__Ecot8_N6RUIze9t6wnicuEZWUVqB6fkq3Mcj2MlloGC26Db82dhnh5LzqRSppZek9GQkk_-6CgojHkN2N-sEbEBBj6qxOXEw&olref=gAAAAABqw3xjkp2DEbK1y7eZ4MiPm6jRHC2UUEdIEfuiowi2Pb_ke31OGDXgCIVuqQ7zY-zj9ZlQ1jS3BWC_e1rwAWWEl1rrhkrd8NRwUNzodknx5EkcENbgCz6P8Ctgo_f35nLkeNqlVZjBMIuIEZ-HLb8PhB87WQw",
    }
]


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
        # Common Aliases
        self.processed_lander_url = self.processed_configured_lander_url
        self.updated_lander = self.updated_configured_lander
        self.lander_get = self.configured_lander_get


# Worker process global state
_WORKER_ID = None
_CONSOLE_LOCK = None


def _init_worker(worker_id_queue, console_lock):
    """Initializes each worker process in the multiprocessing pool."""
    global _WORKER_ID, _CONSOLE_LOCK
    _CONSOLE_LOCK = console_lock
    try:
        _WORKER_ID = worker_id_queue.get_nowait()
    except Exception:
        _WORKER_ID = os.getpid()

    # Reconfigure encoding in child processes
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Ensure instance-specific temp directories exist
    instance_name = f"quick_worker_{_WORKER_ID}"
    os.makedirs(f"./images/{instance_name}", exist_ok=True)
    os.makedirs(f"./zip/{instance_name}", exist_ok=True)


def _safe_print(msg, lock=None):
    """Thread/Process-safe printing to prevent garbled console logs."""
    use_lock = lock or _CONSOLE_LOCK
    if use_lock:
        with use_lock:
            print(msg, flush=True)
    else:
        print(msg, flush=True)


def _execute_single_ad(task_args):
    """
    Executes a single sample ad inside the worker process.
    task_args: (ad_data, index, total, headless_flag)
    """
    ad_data, index, total, headless_flag = task_args
    worker_id = _WORKER_ID if _WORKER_ID is not None else os.getpid()
    instance_name = f"quick_worker_{worker_id}"

    # Enforce headless mode
    if headless_flag:
        os.environ["HEADLESS"] = "true"
    else:
        os.environ["HEADLESS"] = "false"

    # Normalize ad fields
    if "id" not in ad_data and "ad_id" in ad_data:
        ad_data["id"] = ad_data["ad_id"]
    ad_id = ad_data.get("id", 0)
    destination_url = ad_data.get("destination_url", "")
    iso = ad_data.get("iso", ["us"])

    dest_preview = destination_url[:60] + "..." if len(destination_url) > 60 else destination_url
    _safe_print(f"  [Worker {worker_id}] [{index}/{total}] STARTING Ad ID: {ad_id} | ISO: {iso} | URL: {dest_preview}")

    worker_logger = logging.getLogger(f"quick_{instance_name}")
    worker_err_logger = logging.getLogger(f"quick_{instance_name}_err")
    metric = DummyMetric()

    t0 = time.time()
    try:
        success = new_lander.scraping(
            single_data=ad_data,
            metric=metric,
            lander_logger=worker_logger,
            port=f"800{worker_id}",
            instance_no=instance_name,
            count=0,
            error_logger=worker_err_logger
        )
    except Exception as e:
        _safe_print(f"  [Worker {worker_id}] [ERROR] Scraping exception for Ad ID {ad_id}: {e}")
        success = False

    elapsed = round(time.time() - t0, 2)
    res_status = ad_data.get("_result_status", 2 if success else 3)
    res_reason = ad_data.get("_result_reason", "")

    if res_status == 2 and success:
        status_tag = "[PASS] SUCCESS (status: 2)"
    elif res_status == 3 and success:
        status_tag = f"[GATE] STATUS 3 (status: 3) ({res_reason})"
    else:
        status_tag = f"[SKIP] BLOCKED/FAIL (status: 3) ({res_reason})"

    _safe_print(f"  [Worker {worker_id}] [{index}/{total}] DONE Ad ID: {ad_id} in {elapsed}s -> {status_tag}")

    return {
        "ad_id": ad_id,
        "worker_id": worker_id,
        "index": index,
        "total": total,
        "destination_url": destination_url,
        "success": success,
        "status": res_status,
        "reason": res_reason,
        "elapsed_seconds": elapsed,
    }


def parse_ads_file(file_path):
    """
    Parses an ads file supporting:
      1. Python AST literals (e.g. logs/ads.txt with comments & trailing commas)
      2. Standard JSON lists or single objects
      3. Python files defining SAMPLE_ADS = [...]
    """
    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    raw_text = p.read_text(encoding="utf-8", errors="replace").strip()

    # 1. Try ast.literal_eval (cleanly handles comments and trailing commas)
    try:
        parsed = ast.literal_eval(raw_text)
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict):
            return [parsed]
    except Exception:
        pass

    # 2. Try standard JSON
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict):
            return [parsed]
    except Exception:
        pass

    # 3. Try regex extraction of SAMPLE_ADS = [...]
    import re
    match = re.search(r'SAMPLE_ADS\s*=\s*(\[[\s\S]*?\])\s*(?:\n\w|\Z)', raw_text)
    if match:
        try:
            parsed = ast.literal_eval(match.group(1))
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass

    raise ValueError(f"Unable to parse valid ad data from: {file_path}")


def get_default_instances():
    """Reads INSTANCES from config.yaml under default_settings."""
    try:
        cfg = Config()
        return max(1, int(getattr(cfg, "instances", 1) or 1))
    except Exception:
        return 1


def main():
    default_cfg_instances = get_default_instances()

    parser = argparse.ArgumentParser(
        description="PowerAdSpy Quick Sample Ads Runner (Headless + Multi-Instance)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Path to file containing ads (e.g., logs/ads.txt, ads.json). Defaults to inline SAMPLE_ADS."
    )
    parser.add_argument(
        "-n", "--instances",
        type=int,
        default=None,
        help=f"Number of parallel instances to run (default: {default_cfg_instances} from config.yaml)"
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=None,
        help="Limit number of ads to process from the file/list"
    )
    parser.add_argument(
        "--iso",
        type=str,
        default=None,
        help="Fallback country ISO code if missing from ad dictionary (e.g. 'IN', 'US')"
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in visual (headed) mode (default is headless)"
    )

    args = parser.parse_args()

    instances_count = args.instances if args.instances and args.instances > 0 else default_cfg_instances
    is_headless = not args.headed

    # Determine ads list
    ads_to_run = []
    source_name = "inline SAMPLE_ADS"

    if args.file:
        try:
            ads_to_run = parse_ads_file(args.file)
            source_name = args.file
        except Exception as e:
            print(f"[Error] Failed to load ads from '{args.file}': {e}")
            sys.exit(1)
    else:
        ads_to_run = [ad for ad in SAMPLE_ADS if isinstance(ad, dict) and (ad.get("id") or ad.get("destination_url"))]
        # If inline SAMPLE_ADS is empty and logs/ads.txt exists, notify user
        if not ads_to_run and os.path.isfile("logs/ads.txt"):
            print("[Info] Inline SAMPLE_ADS is empty. Auto-loading from logs/ads.txt...")
            try:
                ads_to_run = parse_ads_file("logs/ads.txt")
                source_name = "logs/ads.txt (auto-detected)"
            except Exception as e:
                print(f"[Warning] Failed to auto-load logs/ads.txt: {e}")

    if not ads_to_run:
        print("[Error] No valid ads found to process! Please define SAMPLE_ADS or pass an ads file.")
        print("Example: python quick_run_sample_ads.py logs/ads.txt --limit 5")
        sys.exit(1)

    if args.limit and args.limit > 0:
        ads_to_run = ads_to_run[:args.limit]

    # Apply fallback ISO if specified
    if args.iso:
        for ad in ads_to_run:
            if "iso" not in ad or not ad["iso"]:
                ad["iso"] = [args.iso.upper()]

    total_ads = len(ads_to_run)
    # Don't spin up more worker instances than ads to process
    active_instances = min(instances_count, total_ads)

    print("=" * 76, flush=True)
    print("      POWERADSPY QUICK SAMPLE ADS RUNNER (HEADLESS + MULTI-INSTANCE)", flush=True)
    print("=" * 76, flush=True)
    print(f"  Source of Ads       : {source_name}", flush=True)
    print(f"  Total Ads to Run    : {total_ads}", flush=True)
    print(f"  Configured Instances: {instances_count} (Active Workers: {active_instances})", flush=True)
    print(f"  Execution Mode      : {'HEADLESS (Silent background)' if is_headless else 'HEADED (Visual popup)'}", flush=True)
    print("=" * 76 + "\n", flush=True)

    start_total_time = time.time()
    results = []

    # Prepare task arguments: (ad_data, index, total, headless_flag)
    task_args_list = [
        (ad, idx, total_ads, is_headless)
        for idx, ad in enumerate(ads_to_run, 1)
    ]

    if active_instances <= 1:
        # Single worker execution (runs cleanly without pool overhead)
        global _WORKER_ID
        _WORKER_ID = 1
        for task_arg in task_args_list:
            res = _execute_single_ad(task_arg)
            results.append(res)
    else:
        # Multi-worker execution via multiprocessing.Pool
        manager = mp.Manager()
        worker_id_queue = manager.Queue()
        for wid in range(1, active_instances + 1):
            worker_id_queue.put(wid)
        console_lock = manager.Lock()

        pool = mp.Pool(
            processes=active_instances,
            initializer=_init_worker,
            initargs=(worker_id_queue, console_lock)
        )

        try:
            # imap_unordered yields results dynamically as soon as any worker finishes an ad
            for res in pool.imap_unordered(_execute_single_ad, task_args_list):
                results.append(res)
            pool.close()
            pool.join()
        except KeyboardInterrupt:
            print("\n\n[ABORT] Received KeyboardInterrupt. Terminating all worker instances...")
            pool.terminate()
            pool.join()
            sys.exit(1)
        finally:
            manager.shutdown()

    total_duration = round(time.time() - start_total_time, 2)

    # Sort results by original index
    results.sort(key=lambda x: x.get("index", 0))

    passed_count = sum(1 for r in results if r["status"] == 2 and r["success"])
    gate_count = sum(1 for r in results if r["status"] == 3 and r["success"])
    fail_count = sum(1 for r in results if not r["success"])

    print("\n" + "=" * 76)
    print("                             EXECUTION SUMMARY")
    print("=" * 76)
    print(
        f"  Total Ads: {total_ads} | "
        f"Passed: {passed_count} | "
        f"Login Gate (status 3): {gate_count} | "
        f"Failed/Blocked: {fail_count} | "
        f"Time: {total_duration}s"
    )
    print("-" * 76)
    print(f"  {'Ad ID':<8} | {'Worker':<10} | {'Status':<30} | {'Time':>6} | {'Destination URL'}")
    print("-" * 76)
    for r in results:
        if r["status"] == 2 and r["success"]:
            status_label = "[PASS] SUCCESS (status: 2)"
        elif r["status"] == 3 and r["success"]:
            status_label = "[GATE] STATUS 3 (status: 3)"
        else:
            status_label = "[SKIP] BLOCKED/FAIL (status: 3)"
        worker_label = f"worker_{r.get('worker_id', 1)}"
        dest = r.get("destination_url", "")
        dest_display = dest[:35] + "..." if len(dest) > 35 else dest
        print(f"  {r['ad_id']:<8} | {worker_label:<10} | {status_label:<30} | {r['elapsed_seconds']:>5}s | {dest_display}")
    print("=" * 76)
    print("Logs generated:")
    print("  - Successful Payloads (status 2)  : logs/<DD-MM-YYYY>/successful_payloads.json")
    print("  - Unsuccessful Ads (status 3)     : logs/<DD-MM-YYYY>/unsuccessful_ads.json")
    print("  - All Transactions & API Requests : logs/<DD-MM-YYYY>/payloads.log")
    print("  - Proxy Connections               : logs/<DD-MM-YYYY>/proxy.log")
    print("=" * 76 + "\n")


if __name__ == "__main__":
    main()
