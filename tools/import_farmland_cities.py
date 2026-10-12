"""One-off import of Ontario municipalities from the sibling ontario-farmland project.

Writes config/cities.json (what to count) and data/boundaries/<relation>.json (Overpass `out geom`
element for each city's boundary relation). Rerun to refresh; adding a city by hand means adding a
config entry and a boundary file with the same shape.
"""
import json, re, sys
from pathlib import Path

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "../ontario-farmland")
ROOT = Path(__file__).resolve().parent.parent

tags_by_rel = json.loads((SRC / "cities.json").read_text(encoding="utf-8"))
areas = json.loads((SRC / "areas.json").read_text(encoding="utf-8"))
geom = json.loads((SRC / "cache/boundaries.json").read_text(encoding="utf-8"))
rels = {str(e["id"]): e for e in geom["elements"] if e["type"] == "relation"}

def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

cities = []
for rel_id, tags in sorted(tags_by_rel.items(), key=lambda kv: kv[1]["name"]):
    if rel_id not in rels:
        print("no geometry for", rel_id, tags["name"]); continue
    name = tags["name"]
    cities.append({
        "id": slug(name),
        "name": name,
        "relation": int(rel_id),
        "adminLevel": int(tags.get("admin_level", 0)),
        "countryCodes": ["CA", "CA-ON"],
        "timeZone": "America/Toronto",
        "population": int(tags["population"]) if tags.get("population", "").isdigit() else None,
        "landAreaKm2": areas.get("osm", {}).get(name),
        "boundary": f"data/boundaries/{rel_id}.json",
    })
    (ROOT / "data/boundaries" / f"{rel_id}.json").write_text(json.dumps(rels[rel_id]), encoding="utf-8")

(ROOT / "config/cities.json").write_text(json.dumps({"cities": cities}, indent=2), encoding="utf-8")
print(len(cities), "cities")
