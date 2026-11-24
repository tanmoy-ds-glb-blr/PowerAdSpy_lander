import sys
sys.path.append('.')
import time
from helper import init

url = "https://wego.here.com/r/mylocation/e-eyJuYW1lIjoiIiwiYWRkcmVzcyI6IjI4MCBUb25nIFJvYWQsIExlZWRzLCBFbmdsYW5kLCBVbml0ZWQgS2luZ2RvbSIsImxhdGl0dWRlIjo1My43OTM2LCJsb25naXR1ZGUiOi0xLjU5NjcxfQ==?ref=facebook&link=addresses&fb_locale=en_GB"

def test():
    page, r_session = init.init_dc("in")
    try:
        tiles_loaded = []
        page.on("response", lambda res: tiles_loaded.append((time.time(), res.url)) if "vectortiles" in res.url or "tile" in res.url or "harp" in res.url else None)
        
        t0 = time.time()
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        print(f"domcontentloaded at {time.time() - t0:.2f}s")
        
        for sec in range(1, 30):
            time.sleep(1.0)
            elapsed = time.time() - t0
            tile_count = len(tiles_loaded)
            print(f"Elapsed {elapsed:.1f}s | Tiles fetched so far: {tile_count}")
            if tile_count > 10:
                # Save screenshot when tiles have loaded!
                page.screenshot(path=f"scratch/tiles_{int(elapsed)}s.jpg")
                print(f"Saved tiles_{int(elapsed)}s.jpg with {tile_count} tiles!")
                break

    finally:
        init.close_browser(page)

if __name__ == "__main__":
    test()
