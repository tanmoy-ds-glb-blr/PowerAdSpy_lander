import hashlib
import os
import time
from io import BytesIO

from PIL import Image, ImageFilter, ImageStat

from helper.pipeline import CaptureResult
from helper.proxy_health import ProxyUnavailableError


MEASURE_JS = """() => {
 const d=document.documentElement,b=document.body;
 return {height:Math.ceil(Math.max(d.scrollHeight,b?b.scrollHeight:0,innerHeight)),
 width:Math.ceil(Math.max(d.scrollWidth,b?b.scrollWidth:0,innerWidth)),
 viewportHeight:innerHeight,viewportWidth:innerWidth,
 textLength:b?(b.innerText||'').trim().length:0};
}"""


def _dismiss_known_consent(page, action="accept"):
    selectors = {
        "accept": [
            "#onetrust-accept-btn-handler",
            "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
            "[data-testid='cookie-accept-all']",
        ],
        "reject": [
            "#onetrust-reject-all-handler",
            "#CybotCookiebotDialogBodyButtonDecline",
            "[data-testid='cookie-reject-all']",
        ],
    }
    return bool(page.evaluate("""(selectors) => {
      for (const selector of selectors) {
        const button=document.querySelector(selector);
        if(button && button.getBoundingClientRect().width>0 && button.getBoundingClientRect().height>0) {
          button.click(); return true;
        }
      }
      return false;
    }""", selectors.get(action, selectors["accept"])))


def _settings(config=None):
    get = (lambda key, default: config.get_default(key) if config and config.get_default(key) is not None else default)
    return {
        "max_height": int(get("CAPTURE_MAX_HEIGHT", 32000)),
        "max_width": int(get("CAPTURE_MAX_WIDTH", 1920)),
        "max_steps": int(get("CAPTURE_MAX_SCROLL_STEPS", 40)),
        "max_seconds": float(get("CAPTURE_MAX_SCROLL_SECONDS", 45)),
        "max_bytes": int(get("SCREENSHOT_MAX_BYTES", 1048576)),
        "min_width": int(get("SCREENSHOT_MIN_WIDTH", 960)),
        "min_quality": int(get("SCREENSHOT_MIN_QUALITY", 45)),
        "consent_action": str(get("CONSENT_ACTION", "accept")).lower(),
    }


def _select_primary_scroller(page):
    return page.evaluate("""() => {
      document.querySelectorAll('[data-pas-primary-scroller]').forEach(e => e.removeAttribute('data-pas-primary-scroller'));
      let best=null, bestScore=0;
      for (const el of document.querySelectorAll('body *')) {
        const s=getComputedStyle(el), r=el.getBoundingClientRect();
        const range=el.scrollHeight-el.clientHeight;
        const scrollable=(s.overflowY==='auto'||s.overflowY==='scroll') && range>200;
        if (!scrollable || r.width<innerWidth*.35 || r.height<innerHeight*.35) continue;
        const visibleW=Math.max(0,Math.min(innerWidth,r.right)-Math.max(0,r.left));
        const visibleH=Math.max(0,Math.min(innerHeight,r.bottom)-Math.max(0,r.top));
        const score=visibleW*visibleH*Math.log2(range+2);
        if (score>bestScore) { best=el; bestScore=score; }
      }
      if (!best) return null;
      best.setAttribute('data-pas-primary-scroller','1');
      const r=best.getBoundingClientRect();
      return {scrollHeight:best.scrollHeight,clientHeight:best.clientHeight,width:r.width,height:r.height};
    }""")


