from typing import List

from helper.pipeline import FrameResult, safe_url


AD_MARKERS = ("doubleclick", "googlesyndication", "googleadservices", "adservice", "/ads/", "adnxs", "taboola", "outbrain")


def inspect_frames(page, timeout_ms: int = 1500) -> List[FrameResult]:
    results: List[FrameResult] = []
    main = getattr(page, "main_frame", None)
    for frame in list(getattr(page, "frames", []) or []):
        if frame == main:
            continue
        url = getattr(frame, "url", "") or ""
        item = FrameResult(url=safe_url(url), name=getattr(frame, "name", "") or "")
        item.probable_ad = any(marker in url.lower() for marker in AD_MARKERS)
        try:
            owner = frame.frame_element()
            box = owner.bounding_box()
            item.visible = bool(box and box.get("width", 0) > 0 and box.get("height", 0) > 0)
            state = frame.evaluate("""() => {
                const body = document.body;
                const text = body ? (body.innerText || '').trim() : '';
                const images = Array.from(document.images || []);
                return {
                    visible: !!body && body.getBoundingClientRect().width > 0 && body.getBoundingClientRect().height > 0,
                    textLength: text.length,
                    imageCount: images.length,
                    mediaCount: document.querySelectorAll('img,svg,canvas,video,picture,embed,object').length,
                    pendingImages: images.filter(i => i.getBoundingClientRect().width > 0 && (!i.complete || i.naturalWidth === 0)).length,
                    readyState: document.readyState
                };
            }""")
            item.text_length = int(state.get("textLength") or 0)
            item.image_count = int(state.get("imageCount") or 0)
            item.pending_images = int(state.get("pendingImages") or 0)
            meaningful = item.text_length > 0 or item.image_count > 0 or int(state.get("mediaCount") or 0) > 0
            item.ready = (not item.visible) or (
                state.get("readyState") in ("interactive", "complete") and item.pending_images == 0 and meaningful
            )
        except Exception as exc:
            item.error = str(exc)[:160]
        results.append(item)
    return results
