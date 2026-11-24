import json
import logging
import multiprocessing
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from helper import daily_logging
from helper.log_paths import resolve_log_path


def _record(message, created, *, root="logs", filename="payloads.log", raw=False, max_bytes=100000):
    record = logging.LogRecord("fixture", logging.INFO, __file__, 1, message, (), None)
    record.created = created
    record.pas_root = root
    record.pas_filename = filename
    record.pas_raw = raw
    record.pas_max_bytes = max_bytes
    record.pas_backups = 3
    return record


def _multiprocess_log_writer(log_queue, worker_id, count):
    daily_logging.install_worker_queue(log_queue, 2)
    logger = daily_logging.configure_logger(
        f"mp-fixture-{worker_id}", "logs/shared.json", raw=True,
        timezone="Asia/Kolkata", date_format="%Y-%m-%d",
    )
    for index in range(count):
        logger.info(json.dumps({"worker": worker_id, "index": index}))


class DailyLoggingTests(unittest.TestCase):
    def test_records_route_by_creation_timestamp_across_midnight(self):
        timezone = ZoneInfo("Asia/Kolkata")
        before = datetime(2026, 10, 24, 23, 59, 59, tzinfo=timezone).timestamp()
        after = datetime(2026, 10, 25, 0, 0, 0, tzinfo=timezone).timestamp()
        with tempfile.TemporaryDirectory() as folder:
            router = daily_logging.DailyDirectoryRouter(base_dir=folder)
            router.handle(_record("before", before))
            router.handle(_record("after", after))
            router.handle(_record("late-before", before))
            router.close()
            day_one = Path(folder, "logs", "2026-10-24", "payloads.log").read_text(encoding="utf-8")
            day_two = Path(folder, "logs", "2026-10-25", "payloads.log").read_text(encoding="utf-8")
            self.assertIn("before", day_one)
            self.assertIn("late-before", day_one)
            self.assertNotIn("after", day_one)
            self.assertIn("after", day_two)

    def test_raw_json_has_no_formatter_prefix(self):
        timestamp = datetime(2026, 10, 24, 12, tzinfo=ZoneInfo("Asia/Kolkata")).timestamp()
        payload = {"ad_id": 45, "status": 2}
        with tempfile.TemporaryDirectory() as folder:
            router = daily_logging.DailyDirectoryRouter(base_dir=folder)
            router.handle(_record(json.dumps(payload), timestamp, filename="success.json", raw=True))
            router.close()
            line = Path(folder, "logs", "2026-10-24", "success.json").read_text(encoding="utf-8").strip()
            self.assertEqual(json.loads(line), payload)
            self.assertTrue(line.startswith("{"))

    def test_standard_timestamp_uses_configured_timezone(self):
        timestamp = datetime(2026, 10, 24, 1, 2, 3, tzinfo=ZoneInfo("Asia/Kolkata")).timestamp()
        with tempfile.TemporaryDirectory() as folder:
            router = daily_logging.DailyDirectoryRouter(base_dir=folder)
            router.handle(_record("timezone-check", timestamp))
            router.close()
            line = Path(folder, "logs", "2026-10-24", "payloads.log").read_text(encoding="utf-8")
            self.assertTrue(line.startswith("2026-10-24 01:02:03 | INFO | fixture |"), line)

    def test_size_rotation_stays_in_date_folder(self):
        timestamp = datetime(2026, 10, 24, 12, tzinfo=ZoneInfo("Asia/Kolkata")).timestamp()
        with tempfile.TemporaryDirectory() as folder:
            router = daily_logging.DailyDirectoryRouter(base_dir=folder)
            for index in range(40):
                router.handle(_record(f"{index}:" + "x" * 100, timestamp, max_bytes=1024))
            router.close()
            date_folder = Path(folder, "logs", "2026-10-24")
            self.assertTrue((date_folder / "payloads.log").is_file())
            self.assertTrue((date_folder / "payloads.log.1").is_file())
            self.assertFalse(Path(folder, "logs", "payloads.log").exists())

    def test_unsafe_paths_and_invalid_timezone_are_rejected(self):
        for path in ("logs/../escape.log", "other/file.log", "logs/sub/file.log"):
            with self.assertRaises(ValueError, msg=path):
                daily_logging.split_log_path(path)
        with self.assertRaisesRegex(ValueError, "LOG_TIMEZONE"):
            daily_logging.DailyDirectoryRouter(timezone="Not/A_Real_Zone")
        with self.assertRaisesRegex(ValueError, "LOG_DATE_FORMAT"):
            daily_logging.DailyDirectoryRouter(date_format="%d/%m/%Y")

    def test_error_root_and_restart_append(self):
        timestamp = datetime(2026, 10, 24, 12, tzinfo=ZoneInfo("Asia/Kolkata")).timestamp()
        with tempfile.TemporaryDirectory() as folder:
            first = daily_logging.DailyDirectoryRouter(base_dir=folder)
            first.handle(_record("first", timestamp, root="er_logs", filename="worker.log"))
            first.close()
            second = daily_logging.DailyDirectoryRouter(base_dir=folder)
            second.handle(_record("second", timestamp, root="er_logs", filename="worker.log"))
            second.close()
            content = Path(folder, "er_logs", "2026-10-24", "worker.log").read_text(encoding="utf-8")
            self.assertIn("first", content)
            self.assertIn("second", content)

    def test_repeated_logger_configuration_is_idempotent(self):
        name = "daily-idempotent-fixture"
        daily_logging.configure_logger(name, "logs/idempotent.log")
        logger = daily_logging.configure_logger(name, "logs/idempotent.log")
        managed = [handler for handler in logger.handlers if getattr(handler, "_pas_managed", False)]
        self.assertEqual(len(managed), 1)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    def test_listener_serializes_spawned_process_writes(self):
        context = multiprocessing.get_context("spawn")
        manager = context.Manager()
        try:
            log_queue = manager.Queue(maxsize=1000)
            with tempfile.TemporaryDirectory() as folder:
                listener = daily_logging.LoggingListener(log_queue, base_dir=folder).start()
                processes = [
                    context.Process(target=_multiprocess_log_writer, args=(log_queue, worker_id, 30))
                    for worker_id in range(4)
                ]
                for process in processes:
                    process.start()
                for process in processes:
                    process.join(30)
                    self.assertEqual(process.exitcode, 0)
                listener.stop(15)
                path = resolve_log_path(Path(folder, "logs"), "shared.json")
                rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
                self.assertEqual(len(rows), 120)
                self.assertEqual(len({(row["worker"], row["index"]) for row in rows}), 120)
        finally:
            manager.shutdown()

    def test_resolver_prefers_latest_dated_file_then_legacy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder, "logs")
            older = root / "2026-10-23" / "payloads.log"
            newer = root / "2026-10-24" / "payloads.log"
            older.parent.mkdir(parents=True)
            newer.parent.mkdir(parents=True)
            older.write_text("old", encoding="utf-8")
            newer.write_text("new", encoding="utf-8")
            os.utime(older, (1, 1))
            os.utime(newer, (2, 2))
            self.assertEqual(resolve_log_path(root, "payloads.log"), newer)


if __name__ == "__main__":
    unittest.main()
