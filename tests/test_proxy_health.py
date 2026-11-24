import json
import multiprocessing
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from helper import api_client, init, proxy_health
import new_lander


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}
        self.ok = 200 <= status_code < 400

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.proxies = {}
        self.headers = {}
        self.closed = False
        self.trust_env = True

    def get(self, _url, timeout=None, **_kwargs):
        self.timeout = timeout
        if self.error:
            raise self.error
        return self.response

    def close(self):
        self.closed = True


class Logger:
    def __init__(self):
        self.messages = []

    def info(self, message, *args, **_kwargs):
        self.messages.append(("info", str(message), args))

    def warning(self, message, *args, **_kwargs):
        self.messages.append(("warning", str(message), args))

    def error(self, message, *args, **_kwargs):
        self.messages.append(("error", str(message), args))


class MetricCounter:
    def labels(self, **_kwargs):
        return self

    def inc(self):
        return None


class Metric:
    processed_configured_lander_url = MetricCounter()
    updated_configured_lander = MetricCounter()


def healthy_state():
    state = {}
    proxy_health.initialize_state(state, enabled=True)
    proxy_health.publish_state(
        state,
        True,
        "healthy",
        details={"ip": "203.0.113.10", "country": "US"},
    )
    return state


def _spawn_publish_proxy_down(state, output_queue):
    proxy_health.publish_state(state, False, "spawned worker down")
    output_queue.put(proxy_health.get_snapshot(state))


def _spawn_requeue_and_wait_for_proxy(state, file_lock, in_flight, ad, output_queue):
    try:
        new_lander._release_ad_for_proxy_wait(
            file_lock,
            ad,
            in_flight,
            Logger(),
        )
        output_queue.put(("requeued", dict(ad)))
        resumed = proxy_health.wait_for_available(
            state,
            stale_after_seconds=5.0,
            poll_seconds=0.05,
        )
        output_queue.put(("resumed", resumed))
    except BaseException as exc:
        output_queue.put(("error", f"{type(exc).__name__}: {exc}"))


