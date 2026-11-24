"""Persistent Bright Data probe subprocess used by the parent monitor."""

import json
import sys
import time

from helper import init
from helper.proxy_health import ProxyUnavailableError, sanitize_error


def _emit(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        try:
            command = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(command, dict):
            continue
        if command.get("shutdown"):
            return
        request_id = command.get("request_id")
        country_iso = str(command.get("country_iso") or "us").strip().lower()
        timeout_seconds = command.get("timeout_seconds", 5)
        try:
            details = init.verify_proxy_egress(
                iso=country_iso,
                required=True,
                timeout_seconds=timeout_seconds,
            )
            if not isinstance(details, dict) or not details.get("ip"):
                raise ProxyUnavailableError("health endpoint returned no egress IP")
            response = {
                "request_id": request_id,
                "available": True,
                "details": details,
                "reason": "healthy",
                "observed_at": time.time(),
            }
        except ProxyUnavailableError as exc:
            response = {
                "request_id": request_id,
                "available": False,
                "details": {},
                "reason": exc.reason,
                "stage": exc.stage,
                "currently_unavailable": exc.currently_unavailable,
                "observed_at": exc.observed_at,
                "country_iso": exc.country_iso or country_iso,
            }
        except BaseException as exc:
            response = {
                "request_id": request_id,
                "available": False,
                "details": {},
                "reason": f"{type(exc).__name__}: {sanitize_error(exc)}",
                "observed_at": time.time(),
                "country_iso": country_iso,
            }
        _emit(response)


if __name__ == "__main__":
    main()
