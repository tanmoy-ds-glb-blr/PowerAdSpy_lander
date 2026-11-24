from helper.pipeline import PageSnapshot, safe_url


_MAX_FRAME_DOCUMENTS = 20
_MAX_FRAME_HTML_BYTES = 1024 * 1024


def _bounded_utf8(value, maximum):
    raw = (value or "").encode("utf-8", errors="replace")
    if len(raw) <= maximum:
        return raw.decode("utf-8", errors="replace"), False
    return raw[:maximum].decode("utf-8", errors="ignore"), True


def capture_snapshot(page, frames=None) -> PageSnapshot:
    html = page.content() or ""
    try:
        text = page.inner_text("body", timeout=5000).strip()
    except Exception:
        text = ""
    frame_texts = []
    frame_documents = []
    main = getattr(page, "main_frame", None)
    for frame in list(getattr(page, "frames", []) or []):
        if frame == main:
            continue
        try:
            value = frame.inner_text("body", timeout=1000).strip()
            if value:
                frame_texts.append(value)
        except Exception:
            pass
        if len(frame_documents) >= _MAX_FRAME_DOCUMENTS:
            continue
        document = {
            "url": safe_url(getattr(frame, "url", "") or ""),
            "name": str(getattr(frame, "name", "") or "")[:200],
            "html": "",
            "saved": False,
            "truncated": False,
            "error": "",
        }
        try:
            frame_html, was_truncated = _bounded_utf8(frame.content() or "", _MAX_FRAME_HTML_BYTES)
            document.update(html=frame_html, saved=bool(frame_html), truncated=was_truncated)
        except Exception as exc:
            document["error"] = str(exc)[:200]
        frame_documents.append(document)
    return PageSnapshot(
        url=page.url or "",
        title=page.title() or "",
        html=html,
        text=" ".join(text.split()),
        frame_text=" ".join(" ".join(frame_texts).split()),
        frames=list(frames or []),
        frame_documents=frame_documents,
    )