class ProxyHealthTests(unittest.TestCase):
    def test_strict_egress_probe_accepts_valid_ip(self):
        session = FakeSession(FakeResponse(payload={"ip": "203.0.113.8", "country": "US"}))
        result = init.verify_proxy_egress(
            session=session,
            iso="us",
            required=True,
            timeout_seconds=3,
        )
        self.assertEqual(result["ip"], "203.0.113.8")
        self.assertEqual(session.timeout, (1.5, 1.5))

    def test_strict_egress_probe_rejects_407_without_leaking_credentials(self):
        secret = "top-secret-password"
        response = FakeResponse(
            status_code=407,
            text=f"proxy http://customer:{secret}@brd.superproxy.io rejected",
            headers={"x-brd-err-msg": "client IP is not allowed"},
        )
        with self.assertRaises(proxy_health.ProxyUnavailableError) as caught:
            init.verify_proxy_egress(
                session=FakeSession(response),
                iso="in",
                required=True,
                timeout_seconds=2,
            )
        self.assertIn("HTTP 407", str(caught.exception))
        self.assertNotIn(secret, str(caught.exception))

    def test_strict_egress_probe_rejects_invalid_json_and_missing_ip(self):
        with self.assertRaises(proxy_health.ProxyUnavailableError):
            init.verify_proxy_egress(
                session=FakeSession(FakeResponse(payload=ValueError("bad json"))),
                iso="us",
                required=True,
            )
        with self.assertRaises(proxy_health.ProxyUnavailableError):
            init.verify_proxy_egress(
                session=FakeSession(FakeResponse(payload={"country": "US"})),
                iso="us",
                required=True,
            )

    def test_monitor_transitions_down_then_up_and_checks_quickly(self):
        state = {}
        proxy_health.initialize_state(state, enabled=True)
        calls = []
        recovered = threading.Event()

        def checker(_country, _timeout):
            calls.append(time.monotonic())
            if len(calls) < 3:
                raise proxy_health.ProxyUnavailableError("gateway unavailable")
            return {"ip": "203.0.113.9", "country": "US"}

        def transition(current, _previous):
            if current.get("available"):
                recovered.set()

        monitor = proxy_health.ProxyHealthMonitor(
            state,
            checker,
            interval_seconds=0.1,
            timeout_seconds=0.1,
            on_transition=transition,
        )
        monitor.start()
        try:
            self.assertTrue(recovered.wait(2), proxy_health.get_snapshot(state))
        finally:
            monitor.stop()
        self.assertGreaterEqual(len(calls), 3)
        self.assertTrue(proxy_health.state_is_available(state, stale_after_seconds=2))
        self.assertLessEqual(max(b - a for a, b in zip(calls, calls[1:])), 0.5)

    def test_health_interval_is_hard_capped_at_ten_seconds(self):
        self.assertEqual(proxy_health.clamp_interval(99), 10.0)
        self.assertEqual(proxy_health.clamp_timeout(99), 10.0)

    def test_force_probe_never_reuses_a_completed_success(self):
        state = healthy_state()
        calls = []

        def checker(**_kwargs):
            calls.append(time.monotonic())
            if len(calls) == 1:
                return {"ip": "203.0.113.55", "country": "US"}
            raise proxy_health.ProxyUnavailableError("provider went down")

        with patch.object(new_lander.init, "verify_proxy_egress", side_effect=checker):
            new_lander._ensure_proxy_available(
                state,
                stage="first_boundary",
                country_iso="us",
                force_probe=True,
            )
            with self.assertRaises(proxy_health.ProxyUnavailableError):
                new_lander._ensure_proxy_available(
                    state,
                    stage="second_boundary",
                    country_iso="us",
                    force_probe=True,
                )

        self.assertEqual(len(calls), 2)
        self.assertFalse(proxy_health.get_snapshot(state)["available"])

    def test_parent_monitor_is_not_blocked_by_worker_probe_lock(self):
        worker_probe_lock = threading.Lock()
        state = {
            "_write_lock": threading.RLock(),
            "_probe_lock": worker_probe_lock,
            "_probe_cache": {},
        }
        proxy_health.initialize_state(state, enabled=True)
        recovered = threading.Event()

        def transition(current, _previous):
            if current.get("available"):
                recovered.set()

        monitor = proxy_health.ProxyHealthMonitor(
            state,
            new_lander._monitor_bright_proxy,
            interval_seconds=0.1,
            timeout_seconds=0.1,
            on_transition=transition,
        )
        worker_probe_lock.acquire()
        observed_while_locked = False
        try:
            with patch.object(
                new_lander.init,
                "verify_proxy_egress",
                return_value={"ip": "203.0.113.56", "country": "US"},
            ) as checker:
                monitor.start()
                observed_while_locked = recovered.wait(1.0)
                self.assertGreaterEqual(checker.call_count, 1)
        finally:
            worker_probe_lock.release()
            monitor.stop(timeout=1.0)

        self.assertTrue(observed_while_locked)

    def test_monitor_recovers_the_country_route_that_a_worker_marked_down(self):
        state = healthy_state()
        proxy_health.mark_unavailable(
            state,
            "India route down",
            country_iso="in",
        )
        checked_countries = []
        recovered = threading.Event()

        def checker(country_iso, _timeout):
            checked_countries.append(country_iso)
            return {"ip": "203.0.113.59", "country": country_iso.upper()}

        def transition(current, _previous):
            if current.get("available"):
                recovered.set()

        monitor = proxy_health.ProxyHealthMonitor(
            state,
            checker,
            country_iso="us",
            interval_seconds=0.1,
            timeout_seconds=0.1,
            on_transition=transition,
        )
        monitor.start()
        try:
            self.assertTrue(recovered.wait(1.0))
        finally:
            monitor.stop(timeout=1.0)
        self.assertEqual(checked_countries[0], "in")
        self.assertTrue(proxy_health.get_snapshot(state)["available"])

    def test_unrelated_monitor_success_cannot_clear_new_country_failure(self):
        state = healthy_state()
        first_probe_started = threading.Event()
        release_first_probe = threading.Event()
        affected_route_checked = threading.Event()
        calls = []

        def checker(country_iso, _timeout):
            calls.append(country_iso)
            if len(calls) == 1:
                first_probe_started.set()
                release_first_probe.wait(1.0)
                return {"ip": "203.0.113.60", "country": "US"}
            affected_route_checked.set()
            raise proxy_health.ProxyUnavailableError(
                "route still down",
                country_iso=country_iso,
            )

        monitor = proxy_health.ProxyHealthMonitor(
            state,
            checker,
            country_iso="us",
            interval_seconds=0.1,
            timeout_seconds=0.1,
        )
        monitor.start()
        try:
            self.assertTrue(first_probe_started.wait(1.0))
            proxy_health.mark_unavailable(
                state,
                "India route down",
                country_iso="in",
            )
            release_first_probe.set()
            self.assertTrue(affected_route_checked.wait(1.0))
        finally:
            monitor.stop(timeout=1.0)

        snapshot = proxy_health.get_snapshot(state)
        self.assertFalse(snapshot["available"])
        self.assertEqual(calls[:2], ["us", "in"])

    def test_isolated_monitor_probe_has_hard_deadline_and_restarts(self):
        runner = proxy_health.IsolatedProbeRunner(
            worker_module="tests.proxy_probe_fixture",
            max_wall_seconds=2.0,
        )
        active_process = None
        try:
            runner.start()
            first = runner("us", 2.0)
            second = runner("gb", 2.0)
            self.assertEqual(first["pid"], second["pid"])
            original_pid = first["pid"]

            started = time.monotonic()
            with self.assertRaisesRegex(
                proxy_health.ProxyUnavailableError,
                "hard deadline",
            ):
                runner("slow", 0.2)
            self.assertLess(time.monotonic() - started, 3.0)

            # A timed-out child is discarded; the next call must start a clean
            # worker and successfully return instead of remaining wedged.
            recovered = runner("us", 7.0)
            self.assertEqual(recovered["ip"], "203.0.113.58")
            self.assertNotEqual(recovered["pid"], original_pid)

            with self.assertRaises(proxy_health.ProxyUnavailableError) as caught:
                runner("error", 2.0)
            self.assertEqual(caught.exception.reason, "fixture proxy down")
            self.assertEqual(caught.exception.stage, "fixture_stage")
            self.assertEqual(caught.exception.observed_at, 1234.5)
            active_process = runner.process
        finally:
            runner.close()
        self.assertIsNotNone(active_process)
        self.assertIsNotNone(active_process.poll())

    def test_delayed_worker_failure_cannot_override_newer_recovery(self):
        state = {"_write_lock": threading.RLock()}
        proxy_health.initialize_state(state, enabled=True)
        failure_observed_at = time.time() + 1.0
        recovery_observed_at = failure_observed_at + 1.0
        delayed_error = proxy_health.ProxyUnavailableError(
            "old worker failure",
            observed_at=failure_observed_at,
        )

        proxy_health.publish_state(
            state,
            False,
            delayed_error.reason,
            checked_at=failure_observed_at,
        )
        proxy_health.publish_state(
            state,
            True,
            "healthy",
            details={"ip": "203.0.113.57", "country": "US"},
            checked_at=recovery_observed_at,
        )
        proxy_health.mark_unavailable(
            state,
            delayed_error.reason,
            checked_at=delayed_error.observed_at,
        )

        snapshot = proxy_health.get_snapshot(state)
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["checked_at"], recovery_observed_at)

    def test_api_retry_guard_stops_before_second_http_attempt(self):
        class RetryResponse:
            status_code = 503
            headers = {}

        class RetrySession:
            def __init__(self):
                self.calls = 0

            def request(self, *_args, **_kwargs):
                self.calls += 1
                return RetryResponse()

        session = RetrySession()
        guard_calls = []

        def guard():
            guard_calls.append(time.monotonic())
            if len(guard_calls) == 2:
                raise proxy_health.ProxyUnavailableError("down before retry")

        with patch.object(api_client.time, "sleep", return_value=None):
            with self.assertRaises(proxy_health.ProxyUnavailableError):
                api_client.request(
                    "POST",
                    "https://example.test",
                    session=session,
                    attempts=3,
                    before_attempt=guard,
                )

        self.assertEqual(session.calls, 1)
        self.assertEqual(len(guard_calls), 2)

    def test_navigation_rechecks_proxy_immediately_after_goto(self):
        class Page:
            url = "https://example.test"

            def __init__(self):
                self.goto_calls = 0

            def on(self, *_args):
                return None

            def goto(self, *_args, **_kwargs):
                self.goto_calls += 1
                return None

            def evaluate(self, *_args, **_kwargs):
                return {"text": 1, "media": 0, "area": 1}

            def is_closed(self):
                return False

        page = Page()
        guard_calls = []

        def guard():
            guard_calls.append(time.monotonic())
            if len(guard_calls) >= 2:
                raise proxy_health.ProxyUnavailableError("down during navigation")

        with self.assertRaises(proxy_health.ProxyUnavailableError):
            new_lander.navigation.navigate(
                page,
                "https://example.test",
                attempts=1,
                abort_check=guard,
            )
        self.assertEqual(page.goto_calls, 1)

    def test_media_upload_rechecks_proxy_after_each_http_attempt(self):
        guard_calls = []

        def guard():
            guard_calls.append(time.monotonic())
            if len(guard_calls) >= 3:
                raise proxy_health.ProxyUnavailableError("down during media upload")

        with tempfile.TemporaryDirectory() as folder:
            screenshot = os.path.join(folder, "shot.jpg")
            with open(screenshot, "wb") as handle:
                handle.write(b"not-empty")
            with patch.object(
                new_lander.requests,
                "post",
                return_value=FakeResponse(status_code=503, payload={"code": "503"}),
            ) as upload:
                with self.assertRaises(proxy_health.ProxyUnavailableError):
                    new_lander.make_payload(
                        508,
                        "us",
                        "test",
                        [],
                        "https://example.test",
                        screenshot,
                        "text",
                        [],
                        "2020-01-01",
                        1,
                        2,
                        None,
                        [],
                        Logger(),
                        abort_check=guard,
                    )
        self.assertEqual(upload.call_count, 1)

    def test_concurrent_workers_share_one_recent_probe(self):
        with multiprocessing.Manager() as manager:
            state = manager.dict()
            state["_write_lock"] = manager.RLock()
            state["_probe_lock"] = manager.RLock()
            state["_probe_cache"] = {}
            proxy_health.initialize_state(state, enabled=True)
            checker_calls = []
            results = []

            def checker():
                checker_calls.append(time.monotonic())
                time.sleep(0.05)
                return {"ip": "203.0.113.20", "country": "US"}

            def worker():
                results.append(
                    proxy_health.run_singleflight_probe(
                        state, "us", checker, cache_seconds=1.0
                    )
                )

            workers = [threading.Thread(target=worker) for _ in range(8)]
            for worker_thread in workers:
                worker_thread.start()
            for worker_thread in workers:
                worker_thread.join()
            self.assertEqual(len(checker_calls), 1)
            self.assertEqual(len(results), 8)

    def test_manager_proxy_state_is_windows_spawn_safe(self):
        context = multiprocessing.get_context("spawn")
        with multiprocessing.Manager() as manager:
            state = manager.dict()
            state["_write_lock"] = manager.RLock()
            state["_probe_lock"] = manager.RLock()
            state["_probe_cache"] = {}
            proxy_health.initialize_state(state, enabled=True)
            proxy_health.publish_state(
                state, True, "healthy", details={"ip": "203.0.113.21"}
            )
            output_queue = context.Queue()
            process = context.Process(
                target=_spawn_publish_proxy_down,
                args=(state, output_queue),
            )
            process.start()
            process.join(10)
            self.assertEqual(process.exitcode, 0)
            child_snapshot = output_queue.get(timeout=2)
            self.assertFalse(child_snapshot["available"])
            self.assertFalse(proxy_health.get_snapshot(state)["available"])
            output_queue.close()
            output_queue.join_thread()

    def test_spawned_worker_requeues_waits_and_resumes(self):
        old_cwd = os.getcwd()
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as folder, multiprocessing.Manager() as manager:
            try:
                os.chdir(folder)
                state = manager.dict()
                state["_write_lock"] = manager.RLock()
                state["_probe_lock"] = manager.RLock()
                state["_probe_cache"] = {}
                proxy_health.initialize_state(state, enabled=True)
                proxy_health.mark_unavailable(
                    state,
                    "spawn fixture down",
                    country_iso="us",
                )
                file_lock = manager.Lock()
                in_flight = manager.dict()
                ad = {
                    "id": 510,
                    "destination_url": "https://example.test",
                    "_queue_attempt": 2,
                    "_proxy_unavailable": True,
                    "_proxy_unavailable_reason": "spawn fixture down",
                    "_scrape_run_id": "discard-me",
                }
                in_flight[510] = ("1", time.time(), dict(ad))
                output_queue = context.Queue()
                process = context.Process(
                    target=_spawn_requeue_and_wait_for_proxy,
                    args=(state, file_lock, in_flight, ad, output_queue),
                )
                process.start()
                event, value = output_queue.get(timeout=15)
                self.assertEqual((event, value["_queue_attempt"]), ("requeued", 2))
                self.assertTrue(process.is_alive())
                self.assertNotIn(510, in_flight)
                with open(new_lander._shared_queue_path(), "r", encoding="utf-8") as handle:
                    queued = json.load(handle)
                self.assertEqual(queued[0]["_queue_attempt"], 2)
                self.assertNotIn("_proxy_unavailable", queued[0])
                self.assertNotIn("_scrape_run_id", queued[0])

                proxy_health.publish_state(
                    state,
                    True,
                    "spawn fixture recovered",
                    details={"ip": "203.0.113.63", "country": "US"},
                    country_iso="us",
                )
                event, value = output_queue.get(timeout=5)
                self.assertEqual((event, value), ("resumed", True))
                process.join(10)
                self.assertEqual(process.exitcode, 0)
                output_queue.close()
                output_queue.join_thread()
            finally:
                os.chdir(old_cwd)

    def test_waiter_resumes_after_shared_state_recovers(self):
        state = {}
        proxy_health.initialize_state(state, enabled=True)

        def recover():
            time.sleep(0.1)
            proxy_health.publish_state(
                state,
                True,
                "healthy",
                details={"ip": "203.0.113.11"},
            )

        thread = threading.Thread(target=recover)
        thread.start()
        started = time.monotonic()
        try:
            self.assertTrue(
                proxy_health.wait_for_available(
                    state,
                    stale_after_seconds=2,
                    poll_seconds=0.02,
                )
            )
        finally:
            thread.join()
        self.assertLess(time.monotonic() - started, 1.0)

    def test_outage_during_scrape_invalidates_result_even_after_recovery(self):
        state = healthy_state()
        scrape_started = time.time()
        time.sleep(0.01)
        proxy_health.publish_state(state, False, "down")
        proxy_health.publish_state(
            state,
            True,
            "healthy",
            details={"ip": "203.0.113.12"},
        )
        with self.assertRaises(proxy_health.ProxyUnavailableError) as caught:
            new_lander._ensure_proxy_available(
                state,
                stage="before_final_payload",
                outage_since=scrape_started,
            )
        self.assertFalse(caught.exception.currently_unavailable)

    def test_older_success_cannot_overwrite_newer_down_snapshot(self):
        state = {"_write_lock": threading.RLock()}
        proxy_health.initialize_state(state, enabled=True)
        now = time.time()
        proxy_health.publish_state(state, False, "down", checked_at=now)
        proxy_health.publish_state(
            state,
            True,
            "stale success",
            details={"ip": "203.0.113.30"},
            checked_at=now - 1,
        )
        snapshot = proxy_health.get_snapshot(state)
        self.assertFalse(snapshot["available"])
        self.assertEqual(snapshot["reason"], "down")

    def test_worker_probe_success_cannot_override_monitor_down(self):
        state = healthy_state()
        proxy_health.publish_state(state, False, "monitor down")
        with patch.object(
            new_lander.init,
            "verify_proxy_egress",
            return_value={"ip": "203.0.113.31", "country": "IN"},
        ):
            with self.assertRaises(proxy_health.ProxyUnavailableError):
                new_lander._ensure_proxy_available(
                    state,
                    stage="worker_force_check",
                    country_iso="in",
                    force_probe=True,
                )
        snapshot = proxy_health.get_snapshot(state)
        self.assertFalse(snapshot["available"])
        self.assertEqual(snapshot["reason"], "monitor down")

    def test_proxy_interrupted_ad_requeues_without_attempt_increment(self):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                ad = {
                    "id": 501,
                    "destination_url": "https://example.test",
                    "_queue_attempt": 2,
                    "_proxy_unavailable": True,
                    "_proxy_unavailable_reason": "down",
                    "_result_status": 3,
                    "_scrape_run_id": "old-run",
                }
                leases = {501: ("1", time.time(), dict(ad))}
                new_lander._release_ad_for_proxy_wait(
                    threading.Lock(), ad, leases, Logger()
                )
                with open(new_lander._shared_queue_path(), "r", encoding="utf-8") as handle:
                    queued = json.load(handle)
                self.assertNotIn(501, leases)
                self.assertEqual(queued[0]["_queue_attempt"], 2)
                self.assertNotIn("_proxy_unavailable", queued[0])
                self.assertNotIn("_result_status", queued[0])
                self.assertNotIn("_scrape_run_id", queued[0])
                self.assertFalse(any("dead_letter" in name for name in os.listdir("getApi_data_dev")))
            finally:
                os.chdir(old_cwd)

    def test_proxy_requeue_write_failure_keeps_lease(self):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                ad = {"id": 505, "destination_url": "https://example.test"}
                leases = {505: ("1", time.time(), dict(ad))}
                with patch.object(new_lander, "_atomic_write_json", side_effect=OSError("disk full")):
                    with self.assertRaisesRegex(OSError, "disk full"):
                        new_lander._release_ad_for_proxy_wait(
                            threading.Lock(), ad, leases, Logger()
                        )
                self.assertIn(505, leases)
            finally:
                os.chdir(old_cwd)

    def test_mid_scrape_outage_requeues_waits_and_resumes_end_to_end(self):
        class StopWorkerLoop(Exception):
            pass

        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                ad = {
                    "id": 509,
                    "destination_url": "https://example.test",
                    "iso": ["us"],
                    "_queue_attempt": 2,
                }
                os.makedirs(os.path.dirname(new_lander._shared_queue_path()), exist_ok=True)
                new_lander._atomic_write_json(new_lander._shared_queue_path(), [ad], strict=True)

                state = healthy_state()
                file_lock = threading.Lock()
                in_flight = {}
                completed = {}
                logger = Logger()
                requeued = threading.Event()
                waiting_while_down = threading.Event()
                scrape_attempts = []
                wait_calls = []
                pop_calls = []
                worker_errors = []

                original_release = new_lander._release_ad_for_proxy_wait
                original_wait = new_lander._wait_for_bright_proxy
                original_pop = new_lander.pop_next_ad_from_file

                def release_for_proxy(*args, **kwargs):
                    result = original_release(*args, **kwargs)
                    requeued.set()
                    return result

                def wait_for_proxy(*args, **kwargs):
                    wait_calls.append(time.monotonic())
                    if len(wait_calls) >= 2:
                        waiting_while_down.set()
                    return original_wait(*args, **kwargs)

                def controlled_pop(*args, **kwargs):
                    pop_calls.append(time.monotonic())
                    if len(pop_calls) >= 3:
                        raise StopWorkerLoop()
                    return original_pop(*args, **kwargs)

                def fake_scrape(single_data, *_args, **_kwargs):
                    scrape_attempts.append(dict(single_data))
                    if len(scrape_attempts) == 1:
                        single_data["_proxy_unavailable"] = True
                        single_data["_proxy_unavailable_reason"] = "fixture outage"
                        single_data["_scrape_run_id"] = "discard-this-run"
                        single_data["_result_status"] = 3
                        proxy_health.mark_unavailable(
                            state,
                            "fixture outage",
                            country_iso="us",
                        )
                        return False

                    self.assertTrue(proxy_health.state_is_available(state, 2.0))
                    new_lander.send_payload(
                        [{
                            "ad_id": single_data["id"],
                            "status": 2,
                            "outgoing_url": [],
                            "redirects": [],
                        }],
                        logger,
                        "8999",
                        Metric(),
                    )
                    return True

                def run_worker():
                    try:
                        new_lander.main((
                            "1",
                            "8999",
                            file_lock,
                            in_flight,
                            completed,
                            state,
                        ))
                    except StopWorkerLoop as exc:
                        worker_errors.append(exc)
                    except BaseException as exc:
                        worker_errors.append(exc)

                with patch.object(new_lander, "start_http_server"), patch.object(
                    new_lander, "setup_logger", return_value=logger
                ), patch.object(new_lander, "Metrics", return_value=Metric()), patch.object(
                    new_lander, "scraping", side_effect=fake_scrape
                ), patch.object(
                    new_lander, "_release_ad_for_proxy_wait", side_effect=release_for_proxy
                ), patch.object(
                    new_lander, "_wait_for_bright_proxy", side_effect=wait_for_proxy
                ), patch.object(
                    new_lander, "pop_next_ad_from_file", side_effect=controlled_pop
                ), patch.object(
                    new_lander, "send_payload", return_value=True
                ) as status2_sender, patch.object(
                    new_lander, "send_status3_payload"
                ) as status3_sender:
                    worker = threading.Thread(target=run_worker, daemon=True)
                    worker.start()
                    try:
                        self.assertTrue(requeued.wait(2.0))
                        self.assertTrue(waiting_while_down.wait(2.0))
                        with open(new_lander._shared_queue_path(), "r", encoding="utf-8") as handle:
                            queued = json.load(handle)
                        self.assertEqual(len(queued), 1)
                        self.assertEqual(queued[0]["_queue_attempt"], 2)
                        self.assertNotIn("_proxy_unavailable", queued[0])
                        self.assertNotIn("_scrape_run_id", queued[0])
                        self.assertNotIn("_result_status", queued[0])
                        self.assertNotIn(509, in_flight)
                        status2_sender.assert_not_called()
                        status3_sender.assert_not_called()
                        self.assertTrue(worker.is_alive())

                        proxy_health.publish_state(
                            state,
                            True,
                            "healthy",
                            details={"ip": "203.0.113.61", "country": "US"},
                            country_iso="us",
                        )
                        worker.join(3.0)
                    finally:
                        if worker.is_alive():
                            proxy_health.publish_state(
                                state,
                                True,
                                "test cleanup",
                                details={"ip": "203.0.113.62", "country": "US"},
                                country_iso="us",
                            )
                            worker.join(2.0)

                self.assertFalse(worker.is_alive())
                self.assertEqual(len(scrape_attempts), 2)
                self.assertEqual(scrape_attempts[1]["_queue_attempt"], 2)
                self.assertEqual(status2_sender.call_count, 1)
                status3_sender.assert_not_called()
                self.assertIn(509, completed)
                self.assertNotIn(509, in_flight)
                self.assertEqual(worker_errors and type(worker_errors[0]), StopWorkerLoop)
            finally:
                os.chdir(old_cwd)

    def test_scraping_proxy_outage_sends_no_status3(self):
        ad = {"id": 502, "destination_url": "https://example.test", "iso": ["us"]}
        state = healthy_state()
        logger = Logger()
        with patch.object(
            new_lander.init,
            "verify_proxy_egress",
            return_value={"ip": "203.0.113.40", "country": "US"},
        ), patch.object(
            new_lander.init,
            "init_dc",
            side_effect=proxy_health.ProxyUnavailableError("gateway down"),
        ), patch.object(new_lander, "send_status3_payload") as send_status3, patch.object(
            new_lander, "_finalize_artifacts"
        ), patch.object(new_lander.init, "close_browser"):
            result = new_lander.scraping(
                ad, Metric(), logger, "8999", "test", 0, logger,
                proxy_state=state,
            )
        self.assertFalse(result)
        self.assertTrue(ad.get("_proxy_unavailable"))
        send_status3.assert_not_called()

    def test_worker_gate_runs_before_queue_pop(self):
        state = {}
        proxy_health.initialize_state(state, enabled=True)
        wait_error = RuntimeError("stop after gate")
        logger = Logger()
        with patch.object(new_lander, "start_http_server"), patch.object(
            new_lander, "setup_logger", return_value=logger
        ), patch.object(new_lander, "Metrics", return_value=Metric()), patch.object(
            new_lander.time, "sleep"
        ), patch.object(
            new_lander, "_wait_for_bright_proxy", side_effect=wait_error
        ) as wait_gate, patch.object(
            new_lander, "pop_next_ad_from_file"
        ) as queue_pop, patch.object(
            new_lander, "payload_logger", new_lander.payload_logger
        ), patch.object(
            new_lander, "successful_payload_logger", new_lander.successful_payload_logger
        ), patch.object(
            new_lander, "unsuccessful_ad_logger", new_lander.unsuccessful_ad_logger
        ), patch.object(
            new_lander, "proxy_ad_logger", new_lander.proxy_ad_logger
        ):
            with self.assertRaisesRegex(RuntimeError, "stop after gate"):
                new_lander.main(("1", "8999", threading.Lock(), {}, {}, state))
        wait_gate.assert_called_once()
        queue_pop.assert_not_called()

    def test_final_status2_guard_runs_before_logging_or_api(self):
        payload = {
            "ad_id": 503,
            "status": 2,
            "outgoing_url": [],
            "redirects": [],
        }
        with patch.object(new_lander.api_client, "post_json") as post_json, patch.object(
            new_lander.successful_payload_logger, "info"
        ) as success_log:
            with self.assertRaises(proxy_health.ProxyUnavailableError):
                new_lander.send_payload(
                    [payload],
                    Logger(),
                    "8999",
                    Metric(),
                    pre_send_guard=lambda: (_ for _ in ()).throw(
                        proxy_health.ProxyUnavailableError("down")
                    ),
                )
        post_json.assert_not_called()
        success_log.assert_not_called()

    def test_unsuccessful_status_guard_runs_before_api(self):
        with patch.object(new_lander.api_client, "post_json") as post_json:
            with self.assertRaises(proxy_health.ProxyUnavailableError):
                new_lander.send_status3_payload(
                    504,
                    "us",
                    "https://example.test",
                    "navigation error",
                    Logger(),
                    pre_send_guard=lambda: (_ for _ in ()).throw(
                        proxy_health.ProxyUnavailableError("down")
                    ),
                )
        post_json.assert_not_called()

    def test_final_payload_forwards_guard_to_primary_and_trimmed_attempts(self):
        payload = {
            "ad_id": 506,
            "status": 2,
            "outgoing_url": [],
            "redirects": [],
            "html_path": "https://example.test/too-long",
            "screen_shot": "https://example.test/screenshot.jpg",
        }
        guard = Mock()
        too_long = FakeResponse(
            status_code=500,
            payload={"error": "ER_DATA_TOO_LONG white_ad_lander"},
        )
        accepted = FakeResponse(
            status_code=200,
            payload={"code": "200", "message": "accepted"},
        )
        with patch.object(
            new_lander.api_client,
            "post_json",
            side_effect=[too_long, accepted],
        ) as post_json:
            result = new_lander.send_payload(
                [payload],
                Logger(),
                "8999",
                Metric(),
                pre_send_guard=guard,
            )

        self.assertTrue(result)
        self.assertEqual(post_json.call_count, 2)
        for api_call in post_json.call_args_list:
            self.assertIs(api_call.kwargs.get("before_attempt"), guard)

    def test_status3_retry_stops_when_proxy_drops_before_second_attempt(self):
        retry_response = FakeResponse(status_code=503, payload={"code": "503"})
        guard_calls = []

        def guard():
            # send_status3_payload performs one early guard, and api_client
            # performs one immediately before every request attempt.
            guard_calls.append(time.monotonic())
            if len(guard_calls) == 3:
                raise proxy_health.ProxyUnavailableError("down before status3 retry")

        with patch.object(
            api_client.requests,
            "request",
            return_value=retry_response,
        ) as http_request, patch.object(api_client.time, "sleep", return_value=None):
            with self.assertRaises(proxy_health.ProxyUnavailableError):
                new_lander.send_status3_payload(
                    507,
                    "us",
                    "https://example.test",
                    "navigation error",
                    Logger(),
                    pre_send_guard=guard,
                )

        self.assertEqual(http_request.call_count, 1)
        self.assertEqual(len(guard_calls), 3)

    def test_bright_disabled_bypasses_gate(self):
        original = new_lander.config.bright_proxies
        new_lander.config.bright_proxies = False
        try:
            with patch.object(new_lander.init, "verify_proxy_egress") as probe:
                self.assertEqual(
                    new_lander._ensure_proxy_available(
                        {}, stage="disabled", force_probe=True
                    ),
                    {},
                )
            probe.assert_not_called()
        finally:
            new_lander.config.bright_proxies = original


if __name__ == "__main__":
    unittest.main()
