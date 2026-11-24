import sys
import psutil
import os
import subprocess

_SCRIPT_NAME = "new_lander.py"
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def is_running(script):
    for proc in psutil.process_iter(['name', 'cmdline', 'pid']):
        try:
            name = (proc.info.get('name') or "").lower()
            if "python" in name:
                cmdline = proc.info.get('cmdline') or []
                if len(cmdline) > 1 and any(script in arg for arg in cmdline[1:]) and proc.pid != os.getpid():
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            pass
    return False


if not is_running(_SCRIPT_NAME):
    script_path = os.path.join(_BASE_DIR, _SCRIPT_NAME)
    if os.name == "nt":
        venv_python = os.path.join(_BASE_DIR, "venv", "Scripts", "python.exe")
        python_bin = venv_python if os.path.isfile(venv_python) else sys.executable
    else:
        venv_python = os.path.join(_BASE_DIR, "venv", "bin", "python3")
        python_bin = venv_python if os.path.isfile(venv_python) else sys.executable

    subprocess.Popen([python_bin, script_path], cwd=_BASE_DIR)
    print(f"[restart] Launched {_SCRIPT_NAME} with {python_bin}")
else:
    print(f"[restart] {_SCRIPT_NAME} is already running")