def _bounded_scroll(page, maximum_height, maximum_steps, maximum_seconds, deadline=None, abort_check=None):
    started = time.monotonic()
    primary = _select_primary_scroller(page)
    last_signature = None
    stable = 0
    steps = 0
    while steps < maximum_steps and time.monotonic() - started < maximum_seconds:
        if abort_check:
            abort_check()
        if deadline:
            deadline.check("capture_scroll")
        state = page.evaluate("""(limit) => {
          const d=document.documentElement,b=document.body;
          const target=document.querySelector('[data-pas-primary-scroller="1"]');
          const h=target?target.scrollHeight:Math.ceil(Math.max(d.scrollHeight,b?b.scrollHeight:0,innerHeight));
          const viewport=target?target.clientHeight:innerHeight;
          const current=target?target.scrollTop:window.scrollY;
          const y=Math.min(h-viewport, current + Math.max(400,Math.floor(viewport*.75)));
          if (target) target.scrollTop=Math.max(0,y); else window.scrollTo(0,Math.max(0,y));
          const text=(b?(b.innerText||''):'');
          return {height:h,y:Math.round(y),bottom:y+viewport>=h-5,signature:h+':'+text.length+':'+document.images.length+':'+document.querySelectorAll('iframe').length};
        }""", maximum_height)
        steps += 1
        time.sleep(0.5)
        signature = state.get("signature")
        stable = stable + 1 if signature == last_signature else 0
        last_signature = signature
        if state.get("bottom") or int(state.get("y") or 0) >= maximum_height:
            break
    page.evaluate("""() => { const t=document.querySelector('[data-pas-primary-scroller="1"]'); if(t)t.scrollTop=0; else window.scrollTo(0,0); }""")
    return {"steps": steps, "primary": primary}


def _hydrate_lazy_images_and_reveals(page, wait_for_pending=False, max_wait_seconds=4.0, deadline=None):
    """Promote lazy-loaded images to eager, reveal scroll-hidden elements, and wait briefly for decoding."""
    try:
        page.evaluate("""() => {
          document.querySelectorAll('img').forEach(img => {
            try {
              if (img.loading === 'lazy') img.loading = 'eager';
              const cur = img.getAttribute('src') || '';
              const isPlaceholder = !cur || cur.startsWith('data:image/') || cur.includes('blank.gif') || cur.includes('placeholder') || cur.includes('{width}') || cur.includes('%7Bwidth%7D');
              const targetW = Math.max(360, Math.min(1200, Math.round(img.clientWidth || (img.parentElement && img.parentElement.clientWidth) || 720)));
              if (isPlaceholder) {
                let candidate = img.getAttribute('data-src') || img.getAttribute('data-lazy-src') || img.getAttribute('data-original') || img.getAttribute('data-url') || cur;
                if (candidate) {
                  candidate = candidate.replace(/\{width\}|%7Bwidth%7D/gi, String(targetW));
                  img.setAttribute('src', candidate);
                }
              }
              if (!img.getAttribute('srcset')) {
                const ds = img.getAttribute('data-srcset') || img.getAttribute('data-lazy-srcset');
                if (ds) img.setAttribute('srcset', ds);
              }
              if (img.classList && img.classList.contains('lazyload')) {
                img.classList.remove('lazyload');
                img.classList.add('lazyloaded');
              }
            } catch (e) {}
          });
          document.querySelectorAll('picture source').forEach(src => {
            try {
              if (!src.getAttribute('srcset')) {
                let ds = src.getAttribute('data-srcset') || src.getAttribute('data-lazy-srcset');
                if (ds) {
                  ds = ds.replace(/\{width\}|%7Bwidth%7D/gi, '720');
                  src.setAttribute('srcset', ds);
                }
              }
            } catch (e) {}
          });
          document.querySelectorAll('[data-aos]').forEach(el => el.classList.add('aos-animate'));
          document.querySelectorAll('.wow').forEach(el => el.classList.add('animated'));
          document.querySelectorAll('.preFade, .preSlide, .preScale, .preFlex').forEach(el => {
            el.classList.add('fadeIn');
            el.style.opacity = '1';
            el.style.transform = 'none';
          });
          document.querySelectorAll('[data-sr-id]').forEach(el => {
            el.style.opacity = '1';
            el.style.visibility = 'visible';
          });
        }""")
    except Exception:
        return
    if not wait_for_pending:
        return
    try:
        page.evaluate("""() => {
          if (!document.getElementById('pas-capture-polish')) {
            const st = document.createElement('style');
            st.id = 'pas-capture-polish';
            st.textContent = 'html, body { scrollbar-width: none !important; } *, *::before, *::after { transition-duration: 0s !important; animation-duration: 0s !important; }';
            (document.head || document.documentElement).appendChild(st);
          }
          document.querySelectorAll('header, nav, div, aside, section').forEach(el => {
            try {
              const cs = getComputedStyle(el);
              if (cs.position === 'fixed' || cs.position === 'sticky') {
                const r = el.getBoundingClientRect();
                if (r.height > 0 && r.height < window.innerHeight * 0.6) {
                  el.style.setProperty('position', 'static', 'important');
                }
              }
            } catch (e) {}
          });
          return document.fonts ? document.fonts.ready.then(() => true).catch(() => true) : true;
        }""")
    except Exception:
        pass
    budget = min(max_wait_seconds, deadline.remaining()) if deadline else max_wait_seconds
    end = time.monotonic() + max(0.0, budget)
    while time.monotonic() < end:
        try:
            pending = int(page.evaluate("() => Array.from(document.images).filter(i => (i.currentSrc || i.src) && !i.complete).length") or 0)
            if pending == 0:
                break
        except Exception:
            break
        time.sleep(0.25)


