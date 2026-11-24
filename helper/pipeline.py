from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SENSITIVE_QUERY_KEYS = {"token", "key", "password", "passwd", "secret", "auth", "code", "signature", "sig"}


def safe_url(value: str) -> str:
    """Return a log-safe URL while preserving routing information."""
    try:
        parts = urlsplit(value or "")
        query = []
        for key, val in parse_qsl(parts.query, keep_blank_values=True):
            query.append((key, "[REDACTED]" if key.lower() in SENSITIVE_QUERY_KEYS else val[:120]))
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        return urlunsplit((parts.scheme, host, parts.path, urlencode(query), ""))
    except Exception:
        return "[INVALID_URL]"


@dataclass
class FrameResult:
    url: str = ""
    name: str = ""
    visible: bool = False
    text_length: int = 0
    image_count: int = 0
    pending_images: int = 0
    probable_ad: bool = False
    ready: bool = False
    error: str = ""


@dataclass
class ReadinessResult:
    state: str
    elapsed_ms: int
    document_height: int = 0
    document_width: int = 0
    text_length: int = 0
    pending_images: int = 0
    failed_images: int = 0
    frames: List[FrameResult] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NavigationResult:
    requested_url: str
    final_url: str = ""
    status: Optional[int] = None
    redirects: List[str] = field(default_factory=list)
    attempts: int = 0
    elapsed_ms: int = 0
    error_code: str = ""
    error: str = ""
    request_failures: List[Dict[str, str]] = field(default_factory=list)
    popup_urls: List[str] = field(default_factory=list)
    selected_popup: bool = False
    selected_page: Any = field(default=None, repr=False, compare=False)


class ScrapeDeadline:
    def __init__(self, seconds: float):
        import time
        self._time = time
        self.started = time.monotonic()
        self.ends = self.started + max(1.0, float(seconds))

    def remaining(self) -> float:
        return max(0.0, self.ends - self._time.monotonic())

    def check(self, stage: str):
        if self.remaining() <= 0:
            raise TimeoutError(f"OVERALL_SCRAPE_TIMEOUT at stage={stage}")


@dataclass
class PageSnapshot:
    url: str
    title: str
    html: str
    text: str
    frame_text: str
    frames: List[FrameResult] = field(default_factory=list)
    frame_documents: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CaptureResult:
    image_path: str
    state: str
    mode: str
    width: int
    height: int
    final_bytes: int
    document_height: int
    truncated: bool = False
    reason: str = ""
    quality: int = 0
    mutation_journal: List[str] = field(default_factory=list)
    visual_scores: Dict[str, float] = field(default_factory=dict)
