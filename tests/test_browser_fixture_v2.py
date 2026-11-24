import os
import tempfile
import unittest
from io import BytesIO

from PIL import Image

from helper.capture import capture_page
from helper.page_snapshot import capture_snapshot
from helper.readiness import wait_for_ready
from helper.init import _resolve_chrome_paths


class BrowserPipelineFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
            cls._playwright = sync_playwright().start()
            executable = _resolve_chrome_paths()
            kwargs = {"headless": True}
            if executable:
                kwargs["executable_path"] = executable
            cls._browser = cls._playwright.chromium.launch(**kwargs)
        except Exception as exc:
            raise unittest.SkipTest(f"Playwright browser unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "_browser"):
            cls._browser.close()
        if hasattr(cls, "_playwright"):
            cls._playwright.stop()

    def test_delayed_spa_frame_and_capture(self):
        page = self._browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_content("""
          <!doctype html><html><body style="margin:0">
          <main id="app"></main>
          <script>
          setTimeout(() => {
            document.querySelector('#app').innerHTML = `
              <h1>Delayed application is ready</h1>
              <iframe id="creative" title="creative" srcdoc="<body><div id='frame-root'></div></body>" style="width:600px;height:180px"></iframe>
              <section style="height:2200px;background:linear-gradient(#fff,#579)">Long finite content</section>`;
            const frame=document.querySelector('#creative');
            frame.addEventListener('load',()=>setTimeout(()=>frame.contentDocument.querySelector('#frame-root').textContent='Frame creative ready',700));
          }, 500);
          </script></body></html>
        """)
        ready = wait_for_ready(page, timeout_seconds=8, stable_samples=2)
        self.assertIn(ready.state, ("ready", "degraded"))
        self.assertGreater(ready.text_length, 10)
        self.assertGreaterEqual(len(ready.frames), 1)
        snapshot = capture_snapshot(page, ready.frames)
        self.assertIn("Delayed application is ready", snapshot.text)
        self.assertIn("Frame creative ready", snapshot.frame_text)
        self.assertEqual(len(snapshot.frame_documents), 1)
        self.assertTrue(snapshot.frame_documents[0]["saved"])
        self.assertIn("Frame creative ready", snapshot.frame_documents[0]["html"])
        old_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as folder:
                try:
                    os.chdir(folder)
                    result = capture_page(page, "fixture", "run")
                    self.assertEqual(result.state, "full")
                    self.assertLessEqual(result.final_bytes, 1048576)
                    self.assertTrue(os.path.isfile(result.image_path))
                finally:
                    os.chdir(old_cwd)
        finally:
            os.chdir(old_cwd)
            page.close()

    def test_primary_internal_scroller_is_bounded_and_expanded(self):
        page = self._browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_content("""
          <style>html,body{margin:0;height:100%;overflow:hidden}#app{height:100%;overflow-y:auto}</style>
          <div id="app"><h1>Top</h1><div style="height:2300px;background:linear-gradient(#fee,#eef)"></div><h2>Bottom marker</h2></div>
        """)
        ready = wait_for_ready(page, timeout_seconds=5, stable_samples=1)
        self.assertGreater(ready.text_length, 0)
        old_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as folder:
                try:
                    os.chdir(folder)
                    result = capture_page(page, "inner", "run")
                    self.assertIn("expanded_primary_scroller", result.mutation_journal)
                    self.assertGreater(result.height, 1500)
                    self.assertLessEqual(result.final_bytes, 1048576)
                finally:
                    os.chdir(old_cwd)
        finally:
            page.close()

    def test_infinite_growth_stops_at_capture_bound(self):
        page = self._browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_content("""
          <body><h1>Infinite fixture</h1><div id="feed"></div><script>
          const feed=document.querySelector('#feed');
          function add(){for(let i=0;i<5;i++){let d=document.createElement('div');d.style.height='500px';d.textContent='item '+feed.children.length;feed.appendChild(d)}}
          add(); add(); window.addEventListener('scroll',()=>{if(scrollY+innerHeight>document.body.scrollHeight-300)add()});
          </script></body>
        """)
        old_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as folder:
                try:
                    os.chdir(folder)
                    class Limits:
                        def get_default(self, key):
                            return {"CAPTURE_MAX_HEIGHT": 3000, "CAPTURE_MAX_SCROLL_STEPS": 5, "CAPTURE_MAX_SCROLL_SECONDS": 5}.get(key)
                    result = capture_page(page, "infinite", "run", config=Limits())
                    self.assertEqual(result.state, "partial")
                    self.assertTrue(result.truncated)
                    self.assertLessEqual(result.height, 3000)
                    self.assertGreater(result.height, 1000)
                finally:
                    os.chdir(old_cwd)
        finally:
            page.close()

    def test_segmented_capture_fallback(self):
        page = self._browser.new_page(viewport={"width": 1000, "height": 500})
        page.set_content("""
          <body style="margin:0"><h1>Segment fallback fixture</h1>
          <div style="height:1400px;background:linear-gradient(#fff,#369)"></div></body>
        """)

        class NativeFailureWrapper:
            def __init__(self, wrapped):
                self.wrapped = wrapped
            def __getattr__(self, name):
                return getattr(self.wrapped, name)
            def screenshot(self, **kwargs):
                if kwargs.get("full_page"):
                    raise RuntimeError("injected native full-page failure")
                return self.wrapped.screenshot(**kwargs)

        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                result = capture_page(NativeFailureWrapper(page), "segments", "run")
                self.assertEqual(result.mode, "segmented_fallback")
                self.assertEqual(result.state, "full")
                self.assertTrue(os.path.isfile(result.image_path))
                self.assertLessEqual(result.final_bytes, 1048576)
            finally:
                os.chdir(old_cwd)
        page.close()

    def test_blank_native_capture_retries_with_segments(self):
        page = self._browser.new_page(viewport={"width": 1000, "height": 500})
        page.set_content("""
          <body style="margin:0"><h1>Visual retry fixture</h1>
          <p>This page intentionally contains enough meaningful text for blank screenshot validation.</p>
          <div style="height:900px;background:linear-gradient(#fff,#933)"></div></body>
        """)

        class BlankNativeWrapper:
            def __init__(self, wrapped):
                self.wrapped = wrapped
            def __getattr__(self, name):
                return getattr(self.wrapped, name)
            def screenshot(self, **kwargs):
                if kwargs.get("full_page"):
                    measure = self.wrapped.evaluate("() => ({w:document.documentElement.scrollWidth,h:document.documentElement.scrollHeight})")
                    image = Image.new("RGB", (measure["w"], measure["h"]), "white")
                    output = BytesIO()
                    image.save(output, "PNG")
                    return output.getvalue()
                return self.wrapped.screenshot(**kwargs)

        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                result = capture_page(BlankNativeWrapper(page), "visual-retry", "run")
                self.assertEqual(result.mode, "segmented_visual_retry")
                self.assertEqual(result.visual_scores["dom_rich_but_blank"], 0.0)
            finally:
                os.chdir(old_cwd)
        page.close()


if __name__ == "__main__":
    unittest.main()