def _expand_primary_scroller(page):
    return page.evaluate("""() => {
      const el=document.querySelector('[data-pas-primary-scroller="1"]');
      if(!el) return false;
      el.style.setProperty('height', el.scrollHeight+'px', 'important');
      el.style.setProperty('max-height','none','important');
      el.style.setProperty('overflow-y','visible','important');
      el.style.setProperty('overflow','visible','important');
      let parent=el.parentElement;
      while(parent) {
        parent.style.setProperty('max-height','none','important');
        parent.style.setProperty('overflow-y','visible','important');
        parent.style.setProperty('overflow','visible','important');
        if(parent===document.body || parent===document.documentElement) {
          parent.style.setProperty('height','auto','important');
        }
        parent=parent.parentElement;
      }
      return true;
    }""")


def _visual_scores(image, text_length=0):
    probe = image.convert("L")
    probe.thumbnail((256, 256))
    stat = ImageStat.Stat(probe)
    stddev = float(stat.stddev[0])
    extrema = probe.getextrema()
    uniform = 1.0 if extrema[1] - extrema[0] < 4 else 0.0
    histogram = probe.histogram()
    total = max(1, sum(histogram))
    near_white = sum(histogram[248:]) / total
    near_black = sum(histogram[:8]) / total
    edges = probe.filter(ImageFilter.FIND_EDGES)
    edge_hist = edges.histogram()
    edge_density = sum(edge_hist[24:]) / max(1, sum(edge_hist))
    blank = bool(text_length > 50 and (uniform >= 1.0 or stddev < 2.0 or ((near_white > .995 or near_black > .995) and edge_density < .002)))
    return {
        "luminance_stddev": round(stddev, 3), "uniform": uniform,
        "near_white_ratio": round(near_white, 5), "near_black_ratio": round(near_black, 5),
        "edge_density": round(edge_density, 5), "dom_rich_but_blank": 1.0 if blank else 0.0,
    }


