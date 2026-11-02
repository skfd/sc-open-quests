"""The polygon of an osm-extracts clip, and its regions' .poly files, from the cities counted on it.

  python tools/clip_polygon.py europe [--pad-km 2]

A clip (osm-extracts `clip NAME --polygon FILE`) is a planet extract kept current by the daily diffs
(DESIGN.md, "Current clips in osm-extracts"). Several regions of config/regions.json count one clip
(their "extract"), one region per time zone. Its polygon is every such city's bounding box padded by
--pad-km (2 km: the clipping test of 2026-10-24 gave counts equal to the whole extract), the boxes
unioned so no two outer rings overlap: config/<extract>.geojson. Each region's own boxes, unioned the
same way, go to its "poly" (config/<region>.poly, several sections), which the notes clip reads.

Rerun after adding a city; then `osm_extracts.py clip` (a new clip) or a recut (a changed polygon).
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from shapely.geometry import box, mapping
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import run  # noqa: E402


def padded_box(w, s, e, n, km):
    d_lat = km * 1000 / 111_320.0
    d_lon = km * 1000 / (111_320.0 * math.cos(math.radians(max(abs(s), abs(n)))))
    return box(w - d_lon, s - d_lat, e + d_lon, n + d_lat)


def union_of(cities, km):
    return unary_union([padded_box(*run.city_bbox(ROOT / c["boundary"], c["relation"]), km) for c in cities])


def parts(geom):
    return list(getattr(geom, "geoms", [geom]))


def write_poly(path: Path, name: str, geom) -> None:
    lines = [name]
    for i, g in enumerate(parts(geom), 1):
        lines.append(str(i))
        lines += [f"   {x:.7f}   {y:.7f}" for x, y in g.exterior.coords]
        lines.append("END")
        for j, hole in enumerate(g.interiors, 1):
            lines.append(f"!{i}.{j}")
            lines += [f"   {x:.7f}   {y:.7f}" for x, y in hole.coords]
            lines.append("END")
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("extract")
    ap.add_argument("--pad-km", type=float, default=2.0)
    a = ap.parse_args(argv)
    regs = [r for r in run.regions() if run.region_extract(r) == a.extract]
    if not regs:
        raise SystemExit(f"no region in {run.REGIONS_CONFIG.name} has extract {a.extract}")
    cities = run.read_json(run.CITIES_CONFIG)["cities"]
    everything = []
    for r in regs:
        mine = [c for c in cities if c["region"] == r["id"]]
        if not mine:
            raise SystemExit(f"region {r['id']} has no city")
        g = union_of(mine, a.pad_km)
        write_poly(ROOT / r["poly"], r["id"], g)
        everything += mine
        print(f"{r['poly']}: {len(mine)} cities, {len(parts(g))} part(s)")
    g = union_of(everything, a.pad_km)
    out = ROOT / "config" / f"{a.extract}.geojson"
    run.write_json(out, {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"clip": a.extract, "pad_km": a.pad_km, "cities": len(everything)},
         "geometry": mapping(g)}]})
    print(f"{out.relative_to(ROOT)}: {len(everything)} cities, {len(parts(g))} part(s), "
          f"{g.area:.2f} square degrees")
    return 0


if __name__ == "__main__":
    sys.exit(main())
