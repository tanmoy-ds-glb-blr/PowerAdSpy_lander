import time

from helper.frame_inspector import inspect_frames
from helper.pipeline import ReadinessResult


_PAGE_STATE_JS = """() => {
    const d = document.documentElement, b = document.body;
    const visible = el => {
        const r = el.getBoundingClientRect(), s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
    };
    const images = Array.from(document.images || []).filter(visible);
    const failed = images.filter(i => i.complete && i.naturalWidth === 0).length;
    const pending = images.filter(i => !i.complete).length;
    const text = b ? (b.innerText || '').trim() : '';
    return {
        readyState: document.readyState,
        height: Math.ceil(Math.max(d ? d.scrollHeight : 0, b ? b.scrollHeight : 0, innerHeight)),
        width: Math.ceil(Math.max(d ? d.scrollWidth : 0, b ? b.scrollWidth : 0, innerWidth)),
        textLength: text.length,
        pendingImages: pending,
        failedImages: failed,
        mediaCount: document.querySelectorAll('img,iframe,svg,canvas,video,picture,embed,object').length
        ,fontsReady: !document.fonts || document.fonts.status === 'loaded'
    };
}"""


def wait_for_ready(
    page,
    timeout_seconds: float = 30.0,
    stable_samples: int = 3,
    frame_timeout_ms: int = 1500,
    abort_check=None,
):
    start = time.monotonic()
    deadline = start + max(1.0, timeout_seconds)
    previous = None
    stable = 0
    last = {}
    reasons = []
    if abort_check:
        abort_check()
    try:
        page.wait_for_load_state("domcontentloaded", timeout=min(5000, int(timeout_seconds * 1000)))
    except Exception:
        reasons.append("domcontentloaded_wait_failed")

    while time.monotonic() < deadline:
        if abort_check:
            abort_check()
        try:
            last = page.evaluate(_PAGE_STATE_JS)
        except Exception as exc:
            reasons.append(f"page_state_error:{str(exc)[:80]}")
            time.sleep(0.25)
            continue
        signature = (last.get("height"), last.get("width"), last.get("textLength"), last.get("mediaCount"))
        stable = stable + 1 if signature == previous else 0
        previous = signature
        meaningful = int(last.get("textLength") or 0) > 0 or int(last.get("mediaCount") or 0) > 0
        if last.get("readyState") in ("interactive", "complete") and meaningful and stable >= stable_samples and int(last.get("pendingImages") or 0) == 0 and last.get("fontsReady", True):
            break
        time.sleep(0.5)

    if abort_check:
        abort_check()
    frames = inspect_frames(page, frame_timeout_ms)
    # Give visible late-loading frames the remainder of the shared deadline.
    while time.monotonic() < deadline and any(f.visible and not f.ready for f in frames):
        if abort_check:
            abort_check()
        time.sleep(0.25)
        frames = inspect_frames(page, frame_timeout_ms)
    timed_out = time.monotonic() >= deadline
    if timed_out:
        reasons.append("readiness_deadline_reached")
    if int(last.get("pendingImages") or 0):
        reasons.append("visible_images_pending")
    if not last.get("fontsReady", True):
        reasons.append("fonts_pending")
    if any(f.visible and not f.ready for f in frames):
        reasons.append("visible_frames_not_ready")
    state = "degraded" if reasons else "ready"
    return ReadinessResult(
        state=state,
        elapsed_ms=int((time.monotonic() - start) * 1000),
        document_height=int(last.get("height") or 0),
        document_width=int(last.get("width") or 0),
        text_length=int(last.get("textLength") or 0),
        pending_images=int(last.get("pendingImages") or 0),
        failed_images=int(last.get("failedImages") or 0),
        frames=frames,
        reasons=reasons,
    )