def _capture_segmented(page, width, height, timeout_ms, deadline=None, abort_check=None):
    """Capture bounded document clips and stitch them without an unbounded bitmap request."""
    stitched = Image.new("RGB", (width, height), "white")
    viewport = page.evaluate("() => ({width:innerWidth,height:innerHeight})")
    viewport_width = max(1, int(viewport.get("width") or 1280))
    viewport_height = max(1, int(viewport.get("height") or 720))
    for y in range(0, height, viewport_height):
        for x in range(0, width, viewport_width):
            if abort_check:
                abort_check()
            if deadline:
                deadline.check("capture_segment")
            position = page.evaluate("([x,y]) => { window.scrollTo(x,y); return {x:scrollX,y:scrollY}; }", [x, y])
            time.sleep(0.05)
            tile_timeout = int(min(timeout_ms / 1000.0, deadline.remaining()) * 1000) if deadline else timeout_ms
            data = page.screenshot(timeout=max(1000, tile_timeout))
            tile = Image.open(BytesIO(data)).convert("RGB")
            actual_x = int(position.get("x") or 0)
            actual_y = int(position.get("y") or 0)
            crop_left = max(0, x - actual_x)
            crop_top = max(0, y - actual_y)
            paste_width = min(width - x, tile.width - crop_left)
            paste_height = min(height - y, tile.height - crop_top)
            if paste_width <= 0 or paste_height <= 0:
                raise RuntimeError(f"empty viewport tile at x={x}, y={y}")
            cropped = tile.crop((crop_left, crop_top, crop_left + paste_width, crop_top + paste_height))
            stitched.paste(cropped, (x, y))
    page.evaluate("() => window.scrollTo(0,0)")
    output = BytesIO()
    stitched.save(output, "PNG", optimize=False)
    return output.getvalue()


