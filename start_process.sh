#!/bin/bash
cd "$(dirname "$0")"

# Activate venv if it exists (for standard Linux VM environments)
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Ensure virtual display Xvfb is running on :99 for headless browser
export DISPLAY=:99
if command -v Xvfb >/dev/null 2>&1 && ! pgrep -f "Xvfb :99" >/dev/null; then
    echo "Starting Xvfb on :99..."
    Xvfb :99 -screen 0 1280x800x24 -ac &
    sleep 1
fi

nohup python3 -u new_lander.py > output.log 2>&1 &
echo "Started new_lander.py with PID $!"
