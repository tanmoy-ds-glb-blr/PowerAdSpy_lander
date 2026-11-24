"""Network-free subprocess fixture for IsolatedProbeRunner tests."""

import json
import os
import sys
import time


def main():
    for line in sys.stdin:
        command = json.loads(line)
        if command.get("shutdown"):
            return
        request_id = command.get("request_id")
        country = str(command.get("country_iso") or "us")
        if country == "slow":
            time.sleep(60)
        if country == "error":
            response = {
                "request_id": request_id,
                "available": False,
                "details": {},
                "reason": "fixture proxy down",
                "stage": "fixture_stage",
                "currently_unavailable": True,
                "observed_at": 1234.5,
                "country_iso": country,
                "pid": os.getpid(),
            }
        else:
            response = {
                "request_id": request_id,
                "available": True,
                "details": {
                    "ip": "203.0.113.58",
                    "country": country.upper(),
                    "pid": os.getpid(),
                },
                "reason": "healthy",
                "observed_at": time.time(),
                "pid": os.getpid(),
            }
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
