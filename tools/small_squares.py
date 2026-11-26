"""Small squares: the squares we leave out of the name layer and the parts registry (owner, 2026-11-25).

    <overture venv>/python tools/small_squares.py build [--src data/overture/world] [--out config/small-squares.json]
    python tools/small_squares.py prune      drop every left-out place (these squares and config/dropped-places.json's
                                             twins, run.left_out_places) from config/parts/*.json, by GERS id

A square is a microhood whose `local_type` is "square" in Overture's division.parquet (OSM place=square). It is left out
when its outline is under MAX_M2 and other places of a city's size or smaller cover it: a neighbourhood, macrohood,
borough, another microhood, a locality or a localadmin, whose outlines together hold at least COVER of its area. A square
covered only by a county or larger, or by nothing, stays, and so does a square another place calls its parent. Counts are not
touched: the squares are still counted, only not listed.

Run `build` again at each Overture release (it reads division.parquet and division_area_outlines.parquet, about 6 GB, in
one pass for the squares and one for the places around them, under a 1.5 GB DuckDB cap). The list is by GERS id, so it
needs no change when our place ids do. Areas are on the WGS84 ellipsoid (cylindrical equal-area), within 0.03% of the
geodesic area. The input is untrusted data: it is only read.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "config" / "small-squares.json"
PARTS = ROOT / "config" / "parts"
MAX_M2 = 10000
COVER = 0.95
COVERING = ("neighborhood", "macrohood", "borough", "microhood", "locality", "localadmin")

A = 6378137.0
F = 1 / 298.257223563
E2 = F * (2 - F)
E = math.sqrt(E2)


def _cea(xy):
    """lon/lat degrees -> metres on the ellipsoid's cylindrical equal-area projection (authalic latitude)"""
    import numpy as np
    s = np.sin(np.radians(xy[:, 1]))
    q = (1 - E2) * (s / (1 - E2 * s * s) - 1 / (2 * E) * np.log((1 - E * s) / (1 + E * s)))
    return np.column_stack([A * np.radians(xy[:, 0]), A * q / 2])


def area_m2(geoms):
    """areas in square metres of shapely geometries in lon/lat"""
    import shapely
    return shapely.area(shapely.transform(geoms, _cea))


def covered_share(square, around):
    """the share of square's area that the geometries around it hold together (1.0 when one covers it). A square with no
    area counts as covered when a point on it is."""
    import shapely
    if not around:
        return 0.0
    if any(shapely.covers(g, square) for g in around):
        return 1.0
    a = shapely.area(square)
    if a == 0:
        p = shapely.point_on_surface(square)
        return 1.0 if any(shapely.covers(g, p) for g in around) else 0.0
    return float(shapely.area(shapely.intersection(square, shapely.union_all(around))) / a)


def build(src: Path, out: Path, overture: str) -> dict:
    import duckdb
    import shapely
    src_s = str(src).replace("\\", "/")
    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'; SET threads=2; SET max_temp_directory_size='1GB'; LOAD spatial")
    div = f"read_parquet('{src_s}/division.parquet')"
    squares = {r[0] for r in con.execute(
        f"SELECT id FROM {div} WHERE subtype = 'microhood' AND local_type['en'] = 'square'").fetchall()}
    parents = {r[0] for r in con.execute(f"SELECT DISTINCT parent_division_id FROM {div}").fetchall()}
    outl = f"read_parquet('{src_s}/division_area_outlines.parquet')"
    # the land outline: every division has one (in 2026-10-21.0, 1,082,287 of 1,082,287), and a sort to pick one
    # would hold every geometry; the 1,972 maritime outlines are left out
    pick = f"SELECT division_id, subtype, ST_AsWKB(geometry) FROM {outl} WHERE class = 'land' AND subtype IN {tuple(COVERING)}"
    small, sq_ids = [], []
    cur = con.execute(pick + " AND subtype = 'microhood'")
    while rows := cur.fetchmany(2000):
        keep = [r for r in rows if r[0] in squares and r[0] not in parents]
        if not keep:
            continue
        g = shapely.make_valid(shapely.from_wkb([bytes(r[2]) for r in keep]))
        for r, gg, m in zip(keep, g, area_m2(g)):
            if m < MAX_M2:
                small.append(gg)
                sq_ids.append(r[0])
    tree = shapely.STRtree(small)
    around = [[] for _ in small]
    cur = con.execute(pick)
    while rows := cur.fetchmany(2000):
        rows = [r for r in rows if r[0] not in squares]
        if not rows:
            continue
        for r, g in zip(rows, shapely.from_wkb([bytes(r[2]) for r in rows])):
            for q in tree.query(g, predicate="intersects"):
                around[int(q)].append(shapely.make_valid(g))
    dropped = sorted(i for i, s, a in zip(sq_ids, small, around) if covered_share(s, a) >= COVER)
    doc = {"schema": 1, "overture": overture,
           "rule": {"maxM2": MAX_M2, "cover": COVER, "coveredBy": list(COVERING)},
           "squares": len(squares), "small": len(small), "places": dropped}
    write(out, doc)
    return doc


def write(out: Path, doc: dict) -> None:
    head = {k: v for k, v in doc.items() if k != "places"}
    text = json.dumps(head)[:-1] + ', "places": [\n' + ",\n".join(json.dumps(g) for g in doc["places"]) + "\n]}\n"
    json.loads(text)
    out.write_text(text, encoding="utf-8", newline="\n")


def load(path: Path = OUT) -> set[str]:
    """the GERS ids of the listed squares; no file, none"""
    return set(json.loads(path.read_text(encoding="utf-8"))["places"]) if path.exists() else set()


def prune(parts_dir: Path, gone: set[str]) -> dict[str, int]:
    """drop the parts whose gers is in gone from every registry, keeping the file's one-part-a-line layout;
    {city: parts dropped}"""
    out = {}
    for f in sorted(parts_dir.glob("*.json")):
        text = f.read_text(encoding="utf-8")
        before = json.loads(text)
        lines = text.split("\n")
        kept = [l for l in lines if not ((m := re.search(r'"gers": "([0-9a-f-]{36})"', l)) and m.group(1) in gone)]
        if len(kept) == len(lines):
            continue
        for i in range(len(kept) - 1):   # the part before "]" loses its comma
            if kept[i + 1].startswith("]"):
                kept[i] = kept[i].rstrip(",")
        new = "\n".join(kept)
        after = json.loads(new)
        n = len(before["parts"]) - len(after["parts"])
        if n != sum(1 for p in before["parts"] if p["gers"] in gone) or any(p["gers"] in gone for p in after["parts"]):
            raise SystemExit(f"{f}: one part a line expected")
        f.write_text(new, encoding="utf-8", newline="\n")
        out[f.stem] = n
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "prune"])
    ap.add_argument("--src", type=Path, default=ROOT / "data" / "overture" / "world")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        overture = json.loads((ROOT / "config" / "places.json").read_text(encoding="utf-8"))["overture"]
        doc = build(a.src, a.out, overture)
        print(f"squares {doc['squares']:,}; under {MAX_M2:,} m2 and nobody's parent {doc['small']:,}; "
              f"covered, so left out {len(doc['places']):,} -> {a.out}")
    else:
        sys.path.insert(0, str(ROOT))
        import run
        got = prune(PARTS, set(run.left_out_places(squares=a.out)))
        print(f"dropped {sum(got.values())} parts from {len(got)} cities: {got}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
