"""Shared Bright Data health state and outage coordination helpers.

The parent process owns an independent continuous monitor. Worker checkpoints
may request an immediate validation; simultaneous worker requests share a
single-flight lock so they do not create a probe storm.
"""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from contextlib import nullcontext


MAX_CHECK_INTERVAL_SECONDS = 10.0
DEFAULT_CHECK_INTERVAL_SECONDS = 5.0
DEFAULT_CHECK_TIMEOUT_SECONDS = 5.0
# Leave time for terminating a wedged child process while still keeping the
# complete monitor cycle below the user's ten-second ceiling.
MAX_ISOLATED_PROBE_WALL_SECONDS = 8.0

PROXY_ERROR_MARKERS = (
    "err_proxy_connection_failed",
    "err_tunnel_connection_failed",
    "proxyerror",
    "proxy error",
    "proxy authentication",
    "proxy connect aborted",
    "tunnel connection failed",
    "407 auth",
    "http 407",
    "ip_forbidden",
    "client_10030",
    "brd.superproxy.io",
)


class ProxyUnavailableError(RuntimeError):
    """Raised when Bright Data cannot currently be used safely."""

    def __init__(
        self,
        reason,
        stage=None,
        currently_unavailable=True,
        observed_at=None,
        country_iso=None,
    ):
        self.reason = str(reason or "Bright Data proxy is unavailable")
        self.stage = str(stage or "")
        self.currently_unavailable = bool(currently_unavailable)
        self.observed_at = float(observed_at if observed_at is not None else time.time())
        self.country_iso = str(country_iso or "").strip().lower()
        message = self.reason if not self.stage else f"{self.stage}: {self.reason}"
        super().__init__(message)


def sanitize_error(value):
    """Remove URL user-info if an HTTP library includes it in an error."""
    text = str(value or "")
    return re.sub(r"(?i)(https?://)[^@/\s]+@", r"\1***@", text)[:500]


