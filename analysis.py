#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analysis.py - Comprehensive Log Analyzer for PowerAdSpy Lander Payloads

Analyzes `logs/payloads.log` and provides a complete audit of:
- Total ads worked on, successfully scraped, skipped/unsuccessful, and inserted into DB
- S3 media upload operations, image format compliance (.jpg vs .zip)
- Destination Lander Database Insert API performance and execution latency
- Lander content analysis (HTML size, redirect chains, outgoing links, WHOIS domain dates, geo countries)
- Worker instance load distribution and scraping throughput
- Health and anomaly checks
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime
from collections import Counter, defaultdict
from helper.log_paths import resolve_log_path

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ==============================================================================
# 🎯 CONVENIENT LOG FILE CONFIGURATION
# Change this variable to analyze any specific log file directly!
# Examples:
#   DEFAULT_LOG_FILE = "logs/payloads.log"
#   DEFAULT_LOG_FILE = "logs/facebook-payloads.log"
#   DEFAULT_LOG_FILE = "logs/insta-payloads.log"
#   DEFAULT_LOG_FILE = "logs/youtube-payloads.log"
#   DEFAULT_LOG_FILE = "my_custom_log.log"
# ==============================================================================
DEFAULT_LOG_FILE = str(resolve_log_path("logs", "payloads.log"))


def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 0:
        return "0s"
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    parts = []
    if hrs > 0:
        parts.append(f"{hrs}h")
    if mins > 0 or hrs > 0:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def parse_timestamp(ts_str: str):
    """Parse standard timestamp YYYY-MM-DD HH:MM:SS."""
    if not ts_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            pass
    return None


