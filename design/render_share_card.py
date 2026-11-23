"""Render design/share-card.html into docs/img/share-card.png, 1200x630 exactly.

Needs Playwright's Chromium (`pip install playwright`, `playwright install chromium`). Run it by hand when
the card's design changes, and raise `?v=` on og:image in docs/index.html so networks fetch it again.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "design" / "share-card.html"
TARGET = ROOT / "docs" / "img" / "share-card.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
    page.goto(SOURCE.as_uri())
    page.wait_for_load_state("networkidle")
    missing = page.evaluate("[...document.images].filter((i) => !i.naturalWidth).map((i) => i.src)")
    if missing:
        raise SystemExit(f"images that did not load: {missing}")
    page.screenshot(path=str(TARGET), clip={"x": 0, "y": 0, "width": 1200, "height": 630})
    browser.close()
print(f"{TARGET.relative_to(ROOT)}: {TARGET.stat().st_size} bytes")
