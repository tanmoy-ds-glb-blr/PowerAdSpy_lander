import psutil
import time

current_time = time.time()
print(current_time)
for proc in psutil.process_iter(['name', 'create_time', 'pid']):
    try:
        proc_name = (proc.info.get('name') or "").lower()
        if proc_name in ("chrome", "chrome.exe", "google-chrome", "google-chrome-stable", "chromium", "chromium.exe", "chromium-browser"):
            create_time = proc.info.get('create_time') or proc.create_time()
            if create_time < (current_time - 3600):
                processID = proc.pid
                print(proc_name, ' ::: ', processID, ' ::: ', create_time)
                proc.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, Exception):
        pass