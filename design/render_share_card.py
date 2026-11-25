"""Draw design/project-card.svg into docs/img/share-card.png (1200x630, the og:image of every link), and write its date
and its words into docs/index.html (`?v=`, so that networks fetch it again, and og:image:alt).

The card carries a date and a total, so it goes stale: redraw it with

    python design/project_card.py && python design/render_share_card.py

Needs Pillow and Edge (headless; its profile is a temporary folder). In a gap of the world loop only.
"""
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "design" / "project-card.svg"
LARGE = ROOT / "design" / "project-card.png"
TARGET = ROOT / "docs" / "img" / "share-card.png"
PAGE = ROOT / "docs" / "index.html"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def main():
    if (ROOT.parent / "sc-open-quests" / ".scratch" / "planet-cut" / "RUNNING").exists():
        raise SystemExit("the world loop is running: renders wait for a gap")
    svg = SOURCE.read_text(encoding="utf-8")
    found = re.search(r">(\d+)M</text>.*?>around the world on (\d+ \w+ \d{4})<", svg, re.S)
    if not found:
        raise SystemExit("no headline and date in the card")
    number, when = found.groups()
    day = datetime.strptime(when, "%d %b %Y").date()
    LARGE.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={profile}",
                        "--window-size=1200,630", "--force-device-scale-factor=2", "--hide-scrollbars",
                        f"--screenshot={LARGE}", SOURCE.as_uri()], timeout=60, check=True)
        with Image.open(LARGE) as im:
            if im.size != (2400, 1260):
                raise SystemExit(f"drawn at {im.size}")
            im.convert("RGB").resize((1200, 630), Image.LANCZOS).save(TARGET, optimize=True)
    html = PAGE.read_text(encoding="utf-8")
    html, a = re.subn(r"(img/share-card\.png\?v=)[^\"]*", rf"\g<1>{day}", html)
    html, b = re.subn(r'(<meta property="og:image:alt" content=")[^"]*',
                      rf"\g<1>{number} million open StreetComplete quests around the world on {when}, and the six "
                      "largest quest types.", html)
    if (a, b) != (1, 1):
        raise SystemExit(f"og:image found {a} times, og:image:alt {b}")
    PAGE.write_text(html, encoding="utf-8", newline="\n")
    print(TARGET, TARGET.stat().st_size, day)


if __name__ == "__main__":
    main()
