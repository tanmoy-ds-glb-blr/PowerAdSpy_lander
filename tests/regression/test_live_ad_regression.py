"""Live end-to-end regression tests executing Playwright crawler on sample ads.

These tests execute actual web navigation and proxy scraping.
Skipped by default in offline CI/unit test runs unless RUN_LIVE_REGRESSION=1 is set.
To run:
    RUN_LIVE_REGRESSION=1 python -m unittest tests.regression.test_live_ad_regression
"""

from __future__ import annotations

import os
import unittest

from tests.regression.regression_runner import (
    load_regression_cases,
    get_regression_case_by_id,
    run_live_ad,
)


class LiveAdScrapingRegressionTests(unittest.TestCase):
    """Executes live web scraping against real regression ads."""

    def setUp(self):
        if os.environ.get("RUN_LIVE_REGRESSION", "0").lower() not in ("1", "true", "yes"):
            raise unittest.SkipTest(
                "Skipping live regression test (set RUN_LIVE_REGRESSION=1 to run against live endpoints)"
            )

    def test_live_apple_iphone_18_pro_ad(self):
        """Validates that Ad 134233 (Apple iPhone 18 Pro) scrapes successfully with Status 2."""
        case = get_regression_case_by_id(134233)
        self.assertIsNotNone(case)

        result = run_live_ad(dict(case["ad_data"]), headless=True)
        self.assertEqual(
            result["status"],
            case["expected"]["status"],
            f"Expected status {case['expected']['status']}, got {result['status']}: {result.get('reason')}"
        )
        self.assertTrue(result["success"])

        # Check required fields
        ad_data = result["ad_data"]
        payload = ad_data.get("_last_payload", {})
        insert_data = payload.get("insertData", {})
        if insert_data:
            self.assertEqual(insert_data.get("status"), 2)
            self.assertTrue(insert_data.get("screen_shot"))
            self.assertTrue(insert_data.get("destinations"))


if __name__ == "__main__":
    unittest.main()
