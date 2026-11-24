import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import os
from PIL import Image
import numpy as np

def trim_trailing_blank_void(im, min_void_px=300, padding_px=100):
    w, h = im.size
    if h <= min_void_px:
        return im
    
    # Convert image to numpy array (RGB)
    rgb = np.array(im.convert("RGB"))
    
    # Sample background color from the very bottom row (median across row)
    bottom_row = rgb[-1, :, :]
    bg_color = np.median(bottom_row, axis=0) # [R, G, B]
    
    # Also check bottom-left and bottom-right corner pixels
    corners = np.array([rgb[-1, 0], rgb[-1, -1], rgb[-1, w // 2]])
    corner_std = np.std(corners, axis=0)
    
    # If the bottom edge itself has high variance, it's not a uniform background void
    if np.max(corner_std) > 15:
        return im
    
    # Calculate color difference of each pixel to bg_color
    diff = np.max(np.abs(rgb.astype(np.int16) - bg_color.astype(np.int16)), axis=2) # (H, W)
    
    # A row is considered empty if at least 99.5% of pixels are within color tolerance of bg_color
    tolerance = 8
    row_empty = np.mean(diff <= tolerance, axis=1) >= 0.995
    
    # Find the last row from the bottom that is NOT empty
    non_empty_rows = np.where(~row_empty)[0]
    if len(non_empty_rows) == 0:
        return im # Entire image is empty, don't crop
    
    last_content_y = non_empty_rows[-1]
    void_height = h - 1 - last_content_y
    
    if void_height >= min_void_px:
        new_h = min(h, last_content_y + padding_px)
        return im.crop((0, 0, w, new_h))
    
    return im

# Test on all saved samples
samples = [
    "sample_281981.jpg", # Spotify
    "sample_281944.jpg", # Pinterest
    "sample_43138.jpg",  # Wordsmith
    "sample_281900.jpg", # Sparkling Ice
    "sample_281891.jpg", # MyBobs
]

for s in samples:
    p = os.path.join("images/saved_samples", s)
    if os.path.isfile(p):
        im = Image.open(p)
        trimmed = trim_trailing_blank_void(im)
        print(f"{s:<20}: orig={im.size} -> trimmed={trimmed.size} (diff={im.size[1] - trimmed.size[1]}px)")
