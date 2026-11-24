# Scratch Test Suite & Edge-Case Regression Directory

This directory contains standalone diagnostic scripts, unit tests, and regression verifications for specific landing pages and ads where standard automation logic encounters bugs or edge cases (e.g., sticky scroll tracks, virtualized DOMs, WebGL canvases, full-screen preloaders, or cookie consent walls).

---

## 🧹 Maintenance & Cleanup

### `1_clear_images_from_scratch.py`
Deletes all generated test screenshots (`.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.gif`) in the `scratch/` folder to prevent disk clutter and ensure test runs do not mix new results with old artifacts.

```bash
python scratch/1_clear_images_from_scratch.py
```

---

## 📂 Test Scripts by Target Site & Feature

### 1. 🎵 Spotify (`open.spotify.com`)
* **Problem**: React virtualization (`useInView`) unmounted off-screen cards when a synthetic scroll event was dispatched at `(0, 0)`. Chromium CDP full-page screenshots skipped painting off-screen carousels due to `content-visibility: auto`.
* **Solution**: Globally inject `content-visibility: visible !important`, `contain: none !important`, remove top scroll dispatch, and flush inner containers (`scrollTop = scrollHeight`).
* **Scripts**:
  - `test_spotify_inspect.py`: Full layout capture verifying all 7 recommended album covers and artist cards render across complete document depth.
  - `find_spotify_scrollables.py`: Inspects scrollable parent containers and DOM hierarchy.
  - `inspect_spotify.py` / `inspect_spotify_layout.py` / `inspect_spotify_tree.py`: Deep inspection of Spotify DOM nodes and computed styles.

---

### 2. 📌 Pinterest (`pinterest.com`)
* **Problem**: Pinterest masonry grid containers had hardcoded CSS heights exceeding actual child pins, creating massive trailing blank spaces (>1,000px).
* **Solution**: Automatically detect masonry containers and clamp `style.height` to the bottom of the lowest rendered child pin; pass through `_trim_trailing_blank_void()`.
* **Scripts**:
  - `test_pinterest_capture.py`: Full screenshot test via `screenshot.get()`, verifying masonry clamping and compressed output (< 1 MB).
  - `test_pinterest_clamped.py` / `test_pinterest_masonry.py`: Tests masonry bounding rect calculations.
  - `test_pinterest_combined.py` / `test_unconstrain_pinterest.py`: Tests interaction between container unconstraining and masonry grids.
  - `trace_pinterest_limit.py`: Traces height thresholds and child card bounds.
  - `inspect_pinterest*.py`: Inspects spacer elements, bottom bounds, and DOM layouts.

---

### 3. ✍️ Wordsmith (`wordsmith.ai`)
* **Problem**: Artificial sticky scroll tracks (`.srs-track`) and multi-vh containers (`height: 250vh`) caused content to overlap or left thousands of pixels of empty blank space.
* **Solution**: Target elements with `.srs-track` or height $\ge 150\text{vh}$ / $2000\text{px}$ having sticky children, and reset them to `height: auto` and `position: relative`.
* **Scripts**:
  - `test_wordsmith_tracks.py`: Analyzes oversized elements before/after progressive scrolling.
  - `test_wordsmith_collapsed.py`: Verifies scroll track collapsing on live page.
  - `test_wordsmith_no_uc.py`: Validates clean capture without Usercentrics consent banner.
  - `test_uc.py` / `print_wordsmith_buttons.py`: Tests Usercentrics modal dismissal.
  - `inspect_wordsmith*.py`: Detailed inspection of `.srs-track` wrappers and sticky children.

---

### 4. 🧊 Sparkling Ice (`sparklingice.com`)
* **Problem**: Product carousel had zero height before user interaction; recipe cards were hidden with `opacity: 0`; images were masked with `data:image/svg+xml` placeholders.
* **Solution**: Uncollapse `#si-product-slider__container` to `min-height: 450px`, unmask recipe card images, swap SVG placeholder attributes with real high-res sources, and hide blocking animated headers.
* **Scripts**:
  - `test_both_yt_ads.py`: Joint regression test for Sparkling Ice (281900) and MyBobs (281891) via `screenshot.get()`.
  - `test_sparkling_fix.py`: Dedicated verification of product slider uncollapsing and lazy image swapping.
  - `test_yt_ads.py`: YouTube programmatic ad testbed.
  - `inspect_sparklingice*.py`: Inspects hidden slides, animated factory headers, and slide elements.

---

### 5. 🛋️ Bob's Discount Furniture (`mybobs.com`)
* **Problem**: Heavy full-screen cookie consent dialogs and promotional popups blocked scrolling and prevented main content from rendering.
* **Solution**: Dismiss consent dialogs early, purge full-page fixed backdrop curtains, and progressively scroll to trigger lazy product feeds.
* **Scripts**:
  - `test_bobs_main.py` / `test_bobs_action.py`: Tests progressive scrolling and main section extraction.
  - `test_bobs_repeat.py` / `test_bobs_us.py`: Repeatability tests under US residential proxies.
  - `test_cookie_early.py` / `bobs_console.py`: Monitors console errors and early cookie dismiss timing.
  - `check_bobs_timeline.py` / `inspect_mybobs.py`: DOM inspection over a 20-second timeline.

---

