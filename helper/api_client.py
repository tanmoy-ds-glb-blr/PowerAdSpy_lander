import random
import time
import uuid
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

import requests


RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def retry_delay(response, attempt):
    value = (response.headers.get("Retry-After") or "").strip() if response is not None else ""
    if value:
        try:
            return max(0.0, min(60.0, float(value)))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(value)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return max(0.0, min(60.0, (parsed - datetime.now(timezone.utc)).total_seconds()))
            except Exception:
                pass
    return min(8.0, 2 ** (attempt - 1) + random.random())


def request(
    method,
    url,
    *,
    session=None,
    attempts=3,
    timeout=(15, 180),
    idempotency_key=None,
    before_attempt=None,
    **kwargs,
):
    client = session or requests
    headers = dict(kwargs.pop("headers", {}) or {})
    headers.setdefault("X-Idempotency-Key", idempotency_key or str(uuid.uuid4()))
    last = None
    for attempt in range(1, max(1, int(attempts)) + 1):
        # Keep this outside the requests exception handler. Infrastructure
        # guards (for example Bright Data health) must abort immediately and
        # must never be mistaken for a retryable HTTP transport failure.
        if before_attempt is not None:
            before_attempt()
        try:
            response = client.request(method, url, headers=headers, timeout=timeout, **kwargs)
            last = response
            if response.status_code not in RETRYABLE_STATUS or attempt >= attempts:
                return response
            delay = retry_delay(response, attempt)
        except (requests.Timeout, requests.ConnectionError):
            if attempt >= attempts:
                raise
            delay = min(8.0, 2 ** (attempt - 1) + random.random())
        time.sleep(delay)
    return last


def post_json(
    url,
    body,
    *,
    attempts=3,
    timeout=(15, 180),
    idempotency_key=None,
    before_attempt=None,
):
    return request(
        "POST", url, attempts=attempts, timeout=timeout, idempotency_key=idempotency_key,
        before_attempt=before_attempt,
        json=body, headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
