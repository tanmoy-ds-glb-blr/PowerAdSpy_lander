#!/bin/bash

# Stop only processes started from this configured lander folder.
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"

find_lander_pids() {
    for proc in /proc/[0-9]*; do
        process_dir="$(readlink -f "$proc/cwd" 2>/dev/null)" || continue
        [ "$process_dir" = "$SCRIPT_DIR" ] || continue

        command_line="$(tr '\0' ' ' < "$proc/cmdline" 2>/dev/null)"
        case "$command_line" in
            *new_lander.py*|*quick_run_sample_ads.py*|*test_sample_ads.py*) echo "${proc##*/}" ;;
        esac
    done
}

pids="$(find_lander_pids)"
if [ -z "$pids" ]; then
    echo "No lander or sample runner processes are running."
else
    echo "Stopping lander / sample runner processes (PIDs: $pids)..."
    kill -TERM $pids 2>/dev/null

    for _ in 1 2 3 4 5 6 7 8 9 10; do
        sleep 1
        remaining="$(find_lander_pids)"
        [ -z "$remaining" ] && break
    done

    remaining="$(find_lander_pids)"
    if [ -n "$remaining" ]; then
        kill -KILL $remaining 2>/dev/null
    fi
fi

# Clean up orphaned Chrome instances
pkill -f "chrome" 2>/dev/null || true
pkill -f "chromium" 2>/dev/null || true
if [ -f "kill_old_chrome.py" ]; then
    python3 kill_old_chrome.py 2>/dev/null || true
fi

echo "All lander and sample runner processes stopped."