### 6. 🗺️ Here Maps (`wego.here.com`)
* **Problem**: The map is drawn on HTML5 `<canvas>` using WebGL. Overly aggressive modal/curtain purging stripped the canvas, and insufficient wait times resulted in unrendered grey vector tiles.
* **Solution**: Require 10s lead wait for vector tiles; strictly preserve all `<canvas>` and WebGL layers during curtain/backdrop purging.
* **Scripts**:
  - `test_here_pipeline.py`: Verifies WebGL context and map canvas preservation via `screenshot.get()`.
  - `test_here_maps.py` / `test_10s_and_map.py`: Validates 10-second tile loading threshold.
  - `test_fixed_purge.py` / `test_steps_diag.py`: Step-by-step diagnostic ensuring modal purge never touches canvas.
  - `find_culprit.py` / `find_exact_culprit2.py` / `check_removed.py`: Pinpoints exact JS purging statements.
  - `test_tiles_monitor.py` / `test_timing_and_cookies.py`: Monitors network tile requests and cookie banners.

---

### 7. 🏨 Selectum Hotels (`selectumhotels.com`)
* **Problem**: An animated full-screen preloader overlay covered the page and prevented full-page screenshots from capturing the actual hotel content.
* **Solution**: Detect and dismiss preloader elements, handle proxy connection retries, and purge Didomi consent overlays.
* **Scripts**:
  - `test_selectum_steps.py`: Step-by-step diagnostic of unmasking, scrolling, animation triggers, and preloader removal.
  - `test_preloader.py` / `test_step1b_sel.py`: Tests preloader dismissal without breaking hero banners.
  - `find_s_issue.py` / `test_selectum_debug.py`: Debugging scripts for Didomi popups and network timeouts.

---

### 8. 💻 Hardware & E-commerce (Asus & Flipkart)
* **Problem**: Deeply nested containers with `overflow: hidden` or `max-height: 0` truncated content on hardware product pages and SPAs.
* **Solution**: Recursively unconstrain scrollable containers (`overflow: visible`, `max-height: none`) and restore revealed DOM subtrees.
* **Scripts**:
  - `test_asus_restore.py`: Verifies Asus motherboard product specs and feature card restoration.
  - `test_flipkart_restore.py`: Verifies Flipkart primary inner scroll container unconstraining.

---

### 9. ⚙️ Algorithms & Core Regression
* **`test_trim_void.py`**:
  - Unit test for `_trim_trailing_blank_void()`. Analyzes image bottom rows with color variance tolerance to strip trailing empty voids without touching real content.
* **`test_regression.py`**:
  - End-to-end scraper pipeline test calling `new_lander.scraping()` on real ad URLs (e.g., Adflex, Selectum Hotels) with database insertion verification.
* **`diagnose_three_ads.py`**:
  - Batch diagnostic runner for multiple ad targets.

---

### 10. 🎯 Facebook Sample Ads Regression (43273, 43271, 43016, 43210)
* **`test_pizzahut_43273.py` (Pizza Hut UK - Ad 43273)**:
  - *Problem*: Material UI / Emotion generated `Mui*-root` classes. The overly broad `[class*="root"]` unconstrain selector assigned `min-height: 100vh !important` to 137 subcomponents, ballooning height from 1,413px to over 11,590px with massive white voids.
  - *Solution*: Restricted unconstraining to top-level SPA root containers (`body > #main`, `body > #root`, `body > #app`, etc.) and only apply `min-height: 100vh` when clientHeight is 0.
* **`test_routes_43271.py` (Routes Interiors - Ad 43271)**:
  - *Problem*: Squarespace Fluid Engine uses 46-row CSS grids. Parent walker in `_UNCONSTRAIN_CONTAINERS_JS` forced `grid-template-rows: auto auto auto !important` on every parent grid, crushing rows 4–46 into 0px height and wiping out product & cushion grids. Additionally `sizes="auto"` had no width fallback.
  - *Solution*: Removed `grid-template-rows` mutation from parent walker (restricted strictly to Spotify player container) and provided `sizes="100vw"` fallback in lazy unmasking.
* **`test_eventbrite_43016.py` (Eventbrite UK - Ad 43016)**:
  - *Problem*: Eventbrite Design System (`eds-structure__body-root`) matched `[class*="root"]`, creating 500px voids between search bar and hero banner. Parent walker overwrote `position: absolute` on sidebars. Cookie banner (`aside#consent-banner`) blocked interactions.
  - *Solution*: Removed generic `[class*="root"]`, preserved parent positioning, and added `aside#consent-banner` to cookie banner handlers.
* **`test_gotphoto_43210.py` (GotPhoto UK - Ad 43210)**:
  - *Problem*: WP Rocket delayed JavaScript execution (`type="rocketlazyloadscript"`), preventing the HubSpot form script from loading without real user interaction events, leaving an empty light blue form container.
  - *Solution*: Dispatched synthetic user interaction events (`mousemove`, `scroll`, `keydown`, `click`, `touchstart`) and mouse pointer movement during initialization, accompanied by a dynamic HubSpot iframe mount wait loop.

---

## 🚀 Workflow & Usage

1. **Adding a New Bug Ad**:
   - When an ad from `test_sample_ads.py` fails, create an isolated script in `scratch/` (e.g., `test_<site_name>.py`).
   - Debug and fix the root cause logically in `helper/screenshot.py` or `new_lander.py`.
   - Keep the script in `scratch/` as a permanent regression test.

2. **Running Regression Verification**:
   - Run individual test scripts or execute `test_regression.py` and `test_both_yt_ads.py` on demand.

3. **Cleaning Up Test Artifacts**:
   - Run `python scratch/1_clear_images_from_scratch.py` to keep the directory clean.

