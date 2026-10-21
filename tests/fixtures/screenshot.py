"""Screenshot the site rendered from the fixture data (needs `pip install playwright`).

    python -m http.server 8765 --bind 127.0.0.1      # from the repo root, in another shell
    python tests/fixtures/screenshot.py [data-dir] [out.png] [query]
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

data = sys.argv[1] if len(sys.argv) > 1 else "../tests/fixtures/data"
out = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).with_name("screenshot.png"))
query = sys.argv[3] if len(sys.argv) > 3 else "city=toronto&pin=AddBusStopShelter,AddBenchBackrest"
url = f"http://127.0.0.1:8765/docs/?data={data}&{query}"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1200, "height": 1500}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(500)
    page.screenshot(path=str(out), full_page=False)
    browser.close()
print(f"wrote {out}")
for e in errors:
    print("page error:", e)
