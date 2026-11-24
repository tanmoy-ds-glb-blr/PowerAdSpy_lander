"""Core runner and utilities for PowerAdSpy ad-scraping regression testing."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REGRESSION_DIR = Path(__file__).resolve().parent
_CASES_JSON_PATH = _REGRESSION_DIR / "regression_cases.json"

logger = logging.getLogger("regression_runner")


class DummyCounter:
    """Mock Prometheus Counter for isolated test runs."""
    def labels(self, **_kwargs):
        return self

    def inc(self, _value=1):
        pass


class DummyMetric:
    """Mock Prometheus Metrics container matching new_lander.py requirements."""
    def __init__(self):
        self.processed_configured_lander_url = DummyCounter()
        self.updated_configured_lander = DummyCounter()
        self.configured_lander_get = DummyCounter()
        # Aliases used in different modules
        self.processed_lander_url = self.processed_configured_lander_url
        self.updated_lander = self.updated_configured_lander
        self.lander_get = self.configured_lander_get


def load_regression_cases(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Loads all regression test cases from regression_cases.json.

    Args:
        category: Optional category filter (e.g. 'valid_lander', 'bot_waf_challenge').
    """
    if not _CASES_JSON_PATH.is_file():
        raise FileNotFoundError(f"Regression cases file missing: {_CASES_JSON_PATH}")

    with open(_CASES_JSON_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if category:
        cases = [c for c in cases if c.get("category") == category]

    return cases


def get_regression_case_by_id(identifier: Any) -> Optional[Dict[str, Any]]:
    """Lookup a regression case by its ad id or case_code."""
    cases = load_regression_cases()
    str_ident = str(identifier).strip()
    for c in cases:
        if str(c.get("id")) == str_ident or str(c.get("case_code", "")).lower() == str_ident.lower():
            return c
    return None


def run_live_ad(
    ad_data: Dict[str, Any],
    headless: bool = True,
    logger_override: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """Executes live scraping on a single ad using new_lander.scraping.

    Args:
        ad_data: Dictionary containing ad properties ('id', 'destination_url', 'iso', etc.)
        headless: True for background execution, False to display visual browser window
        logger_override: Custom logger instance

    Returns:
        Structured result dictionary with status, reason, success, and timing.
    """
    import new_lander
    from helper import init

    if "id" not in ad_data and "ad_id" in ad_data:
        ad_data["id"] = ad_data["ad_id"]

    ad_id = ad_data.get("id", 0)
    destination_url = ad_data.get("destination_url", "")
    iso = ad_data.get("iso", ["us"])

    os.environ["HEADLESS"] = "true" if headless else "false"

    run_logger = logger_override or logging.getLogger(f"reg_test_{ad_id}")
    error_logger = logging.getLogger(f"reg_test_err_{ad_id}")
    metric = DummyMetric()

    t0 = time.time()
    try:
        success = new_lander.scraping(
            single_data=ad_data,
            metric=metric,
            lander_logger=run_logger,
            port="reg_test",
            instance_no=f"reg_{ad_id}",
            count=0,
            error_logger=error_logger,
        )
    except Exception as exc:
        success = False
        ad_data["_result_status"] = 3
        ad_data["_result_reason"] = f"Exception: {exc}"

    elapsed = round(time.time() - t0, 2)
    res_status = ad_data.get("_result_status", 2 if success else 3)
    res_reason = ad_data.get("_result_reason", "")

    return {
        "ad_id": ad_id,
        "destination_url": destination_url,
        "iso": iso,
        "success": bool(success),
        "status": res_status,
        "reason": res_reason,
        "elapsed_seconds": elapsed,
        "ad_data": ad_data,
    }


def evaluate_mock_page_status(mock_page) -> tuple[bool, str]:
    """Helper to evaluate check_page_status using new_lander logic."""
    import new_lander
    return new_lander.check_page_status(mock_page)


def evaluate_mock_login_gate(
    mock_page,
    destination_url: str = "",
    final_url: str = "",
    body_text: str = "",
) -> tuple[bool, str]:
    """Helper to evaluate is_login_or_signup_page using new_lander logic."""
    import new_lander
    return new_lander.is_login_or_signup_page(
        mock_page,
        destination_url=destination_url,
        final_url=final_url,
        ret_text=body_text,
    )
