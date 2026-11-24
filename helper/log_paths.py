"""Resolve current or historical files in the daily log directory layout."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def today_folder(timezone="Asia/Kolkata", date_format="%d-%m-%Y"):
    return datetime.now(ZoneInfo(timezone)).strftime(date_format)


def dated_log_path(root, filename, date=None, timezone="Asia/Kolkata", date_format="%d-%m-%Y"):
    return Path(root) / (date or today_folder(timezone, date_format)) / filename


def resolve_log_path(root, filename, date=None, timezone="Asia/Kolkata", date_format="%d-%m-%Y"):
    requested = dated_log_path(root, filename, date, timezone, date_format)
    if requested.is_file() or date:
        return requested
    base = Path(root)
    candidates = sorted(
        (path for path in base.glob(f"*/{filename}") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]
    legacy = base / filename
    return legacy if legacy.is_file() else requested
