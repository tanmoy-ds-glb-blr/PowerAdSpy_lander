"""Process-safe logging routed into timezone-aware daily directories."""

import logging
import logging.handlers
import atexit
import os
import queue as queue_module
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ALLOWED_ROOTS = {"logs", "er_logs"}
_worker_queue = None
_worker_put_timeout = 2.0
_local_routers = {}
_local_lock = threading.RLock()
_last_stderr_at = 0.0


def _stderr_warning(message):
    global _last_stderr_at
    now = time.monotonic()
    if now - _last_stderr_at < 10:
        return
    _last_stderr_at = now
    try:
        print(f"[Logging Warning] {message}", file=sys.stderr, flush=True)
    except Exception:
        pass


def validate_timezone(name):
    try:
        return ZoneInfo(str(name or "Asia/Kolkata"))
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Invalid LOG_TIMEZONE: {name}") from exc


def validate_date_format(date_format, timezone="Asia/Kolkata"):
    value = datetime(2026, 10, 24, tzinfo=validate_timezone(timezone)).strftime(str(date_format))
    if not value or value in (".", "..") or any(char in value for char in ("/", "\\", ":")):
        raise ValueError(f"LOG_DATE_FORMAT must produce one safe directory name: {date_format}")
    return str(date_format)


def split_log_path(path):
    normalized = str(path).replace("\\", "/").strip("/")
    parts = normalized.split("/")
    if len(parts) != 2 or parts[0] not in ALLOWED_ROOTS:
        raise ValueError(f"Log path must be logs/<file> or er_logs/<file>: {path}")
    filename = parts[1]
    if not filename or filename in (".", "..") or Path(filename).name != filename:
        raise ValueError(f"Unsafe log filename: {filename}")
    return parts[0], filename


class TimezoneFormatter(logging.Formatter):
    def __init__(self, fmt, datefmt, timezone):
        super().__init__(fmt, datefmt)
        self.timezone = validate_timezone(timezone)

    def formatTime(self, record, datefmt=None):
        value = datetime.fromtimestamp(record.created, self.timezone)
        return value.strftime(datefmt) if datefmt else value.isoformat(timespec="milliseconds")


class DailyDirectoryRouter(logging.Handler):
    """Route records to one size-rotating handler per root/date/filename."""

    def __init__(self, *, base_dir=None, timezone="Asia/Kolkata", date_format="%d-%m-%Y", idle_seconds=3600,
                 daily_folders=True):
        super().__init__(logging.DEBUG)
        self.base_dir = Path(base_dir).resolve() if base_dir else None
        self.timezone_name = str(timezone)
        self.timezone = validate_timezone(timezone)
        self.date_format = validate_date_format(date_format, timezone)
        self.idle_seconds = max(60.0, float(idle_seconds))
        self.daily_folders = bool(daily_folders)
        self._handlers = {}

    def _base(self):
        return self.base_dir or Path.cwd().resolve()

    def _date_for(self, record):
        date_name = datetime.fromtimestamp(record.created, self.timezone).strftime(self.date_format)
        if not date_name or date_name in (".", "..") or any(char in date_name for char in ("/", "\\", ":")):
            raise ValueError(f"Unsafe rendered log date: {date_name}")
        return date_name

    def _handler_for(self, record):
        root = getattr(record, "pas_root", "")
        filename = getattr(record, "pas_filename", "")
        split_log_path(f"{root}/{filename}")
        raw = bool(getattr(record, "pas_raw", False))
        max_bytes = max(1024, int(getattr(record, "pas_max_bytes", 52_428_800)))
        backups = max(0, int(getattr(record, "pas_backups", 50)))
        date_name = self._date_for(record)
        base = self._base()
        key = (str(base), root, date_name if self.daily_folders else "", filename, raw, max_bytes, backups)
        current = self._handlers.get(key)
        if current:
            current[1] = time.monotonic()
            return current[0]
        folder = (base / root / date_name).resolve() if self.daily_folders else (base / root).resolve()
        approved_root = (base / root).resolve()
        if os.path.commonpath((str(folder), str(approved_root))) != str(approved_root):
            raise ValueError(f"Log destination escaped approved root: {folder}")
        folder.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            folder / filename,
            encoding="utf-8",
            maxBytes=max_bytes,
            backupCount=backups,
        )
        if raw:
            formatter = logging.Formatter("%(message)s")
        else:
            formatter = TimezoneFormatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                "%Y-%m-%d %H:%M:%S",
                self.timezone_name,
            )
        handler.setFormatter(formatter)
        self._handlers[key] = [handler, time.monotonic()]
        self._close_idle(exclude=key)
        return handler

    def _close_idle(self, exclude=None):
        now = time.monotonic()
        for key, (handler, last_used) in list(self._handlers.items()):
            if key != exclude and now - last_used >= self.idle_seconds:
                handler.close()
                self._handlers.pop(key, None)

    def emit(self, record):
        try:
            self._handler_for(record).emit(record)
        except Exception as exc:
            _stderr_warning(f"failed to write {getattr(record, 'pas_filename', '?')}: {exc}")

    def flush(self):
        for handler, _last_used in list(self._handlers.values()):
            try:
                handler.flush()
            except Exception:
                pass

    def close(self):
        self.acquire()
        try:
            for handler, _last_used in list(self._handlers.values()):
                try:
                    handler.flush()
                    handler.close()
                except Exception:
                    pass
            self._handlers.clear()
            super().close()
        finally:
            self.release()