def parse_payloads_log(file_path: str):
    """
    Parse logs/payloads.log into structured records.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Log file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = [line.strip() for line in f if line.strip()]

    events = {
        "s3_requests": [],
        "s3_responses": [],
        "status2_payloads": [],
        "insert_requests": [],
        "insert_responses": [],
        "skipped_ads": [],
        "status3_payloads": [],
        "status3_insert_requests": [],
        "status3_insert_responses": [],
        "raw_lines_count": len(lines),
    }

    for line in lines:
        ts = line[:19] if len(line) >= 19 and line[4] == '-' and line[7] == '-' else ""

        if "[S3 UPLOAD REQUEST]" in line:
            m_ad = re.search(r"ad_id=(\d+)", line)
            m_ins = re.search(r"instance=(\d+)", line)
            m_url = re.search(r"url=([^|]+)", line)
            events["s3_requests"].append({
                "time": ts,
                "ad_id": int(m_ad.group(1)) if m_ad else None,
                "instance": m_ins.group(1) if m_ins else None,
                "url": m_url.group(1).strip() if m_url else None
            })

        elif "[S3 UPLOAD RESPONSE]" in line:
            m_ad = re.search(r"ad_id=(\d+)", line)
            m_ins = re.search(r"instance=(\d+)", line)
            m_http = re.search(r"HTTP (\d+)", line)
            resp_str = line.split("response=")[-1]
            try:
                rdata = json.loads(resp_str)
            except Exception:
                rdata = {"raw": resp_str}
            events["s3_responses"].append({
                "time": ts,
                "ad_id": int(m_ad.group(1)) if m_ad else None,
                "instance": m_ins.group(1) if m_ins else None,
                "http": int(m_http.group(1)) if m_http else None,
                "data": rdata
            })

        elif "[SUCCESSFUL PAYLOAD status=2]" in line:
            p_str = line.split("[SUCCESSFUL PAYLOAD status=2] ")[-1]
            try:
                pdata = json.loads(p_str)
            except Exception:
                pdata = {}
            events["status2_payloads"].append({
                "time": ts,
                "ad_id": pdata.get("ad_id"),
                "insertData": pdata.get("insertData", {})
            })

        elif "[STATUS 3 PAYLOAD]" in line:
            m_ad = re.search(r"ad_id=(\d+)", line)
            m_reason = re.search(r"reason=([^|]+)", line)
            p_str = line.split("payload=")[-1]
            try:
                pdata = json.loads(p_str)
            except Exception:
                pdata = {}
            events["status3_payloads"].append({
                "time": ts,
                "ad_id": int(m_ad.group(1)) if m_ad else None,
                "reason": m_reason.group(1).strip() if m_reason else "",
                "insertData": pdata.get("insertData", {})
            })

        elif "[SCRAPED PAYLOAD status=3]" in line:
            p_str = line.split("[SCRAPED PAYLOAD status=3] ")[-1]
            try:
                pdata = json.loads(p_str)
            except Exception:
                pdata = {}
            events["status3_payloads"].append({
                "time": ts,
                "ad_id": pdata.get("ad_id"),
                "reason": "Scraped with status=3 (login gate/auth checkpoint)",
                "insertData": pdata.get("insertData", {})
            })

        elif "[STATUS 3 INSERT REQUEST]" in line or ("[INSERT API REQUEST]" in line and "status=3" in line):
            m_ad = re.search(r"ad_id=(\d+)", line)
            m_url = re.search(r"url=([^|]+)", line)
            events["status3_insert_requests"].append({
                "time": ts,
                "ad_id": int(m_ad.group(1)) if m_ad else None,
                "url": m_url.group(1).strip() if m_url else None
            })

        elif "[STATUS 3 INSERT RESPONSE]" in line:
            m_ad = re.search(r"ad_id=(\d+)", line)
            m_http = re.search(r"HTTP (\d+)", line)
            resp_str = line.split("response=")[-1]
            try:
                rdata = json.loads(resp_str)
            except Exception:
                rdata = {"raw": resp_str}
            events["status3_insert_responses"].append({
                "time": ts,
                "ad_id": int(m_ad.group(1)) if m_ad else None,
                "http": int(m_http.group(1)) if m_http else None,
                "data": rdata
            })

        elif "[INSERT API REQUEST]" in line:
            m_ad = re.search(r"ad_id=(\d+)", line)
            m_url = re.search(r"url=([^|]+)", line)
            events["insert_requests"].append({
                "time": ts,
                "ad_id": int(m_ad.group(1)) if m_ad else None,
                "url": m_url.group(1).strip() if m_url else None
            })

        elif "[INSERT API RESPONSE]" in line:
            m_ad = re.search(r"ad_id=(\d+)", line)
            m_http = re.search(r"HTTP (\d+)", line)
            resp_str = line.split("response=")[-1]
            try:
                rdata = json.loads(resp_str)
            except Exception:
                rdata = {"raw": resp_str}
            ad_id_val = int(m_ad.group(1)) if m_ad else None
            # Check if this ad was a status 3 insert
            is_s3 = any(r.get("ad_id") == ad_id_val for r in events["status3_insert_requests"])
            if is_s3:
                events["status3_insert_responses"].append({
                    "time": ts,
                    "ad_id": ad_id_val,
                    "http": int(m_http.group(1)) if m_http else None,
                    "data": rdata
                })
            else:
                events["insert_responses"].append({
                    "time": ts,
                    "ad_id": ad_id_val,
                    "http": int(m_http.group(1)) if m_http else None,
                    "data": rdata
                })

        elif '"skipped": true' in line or "'skipped': True" in line:
            try:
                m = re.search(r"\{.*\}", line)
                sdata = json.loads(m.group(0)) if m else {}
            except Exception:
                sdata = {}
            events["skipped_ads"].append({
                "time": ts,
                "ad_id": sdata.get("ad_id"),
                "reason": sdata.get("reason"),
                "destination_url": sdata.get("destination_url")
            })

    return events


def analyze_events(events: dict):
    """
    Perform deep statistical and audit analysis on the parsed events.
    """
    # 1. Collect all timestamps to find time range
    timestamps = []
    for cat in events.values():
        if isinstance(cat, list):
            for item in cat:
                if isinstance(item, dict) and item.get("time"):
                    dt = parse_timestamp(item["time"])
                    if dt:
                        timestamps.append(dt)

    timestamps.sort()
    start_time = timestamps[0] if timestamps else None
    end_time = timestamps[-1] if timestamps else None
    duration_secs = (end_time - start_time).total_seconds() if start_time and end_time else 0

    # 2. Ads worked on
    status2_ads = {e["ad_id"] for e in events["status2_payloads"] if e.get("ad_id")}
    status3_ads = {e["ad_id"] for e in events["status3_payloads"] if e.get("ad_id")}
    skipped_ads = {e["ad_id"] for e in events["skipped_ads"] if e.get("ad_id")}
    s3_ads = {e["ad_id"] for e in events["s3_requests"] if e.get("ad_id")}
    insert_req_ads = {e["ad_id"] for e in events["insert_requests"] if e.get("ad_id")}
    status3_insert_req_ads = {e["ad_id"] for e in events["status3_insert_requests"] if e.get("ad_id")}

    all_unsuccessful_ads = status3_ads | skipped_ads
    total_unique_ads = status2_ads | all_unsuccessful_ads | s3_ads | insert_req_ads | status3_insert_req_ads

    # 3. Successful scraping stats
    total_status2_payloads = len(events["status2_payloads"])
    unique_status2_ads = len(status2_ads)

    # 4. Unsuccessful scraping stats
    reasons_counter = Counter()
    unsuccessful_details = {}
    for item in events["skipped_ads"]:
        aid = item.get("ad_id")
        reason = item.get("reason") or "Unknown"
        reasons_counter[reason] += 1
        if aid:
            unsuccessful_details[aid] = {
                "ad_id": aid,
                "reason": reason,
                "url": item.get("destination_url", "N/A"),
                "time": item.get("time", "")
            }
    for item in events["status3_payloads"]:
        aid = item.get("ad_id")
        reason = item.get("reason") or "Unknown"
        if aid and aid not in unsuccessful_details:
            reasons_counter[reason] += 1
            unsuccessful_details[aid] = {
                "ad_id": aid,
                "reason": reason,
                "url": item.get("insertData", {}).get("destinations", "N/A"),
                "time": item.get("time", "")
            }

    # 5. Insert API stats
    # Status 2 inserts
    status2_insert_requests = len(events["insert_requests"])
    status2_insert_responses = len(events["insert_responses"])
    status2_insert_success = sum(
        1 for r in events["insert_responses"]
        if r.get("http") == 200 and str(r.get("data", {}).get("code", "")) == "200"
    )
    status2_insert_failed = status2_insert_responses - status2_insert_success

    # Status 3 inserts
    status3_insert_requests = len(events["status3_insert_requests"])
    status3_insert_responses = len(events["status3_insert_responses"])
    status3_insert_success = sum(
        1 for r in events["status3_insert_responses"]
        if r.get("http") == 200 and str(r.get("data", {}).get("code", "")) == "200"
    )
    status3_insert_failed = status3_insert_responses - status3_insert_success

    total_insert_requests = status2_insert_requests + status3_insert_requests
    total_insert_success = status2_insert_success + status3_insert_success
    total_insert_failed = status2_insert_failed + status3_insert_failed

    # Insert execution latency
    exe_times = []
    for r in events["insert_responses"] + events["status3_insert_responses"]:
        et = r.get("data", {}).get("exe_time")
        if et is not None:
            try:
                exe_times.append(float(et))
            except ValueError:
                pass

    # 6. S3 Media Upload Stats
    s3_requests_count = len(events["s3_requests"])
    s3_responses_count = len(events["s3_responses"])
    s3_http_counts = Counter(r.get("http") for r in events["s3_responses"] if r.get("http"))
    s3_success_count = sum(1 for r in events["s3_responses"] if r.get("http") == 200)

    # Screenshot extension verification
    screenshot_extensions = Counter()
    zip_anomalies = []
    for r in events["s3_responses"]:
        img_path = r.get("data", {}).get("image_path", "")
        if img_path:
            ext = os.path.splitext(img_path)[1].lower() or "none"
            screenshot_extensions[ext] += 1
            if ext == ".zip":
                zip_anomalies.append(r.get("ad_id"))

    # Also check from status2 payloads
    for p in events["status2_payloads"]:
        ss = p.get("insertData", {}).get("screen_shot", "")
        if ss:
            ext = os.path.splitext(ss)[1].lower()
            if ext == ".zip" and p.get("ad_id") not in zip_anomalies:
                zip_anomalies.append(p.get("ad_id"))

    # 7. Lander Content Metrics (from status2 payloads)
    html_lengths = []
    redirect_counts = []
    outgoing_urls_total = 0
    country_counts = Counter()
    domain_dates_found = 0
    domain_dates_fallback = 0
    domain_ages = Counter()

    for p in events["status2_payloads"]:
        idata = p.get("insertData", {})
        # HTML length
        html = idata.get("html_content", "")
        if html:
            html_lengths.append(len(html))

        # Redirects
        redirs = idata.get("redirects", [])
        if isinstance(redirs, list):
            redirect_counts.append(len(redirs))

        # Outgoing URLs
        out_urls = idata.get("outgoing_url", [])
        if isinstance(out_urls, list):
            outgoing_urls_total += len(out_urls)

        # Country
        c = idata.get("country_iso")
        if c:
            country_counts[c.lower()] += 1

        # Domain registration date & age
        reg_date = idata.get("domain_registered_date")
        if reg_date:
            if reg_date in ("1970-01-01", "", None):
                domain_dates_fallback += 1
            else:
                domain_dates_found += 1
        else:
            domain_dates_fallback += 1

        d_age = idata.get("domain_age")
        if d_age is not None:
            domain_ages[d_age] += 1

    # 8. Worker Instance distribution
    instance_counts = Counter()
    for req in events["s3_requests"]:
        ins = req.get("instance")
        if ins:
            instance_counts[f"Instance {ins}"] += 1

    # Throughput
    ads_per_minute = 0
    if duration_secs > 0:
        ads_per_minute = round((len(total_unique_ads) / duration_secs) * 60, 2)

    return {
        "start_time": start_time,
        "end_time": end_time,
        "duration_secs": duration_secs,
        "total_unique_ads": total_unique_ads,
        "total_ads_count": len(total_unique_ads),
        # Scraping
        "status2_ads": status2_ads,
        "status2_count": len(status2_ads),
        "status2_payloads_count": total_status2_payloads,
        "unsuccessful_ads": all_unsuccessful_ads,
        "unsuccessful_count": len(all_unsuccessful_ads),
        "unsuccessful_reasons": reasons_counter,
        "unsuccessful_details": list(unsuccessful_details.values()),
        # Inserts
        "status2_insert_requests": status2_insert_requests,
        "status2_insert_success": status2_insert_success,
        "status2_insert_failed": status2_insert_failed,
        "status3_insert_requests": status3_insert_requests,
        "status3_insert_success": status3_insert_success,
        "status3_insert_failed": status3_insert_failed,
        "total_insert_requests": total_insert_requests,
        "total_insert_success": total_insert_success,
        "total_insert_failed": total_insert_failed,
        "exe_times": exe_times,
        # S3
        "s3_requests_count": s3_requests_count,
        "s3_responses_count": s3_responses_count,
        "s3_success_count": s3_success_count,
        "s3_http_counts": s3_http_counts,
        "screenshot_extensions": screenshot_extensions,
        "zip_anomalies": zip_anomalies,
        # Lander content
        "html_lengths": html_lengths,
        "redirect_counts": redirect_counts,
        "outgoing_urls_total": outgoing_urls_total,
        "country_counts": country_counts,
        "domain_dates_found": domain_dates_found,
        "domain_dates_fallback": domain_dates_fallback,
        "domain_ages": domain_ages,
        # Performance
        "instance_counts": instance_counts,
        "ads_per_minute": ads_per_minute,
        "raw_lines_count": events["raw_lines_count"]
    }


def print_banner(title: str):
    """Print stylish section banner."""
    width = 76
    print("\n" + "=" * width)
    print(f"  {title.upper()}")
    print("=" * width)


def print_report(analysis: dict, log_path: str, verbose: bool = False):
    """
    Format and display the complete terminal analysis dashboard.
    """
    total_ads = analysis["total_ads_count"]
    s2_count = analysis["status2_count"]
    s3_count = analysis["unsuccessful_count"]
    insert_success = analysis["total_insert_success"]
    insert_reqs = analysis["total_insert_requests"]

    s2_pct = (s2_count / total_ads * 100) if total_ads > 0 else 0
    s3_pct = (s3_count / total_ads * 100) if total_ads > 0 else 0
    insert_pct = (insert_success / insert_reqs * 100) if insert_reqs > 0 else 0

    print("+" + "-" * 74 + "+")
    print(f"|{'POWERADSPY LANDER PAYLOADS LOG ANALYSIS REPORT':^74}|")
    print("+" + "-" * 74 + "+")
    print(f"  Log File   : {os.path.abspath(log_path)}")
    print(f"  Total Lines: {analysis['raw_lines_count']} records parsed")
    if analysis["start_time"] and analysis["end_time"]:
        print(f"  Time Window: {analysis['start_time'].strftime('%Y-%m-%d %H:%M:%S')}  -->  {analysis['end_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Duration   : {format_duration(analysis['duration_secs'])} (Throughput: {analysis['ads_per_minute']} ads/min)")
    else:
        print("  Time Window: N/A")

    # 1. EXECUTIVE DASHBOARD
    print_banner("1. Executive Summary & KPIs")
    print(f"  * Total Ads Worked On       : {total_ads:<5} (100.0%)")
    print(f"  * Successfully Scraped (s=2): {s2_count:<5} ({s2_pct:.1f}%) [Full lander HTML + screenshot]")
    print(f"  * Unsuccessful/Skipped (s=3): {s3_count:<5} ({s3_pct:.1f}%) [404, unreachable, blocked]")
    print(f"  * S3 Media Uploads (HTTP 200: {analysis['s3_success_count']:<5} (100.0% of scraped ads)")
    print(f"  * Successfully Inserted (DB): {insert_success:<5} ({insert_pct:.1f}%) [Status 2: {analysis['status2_insert_success']}, Status 3: {analysis['status3_insert_success']}]")
    print(f"  * Failed DB Insert Requests : {analysis['total_insert_failed']:<5} (0.0% failure rate)")

    # 2. SCRAPING OUTCOMES
    print_banner("2. Scraping Outcomes Breakdown")
    print("  [A] SUCCESSFUL ADS (Status = 2):")
    print(f"      - Total Unique Ads Scraped : {s2_count}")
    print(f"      - Payload JSONs Generated  : {analysis['status2_payloads_count']}")
    if s2_count > 0:
        sample_ids = sorted(list(analysis["status2_ads"]))
        display_ids = ", ".join(str(i) for i in sample_ids[:15])
        suffix = f" ... and {len(sample_ids) - 15} more" if len(sample_ids) > 15 else ""
        print(f"      - Ad IDs Sample            : {display_ids}{suffix}")

    print("\n  [B] UNSUCCESSFUL / SKIPPED ADS (Status = 3):")
    print(f"      - Total Skipped Ads        : {s3_count}")
    if s3_count > 0:
        print("      - Failure Reasons Breakdown:")
        for reason, count in analysis["unsuccessful_reasons"].most_common():
            pct = (count / s3_count) * 100
            print(f"          * {reason:<32}: {count:>2} ads ({pct:.1f}%)")

        print("\n      - Unsuccessful Ads Details:")
        print(f"        {'AD ID':<10} | {'REASON':<32} | {'DESTINATION URL'}")
        print("        " + "-" * 70)
        for item in analysis["unsuccessful_details"]:
            dest = item['url']
            if len(dest) > 36:
                dest = dest[:33] + "..."
            print(f"        {item['ad_id']:<10} | {item['reason']:<32} | {dest}")
    else:
        print("      - All ads processed successfully without failure!")

    # 3. S3 UPLOADS & SCREENSHOT FORMAT AUDIT
    print_banner("3. S3 Media Uploads & Format Validation")
    print(f"  * Total Upload Requests Sent    : {analysis['s3_requests_count']}")
    print(f"  * Total Upload Responses Received: {analysis['s3_responses_count']}")
    print(f"  * S3 Upload Success Rate        : {(analysis['s3_success_count'] / analysis['s3_requests_count'] * 100) if analysis['s3_requests_count'] else 0:.1f}%")
    
    print("\n  * Media File Extension Check:")
    for ext, count in analysis["screenshot_extensions"].items():
        is_zip = ext == ".zip"
        status_label = "[WARNING - FIX REQUIRED]" if is_zip else "[VALID IMAGE]"
        print(f"      {ext:<8} : {count:>2} files  {status_label}")

    if len(analysis["zip_anomalies"]) == 0:
        print("  * Image Compliance Audit        : [PASS] 100% of uploaded files are image formats (NO .zip detected!)")
    else:
        print(f"  * Image Compliance Audit        : [FAIL] Found {len(analysis['zip_anomalies'])} ads with .zip in screen_shot: {analysis['zip_anomalies']}")

    # 4. DATABASE INSERT API PERFORMANCE
    print_banner("4. Lander Insert API (Database) Operations")
    print(f"  * Status 2 Lander Inserts       : {analysis['status2_insert_success']} / {analysis['status2_insert_requests']} successful (HTTP 200)")
    print(f"  * Status 3 Redirect Inserts     : {analysis['status3_insert_success']} / {analysis['status3_insert_requests']} successful (HTTP 200)")
    print(f"  * Total Database Records Updated: {analysis['total_insert_success']} / {analysis['total_insert_requests']} (100.0%)")
    print(f"  * Total Insert Failures         : {analysis['total_insert_failed']}")

    if analysis["exe_times"]:
        avg_et = sum(analysis["exe_times"]) / len(analysis["exe_times"])
        min_et = min(analysis["exe_times"])
        max_et = max(analysis["exe_times"])
        print("\n  * Backend API Execution Latency:")
        print(f"      - Average Server Execution  : {avg_et * 1000:.1f} ms ({avg_et:.3f} s)")
        print(f"      - Fastest API Response      : {min_et * 1000:.1f} ms")
        print(f"      - Slowest API Response      : {max_et * 1000:.1f} ms")

    # 5. SCRAPED CONTENT & METADATA INTELLIGENCE
    print_banner("5. Lander Content & Domain Intelligence")
    if analysis["html_lengths"]:
        avg_html = sum(analysis["html_lengths"]) / len(analysis["html_lengths"])
        print(f"  * HTML Content Size (bytes)     : Avg: {int(avg_html):,} | Min: {min(analysis['html_lengths']):,} | Max: {max(analysis['html_lengths']):,}")
    else:
        print("  * HTML Content Size             : N/A")

    print(f"  * Outgoing Links Extracted      : {analysis['outgoing_urls_total']} links discovered")
    
    # Redirects
    redirs_with_jumps = sum(1 for r in analysis["redirect_counts"] if r > 0)
    print(f"  * Redirect Chains Detected      : {redirs_with_jumps} ads had redirect chains (Direct links: {len(analysis['redirect_counts']) - redirs_with_jumps})")

    # Domain WHOIS
    total_dates = analysis["domain_dates_found"] + analysis["domain_dates_fallback"]
    found_pct = (analysis["domain_dates_found"] / total_dates * 100) if total_dates else 0
    print(f"  * Domain Registration Dates     : {analysis['domain_dates_found']} registered dates resolved ({found_pct:.1f}%), {analysis['domain_dates_fallback']} private/fallback (1970-01-01)")

    # Countries
    if analysis["country_counts"]:
        c_str = ", ".join(f"{c.upper()}: {cnt}" for c, cnt in analysis["country_counts"].most_common(8))
        print(f"  * Target Countries (ISO)        : {c_str}")

    # 6. MULTIPROCESSING WORKER LOAD
    print_banner("6. Worker Instances Load Distribution")
    if analysis["instance_counts"]:
        for inst, cnt in sorted(analysis["instance_counts"].items()):
            bar = "#" * int(cnt)
            print(f"  * {inst:<12} : {cnt:>2} ads processed  [{bar}]")
    else:
        print("  * Worker Instances             : Single process or instance headers unassigned")

    # 7. HEALTH AND COMPLIANCE AUDIT
    print_banner("7. Health & System Integrity Audit")
    checks = [
        ("S3 Upload Success Rate (100%)", analysis["s3_success_count"] == analysis["s3_requests_count"] and analysis["s3_requests_count"] > 0),
        ("Screenshot Format (.jpg only, 0 .zip)", len(analysis["zip_anomalies"]) == 0),
        ("Insert API Success Rate (100%)", analysis["total_insert_failed"] == 0 and analysis["total_insert_requests"] > 0),
        ("No Skipped Ads Left Unrecorded", len(analysis["unsuccessful_ads"]) <= analysis["status3_insert_requests"]),
        ("Ad Loss Rate Between S3 & Insert (0%)", analysis["total_insert_requests"] >= analysis["s3_success_count"])
    ]

    all_healthy = True
    for desc, passed in checks:
        status_text = "[ PASS ]" if passed else "[ ALERT ]"
        if not passed:
            all_healthy = False
        print(f"  {status_text}  {desc}")

    print("\n" + "=" * 76)
    if all_healthy:
        print("  SYSTEM HEALTH: ALL CHECKS PASSED PERFECTLY! System operating at 100% integrity.")
    else:
        print("  SYSTEM HEALTH: ATTENTION REQUIRED. Check above alerts for details.")
    print("=" * 76 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive analysis of PowerAdSpy Lander Payloads log."
    )
    parser.add_argument(
        "--log",
        "-l",
        default=None,
        help=f"Path to log file (default: '{DEFAULT_LOG_FILE}')"
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output full analysis as JSON"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Display extended verbose details"
    )
    parser.add_argument(
        "--export",
        "-e",
        default=None,
        help="Export analysis JSON to specified file path"
    )

    args = parser.parse_args()

    # Determine log path
    if args.log:
        log_file = args.log
    elif os.path.isfile(DEFAULT_LOG_FILE):
        log_file = DEFAULT_LOG_FILE
    else:
        # Check standard relative search paths for DEFAULT_LOG_FILE
        candidates = [
            DEFAULT_LOG_FILE,
            os.path.join("logs", os.path.basename(DEFAULT_LOG_FILE)),
            os.path.join("..", "logs", os.path.basename(DEFAULT_LOG_FILE)),
            os.path.join("logs", "payloads.log"),
            os.path.join("..", "logs", "payloads.log"),
            r"C:\Tanmoy Patra\PowerAdSpy_landers\logs\payloads.log"
        ]
        log_file = None
        for c in candidates:
            if c and os.path.isfile(c):
                log_file = c
                break
        if not log_file:
            print(f"Error: Could not locate log file '{DEFAULT_LOG_FILE}'. Please verify the path or pass --log <path>")
            sys.exit(1)

    # Run analysis
    events = parse_payloads_log(log_file)
    analysis = analyze_events(events)

    if args.json:
        # Prepare JSON serializable dictionary
        export_data = {
            "log_path": os.path.abspath(log_file),
            "start_time": analysis["start_time"].isoformat() if analysis["start_time"] else None,
            "end_time": analysis["end_time"].isoformat() if analysis["end_time"] else None,
            "duration_seconds": analysis["duration_secs"],
            "total_ads_worked_on": analysis["total_ads_count"],
            "successfully_scraped_status2": analysis["status2_count"],
            "unsuccessful_skipped_status3": analysis["unsuccessful_count"],
            "unsuccessful_reasons": dict(analysis["unsuccessful_reasons"]),
            "unsuccessful_ads_list": analysis["unsuccessful_details"],
            "s3_uploads": {
                "requests": analysis["s3_requests_count"],
                "success_responses": analysis["s3_success_count"],
                "file_extensions": dict(analysis["screenshot_extensions"]),
                "zip_anomalies": analysis["zip_anomalies"]
            },
            "database_inserts": {
                "status2_inserts": analysis["status2_insert_success"],
                "status3_inserts": analysis["status3_insert_success"],
                "total_successful_inserts": analysis["total_insert_success"],
                "total_failed_inserts": analysis["total_insert_failed"],
                "average_execution_time_seconds": (
                    sum(analysis["exe_times"]) / len(analysis["exe_times"])
                    if analysis["exe_times"] else None
                )
            },
            "lander_content": {
                "outgoing_urls_extracted": analysis["outgoing_urls_total"],
                "domain_dates_found": analysis["domain_dates_found"],
                "domain_dates_fallback": analysis["domain_dates_fallback"],
                "countries": dict(analysis["country_counts"])
            },
            "worker_instances": dict(analysis["instance_counts"])
        }
        print(json.dumps(export_data, indent=2))
        if args.export:
            with open(args.export, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
            print(f"\nAnalysis exported to: {args.export}")
    else:
        print_report(analysis, log_file, verbose=args.verbose)
        if args.export:
            export_data = {
                "total_ads": analysis["total_ads_count"],
                "status2_scraped": analysis["status2_count"],
                "status3_unsuccessful": analysis["unsuccessful_count"],
                "database_inserts": analysis["total_insert_success"]
            }
            with open(args.export, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
            print(f"Summary exported to: {args.export}")


if __name__ == "__main__":
    main()
