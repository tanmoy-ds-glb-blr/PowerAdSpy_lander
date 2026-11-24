# PowerAdSpy Ad-Scraping Regression Testing System

## 1. Overview & Purpose

Web scrapers operate against an evolving web landscape where anti-bot firewalls, localized single-page applications (SPAs), authentication walls, and CDN blocks frequently change.

Whenever a defect is discovered (e.g. an ad being falsely marked as blocked, an uncaught WAF signature, an error page marked as success, or a missing field in the payload), that ad and its failure scenario are added to this **Regression Testing Suite**.

This system ensures that:
1. **Bugs never reappear:** Once an ad-scraping defect is resolved, the test suite guarantees future code modifications will not reintroduce the issue.
2. **Pre-Push Gate:** Developers can run a 6-second offline regression suite before pushing to GitHub.
3. **Single Source of Truth:** Test cases are centrally maintained in `tests/regression/regression_cases.json`, powering both automated unit tests and interactive manual runs.

---

## 2. Directory Structure

```text
PowerAdSpy_lander/
├── tests/
│   ├── regression/
│   │   ├── __init__.py                  # Package exports
│   │   ├── regression_cases.json        # Central catalog of all defect scenarios
│   │   ├── regression_runner.py         # Shared runner, metrics mocks, and helpers
│   │   ├── test_ad_regression.py        # Fast offline unit & DOM regression test suite
│   │   └── test_live_ad_regression.py   # Live end-to-end network test suite
│   ├── test_pipeline_v2.py              # Pipeline & API payload tests
│   ├── test_browser_fixture_v2.py       # Playwright browser integration tests
│   ├── test_proxy_health.py             # Proxy health & outage coordination tests
│   └── test_daily_logging.py            # Daily log directory rotation tests
├── run_regression_tests.py              # CLI test runner for developers
├── test_sample_ads.py                   # Interactive sample ads runner (visual popup mode)
└── REGRESSION_TESTING.md                # This documentation
```

---

## 3. Catalog of Tracked Defects & Initial Test Cases

