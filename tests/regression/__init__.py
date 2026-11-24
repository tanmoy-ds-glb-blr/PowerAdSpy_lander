"""PowerAdSpy Ad-Scraping Regression Testing Suite."""

from .regression_runner import (
    load_regression_cases,
    get_regression_case_by_id,
    run_live_ad,
    evaluate_mock_page_status,
    evaluate_mock_login_gate,
)

__all__ = [
    "load_regression_cases",
    "get_regression_case_by_id",
    "run_live_ad",
    "evaluate_mock_page_status",
    "evaluate_mock_login_gate",
]
