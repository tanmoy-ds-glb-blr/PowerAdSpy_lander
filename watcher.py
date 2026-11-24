import psutil
import subprocess
import time
import os
import logging

# CONFIGURATION
SCRIPT_KEYWORD = "new_lander.py"  # Use part of your script name here
PROGRAM_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "start_process.sh")
CHECK_INTERVAL = 10  # seconds

# LOGGING SETUP
logging.basicConfig(
    filename="daemon_log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def is_script_running(keyword):
    """Check if any python process is running with the given script name"""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            name = (proc.info.get('name') or "").lower()
            if 'python' in name:
                cmdline = ' '.join(proc.info.get('cmdline') or [])
                if keyword in cmdline:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            continue
    return False

def start_program(path):
    try:
        logging.info(f"[Watcher] Trying to run: {path}")
        if os.name == "nt":
            subprocess.Popen([path], shell=True)
        else:
            subprocess.Popen(["bash", path])
        logging.info(f"[Watcher] Successfully launched: {path}")
    except Exception as e:
        logging.warning(f"[Watcher] Failed to launch {path}: {e}")

def daemon_loop():
    logging.info(f"Daemon started to monitor script containing: {SCRIPT_KEYWORD}")
    while True:
        if not is_script_running(SCRIPT_KEYWORD):
            logging.warning(f"Script not running. Restarting...")
            start_program(PROGRAM_PATH)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        daemon_loop()
    except KeyboardInterrupt:
        logging.info("Daemon stopped manually.")
    except Exception as e:
        logging.exception("Unexpected error:")