def encode_under_limit(image, path, max_bytes=1048576, min_width=960, min_quality=45):
    if image.mode != "RGB":
        base = Image.new("RGB", image.size, "white")
        if image.mode == "RGBA":
            base.paste(image, mask=image.getchannel("A"))
        else:
            base.paste(image.convert("RGB"))
        image = base
    working = image
    chosen = None
    chosen_quality = 0
    while True:
        low, high = min_quality, 90
        while low <= high:
            quality = (low + high) // 2
            buf = BytesIO()
            working.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
            data = buf.getvalue()
            if len(data) <= max_bytes:
                chosen, chosen_quality = data, quality
                low = quality + 1
            else:
                high = quality - 1
        if chosen is not None:
            break
        if working.width <= min_width:
            # If we reached minimum width and minimum quality, intelligently trim trailing height
            # to maximize captured page height within max_bytes, preserving as much content as possible.
            if max_bytes >= 10000 and working.height > 1000:
                new_h = int(working.height * 0.85)
                if new_h < 500:
                    raise RuntimeError(f"COMPRESSION_LIMIT_FAILED: cannot reach {max_bytes} bytes at minimum width {min_width}")
                working = working.crop((0, 0, working.width, new_h))
                continue
            raise RuntimeError(f"COMPRESSION_LIMIT_FAILED: cannot reach {max_bytes} bytes at minimum width {min_width}")
        new_width = max(min_width, int(working.width * 0.85))
        new_height = max(1, round(working.height * new_width / working.width))
        working = working.resize((new_width, new_height), Image.Resampling.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(chosen)
    if os.path.getsize(path) > max_bytes:
        raise RuntimeError("COMPRESSION_LIMIT_FAILED: encoder postcondition failed")
    return working.width, working.height, len(chosen), chosen_quality


def _has_visible_cross_origin_iframe(page):
    """Return True if the page contains a visible content-sized cross-origin iframe."""
    try:
        return bool(page.evaluate("""() => {
          const origin = location.origin;
          for (const f of document.querySelectorAll('iframe')) {
            const src = f.getAttribute('src') || '';
            if (!src || src === 'about:blank' || src.startsWith('javascript:')) continue;
            const r = f.getBoundingClientRect();
            if (r.width < 100 || r.height < 100) continue;
            const cs = getComputedStyle(f);
            if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue;
            try {
              const u = new URL(src, location.href);
              if (u.origin !== origin) return true;
            } catch (e) {}
          }
          return false;
        }"""))
    except Exception:
        return False


def capture_page(page, img_name, instance_no, config=None, deadline=None, abort_check=None):
    cfg = _settings(config)
    target = os.path.join("images", str(instance_no), f"{img_name}.jpg")
    journal = []
    if abort_check:
        abort_check()
    if _dismiss_known_consent(page, cfg["consent_action"]):
        journal.append(f"known_consent_{cfg['consent_action']}")
        time.sleep(0.25)
    initial = page.evaluate(MEASURE_JS)
    doc_height = int(initial.get("height") or 0)
    doc_width = int(initial.get("width") or 0)
    _hydrate_lazy_images_and_reveals(page, wait_for_pending=False, deadline=deadline)
    scroll_seconds = min(cfg["max_seconds"], deadline.remaining()) if deadline else cfg["max_seconds"]
    scroll_result = _bounded_scroll(
        page,
        cfg["max_height"],
        cfg["max_steps"],
        scroll_seconds,
        deadline=deadline,
        abort_check=abort_check,
    )
    if scroll_result.get("primary") and _expand_primary_scroller(page):
        journal.append("expanded_primary_scroller")
    _hydrate_lazy_images_and_reveals(page, wait_for_pending=True, max_wait_seconds=4.0, deadline=deadline)
    final = page.evaluate(MEASURE_JS)
    doc_height = max(doc_height, int(final.get("height") or 0))
    doc_width = max(doc_width, int(final.get("width") or 0))
    capture_height = min(max(1, doc_height), cfg["max_height"])
    capture_width = min(max(1, doc_width), cfg["max_width"])
    truncated = doc_height > cfg["max_height"] or doc_width > cfg["max_width"]
    mode = "native_full"
    screenshot_timeout = int(min(60.0, deadline.remaining()) * 1000) if deadline else 60000
    if screenshot_timeout <= 0:
        raise TimeoutError("OVERALL_SCRAPE_TIMEOUT at stage=capture_screenshot")
    try:
        if abort_check:
            abort_check()
        if _has_visible_cross_origin_iframe(page):
            raw = _capture_segmented(
                page,
                capture_width,
                capture_height,
                screenshot_timeout,
                deadline=deadline,
                abort_check=abort_check,
            )
            mode = "segmented_cross_origin_iframe"
        elif not truncated:
            raw = page.screenshot(full_page=True, timeout=screenshot_timeout)
        else:
            mode = "bounded_clip"
            try:
                raw = page.screenshot(
                    full_page=True,
                    clip={"x": 0, "y": 0, "width": capture_width, "height": capture_height},
                    timeout=screenshot_timeout,
                )
            except Exception:
                raw = page.screenshot(full_page=True, timeout=screenshot_timeout)
    except ProxyUnavailableError:
        raise
    except Exception as exc:
        try:
            raw = _capture_segmented(
                page,
                capture_width,
                capture_height,
                screenshot_timeout,
                deadline=deadline,
                abort_check=abort_check,
            )
            mode = "segmented_fallback"
        except ProxyUnavailableError:
            raise
        except Exception as segmented_exc:
            raise RuntimeError(f"CAPTURE_NATIVE_FAILED: {exc}; segmented fallback failed: {segmented_exc}") from segmented_exc
    image = Image.open(BytesIO(raw)).convert("RGB")
    if image.height > capture_height or image.width > capture_width:
        image = image.crop((0, 0, min(image.width, capture_width), min(image.height, capture_height)))
    scores = _visual_scores(image, int(final.get("textLength") or 0))
    if scores["dom_rich_but_blank"] and mode != "segmented_fallback":
        raw = _capture_segmented(
            page,
            capture_width,
            capture_height,
            screenshot_timeout,
            deadline=deadline,
            abort_check=abort_check,
        )
        image = Image.open(BytesIO(raw)).convert("RGB")
        scores = _visual_scores(image, int(final.get("textLength") or 0))
        mode = "segmented_visual_retry"
    if scores["dom_rich_but_blank"]:
        raise RuntimeError("CAPTURE_VISUAL_BLANK: DOM contains content but screenshot is nearly uniform")
    width, height, final_bytes, quality = encode_under_limit(
        image, target, cfg["max_bytes"], cfg["min_width"], cfg["min_quality"]
    )
    state = "partial" if truncated else "full"
    reason = "capture_bounds_reached" if truncated else ""
    return CaptureResult(target, state, mode, width, height, final_bytes, doc_height, truncated, reason, quality, journal, scores)