def clamp_interval(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_CHECK_INTERVAL_SECONDS
    return min(MAX_CHECK_INTERVAL_SECONDS, max(0.1, parsed))


def clamp_timeout(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_CHECK_TIMEOUT_SECONDS
    # A bounded probe lets a new check begin at least every ten seconds even
    # when the gateway silently drops connections.
    return min(MAX_CHECK_INTERVAL_SECONDS, max(0.1, parsed))


def initial_snapshot(enabled):
    now = time.time()
    return {
        "enabled": bool(enabled),
        "initialized": not bool(enabled),
        "available": not bool(enabled),
        "reason": "health check has not completed" if enabled else "Bright Data proxies disabled",
        "checked_at": now if not enabled else 0.0,
        "generation": 0,
        "egress_ip": "",
        "egress_country": "",
        "last_down_at": 0.0,
        "last_up_at": now if not enabled else 0.0,
        "checked_country": "",
        "down_country": "",
    }


def initialize_state(shared_state, enabled):
    snapshot = initial_snapshot(enabled)
    shared_state["snapshot"] = snapshot
    return snapshot


def _write_lock(shared_state):
    try:
        lock = shared_state.get("_write_lock")
    except Exception:
        lock = None
    return lock if lock is not None else nullcontext()


def _probe_lock(shared_state):
    try:
        lock = shared_state.get("_probe_lock")
    except Exception:
        lock = None
    return lock if lock is not None else nullcontext()


def run_singleflight_probe(shared_state, country_iso, checker, cache_seconds=1.0):
    """Serialize worker probes and optionally share a recent country result.

    With a zero cache duration, callers that arrived while another check was
    genuinely in flight may reuse that result, while a caller arriving after
    completion always performs a fresh check.
    """
    if shared_state is None:
        return checker()
    country_iso = str(country_iso or "us").strip().lower()
    requested_at_monotonic = time.monotonic()
    with _probe_lock(shared_state):
        try:
            cache = dict(shared_state.get("_probe_cache", {}) or {})
        except Exception:
            cache = {}
        cached = cache.get(country_iso)
        now_monotonic = time.monotonic()
        cached_at = float(cached.get("checked_at") or 0.0) if isinstance(cached, dict) else 0.0
        cached_monotonic = float(cached.get("completed_monotonic") or 0.0) if isinstance(cached, dict) else 0.0
        cache_duration = max(0.0, float(cache_seconds))
        recent_cached_result = (
            cache_duration > 0.0
            and cached_monotonic > 0.0
            and now_monotonic - cached_monotonic <= cache_duration
        )
        joined_inflight_result = (
            cache_duration == 0.0
            and cached_monotonic > requested_at_monotonic
        )
        if isinstance(cached, dict) and (recent_cached_result or joined_inflight_result):
            if cached.get("available"):
                return dict(cached.get("details") or {})
            raise ProxyUnavailableError(
                cached.get("reason") or "cached proxy probe failed",
                observed_at=cached_at or None,
                country_iso=country_iso,
            )

        try:
            details = checker()
            if not isinstance(details, dict) or not details.get("ip"):
                raise ProxyUnavailableError("health endpoint returned no egress IP")
        except ProxyUnavailableError as exc:
            observed_at = getattr(exc, "observed_at", time.time())
            cache[country_iso] = {
                "available": False,
                "reason": exc.reason,
                "details": {},
                "checked_at": observed_at,
                "completed_monotonic": time.monotonic(),
            }
            shared_state["_probe_cache"] = cache
            raise
        except Exception as exc:
            unavailable = ProxyUnavailableError(
                f"{type(exc).__name__}: {sanitize_error(exc)}"
            )
            cache[country_iso] = {
                "available": False,
                "reason": unavailable.reason,
                "details": {},
                "checked_at": unavailable.observed_at,
                "completed_monotonic": time.monotonic(),
            }
            shared_state["_probe_cache"] = cache
            raise unavailable from exc

        observed_at = time.time()
        cache[country_iso] = {
            "available": True,
            "reason": "healthy",
            "details": dict(details),
            "checked_at": observed_at,
            "completed_monotonic": time.monotonic(),
        }
        shared_state["_probe_cache"] = cache
        return details


def get_snapshot(shared_state):
    if shared_state is None:
        return {}
    try:
        value = shared_state.get("snapshot", {})
        return dict(value) if isinstance(value, dict) else {}
    except Exception:
        return {}


def publish_state(
    shared_state,
    available,
    reason,
    details=None,
    checked_at=None,
    country_iso=None,
):
    with _write_lock(shared_state):
        previous = get_snapshot(shared_state)
        details = details if isinstance(details, dict) else {}
        checked_country = str(country_iso or "").strip().lower()
        check_time = float(checked_at if checked_at is not None else time.time())
        if check_time < float(previous.get("checked_at") or 0.0):
            # A slow result must not overwrite a newer outage/recovery result.
            return previous, previous
        transitioned_down = bool(
            not available
            and (not previous.get("initialized") or previous.get("available"))
        )
        transitioned_up = bool(
            available
            and (not previous.get("initialized") or not previous.get("available"))
        )
        snapshot = {
            "enabled": bool(previous.get("enabled", True)),
            "initialized": True,
            "available": bool(available),
            "reason": sanitize_error(reason) or ("healthy" if available else "unavailable"),
            "checked_at": check_time,
            "generation": int(previous.get("generation", 0)) + 1,
            "egress_ip": str(details.get("ip") or ""),
            "egress_country": str(details.get("country") or ""),
            "last_down_at": max(
                check_time if transitioned_down else 0.0,
                float(previous.get("last_down_at") or 0.0),
            ),
            "last_up_at": check_time if transitioned_up else float(previous.get("last_up_at") or 0.0),
            "checked_country": checked_country,
            "down_country": "" if available else (
                checked_country or str(previous.get("down_country") or "").strip().lower()
            ),
        }
        shared_state["snapshot"] = snapshot
    return previous, snapshot


def mark_unavailable(shared_state, reason, checked_at=None, country_iso=None):
    if shared_state is None:
        return {}, {}
    return publish_state(
        shared_state,
        False,
        reason,
        checked_at=checked_at,
        country_iso=country_iso,
    )


def _snapshot_is_available(snapshot, stale_after_seconds=None):
    if not snapshot:
        return False
    if not snapshot.get("enabled", True):
        return True
    if not snapshot.get("initialized") or not snapshot.get("available"):
        return False
    if stale_after_seconds is not None:
        checked_at = float(snapshot.get("checked_at") or 0.0)
        if checked_at <= 0 or time.time() - checked_at > float(stale_after_seconds):
            return False
    return True


def state_is_available(shared_state, stale_after_seconds=None):
    return _snapshot_is_available(
        get_snapshot(shared_state),
        stale_after_seconds=stale_after_seconds,
    )


def require_available(shared_state, stage, stale_after_seconds=None):
    snapshot = get_snapshot(shared_state)
    if _snapshot_is_available(snapshot, stale_after_seconds=stale_after_seconds):
        return snapshot
    reason = snapshot.get("reason") or "proxy health is unknown"
    if snapshot.get("available") and stale_after_seconds is not None:
        reason = "proxy health monitor state is stale"
    raise ProxyUnavailableError(
        reason,
        stage=stage,
        observed_at=float(snapshot.get("checked_at") or time.time()),
        country_iso=snapshot.get("down_country"),
    )


def wait_for_available(
    shared_state,
    stale_after_seconds=None,
    poll_seconds=0.5,
    stop_event=None,
    on_wait=None,
    report_every_seconds=60.0,
):
    """Wait until the shared state is healthy, without performing extra probes."""
    last_report = 0.0
    while True:
        if state_is_available(shared_state, stale_after_seconds=stale_after_seconds):
            return True
        if stop_event is not None and stop_event.is_set():
            return False
        now = time.monotonic()
        if on_wait is not None and (last_report == 0.0 or now - last_report >= report_every_seconds):
            try:
                on_wait(get_snapshot(shared_state))
            except Exception:
                pass
            last_report = now
        delay = max(0.05, min(float(poll_seconds), 1.0))
        if stop_event is not None:
            if stop_event.wait(delay):
                return False
        else:
            time.sleep(delay)


def looks_like_proxy_error(error):
    value = str(error or "").lower()
    return any(marker in value for marker in PROXY_ERROR_MARKERS)


def _read_probe_responses(process, responses):
    """Decode newline-delimited worker responses without blocking the monitor."""
    try:
        for line in iter(process.stdout.readline, ""):
            try:
                response = json.loads(line)
            except (TypeError, ValueError):
                continue
            if isinstance(response, dict):
                responses.put(response)
    finally:
        responses.put({"_worker_eof": True, "returncode": process.poll()})


class IsolatedProbeRunner:
    """Run a reusable checker process with a hard wall-clock deadline."""

    def __init__(
        self,
        worker_module="helper.proxy_probe_worker",
        max_wall_seconds=MAX_ISOLATED_PROBE_WALL_SECONDS,
    ):
        self.worker_module = str(worker_module)
        self.max_wall_seconds = min(
            MAX_ISOLATED_PROBE_WALL_SECONDS,
            max(0.1, float(max_wall_seconds)),
        )
        self.lock = threading.Lock()
        self.process = None
        self.reader = None
        self.responses = None
        self.retired_processes = []
        self.request_id = 0
        self.closed = False

    def _reap_retired(self):
        still_running = []
        for process in self.retired_processes:
            if process.poll() is None:
                try:
                    process.kill()
                    process.wait(timeout=0.1)
                except Exception:
                    still_running.append(process)
        self.retired_processes = still_running

    def _discard_worker(self):
        process, reader = self.process, self.reader
        self.process = None
        self.reader = None
        self.responses = None
        if process is None:
            self._reap_retired()
            return
        if process.stdin is not None:
            try:
                process.stdin.close()
            except Exception:
                pass
        try:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=0.25)
            if process.poll() is None:
                process.kill()
                process.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            self.retired_processes.append(process)
        except Exception:
            pass
        if process.stdout is not None:
            try:
                process.stdout.close()
            except Exception:
                pass
        if reader is not None and reader.is_alive():
            reader.join(timeout=0.1)
        self._reap_retired()

    def _start_worker(self):
        if self.closed:
            raise RuntimeError("isolated proxy probe runner is closed")
        if self.process is not None and self.process.poll() is None:
            return
        self._discard_worker()
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        process = subprocess.Popen(
            [sys.executable, "-u", "-m", self.worker_module],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            cwd=project_root,
            creationflags=creation_flags,
        )
        responses = queue.Queue()
        reader = threading.Thread(
            target=_read_probe_responses,
            args=(process, responses),
            name="bright-proxy-probe-reader",
            daemon=True,
        )
        reader.start()
        self.process = process
        self.reader = reader
        self.responses = responses

    def start(self):
        with self.lock:
            self._start_worker()

    def __call__(self, country_iso, timeout_seconds):
        request_timeout = clamp_timeout(timeout_seconds)
        # The child receives the configured requests budget. Keep the
        # supervisor deadline separate so a freshly spawned interpreter has
        # startup/IPC headroom without extending the absolute eight-second
        # wall-clock limit.
        budget = self.max_wall_seconds
        started_at = time.monotonic()
        with self.lock:
            self._start_worker()
            self.request_id += 1
            request_id = self.request_id
            try:
                command = {
                    "request_id": request_id,
                    "country_iso": str(country_iso or "us").strip().lower(),
                    "timeout_seconds": request_timeout,
                }
                self.process.stdin.write(json.dumps(command) + "\n")
                self.process.stdin.flush()
            except (BrokenPipeError, OSError, ValueError) as exc:
                self._discard_worker()
                raise ProxyUnavailableError(
                    f"proxy health worker communication failed: {type(exc).__name__}",
                    stage="continuous_proxy_monitor",
                ) from exc
            response = None
            while response is None:
                remaining = max(0.0, budget - (time.monotonic() - started_at))
                if remaining <= 0:
                    observed_at = time.time()
                    self._discard_worker()
                    raise ProxyUnavailableError(
                        f"proxy health check exceeded {budget:.1f}s hard deadline",
                        stage="continuous_proxy_monitor",
                        observed_at=observed_at,
                    )
                try:
                    candidate = self.responses.get(timeout=remaining)
                except queue.Empty:
                    observed_at = time.time()
                    self._discard_worker()
                    raise ProxyUnavailableError(
                        f"proxy health check exceeded {budget:.1f}s hard deadline",
                        stage="continuous_proxy_monitor",
                        observed_at=observed_at,
                    )
                if candidate.get("_worker_eof"):
                    self._discard_worker()
                    raise ProxyUnavailableError(
                        "proxy health worker stopped unexpectedly",
                        stage="continuous_proxy_monitor",
                    )
                if candidate.get("request_id") == request_id:
                    response = candidate
            if not isinstance(response, dict) or response.get("request_id") != request_id:
                self._discard_worker()
                raise ProxyUnavailableError(
                    "proxy health worker returned an invalid response",
                    stage="continuous_proxy_monitor",
                )
            if not response.get("available"):
                raise ProxyUnavailableError(
                    response.get("reason") or "Bright Data proxy is unavailable",
                    stage=response.get("stage") or "continuous_proxy_monitor",
                    currently_unavailable=response.get("currently_unavailable", True),
                    observed_at=response.get("observed_at"),
                    country_iso=response.get("country_iso"),
                )
            return dict(response.get("details") or {})

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            if self.process is not None and self.process.stdin is not None:
                try:
                    self.process.stdin.write(json.dumps({"shutdown": True}) + "\n")
                    self.process.stdin.flush()
                except Exception:
                    pass
            self._discard_worker()


class ProxyHealthMonitor:
    """Continuously probes Bright Data and publishes one shared health snapshot."""

    def __init__(
        self,
        shared_state,
        checker,
        country_iso="us",
        interval_seconds=DEFAULT_CHECK_INTERVAL_SECONDS,
        timeout_seconds=DEFAULT_CHECK_TIMEOUT_SECONDS,
        on_transition=None,
    ):
        self.shared_state = shared_state
        self.checker = checker
        self.country_iso = str(country_iso or "us").strip().lower()
        self.interval_seconds = clamp_interval(interval_seconds)
        self.timeout_seconds = clamp_timeout(timeout_seconds)
        self.on_transition = on_transition
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="bright-proxy-health", daemon=True)

    def start(self):
        if not self.thread.is_alive():
            self.thread.start()

    def stop(self, timeout=None):
        self.stop_event.set()
        if self.thread.is_alive():
            join_timeout = timeout if timeout is not None else self.timeout_seconds + 2.0
            self.thread.join(timeout=max(0.1, float(join_timeout)))

    def _notify_transition(self, previous, current):
        changed = (
            not previous.get("initialized")
            or bool(previous.get("available")) != bool(current.get("available"))
        )
        if changed and self.on_transition is not None:
            try:
                self.on_transition(current, previous)
            except Exception:
                pass

    def _run(self):
        next_started_at = time.monotonic()
        while not self.stop_event.is_set():
            wait_for = max(0.0, next_started_at - time.monotonic())
            if self.stop_event.wait(wait_for):
                return

            started_at = time.monotonic()
            current_snapshot = get_snapshot(self.shared_state)
            down_country = str(current_snapshot.get("down_country") or "").strip().lower()
            probe_country = (
                down_country
                if current_snapshot.get("initialized")
                and not current_snapshot.get("available")
                and down_country
                else self.country_iso
            )
            try:
                details = self.checker(probe_country, self.timeout_seconds)
                if not isinstance(details, dict) or not details.get("ip"):
                    raise ProxyUnavailableError("health endpoint returned no egress IP")
                observed_at = time.time()
                latest = get_snapshot(self.shared_state)
                latest_down_country = str(latest.get("down_country") or "").strip().lower()
                if (
                    latest.get("initialized")
                    and not latest.get("available")
                    and latest_down_country
                    and latest_down_country != probe_country
                ):
                    # A worker discovered a different country-route failure
                    # while this check was in flight. Do not let an unrelated
                    # healthy route clear it; the next cycle checks that route.
                    previous, current = latest, latest
                else:
                    previous, current = publish_state(
                        self.shared_state,
                        True,
                        "healthy",
                        details=details,
                        checked_at=observed_at,
                        country_iso=probe_country,
                    )
            except ProxyUnavailableError as exc:
                observed_at = getattr(exc, "observed_at", time.time())
                previous, current = publish_state(
                    self.shared_state,
                    False,
                    exc.reason,
                    checked_at=observed_at,
                    country_iso=probe_country,
                )
            except Exception as exc:
                observed_at = time.time()
                previous, current = publish_state(
                    self.shared_state,
                    False,
                    f"{type(exc).__name__}: {sanitize_error(exc)}",
                    checked_at=observed_at,
                    country_iso=probe_country,
                )
            self._notify_transition(previous, current)

            # Schedule by probe start time.  Slow/timeout probes therefore do
            # not add another full interval before the next recovery check.
            next_started_at = started_at + self.interval_seconds
