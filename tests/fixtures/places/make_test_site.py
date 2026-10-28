"""Build a throwaway copy of the site with the place fixtures in it, to try place browsing locally.

    python tests/fixtures/places/make_test_site.py [out-dir]     # default: %TEMP%/scoq-site
    python -m http.server 8765 --bind 127.0.0.1 --directory <out-dir>
    open http://127.0.0.1:8765/docs/?view=places

Copies docs/ to <out-dir>/docs, the shards from places/ to docs/places/, parts/toronto.json to
docs/data/parts/, and writes `cities.toronto.parts` (data/toronto-parts.json) into the copy of
Ontario's newest snapshot. Nothing is written under the repo's docs/.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "scoq-site"
site = out / "docs"
if site.exists():
    shutil.rmtree(site)
shutil.copytree(ROOT / "docs", site)
shutil.copytree(HERE / "places", site / "places")
shutil.copytree(HERE / "data/parts", site / "data/parts")
cities = json.load(open(site / "data/cities.json", encoding="utf-8"))["cities"]
tor = next(c for c in cities if c["id"] == "toronto")
snap = site / f"data/{tor['region']}/snapshots/{tor['asOfDate']}.json"
s = json.load(open(snap, encoding="utf-8"))
s["cities"]["toronto"]["parts"] = json.load(open(HERE / "data/toronto-parts.json", encoding="utf-8"))
with open(snap, "w", encoding="utf-8") as fh:
    json.dump(s, fh, separators=(",", ":"))
print(site)
