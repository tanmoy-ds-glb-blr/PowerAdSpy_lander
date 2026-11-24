"""Local, network-free smoke test for new_lander's configured log streams."""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import new_lander
from helper import daily_logging
from helper.log_paths import today_folder


def main():
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as folder:
        try:
            os.chdir(folder)
            streams = [
                ("smoke_payload", "logs/payloads.log", False),
                ("smoke_success", "logs/successful_payloads.json", True),
                ("smoke_unsuccessful", "logs/unsuccessful_ads.json", True),
                ("smoke_proxy", "logs/proxy.log", True),
                ("smoke_proxy_health", "logs/proxy_health.log", True),
                ("smoke_worker", "logs/1_chatgpt_lander_logger.log", False),
                ("smoke_error", "er_logs/1_chatgpt_error_logger.log", False),
            ]
            for name, path, raw in streams:
                logger = new_lander.setup_logger(name, path, level=logging.INFO, raw=raw)
                logger.info(json.dumps({"stream": name}) if raw else f"smoke:{name}")
            daily_logging.close_local_logging()
            date_name = today_folder(
                str(new_lander.config.get_default("LOG_TIMEZONE") or "Asia/Kolkata"),
                str(new_lander.config.get_default("LOG_DATE_FORMAT") or "%Y-%m-%d"),
            )
            expected = [Path(root, date_name, Path(path).name) for _name, path, _raw in streams for root in [path.split("/", 1)[0]]]
            missing = [str(path) for path in expected if not path.is_file() or path.stat().st_size == 0]
            flat_files = [str(Path(path)) for _name, path, _raw in streams if Path(path).is_file()]
            if missing or flat_files:
                raise AssertionError({"missing": missing, "unexpected_flat_files": flat_files})
            for _name, path, raw in streams:
                if raw:
                    target = Path(path.split("/", 1)[0], date_name, Path(path).name)
                    json.loads(target.read_text(encoding="utf-8").strip())
            print(json.dumps({"status": "PASS", "date_folder": date_name, "files": [str(path) for path in expected]}))
        finally:
            os.chdir(original)


if __name__ == "__main__":
    main()