class _LocalRoutingHandler(logging.Handler):
    def __init__(self, router, spec):
        super().__init__(logging.DEBUG)
        self.router = router
        self.spec = dict(spec)
        self._pas_managed = True

    def emit(self, record):
        for key, value in self.spec.items():
            setattr(record, key, value)
        self.router.handle(record)

    def flush(self):
        self.router.flush()


class DailyQueueHandler(logging.handlers.QueueHandler):
    def __init__(self, log_queue, spec, put_timeout=2.0):
        super().__init__(log_queue)
        self.spec = dict(spec)
        self.put_timeout = max(0.01, float(put_timeout))
        self._pas_managed = True

    def enqueue(self, record):
        self.queue.put(record, block=True, timeout=self.put_timeout)

    def emit(self, record):
        try:
            for key, value in self.spec.items():
                setattr(record, key, value)
            self.enqueue(self.prepare(record))
        except queue_module.Full:
            _stderr_warning(f"logging queue full; record dropped for {self.spec.get('pas_filename')}")
        except Exception as exc:
            _stderr_warning(f"failed to enqueue log record: {exc}")


def _router_for(timezone, date_format, idle_seconds, daily_folders):
    key = (str(timezone), str(date_format), float(idle_seconds), bool(daily_folders))
    with _local_lock:
        router = _local_routers.get(key)
        if router is None:
            router = DailyDirectoryRouter(
                timezone=timezone, date_format=date_format, idle_seconds=idle_seconds,
                daily_folders=daily_folders,
            )
            _local_routers[key] = router
        return router


def configure_logger(name, path, *, level=logging.INFO, max_bytes=52_428_800, backups=50,
                     raw=False, timezone="Asia/Kolkata", date_format="%d-%m-%Y", idle_seconds=3600,
                     daily_folders=True):
    root, filename = split_log_path(path)
    spec = {
        "pas_root": root,
        "pas_filename": filename,
        "pas_raw": bool(raw),
        "pas_max_bytes": int(max_bytes),
        "pas_backups": int(backups),
    }
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    logger._pas_log_spec = {
        "path": path, "level": level, "max_bytes": max_bytes, "backups": backups,
        "raw": raw, "timezone": timezone, "date_format": date_format, "idle_seconds": idle_seconds,
        "daily_folders": daily_folders,
    }
    for handler in list(logger.handlers):
        if getattr(handler, "_pas_managed", False):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
    if _worker_queue is not None:
        handler = DailyQueueHandler(_worker_queue, spec, _worker_put_timeout)
    else:
        handler = _LocalRoutingHandler(_router_for(timezone, date_format, idle_seconds, daily_folders), spec)
    logger.addHandler(handler)
    return logger


def install_worker_queue(log_queue, put_timeout=2.0):
    global _worker_queue, _worker_put_timeout
    _worker_queue = log_queue
    _worker_put_timeout = max(0.01, float(put_timeout))
    for logger in list(logging.Logger.manager.loggerDict.values()):
        if isinstance(logger, logging.Logger) and hasattr(logger, "_pas_log_spec"):
            configure_logger(logger.name, **logger._pas_log_spec)


class LoggingListener:
    def __init__(self, log_queue, *, base_dir=None, timezone="Asia/Kolkata", date_format="%d-%m-%Y", idle_seconds=3600,
                 daily_folders=True):
        self.queue = log_queue
        self.router = DailyDirectoryRouter(
            base_dir=base_dir, timezone=timezone, date_format=date_format, idle_seconds=idle_seconds,
            daily_folders=daily_folders,
        )
        self.thread = threading.Thread(target=self._run, name="daily-log-listener", daemon=True)
        self.failure = None

    def start(self):
        self.thread.start()
        return self

    def _run(self):
        try:
            while True:
                record = self.queue.get()
                if record is None:
                    break
                self.router.handle(record)
        except Exception as exc:
            self.failure = exc
            _stderr_warning(f"logging listener stopped unexpectedly: {exc}")
        finally:
            self.router.close()

    def stop(self, timeout=15):
        deadline = time.monotonic() + max(1.0, float(timeout))
        while True:
            try:
                self.queue.put(None, block=True, timeout=max(0.1, min(1.0, deadline - time.monotonic())))
                break
            except queue_module.Full:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Could not enqueue logging shutdown sentinel")
        self.thread.join(max(0.1, deadline - time.monotonic()))
        if self.thread.is_alive():
            raise TimeoutError("Logging listener did not stop within timeout")
        if self.failure:
            raise RuntimeError(f"Logging listener failed: {self.failure}")


def close_local_logging():
    with _local_lock:
        for router in _local_routers.values():
            router.close()
        _local_routers.clear()


atexit.register(close_local_logging)