All regression cases are maintained in [`tests/regression/regression_cases.json`](file:///c:/Tanmoy%20Patra/PowerAdSpy_lander/tests/regression/regression_cases.json).

| Case Code | Ad ID | Category | Scenario / Defect History | Expected Status |
| :--- | :--- | :--- | :--- | :--- |
| **`REG-001`** | `134233` | `valid_lander` | **Apple iPhone 18 Pro Rich Lander:** Deep localized Apple lander with international banners, dense DOM, variable aperture specs, and high-resolution media. Must extract complete text, screenshot, and status 2 without timeout or false-positive dead-page skip. | **Status 2** (Success) |
| **`REG-002`** | `134235` | `login_checkpoint` | **Facebook Login Checkpoint:** Ad destination redirected through `l.facebook.com` to Facebook auth checkpoint (`/login`). Must be detected by `is_login_or_signup_page` and classified as Status 3 (Login Gate). | **Status 3** (Login Wall) |
| **`REG-003`** | `134230` | `http_error_403` | **Reliance Digital HTTP 403 Forbidden:** Store server returns HTTP 403 status code due to CDN/firewall. Must be detected by Navigation Timing responseStatus check. | **Status 3** (Blocked) |
| **`REG-004`** | `474` | `http_error_403` | **Saks Fifth Avenue 403 Geo-Block:** Akamai / EdgeSuite 403 Access Denied block on unauthorized IPs. Caught by HTTP status or blocked title markers. | **Status 3** (Blocked) |
| **`REG-005`** | `467` | `bot_waf_challenge` | **SoFi Cloudflare Turnstile:** Embedded `challenges.cloudflare.com` verification script. Caught by `BOT_OR_WAF_MARKERS` in page source. | **Status 3** (WAF Challenge) |
| **`REG-006`** | `399` | `bot_waf_challenge` | **Groupon Cloudflare Challenge Platform:** `challenge-platform` / `cf-browser-verification` interstitial. Caught by Bot/WAF markers. | **Status 3** (WAF Challenge) |
| **`REG-007`** | `79` | `dynamic_spa` | **Ixigo Flights Dynamic SPA:** Client-side React flight search form. Previously risked false-positive empty DOM skip before JS mounted. Must wait for DOM stabilization and extract valid status 2. | **Status 2** (Success) |
| **`REG-008`** | `99901` | `false_positive_prevention` | **E-Commerce Store with Slide-Out Login Drawer:** Rich store page (>200 words) with customer login drawer. Must NOT be falsely classified as a login gate. | **Status 2** (Success) |
| **`REG-009`** | `99902` | `false_positive_prevention` | **i18n Translation Bundle in Script:** Brand store containing error strings in `<script>` JSON dictionary. Must ONLY check visible body text, avoiding false-positive dead-page skip. | **Status 2** (Success) |
| **`REG-010`** | `99903` | `empty_url_handling` | **Missing / Empty Destination URL:** Ad with empty `destination_url`. Handled safely as Status 3 without launching browser or raising uncaught exceptions. | **Status 3** (Skipped) |
| **`REG-011`** | `99904` | `dead_page` | **Genuine 404 Not Found Dead Page:** Visible "404 Page Not Found" in body text. Caught by `DEAD_PAGE_TEXT_MARKERS` and classified as Status 3. | **Status 3** (Dead Page) |

---

## 4. How to Run the Tests

### Option A: Standard Fast Regression Suite (Run Before Git Push)
Executes all offline regression test cases using mock fixtures and real local headless Chromium DOM rendering:
```powershell
.\venv\Scripts\python.exe run_regression_tests.py
```
*(Runs in ~6 seconds; requires no external network or proxy connectivity).*

### Option B: Run All Project Tests (Unit + Pipeline + Regression)
Executes all 71+ test cases across the entire repository:
```powershell
.\venv\Scripts\python.exe run_regression_tests.py --all
# Or via standard unittest:
.\venv\Scripts\python.exe -m unittest discover tests
```

### Option C: Live End-to-End Regression (Real Proxy & Network)
Runs actual web scraping against the sample ad URLs using Playwright:
```powershell
.\venv\Scripts\python.exe run_regression_tests.py --live
```

### Option D: Test a Specific Ad with Visual Browser Window
Allows stepping through a single problematic ad visually:
```powershell
# Using the regression CLI:
.\venv\Scripts\python.exe run_regression_tests.py --ad 134233 --headed

# Or using the interactive sample runner:
.\venv\Scripts\python.exe test_sample_ads.py --ad 134233 --headed
```

---

## 5. How to Add a New Problematic Ad / Defect Case

Whenever an ad encounters a scraping failure in production or manual testing:

### Step 1: Add the Ad to `tests/regression/regression_cases.json`
Append a new entry to the JSON array:
```json
{
  "id": 134500,
  "case_code": "REG-012",
  "title": "BrandName Shopify Store Geo-Redirect",
  "category": "geo_redirect",
  "defect_history": "Ad destination redirected to country picker modal causing layout freeze.",
  "ad_data": {
    "id": 134500,
    "destination_url": "https://example-brand.com/special-deal",
    "iso": ["us"]
  },
  "expected": {
    "status": 2,
    "requires_screenshot": true,
    "min_text_length": 200
  }
}
```

### Step 2: Add an Offline DOM / Unit Check (if applicable)
If the defect relates to a specific WAF signature, login pattern, or status marker, add a test method to [`tests/regression/test_ad_regression.py`](file:///c:/Tanmoy%20Patra/PowerAdSpy_lander/tests/regression/test_ad_regression.py):
```python
def test_brandname_geo_modal_defect(self):
    page = MockSimplePage(url="https://example-brand.com/special-deal", ...)
    is_bad, reason = evaluate_mock_page_status(page)
    self.assertFalse(is_bad)
```

### Step 3: Run the Regression Suite
```powershell
.\venv\Scripts\python.exe run_regression_tests.py
```
Ensure the suite passes with 100% OK.

---

## 6. Pre-Push Verification Checklist

Before pushing any code changes to `origin/main`:

1. **Verify Regression Suite:**
   ```powershell
   .\venv\Scripts\python.exe run_regression_tests.py
   ```
   *Expected: All tests pass with exit code 0.*
2. **Verify Full Test Suite:**
   ```powershell
   .\venv\Scripts\python.exe -m unittest discover tests
   ```
   *Expected: 71+ tests pass.*
3. **Verify Git Status:**
   ```powershell
   git status
   ```
   *Ensure `.env` is NOT staged (only `.env.example` is committed).*
