#!/usr/bin/env python3
"""PowerAdSpy Ad-Scraping Regression Test Suite CLI.

Usage:
    # 1. Run standard fast offline regression suite (recommended before git push)
    python run_regression_tests.py

    # 2. Run all tests in the repository (unit + pipeline + regression)
    python run_regression_tests.py --all

    # 3. Run live end-to-end regression tests against real ad destinations
    python run_regression_tests.py --live

    # 4. Run a specific ad by ID or case code
    python run_regression_tests.py --ad 134233

    # 5. Run live ad with visual browser window popup
    python run_regression_tests.py --ad 134233 --headed
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import unittest

# Ensure UTF-8 output across Windows & Linux consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from tests.regression.regression_runner import (
    load_regression_cases,
    get_regression_case_by_id,
    run_live_ad,
)


def run_unit_regression() -> bool:
    """Executes the offline regression test suite."""
    print("\n" + "=" * 76)
    print("      RUNNING FAST OFFLINE AD-SCRAPING REGRESSION TEST SUITE")
    print("=" * 76)
    suite = unittest.defaultTestLoader.loadTestsFromName("tests.regression.test_ad_regression")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


def run_all_tests() -> bool:
    """Executes all tests in the tests/ directory."""
    print("\n" + "=" * 76)
    print("         RUNNING COMPLETE TEST SUITE (UNIT + PIPELINE + REGRESSION)")
    print("=" * 76)
    suite = unittest.defaultTestLoader.discover("tests")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


def run_live_cases(ad_filter: str | None = None, headed: bool = False) -> bool:
    """Executes live scraping on regression cases."""
    print("\n" + "=" * 76)
    print("         RUNNING LIVE AD-SCRAPING REGRESSION SUITE")
    if headed:
        print("  [VISUAL POPUP ACTIVE] Browser window will appear during execution")
    else:
        print("  [HEADLESS ACTIVE] Running silently in background")
    print("=" * 76)

    cases = load_regression_cases()
    if ad_filter:
        cases = [
            c for c in cases
            if str(c.get("id")) == str(ad_filter).strip()
            or str(c.get("case_code", "")).lower() == str(ad_filter).lower()
        ]
        if not cases:
            print(f"[ERROR] No regression case found matching filter: {ad_filter}")
            return False

    # Filter to cases with destination URLs
    cases_to_run = [c for c in cases if c.get("ad_data", {}).get("destination_url")]
    print(f"Total live ads to process: {len(cases_to_run)}\n")

    results = []
    all_passed = True
    for idx, case in enumerate(cases_to_run, 1):
        ad_id = case.get("id")
        code = case.get("case_code", "")
        title = case.get("title", "")
        expected_status = case.get("expected", {}).get("status", 2)
        expected_reason = case.get("expected", {}).get("reason_contains")

        print("-" * 76)
        print(f"[{idx}/{len(cases_to_run)}] {code} (Ad ID: {ad_id}) - {title}")
        print(f"  URL: {case['ad_data'].get('destination_url')}")
        print(f"  Expected Status: {expected_status}")

        res = run_live_ad(dict(case["ad_data"]), headless=not headed)
        results.append((case, res))

        status_ok = (res["status"] == expected_status)
        reason_ok = True
        if expected_reason and expected_reason not in res.get("reason", ""):
            reason_ok = False

        if status_ok and reason_ok:
            print(f"  [PASS] Got status: {res['status']} in {res['elapsed_seconds']}s")
        else:
            all_passed = False
            print(f"  [FAIL] Expected status {expected_status}, got {res['status']} ({res.get('reason')})")

    print("\n" + "=" * 76)
    print("                             LIVE REGRESSION SUMMARY")
    print("=" * 76)
    for case, r in results:
        code = case.get("case_code", "")
        ad_id = r["ad_id"]
        exp = case.get("expected", {}).get("status")
        got = r["status"]
        verdict = "[PASS]" if exp == got else "[FAIL]"
        print(f"  {verdict} {code:<8} (Ad {ad_id:<7}) | Expected: {exp} | Actual: {got} | {r['elapsed_seconds']:>5}s | {r['destination_url'][:30]}")
    print("=" * 76 + "\n")

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="PowerAdSpy Ad-Scraping Regression Test Suite")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run the complete test suite across the entire project",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live regression tests against real ad destinations",
    )
    parser.add_argument(
        "--ad",
        type=str,
        default=None,
        help="Run a specific ad by ID or case code (e.g. 134233 or REG-001)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Display visual browser window (for live ad visual inspection)",
    )

    args = parser.parse_args()

    t_start = time.time()
    if args.ad:
        success = run_live_cases(ad_filter=args.ad, headed=args.headed)
    elif args.live:
        success = run_live_cases(headed=args.headed)
    elif args.all:
        success = run_all_tests()
    else:
        success = run_unit_regression()

    elapsed = round(time.time() - t_start, 2)
    if success:
        print(f"\n[REGRESSION SUITE PASSED] All checks completed successfully in {elapsed}s.\n")
        sys.exit(0)
    else:
        print(f"\n[REGRESSION SUITE FAILED] One or more test cases failed in {elapsed}s.\n", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
