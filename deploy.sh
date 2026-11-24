#!/bin/bash
set -e

echo "=== Step 1: System Dependencies ==="
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv xvfb wget unzip curl jq

echo "=== Step 2: Install Google Chrome ==="
if ! command -v google-chrome &>/dev/null; then
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo apt install -y ./google-chrome-stable_current_amd64.deb
    rm -f google-chrome-stable_current_amd64.deb
fi
echo "Chrome version: $(google-chrome --version)"

echo "=== Step 3: Create Virtual Environment ==="
cd "$(dirname "$0")"
python3 -m venv venv
source venv/bin/activate

echo "=== Step 4: Install Python Packages ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Step 5: Create Required Directories ==="
mkdir -p logs er_logs images zip getApi_data getApi_data_dev setup helper/luminati_new

echo "=== Step 6: Make Scripts Executable ==="
chmod +x start_process.sh stop_process.sh start_instagram.sh stop_instagram.sh deploy.sh

echo ""
echo "=== All Done! ==="
echo ""
echo "Edit config.yaml to configure your network and API endpoints."
echo ""
echo "To start:    ./start_process.sh"
echo "To stop:     ./stop_process.sh"
echo "Watch logs:  tail -f output.log"
echo "Kill old chrome instances: python3 kill_old_chrome.py"
