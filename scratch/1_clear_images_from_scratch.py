"""
Utility script to clear all generated test/debug images from the scratch/ folder.

Usage:
    python scratch/1_clear_images_from_scratch.py
"""

import os
import glob

IMAGE_EXTENSIONS = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.gif")

def clear_scratch_images():
    scratch_dir = os.path.dirname(os.path.abspath(__file__))
    removed_count = 0
    total_bytes = 0

    print(f"Scanning for images in: {scratch_dir}")

    for ext in IMAGE_EXTENSIONS:
        pattern = os.path.join(scratch_dir, ext)
        for file_path in glob.glob(pattern):
            try:
                size = os.path.getsize(file_path)
                os.remove(file_path)
                removed_count += 1
                total_bytes += size
                print(f"  [DELETED] {os.path.basename(file_path)} ({size / 1024:.1f} KB)")
            except Exception as e:
                print(f"  [ERROR] Could not delete {os.path.basename(file_path)}: {e}")

    mb_freed = total_bytes / (1024 * 1024)
    print(f"\nDone! Cleared {removed_count} images ({mb_freed:.2f} MB freed).")

if __name__ == "__main__":
    clear_scratch_images()
