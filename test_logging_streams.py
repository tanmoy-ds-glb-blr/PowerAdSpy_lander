import os
import sys
import json
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import new_lander
from helper import init
from helper.log_paths import dated_log_path

PASS = "[PASS]"
FAIL = "[FAIL]"


def current_log(filename):
    return str(dated_log_path(
        "logs", filename,
        timezone=str(new_lander.config.get_default("LOG_TIMEZONE") or "Asia/Kolkata"),
        date_format=str(new_lander.config.get_default("LOG_DATE_FORMAT") or "%Y-%m-%d"),
    ))


def step(label):
    print(f"\n{'='*65}")
    print(f"  {label}")
    print(f"{'='*65}")


def main():
    os.makedirs("logs", exist_ok=True)

    # ── Test 1: Proxy Logging (log_proxy_ad) ──────────────────────────────────
    step("Test 1: Verify logs/proxy.log")
    test_ad_1 = {
        "id": 999001,
        "destination_url": "https://example.com/test1",
        "iso": ["us"],
        "publisher_platform": "instagram"
    }
    class MockSession:
        _egress_info = {"ip": "1.2.3.4", "country": "US"}

    mock_sess = MockSession()
    new_lander.log_proxy_ad(test_ad_1, mock_sess, "us")

    proxy_log_path = current_log("proxy.log")
    assert os.path.isfile(proxy_log_path), f"{FAIL} {proxy_log_path} not found"
    
    with open(proxy_log_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    
    assert len(lines) > 0, f"{FAIL} {proxy_log_path} is empty"
    last_entry = json.loads(lines[-1])
    assert last_entry.get("ad_id") == 999001, f"{FAIL} wrong ad_id"
    assert last_entry.get("proxy", {}).get("egress_ip") == "1.2.3.4", f"{FAIL} wrong egress IP"
    assert last_entry.get("ad", {}).get("destination_url") == "https://example.com/test1", f"{FAIL} wrong ad"
    print(f"{PASS}  logs/proxy.log recorded valid proxy entry with ad object:")
    print(f"       ad_id={last_entry['ad_id']} | ip={last_entry['proxy']['egress_ip']} | host={last_entry['proxy']['host']}")

    # ── Test 2: Unsuccessful Ad Logging (log_unsuccessful_ad) ─────────────────
    step("Test 2: Verify logs/unsuccessful_ads.json")
    test_ad_failed = {
        "id": 999002,
        "destination_url": "https://example.com/dead404",
        "iso": ["in"],
        "ad_type": "carousel"
    }
    new_lander.log_unsuccessful_ad(test_ad_failed, "HTTP Error Status 404", final_url="https://example.com/dead404")

    unsuccess_path = current_log("unsuccessful_ads.json")
    assert os.path.isfile(unsuccess_path), f"{FAIL} {unsuccess_path} not found"

    with open(unsuccess_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) > 0, f"{FAIL} {unsuccess_path} is empty"
    last_failed = json.loads(lines[-1])
    assert last_failed.get("ad_id") == 999002, f"{FAIL} wrong ad_id in unsuccessful log"
    assert last_failed.get("reason") == "HTTP Error Status 404", f"{FAIL} wrong reason"
    assert last_failed.get("raw_ad", {}).get("ad_type") == "carousel", f"{FAIL} raw_ad dictionary missing fields"
    print(f"{PASS}  logs/unsuccessful_ads.json recorded raw ad dictionary:")
    print(f"       ad_id={last_failed['ad_id']} | reason={last_failed['reason']} | raw_ad destination={last_failed['raw_ad']['destination_url']}")

    # ── Test 3: Successful Payload Logging (successful_payload_logger) ────────
    step("Test 3: Verify logs/successful_payloads.json & Separation from payloads.log")
    test_payload_status2 = {
        "ad_id": 999003,
        "insertData": {
            "ad_id": 999003,
            "status": 2,
            "destinations": "https://in.puma.com/in/en",
            "screen_shot": "https://s3.amazonaws.com/test_shot.jpg",
            "html_path": "https://s3.amazonaws.com/test_html.zip"
        }
    }
    new_lander.successful_payload_logger.info(json.dumps(test_payload_status2, ensure_ascii=False))

    success_path = current_log("successful_payloads.json")
    assert os.path.isfile(success_path), f"{FAIL} {success_path} not found"

    with open(success_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) > 0, f"{FAIL} {success_path} is empty"
    last_success = json.loads(lines[-1])
    assert last_success.get("ad_id") == 999003, f"{FAIL} wrong ad_id in successful payloads"
    assert last_success.get("insertData", {}).get("status") == 2, f"{FAIL} status is not 2"
    print(f"{PASS}  logs/successful_payloads.json recorded status:2 payload:")
    print(f"       ad_id={last_success['ad_id']} | status={last_success['insertData']['status']} | screenshot={last_success['insertData']['screen_shot']}")

    # Verify that the status 2 payload was NOT written to logs/payloads.log
    payload_log_path = current_log("payloads.log")
    if os.path.isfile(payload_log_path):
        with open(payload_log_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "999003" not in content, f"{FAIL} status=2 payload was unexpectedly logged into logs/payloads.log!"
        print(f"{PASS}  Verified: status=2 payload is NOT duplicated in logs/payloads.log")

    # ── Test 4: General Diagnostics in logs/payloads.log ──────────────────────
    step("Test 4: Verify logs/payloads.log for general diagnostics")
    diag_entry = json.dumps({"skipped": True, "ad_id": 999004, "reason": "Diagnostic test skip"})
    new_lander.payload_logger.info(diag_entry)
    with open(payload_log_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Diagnostic test skip" in content, f"{FAIL} general diagnostic entry missing from payloads.log"
    print(f"{PASS}  logs/payloads.log successfully stores general diagnostic entries")

    # ── Test 5: Real Browser + Bright Data Proxy Integration ──────────────────
    step("Test 5: Live Playwright Proxy Verification")
    res = init.init_dc("us")
    if not res:
        print(f"{FAIL} Playwright initialization failed")
        sys.exit(1)
    page, r_session = res
    try:
        egress = getattr(r_session, "_egress_info", {}) or {}
        print(f"{PASS}  Live egress retrieved from init_dc: IP={egress.get('ip')} | Country={egress.get('country')}")
        assert egress.get("country") == "US", f"{FAIL} unexpected country: {egress}"

        live_ad = {
            "id": 999005,
            "destination_url": "https://in.puma.com/in/en",
            "iso": ["us"]
        }
        new_lander.log_proxy_ad(live_ad, r_session, "us")
        with open(proxy_log_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        last_live = json.loads(lines[-1])
        assert last_live.get("ad_id") == 999005
        assert last_live.get("proxy", {}).get("egress_ip") == egress.get("ip")
        print(f"{PASS}  Live proxy entry written to logs/proxy.log with real egress IP {egress.get('ip')}")
    finally:
        init.close_browser(page)

    # ── All Passed ────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print("  ✅ ALL LOGGING STREAMS VERIFIED SUCCESSFULLY!")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
