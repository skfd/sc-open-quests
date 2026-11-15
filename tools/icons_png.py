"""Draw docs/icons/*.svg as PNGs in docs/icons/png/, for clients that can't show SVG.

    python tools/icons_png.py

The Open Quests iPhone widget runs in Scriptable, which shows PNG and JPEG but not SVG
(sc-open-quests-widget, ios/open-quests.js). Each icon becomes a 96 px square with a transparent
background: 32 pt at the iPhone's 3x. Rerun after tools/sc_assets.py, on every SC version bump; it
rewrites every PNG and deletes those whose SVG is gone.

Needs Chrome or Edge (headless draws the SVGs, as a browser would) and Pillow (cuts the sheet up).
"""
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "docs" / "icons"
OUT = ICONS / "png"
SIZE = 96
GAP = 8  # between cells, so antialiasing never bleeds into a neighbour
COLUMNS = 16
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/opt/pw-browsers/chromium",
    "google-chrome",
    "chromium",
]


def browser() -> str:
    for b in BROWSERS:
        if Path(b).exists() or shutil.which(b):
            return b
    sys.exit("icons_png: no Chrome, Edge or Chromium found")


def main() -> None:
    svgs = sorted(ICONS.glob("*.svg"))
    if not svgs:
        sys.exit(f"icons_png: no SVGs in {ICONS}")
    cell = SIZE + GAP
    rows = math.ceil(len(svgs) / COLUMNS)
    width, height = COLUMNS * cell, rows * cell
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "sheet.html"
        shot = Path(tmp) / "sheet.png"
        imgs = "".join(
            f'<img src="{svg.as_uri()}" style="left:{(i % COLUMNS) * cell}px;top:{(i // COLUMNS) * cell}px">'
            for i, svg in enumerate(svgs)
        )
        page.write_text(
            "<!doctype html><style>html,body{margin:0;background:transparent}"
            f"img{{position:absolute;width:{SIZE}px;height:{SIZE}px}}</style>{imgs}",
            "utf-8",
        )
        subprocess.run(
            [browser(), "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
             "--default-background-color=00000000", "--virtual-time-budget=10000",
             f"--window-size={width},{height}", f"--screenshot={shot}", page.as_uri()],
            check=True, capture_output=True,
        )
        sheet = Image.open(shot).convert("RGBA")
        if sheet.size != (width, height):
            sys.exit(f"icons_png: the browser drew {sheet.size}, expected {(width, height)}")
        OUT.mkdir(exist_ok=True)
        empty = []
        for i, svg in enumerate(svgs):
            x, y = (i % COLUMNS) * cell, (i // COLUMNS) * cell
            icon = sheet.crop((x, y, x + SIZE, y + SIZE))
            if icon.getbbox() is None:
                empty.append(svg.name)  # nothing drawn: never publish a blank icon
                continue
            icon.save(OUT / f"{svg.stem}.png", optimize=True)
    wanted = {f"{s.stem}.png" for s in svgs}
    for old in OUT.glob("*.png"):
        if old.name not in wanted:
            old.unlink()
    if empty:
        sys.exit(f"icons_png: drew nothing for {', '.join(empty)}")
    size = sum(p.stat().st_size for p in OUT.glob("*.png"))
    print(f"{len(svgs)} icons -> {OUT} ({size // 1024} KB)")


if __name__ == "__main__":
    main()
