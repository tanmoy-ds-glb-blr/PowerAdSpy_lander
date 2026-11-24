import os
import shutil
import tempfile


def delete(filepath):
    if not os.path.isdir(filepath):
        return
    for myfile in os.listdir(filepath):
        try:
            del_path = os.path.join(filepath, myfile)
            if os.path.isdir(del_path):
                shutil.rmtree(del_path)
            elif os.path.isfile(del_path):
                os.remove(del_path)
        except OSError as e:
            print("Error: %s - %s." % (e.filename, e.strerror))


def delete_chrome_temps(filepath):
    if not os.path.isdir(filepath):
        return
    for myfile in os.listdir(filepath):
        if any(k in str(myfile) for k in ("scoped_dir", "chrome_", "ChromiumTemp", ".com.google.Chrome")):
            try:
                del_path = os.path.join(filepath, myfile)
                if os.path.isdir(del_path):
                    shutil.rmtree(del_path)
                elif os.path.isfile(del_path):
                    os.remove(del_path)
            except OSError as e:
                print("Error: %s - %s." % (e.filename, e.strerror))


# Clean system temp directory (Linux: /tmp)
tmp = tempfile.gettempdir()
delete_chrome_temps(tmp)
delete_chrome_temps("/tmp")

print(f"[temp_del] Cleaned Chrome temp files from {tmp}")
