"""A country counted as cells, every Overture place getting a number by position: the world-count
prototype (DESIGN.md, "The whole world: measured and proposed"; "Germany as cells: the world prototype").

  .scratch/overture/.venv/Scripts/python tools/world_cells.py places  --country DE --out DIR
  .scratch/overture/.venv/Scripts/python tools/world_cells.py plan --grid DIR/nodegrid.json --out DIR
        [--file-nodes 130e6] [--cell-nodes 15e6] [--cities id,id,...]
  python tools/world_cells.py cut      --pbf germany.osm.pbf --out DIR [--keep-regions]
  python tools/world_cells.py notes    --out DIR
  python tools/world_cells.py count    --out DIR [--engines 2] [--heap-gb 30] [--delete-cut]
        [--dump-ids FILE] [--only f3,f7]
  python tools/world_cells.py baseline --pbf germany.osm.pbf --cities berlin,hamburg,... --out DIR
  python tools/world_cells.py report   --out DIR

`nodegrid.json` comes from the engine (`sc-open-quests-engine nodegrid --pbf ... --out ...`). Everything
is written under DIR (a scratch folder); nothing the pipeline or the site reads changes.

- **places**: every division of the country in Overture (config/places.json's release, data/overture/)
  that has an area and whose own source is an OSM relation or way (the owner's rule, 2026-10-24), its
  land area where it has one, as one GeoJSON file each: DIR/places.json and DIR/geo/<placeId>.geojson.
- **plan**: the node grid cut, k-d style at the weighted median of the longer side, first into regions of
  at most 8 files' worth (REGION_FILES), each region into files of at most --file-nodes nodes, then each
  file into cells of at most --cell-nodes and at most CAP_DEG (10) degrees a side: SC's LatLonRaster is
  sized by a cell's box, and the engine refuses a box of over 500M raster squares. The planet's edges stay
  on the globe, the east one short of 180 (EAST_MAX), and a cell with no nodes takes the zone at its centre. The cells tile the grid's
  bounding box exactly (shared edges are the same floats, and the engine's even-odd test is half-open,
  so a point on an edge is in exactly one cell), so every element's centre is in one cell. Writes
  DIR/plan.json, per file DIR/files/<f>/cities.json (each cell a "city" with a rectangle boundary) and
  DIR/files/<f>/parts/<cell>.json (every place whose bbox meets the cell, plus the counted cities' own
  OSM polygons as parts "osm-<city>", for the check against whole-city counts). A cell has no countryCodes,
  so the engine gates each quest at its position as the app does (Gating.kt), and it gets the time zone
  that holds most of its nodes (timezonefinder over the node grid; the venv above has it); plan prints how
  many nodes lie in a zone whose UTC offset differs from their cell's. Without DIR/places.json (no `places`
  run) only the cities given by --cities are parts: a check of cells against whole cities, no place numbers.
- **cut**: `osmium extract` (docker image name-ru-repair-osmium) with a bbox output per file: the
  file's cells padded by PAD_M, strategy smart, so a cell's 1 km ring (AreaPass.AREA_PADDING_M) and its
  multipolygons are whole. At most 8 outputs a pass (4.2 GB each). With more than one region (a planet),
  the regions first (each the union of its files' boxes), then each region's files from it, the region
  deleted after. An output is written as .part and renamed, so a rerun skips what is whole.
- **notes**: the store's newest notes dump clipped, in one pass (tools/clip_notes.py), to each file's bbox
  (DIR/files/<f>/notes.jsonl) and to the counted cities' boxes for the baseline (DIR/notes-cities.jsonl).
- **count**: the engine over each file with its cells, parts and notes, --engines at once, largest first,
  none started where it would run into the daily update (backfill_history.QUIET). --delete-cut deletes a
  file once counted; --dump-ids writes the matches of the listed elements to files/<f>/matches.tsv (the
  stream's oracle); --only counts the files named.
  The JVM runs in plan.json's timeZone (UTC when the cells' zones differ); each cell's age filters run in
  its own zone.
- **baseline**: the counted cities as whole cities over the same file, notes and quests, with their typed
  countryCodes, one run per time zone of config/cities.json (as the daily run's regions).
- **report**: places summed over cells; the counted cities' OSM-polygon parts against the baseline (the
  owner's 0.1% bar), and their Overture place against the same, as a separate boundary difference.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
import backfill_history as bh  # noqa: E402

PAD_M = 2000.0  # around a file's cells: more than the engine's 1 km ring
# kk-SCOpenQuests-sidebyside, 15:10 local daily until 2026-11-14, about 12 minutes (HANDOFF.md, item 8)
SIDE_BY_SIDE = ((20, 5), (20, 40), "2026-11-14")


def quiet(ahead_minutes: int = 0) -> None:
    """Wait out the daily update's window (backfill_history.QUIET) and the side-by-side run's; with
    ahead_minutes, also a step that long would reach either."""
    from datetime import datetime, timedelta, timezone, time as dtime
    while True:
        bh.wait_for_quiet(ahead_minutes)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        start, end = (datetime.combine(now.date(), dtime(*hm)) for hm in SIDE_BY_SIDE[:2])
        if now.date().isoformat() > SIDE_BY_SIDE[2] or not (start - timedelta(minutes=ahead_minutes) <= now < end):
            return
        run.log("waiting out the side-by-side run")
        time.sleep(300)
OVERTURE = ROOT / "data" / "overture"


def zones_of(grid: dict, step: float) -> dict:
    """The time zone at the centre of every node-grid square (timezonefinder)."""
    try:
        from timezonefinder import TimezoneFinder
    except ImportError:
        raise SystemExit("plan needs timezonefinder: run it with .scratch/overture/.venv/Scripts/python")
    return {k: zone_at((k[0] + 0.5) * step, (k[1] + 0.5) * step) for k in grid}


_tf = None


def zone_at(lat: float, lon: float) -> str:
    """timezonefinder's zone (an Etc/GMT zone over open sea), UTC where it has none."""
    global _tf
    if _tf is None:
        from timezonefinder import TimezoneFinder
        _tf = TimezoneFinder()
    return _tf.timezone_at(lat=max(-89.99, min(89.99, lat)), lng=max(-179.99, min(179.99, lon))) or "UTC"


def utc_offset(zone: str):
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    return datetime.now(timezone.utc).astimezone(ZoneInfo(zone)).utcoffset()


def rel(p: Path) -> str:
    return p.resolve().relative_to(ROOT).as_posix()


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


# --- places --------------------------------------------------------------------------------------

def places(country: str | None, out: Path) -> None:
    """Every countable division (an area, its own source an OSM relation or way) as places.json and one
    GeoJSON file each under geo/<first two id digits>/. With a country, Overture's country pull
    (data/overture/); without, the world (data/overture/world/, its outlines from overture_pull.py
    --outlines). Rows are streamed: a million outlines do not fit in memory at once."""
    import duckdb
    con = duckdb.connect()
    con.sql("LOAD spatial")
    con.sql("SET memory_limit = '8GB'; SET preserve_insertion_order = false")
    src = (OVERTURE if country else OVERTURE / "world").as_posix()
    area_file = f"{src}/division_area.parquet" if country else f"{src}/division_area_outlines.parquet"
    if not country and not Path(area_file).exists():
        raise SystemExit(f"{area_file} missing: run tools/overture_pull.py <release> --outlines")
    where = "WHERE country = $cc" if country else ""
    params = {"cc": country} if country else {}
    # the area picked per division (its land area first), without reading the outlines; file_row_number
    # tells two areas of one division apart
    con.execute(f"""
    CREATE TEMP TABLE pick AS
    WITH d AS (
      SELECT id, names."primary" AS name, subtype, country, parent_division_id AS parent,
        [s.record_id FOR s IN sources IF s.dataset = 'OpenStreetMap' AND s.property = ''] AS own
      FROM read_parquet('{src}/division.parquet') {where}
    ), a AS (
      SELECT division_id, class, file_row_number AS rn,
        row_number() OVER (PARTITION BY division_id ORDER BY (class = 'land') DESC, file_row_number) AS k
      FROM read_parquet('{area_file}', file_row_number = true) {where}
    )
    SELECT d.id, d.name, d.subtype, d.country, d.parent, d.own[1] AS osm, a.rn
    FROM d JOIN a ON a.division_id = d.id AND a.k = 1
    WHERE len(d.own) > 0 AND (d.own[1] LIKE 'r%' OR d.own[1] LIKE 'w%')
    """, params)
    total = con.execute("SELECT count(*) FROM pick").fetchone()[0]
    cur = con.execute(f"""
    SELECT p.id, p.name, p.subtype, p.country, p.parent, p.osm, ST_AsGeoJSON(g.geometry),
           g.bbox.xmin, g.bbox.ymin, g.bbox.xmax, g.bbox.ymax
    FROM read_parquet('{area_file}', file_row_number = true) g JOIN pick p ON p.rn = g.file_row_number
    """)
    geo = out / "geo"
    result, seen, skipped = [], set(), collections.Counter()
    t = time.time()
    while rows := cur.fetchmany(2000):
        for gers, name, subtype, cc, parent, osm, g, xmin, ymin, xmax, ymax in rows:
            pid = gers.replace("-", "")[:12].lower()
            if pid in seen:
                raise SystemExit(f"place id {pid} twice")
            seen.add(pid)
            gj = json.loads(g)
            if gj["type"] not in ("Polygon", "MultiPolygon"):
                skipped[gj["type"]] += 1
                continue
            p = geo / pid[:2] / f"{pid}.geojson"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(g, encoding="utf-8")
            result.append({"id": pid, "gers": gers, "name": name, "subtype": subtype, "country": cc, "parent": parent,
                           "osm": osm.split("@")[0], "bbox": [xmin, ymin, xmax, ymax], "geometry": rel(p)})
        if len(seen) % 100_000 < 2000:
            print(f"places: {len(seen):,} of {total:,}, {time.time() - t:.0f} s", flush=True)
    result.sort(key=lambda p: p["id"])
    write_json(out / "places.json", {"country": country, "overture": read_json(ROOT / "config/places.json")["overture"],
                                     "places": result})
    by = collections.Counter(p["subtype"] for p in result)
    print(f"{len(result)} places ({dict(by)}); skipped geometries {dict(skipped)}; {time.time() - t:.0f} s")


# --- plan ----------------------------------------------------------------------------------------

# A cell's sides in degrees, at most: SC's LatLonRaster (AddHousenumber, AddIsAmenityIndoor) is sized by the
# map data's box at 0.0005 degrees a square, and the engine refuses a box of over 500M squares (AreaPass.kt,
# MAX_RASTER_SLOTS). 10 by 10 degrees and the 1 km ring is 400M. The engine also cuts the box down to its
# data, so this bounds the worst case: a sparse cell with data at opposite corners.
CAP_DEG = 10.0
# The east edge stays short of 180: SC's country lookup reads 180 as -180 and takes a box for a sliver on the
# antimeridian (DESIGN.md, "The stream, step 5"). A node at exactly 180 is in no cell.
EAST_MAX = 179.9999999
# Files are grouped into regions of at most this many, so that one osmium extract pass (4.2 GB per output)
# fits docker: the planet is cut into regions, each region into its files.
REGION_FILES = 8
MAX_RASTER_SLOTS = 500_000_000  # AreaPass.kt


def kd(items: list, step: float, rect: tuple[int, int, int, int], limit: float,
       cap: int | None = None) -> list[tuple[tuple[int, int, int, int], list]]:
    """Split rect (r0, r1, c0, c1, inclusive square indices) at the weighted median of its longer side until
    each part holds at most limit nodes and, with cap, spans at most cap squares a side. items are the
    (row, col, nodes) inside rect; returns (rect, items) leaves. A part with no nodes is still a leaf (a
    long way's centre can lie there), so the leaves tile rect."""
    r0, r1, c0, c1 = rect
    total = sum(n for _, _, n in items)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    too_big = cap is not None and (h > cap or w > cap)
    if (total <= limit and not too_big) or (h == 1 and w == 1):
        return [(rect, items)]
    if too_big and total <= limit:
        tall = h >= w  # split the side over the cap, in the middle
        mid = (r0 + r1) // 2 if tall else (c0 + c1) // 2
        cut = mid
    else:
        lat = (r0 + r1 + 1) / 2 * step
        tall = h >= w * math.cos(math.radians(max(-85.0, min(85.0, lat))))
        if tall and h == 1:
            tall = False
        if not tall and w == 1:
            tall = True
        lo, hi = (r0, r1) if tall else (c0, c1)
        marg = collections.Counter()
        for r, c, n in items:
            marg[r if tall else c] += n
        acc, cut = 0, lo
        for k in range(lo, hi):  # cut after k: halves lo..k and k+1..hi
            acc += marg[k]
            cut = k
            if acc >= total / 2:
                break
    if tall:
        a, b = (r0, cut, c0, c1), (cut + 1, r1, c0, c1)
        ia = [it for it in items if it[0] <= cut]; ib = [it for it in items if it[0] > cut]
    else:
        a, b = (r0, r1, c0, cut), (r0, r1, cut + 1, c1)
        ia = [it for it in items if it[1] <= cut]; ib = [it for it in items if it[1] > cut]
    return kd(ia, step, a, limit, cap) + kd(ib, step, b, limit, cap)


def check_boxes(files: list[dict]) -> None:
    """Every file box and cell rectangle the right way round, and every cell's box with the engine's 1 km
    ring (AreaPass.kt) under MAX_RASTER_SLOTS: the engine would refuse it in the middle of a long run."""
    bad = []
    for f in files:
        w, s, e, n = f["bbox"]
        if not (w < e and s < n):
            bad.append(f"{f['id']} box {f['bbox']}")
        for c in f["cells"]:
            cs, cw, cn, ce = c["rect"]
            dlat = 1000.0 / 111_320.0
            dlon = 1000.0 / (111_320.0 * math.cos(math.radians(min(85.0, max(abs(cs), abs(cn))))))
            ps, pw, pn, pe = max(-90.0, cs - dlat), max(-180.0, cw - dlon), min(90.0, cn + dlat), min(180.0, ce + dlon)
            slots = math.ceil((pn - ps) / 0.0005) * math.ceil((pe - pw) / 0.0005)
            if not (cw < ce and cs < cn):
                bad.append(f"{c['id']} rect {c['rect']}")
            elif slots > MAX_RASTER_SLOTS:
                bad.append(f"{c['id']} {slots:,} raster squares")
    if bad:
        raise SystemExit("plan: boxes the engine cannot take: " + "; ".join(bad[:20]))


def rect_nodes(items) -> int:
    return sum(n for _, _, n in items)


def boundary_rings(boundary: dict) -> list[list[tuple[float, float]]]:
    """An Overpass relation's way members stitched into closed rings, (lon, lat)."""
    ways = [[(p["lon"], p["lat"]) for p in m["geometry"]] for m in boundary["members"] if m["type"] == "way"]
    by_end = collections.defaultdict(set)
    for i, w in enumerate(ways):
        by_end[w[0]].add(i)
        by_end[w[-1]].add(i)
    used, out = set(), []
    for i, w in enumerate(ways):
        if i in used:
            continue
        used.add(i)
        ring = list(w)
        while ring[0] != ring[-1]:
            nxt = next((j for j in by_end[ring[-1]] if j not in used), None)
            if nxt is None:
                raise ValueError(f"relation {boundary['id']}: a ring does not close")
            used.add(nxt)
            ring += ways[nxt][1:] if ways[nxt][0] == ring[-1] else ways[nxt][::-1][1:]
        out.append(ring)
    return out


def city_parts(country: str | None, out: Path, ids: list[str] | None = None) -> list[dict]:
    """The counted cities of the country (or those of [ids]), each as a GeoJSON MultiPolygon of its own boundary file."""
    res = []
    for c in run.read_json(run.CITIES_CONFIG)["cities"]:
        if (c["id"] not in ids) if ids else (country not in c["countryCodes"]):
            continue
        b = run.read_json(ROOT / c["boundary"])
        b = next(e for e in b.get("elements", [b]) if e.get("type") == "relation" and e.get("id") == c["relation"])
        rings = boundary_rings(b)
        p = out / "geo" / f"osm-{c['id']}.geojson"
        p.write_text(json.dumps({"type": "MultiPolygon", "coordinates": [[[list(x) for x in r]] for r in rings]}))
        pts = [x for r in rings for x in r]
        res.append({"id": f"osm-{c['id']}", "city": c["id"], "geometry": rel(p),
                    "bbox": [min(x[0] for x in pts), min(x[1] for x in pts), max(x[0] for x in pts), max(x[1] for x in pts)]})
    return res


def plan(grid_path: Path, out: Path, file_nodes: float, cell_nodes: float, ids: list[str] | None = None) -> None:
    g = read_json(grid_path)
    step = g["step"]
    items = [tuple(x) for x in g["cells"]]
    whole = (min(r for r, _, _ in items), max(r for r, _, _ in items),
             min(c for _, c, _ in items), max(c for _, c, _ in items))
    pl = read_json(out / "places.json") if (out / "places.json").exists() else {"country": None, "places": []}
    country = pl["country"]
    (out / "geo").mkdir(parents=True, exist_ok=True)
    extra = city_parts(country, out, ids)
    if ids and len(extra) != len(ids):
        raise SystemExit(f"--cities: not in config: {sorted(set(ids) - {c['city'] for c in extra})}")
    places_ = pl["places"] + extra
    import numpy as np  # the world's million places against each cell: one vectorised box test, not a loop
    pb = np.array([p["bbox"] for p in places_], dtype=float).reshape(-1, 4)  # w s e n
    t = time.time()
    square_zone = zones_of({(r, c): n for r, c, n in items}, step)
    print(f"plan: {len(items):,} squares, time zones looked up in {time.time() - t:.0f} s", flush=True)
    zone_offset = {z: utc_offset(z) for z in set(square_zone.values())}
    off_nodes = 0
    cap = max(1, int(CAP_DEG / step + 1e-9))

    def deg(rect):  # (s, w, n, e): k * step, the same float for a shared edge; on the globe
        r0, r1, c0, c1 = rect
        return max(-90.0, r0 * step), max(-180.0, c0 * step), min(90.0, (r1 + 1) * step), min(EAST_MAX, (c1 + 1) * step)

    def padded(rect):  # [w, s, e, n] with PAD_M all round, the ring's width taken at 85 degrees at most
        s, w, n, e = deg(rect)
        dlat = PAD_M / 111_320.0
        dlon = PAD_M / (111_320.0 * math.cos(math.radians(min(85.0, max(abs(s), abs(n))))))
        return [max(-180.0, w - dlon), max(-90.0, s - dlat), min(180.0, e + dlon), min(90.0, n + dlat)]

    # regions of up to REGION_FILES files, then files, then cells: the planet is cut in two stages
    leaves = []
    for ri, (rrect, ritems) in enumerate(kd(items, step, whole, file_nodes * REGION_FILES)):
        leaves += [(ri, frect, fitems) for frect, fitems in kd(ritems, step, rrect, file_nodes)]
    files = []
    region_files = collections.defaultdict(list)
    for fi, (ri, frect, fitems) in enumerate(sorted(leaves, key=lambda x: -rect_nodes(x[2]))):
        fid = f"f{fi}"
        region_files[ri].append(fid)
        d = out / "files" / fid
        (d / "cells").mkdir(parents=True, exist_ok=True)
        (d / "parts").mkdir(parents=True, exist_ok=True)
        cities, cells = [], []
        for ci, (crect, citems) in enumerate(kd(fitems, step, frect, cell_nodes, cap)):
            s, w, n, e = deg(crect)
            cid = f"{fid}c{ci}"
            rid = 980000000 + fi * 10000 + ci
            ring = [{"lat": s, "lon": w}, {"lat": s, "lon": e}, {"lat": n, "lon": e}, {"lat": n, "lon": w}, {"lat": s, "lon": w}]
            bpath = d / "cells" / f"{cid}.json"
            write_json(bpath, {"type": "relation", "id": rid, "bounds": {"minlat": s, "minlon": w, "maxlat": n, "maxlon": e},
                               "members": [{"type": "way", "ref": rid, "role": "outer", "geometry": ring}],
                               "tags": {"name": cid}})
            by_zone = collections.Counter()
            for r, c, cnt in citems:
                by_zone[square_zone[(r, c)]] += cnt
            # a cell with no nodes: the zone at its centre
            tz = by_zone.most_common(1)[0][0] if by_zone else zone_at((s + n) / 2, (w + e) / 2)
            if tz not in zone_offset:
                zone_offset[tz] = utc_offset(tz)
            off_nodes += sum(cnt for r, c, cnt in citems if zone_offset[square_zone[(r, c)]] != zone_offset[tz])
            # no countryCodes: gated by position (Gating.kt)
            cities.append({"id": cid, "name": cid, "relation": rid, "adminLevel": 2, "countryCodes": None,
                           "timeZone": tz, "population": 1, "landAreaKm2": 1.0, "boundary": rel(bpath), "region": fid})
            hit = np.nonzero((pb[:, 0] <= e) & (pb[:, 2] >= w) & (pb[:, 1] <= n) & (pb[:, 3] >= s))[0]
            ps = [{"id": places_[i]["id"], "geometry": places_[i]["geometry"]} for i in hit]
            write_json(d / "parts" / f"{cid}.json", {"schema": 1, "city": cid, "parts": ps})
            cells.append({"id": cid, "rect": [s, w, n, e], "nodes": rect_nodes(citems), "parts": len(ps), "timeZone": tz})
        write_json(d / "cities.json", {"cities": cities})
        files.append({"id": fid, "rect": list(deg(frect)), "bbox": padded(frect), "nodes": rect_nodes(fitems), "cells": cells})
    by_id = {f["id"]: f for f in files}
    regions = []
    # largest first, as the files; each region's box is the union of its files' padded boxes, so the
    # second stage cuts every file from it whole, with the same strategy
    for ri, fids in enumerate(sorted(region_files.values(), key=lambda fs: -sum(by_id[x]["nodes"] for x in fs))):
        fb = [by_id[x]["bbox"] for x in fids]
        regions.append({"id": f"r{ri}", "bbox": [min(b[0] for b in fb), min(b[1] for b in fb), max(b[2] for b in fb),
                                                 max(b[3] for b in fb)], "files": fids,
                        "nodes": sum(by_id[x]["nodes"] for x in fids)})
    check_boxes(files)
    s, w, n, e = deg(whole)
    cell_zones = sorted({c["timeZone"] for f in files for c in f["cells"]})
    # the JVM's zone names the snapshot's date; each cell's age filters run in its own
    jvm_zone = cell_zones[0] if len(cell_zones) == 1 else "UTC"
    write_json(out / "plan.json", {"country": country, "timeZone": jvm_zone, "cellZones": cell_zones, "step": step,
                                   "nodes": g["nodes"], "bbox": [w, s, e, n], "cityParts": extra, "regions": regions,
                                   "files": files})
    for f in files:
        print(f"{f['id']}: {f['nodes'] / 1e6:.0f}M nodes, {len(f['cells'])} cells "
              f"({min(c['nodes'] for c in f['cells']) / 1e6:.1f}-{max(c['nodes'] for c in f['cells']) / 1e6:.1f}M), "
              f"{sum(c['parts'] for c in f['cells'])} part entries")
    for r in regions:
        print(f"{r['id']}: {r['nodes'] / 1e6:.0f}M nodes, files {', '.join(r['files'])}")
    allc = [c for f in files for c in f["cells"]]
    big = max(allc, key=lambda c: (c["rect"][2] - c["rect"][0]) * (c["rect"][3] - c["rect"][1]))
    print(f"{len(regions)} regions, {len(files)} files, {len(allc)} cells ({sum(1 for c in allc if not c['nodes'])} "
          f"with no nodes); largest cell {big['id']} {big['rect'][2] - big['rect'][0]:.2f} by "
          f"{big['rect'][3] - big['rect'][1]:.2f} degrees; {len(cell_zones)} zones; {off_nodes:,} nodes "
          f"({off_nodes / g['nodes'] * 100:.3f}%) in a zone whose UTC offset differs from their cell's")


# --- cut -----------------------------------------------------------------------------------------

# osmium extract holds about 4.2 GB per output (DESIGN.md, "Only this machine: measured"); docker's VM is 43 GB
MAX_OUTPUTS = int(os.environ.get("WORLD_CELLS_MAX_OUTPUTS", "8"))  # override for a rehearsal beside another osmium


def extract(src: Path, outdir: Path, outputs: list[tuple[str, list]], tag: str, ahead_minutes: int = 0) -> None:
    """`osmium extract` of src into outdir, one bbox output per (name, bbox), strategy smart, in passes of at
    most MAX_OUTPUTS. Each output is written as .part and renamed once its pass succeeds, so an output that
    exists is whole and is skipped by a rerun."""
    outdir.mkdir(parents=True, exist_ok=True)
    todo = [(n, b) for n, b in outputs if not (outdir / n).exists()]
    # null copies the input's value: the engine refuses a file without its replication timestamp
    header = {k: None for k in ("osmosis_replication_timestamp", "osmosis_replication_sequence_number",
                                "osmosis_replication_base_url", "timestamp")}
    for i in range(0, len(todo), MAX_OUTPUTS):
        batch = todo[i:i + MAX_OUTPUTS]
        for n, _ in batch:
            (outdir / f"{n}.part").unlink(missing_ok=True)
        cfg = {"directory": "/out", "extracts": [
            {"output": f"{n}.part", "output_format": "pbf", "bbox": b, "output_header": header} for n, b in batch]}
        conf = f"extract-{tag}-{i // MAX_OUTPUTS}.json"
        quiet(ahead_minutes)  # 8 outputs hold about 34 GB of docker's memory
        write_json(outdir / conf, cfg)
        t = time.time()
        print(f"cut {src.name}: {', '.join(n for n, _ in batch)} ...", flush=True)
        cmd = ["docker", "run", "--rm", "--name", f"world-cells-cut-{os.getpid()}",
               "-v", f"{src.parent.resolve()}:/in:ro", "-v", f"{outdir.resolve()}:/out", "--entrypoint", "osmium",
               "name-ru-repair-osmium", "extract", "-c", f"/out/{conf}", "-s", "smart", "--overwrite",
               f"/in/{src.name}"]
        r = subprocess.run(cmd, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
        if r.returncode:
            raise SystemExit(f"osmium extract of {src.name} failed: {r.returncode}")
        for n, _ in batch:
            (outdir / f"{n}.part").rename(outdir / n)
        print(f"cut {src.name}: {len(batch)} outputs in {time.time() - t:.0f} s", flush=True)


def cut(pbf: Path, out: Path, keep_regions: bool = False) -> None:
    """The plan's files from pbf. With one region, in one stage; with more (a planet), each region first, a
    pass over pbf per MAX_OUTPUTS regions, then each region's files from it, and the region deleted
    (--keep-regions keeps it). A rerun skips every file and region already cut."""
    p = read_json(out / "plan.json")
    cutdir = out / "cut"
    by_id = {f["id"]: f for f in p["files"]}
    regions = p.get("regions") or [{"id": "r0", "files": list(by_id), "bbox": None}]
    t = time.time()
    if len(regions) == 1:
        extract(pbf, cutdir, [(f"{fid}.osm.pbf", by_id[fid]["bbox"]) for fid in regions[0]["files"]], "files")
    else:
        rdir = cutdir / "regions"
        need = [r for r in regions if not all((cutdir / f"{fid}.osm.pbf").exists() for fid in r["files"])]
        extract(pbf, rdir, [(f"{r['id']}.osm.pbf", r["bbox"]) for r in need], "regions")
        for r in need:
            src = rdir / f"{r['id']}.osm.pbf"
            extract(src, cutdir, [(f"{fid}.osm.pbf", by_id[fid]["bbox"]) for fid in r["files"]], r["id"], ahead_minutes=30)
            if not keep_regions:
                src.unlink()
    print(f"cut {len(p['files'])} files in {len(regions)} region(s), {time.time() - t:.0f} s")


# --- notes ---------------------------------------------------------------------------------------

def box_poly(path: Path, box) -> Path:
    w, s, e, n = box
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"box\n1\n   {w} {s}\n   {e} {s}\n   {e} {n}\n   {w} {n}\n   {w} {s}\nEND\nEND\n")
    return path


def notes(out: Path) -> None:
    """One pass over the dump: a clip per file (its padded bbox) and one for the baseline's cities."""
    p = read_json(out / "plan.json")
    clips = [{"poly": str(box_poly(out / "files" / f["id"] / "bbox.poly", f["bbox"])),
              "out": str(out / "files" / f["id"] / "notes.jsonl")} for f in p["files"]]
    pad = 1000.0 / 111_320.0  # the cities' boxes padded by about 1 km, as run.py pads a region's
    boxes = [[cp["bbox"][0] - 2 * pad, cp["bbox"][1] - pad, cp["bbox"][2] + 2 * pad, cp["bbox"][3] + pad]
             for cp in p["cityParts"]]
    if boxes:
        clips.append({"poly": str(box_poly(out / "cities.poly", boxes[0])), "out": str(out / "notes-cities.jsonl"),
                      "boxes": boxes})
    cfg = out / "notes-clips.json"
    write_json(cfg, {"clips": clips})
    dump = run.notes_dump()
    subprocess.run([sys.executable, str(ROOT / "tools/clip_notes.py"), str(dump), "--config", str(cfg)], check=True)
    print(f"notes from {dump.name}: {len(clips)} clips")


def notes_for(out: Path, fid: str | None) -> Path:
    """a file's own notes clip (or the baseline's), else the single clip of runs before per-file clips"""
    own = out / "files" / fid / "notes.jsonl" if fid else out / "notes-cities.jsonl"
    return own if own.exists() else out / "notes.jsonl"


# --- count ---------------------------------------------------------------------------------------

def commit_free_gb() -> float | None:
    """Windows' commit headroom in GiB: the commit limit (RAM plus page file) less what is committed.
    A JVM that cannot commit its heap dies ("The paging file is too small"), however much RAM is idle.
    None off Windows."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class Info(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD)] + [(n, ctypes.c_size_t) for n in (
            "CommitTotal", "CommitLimit", "CommitPeak", "PhysicalTotal", "PhysicalAvailable", "SystemCache",
            "KernelTotal", "KernelPaged", "KernelNonpaged", "PageSize")] + [
            (n, wintypes.DWORD) for n in ("HandleCount", "ProcessCount", "ThreadCount")]
    info = Info()
    info.cb = ctypes.sizeof(info)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb):
        return None
    return (info.CommitLimit - info.CommitTotal) * info.PageSize / 2**30


# An engine starts only with its whole heap free plus this much (the JVM's own memory beyond the heap).
MARGIN_GB = 4
# Each engine commits its whole heap at start (-Xms = -Xmx), so the headroom read after this long counts it.
STARTUP_S = 45
# What a JVM prints when Windows refuses it memory: the file goes back in the queue, it did not fail.
MEMORY_REFUSED = ("paging file is too small", "insufficient memory for the Java Runtime",
                  "Could not reserve enough space")


def engine(args: list[str], tz: str, heap_gb: int, log: Path, commit_all: bool = False) -> tuple[int, float]:
    env = run.engine_env(tz)  # no heap=True: the -Xmx below is what two engines at once can each have
    opts = f" -Xmx{heap_gb}g -XX:ErrorFile={log.parent / 'hs_err_%p.log'}"
    if commit_all:  # the heap committed up front, so the next engine's memory check sees all of it
        opts += f" -Xms{heap_gb}g"
    env["JAVA_OPTS"] = (env.get("JAVA_OPTS", "") + opts).strip()
    t = time.time()
    with open(log, "w", encoding="utf-8") as f:
        r = subprocess.run([str(run.ENGINE_BAT), *args], cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT)
    return r.returncode, time.time() - t


def count(out: Path, engines: int, heap_gb: int, delete_cut: bool = False, dump_ids: Path | None = None,
          only: list[str] | None = None, give_up_s: float = 7200, state: bool = False) -> None:
    """Up to `engines` at once, as memory allows: a file starts only when Windows can commit its heap
    (commit_free_gb), so the count runs one engine while something else holds memory and two when it
    is free. A file Windows refused memory goes back in the queue. With no engine of ours running and
    still no room after give_up_s, the files left are reported failed."""
    p = read_json(out / "plan.json")
    quests = run.newest_quests_file()
    gated = commit_free_gb() is not None
    # --state: a recount of the same cut for the stream's seed, beside the count, not over it
    done_name, out_name = ("state-done.json", "out-state") if state else ("done.json", "out")

    def one(f):
        d = out / "files" / f["id"]
        pbf = out / "cut" / f"{f['id']}.osm.pbf"
        log = d / "log.txt"
        code, secs = engine(["count", "--pbf", str(pbf), "--quests", rel(quests), "--cities", rel(d / "cities.json"),
                             "--out", rel(d / out_name), "--notes", rel(notes_for(out, f["id"])), "--parts", rel(d / "parts"),
                             *(["--dump-matches", rel(d / "matches.tsv"), "--dump-ids", rel(dump_ids)] if dump_ids else []),
                             *(["--dump-state", rel(d / "state.bin")] if state else [])],
                            p["timeZone"], heap_gb, log, commit_all=gated)
        if code:
            text = log.read_text(encoding="utf-8", errors="replace")
            if any(s in text for s in MEMORY_REFUSED):
                return f, "memory"
            return f, f"FAILED ({code}), see {log}"
        write_json(d / done_name, {"wallSeconds": round(secs, 1)})
        if delete_cut:
            pbf.unlink()
        return f, f"{secs:.0f} s"

    from collections import deque
    queue = deque()  # plan.json lists the largest file first
    for f in p["files"]:
        if only and f["id"] not in only:
            continue
        if (out / "files" / f["id"] / done_name).exists():
            print(f"{f['id']}: done before", flush=True)
        else:
            queue.append(f)
    t = time.time()
    failed, running, refused = [], {}, {}
    last_start = idle_since = 0.0
    last_wait_log = 0.0
    most = 0
    with ThreadPoolExecutor(engines) as ex:
        while queue or running:
            for fut in [x for x in running if x.done()]:
                running.pop(fut)
                f, msg = fut.result()
                if msg == "memory":
                    refused[f["id"]] = refused.get(f["id"], 0) + 1
                    if refused[f["id"]] >= 5:
                        print(f"{f['id']}: FAILED (Windows refused its memory 5 times)", flush=True)
                        failed.append(f["id"])
                    else:
                        print(f"{f['id']}: Windows refused its memory ({refused[f['id']]}x), queued again", flush=True)
                        queue.append(f)
                else:
                    print(f"{f['id']}: {msg}", flush=True)
                    if msg.startswith("FAILED"):
                        failed.append(f["id"])
            if queue and len(running) < engines and time.time() - last_start >= STARTUP_S:
                # no file starts where it would run into the daily update (an engine and its own do not fit)
                quiet(ahead_minutes=40)
                free = commit_free_gb()
                if free is None or free >= heap_gb + MARGIN_GB:
                    f = queue.popleft()
                    running[ex.submit(one, f)] = f
                    most = max(most, len(running))
                    last_start, idle_since = time.time(), 0.0
                    run.log(f"count: {f['id']} started, {len(running)} engine(s) running"
                            + (f", {free:.0f} GiB was free" if free is not None else ""))
                    continue
                if time.time() - last_wait_log >= 600:
                    run.log(f"count: waiting for memory, {free:.0f} GiB free, an engine needs {heap_gb + MARGIN_GB}; "
                            f"{len(running)} running, {len(queue)} queued")
                    last_wait_log = time.time()
                if not running:
                    idle_since = idle_since or time.time()
                    if time.time() - idle_since >= give_up_s:
                        for f in queue:
                            print(f"{f['id']}: FAILED (no memory for {heap_gb} GiB in {give_up_s:.0f} s)", flush=True)
                            failed.append(f["id"])
                        queue.clear()
            time.sleep(5)
    print(f"count: {time.time() - t:.0f} s, up to {most} engine(s) at once")
    if failed:
        raise SystemExit(f"count: {len(failed)} file(s) failed: {', '.join(failed)}")


def baseline(pbf: Path, cities: list[str], out: Path, heap_gb: int) -> None:
    """The cities counted whole, one run per time zone (each in a JVM of its zone, as a daily region run)."""
    conf = [c for c in run.read_json(run.CITIES_CONFIG)["cities"] if c["id"] in cities]
    quests = run.newest_quests_file()
    by_zone = collections.defaultdict(list)
    for c in conf:
        by_zone[c["timeZone"]].append({**c, "region": "baseline"})
    for tz, cs in sorted(by_zone.items()):
        d = out / "baseline" / tz.replace("/", "-")
        if (d / "done.json").exists():
            print(f"baseline {tz}: done before")
            continue
        write_json(d / "cities.json", {"cities": cs})
        code, secs = engine(["count", "--pbf", str(pbf), "--quests", rel(quests), "--cities", rel(d / "cities.json"),
                             "--out", rel(d / "out"), "--notes", rel(notes_for(out, None))], tz, heap_gb, d / "log.txt")
        if code == 0:
            write_json(d / "done.json", {"wallSeconds": round(secs, 1)})
        print(f"baseline {tz} ({len(cs)} cities): exit {code}, {secs:.0f} s", flush=True)


# --- report --------------------------------------------------------------------------------------

def snapshot(d: Path) -> dict:
    return read_json(next(iter(sorted((d / "out" / "snapshots").glob("*.json")))))


def report(out: Path, archive: str | None = None) -> None:
    """With archive (a date), the cities are held against their published snapshots of that date
    (data/archive/<region>/snapshots/<date>.json), each row with its snapshot's asOf, not a baseline run."""
    p = read_json(out / "plan.json")
    pl = {x["id"]: x for x in read_json(out / "places.json")["places"]} if (out / "places.json").exists() else {}
    quests = run.read_json(run.newest_quests_file())["quests"]
    disabled = {q["name"] for q in quests if q.get("defaultDisabled")}
    sums = collections.defaultdict(collections.Counter)  # place -> quest -> open
    cell_total = collections.Counter()
    for f in p["files"]:
        snap = snapshot(out / "files" / f["id"])
        for cid, c in snap["cities"].items():
            for q, v in c["quests"].items():
                cell_total[q] += v.get("open") or 0
            for pid, qs in (c.get("parts") or {}).items():
                sums[pid].update(qs)
    base = {"cities": {}}
    as_of = {}
    if archive:
        for f in sorted((ROOT / "data" / "archive").glob(f"*/snapshots/{archive}.json")):
            snap = read_json(f)
            base["cities"].update(snap["cities"])
            as_of.update({c: snap["asOf"] for c in snap["cities"]})
    elif (out / "baseline" / "out" / "snapshots").is_dir():  # a run from before baselines per zone
        base["cities"].update(snapshot(out / "baseline")["cities"])
    for d in sorted((out / "baseline").iterdir()) if (out / "baseline").is_dir() and not archive else []:
        if (d / "out" / "snapshots").is_dir():
            base["cities"].update(snapshot(d)["cities"])
    lines = [f"# {p['country'] or 'The cities ' + ', '.join(c['city'] for c in p['cityParts'])} as cells: {len(p['files'])} files, {sum(len(f['cells']) for f in p['files'])} cells, "
             f"{p['nodes'] / 1e6:.0f}M nodes", ""]

    def tot(qs, leave=()):
        return sum(n for q, n in qs.items() if q not in leave)

    lines.append(f"Every open quest in the cells: {tot(cell_total):,}; app default: {tot(cell_total, disabled):,}")
    country = [k for k, v in pl.items() if v["subtype"] == "country"]
    for k in country:  # a world run lists every country; those with nothing in these cells are only counted
        if sums[k]:
            lines.append(f"Country place {pl[k]['name']} ({k}): every {tot(sums[k]):,}, default {tot(sums[k], disabled):,}")
    if empty := sum(1 for k in country if not sums[k]):
        lines.append(f"Country places with nothing in these cells: {empty}")
    lines += ["", "## Counted cities: cells (OSM polygon as a part) against the whole-city count, same file", "",
              "| city | whole city (default) | cells (default) | diff | every quest diff | quests that differ |"
              + (" city count's asOf |" if archive else ""),
              "|---|---|---|---|---|---|" + ("---|" if archive else "")]
    rows = []
    for cp in p["cityParts"]:
        city = cp["city"]
        if city not in base["cities"]:
            lines.append(f"| {city} | no count | | | | |")
            continue
        b = {q: v.get("open") or 0 for q, v in base["cities"][city]["quests"].items()}
        c = sums[cp["id"]]
        bd, cd = tot(b, disabled), tot(c, disabled)
        diff = {q: c.get(q, 0) - b.get(q, 0) for q in set(b) | set(c) if c.get(q, 0) != b.get(q, 0)}
        top = ", ".join(f"{q} {v:+d}" for q, v in sorted(diff.items(), key=lambda kv: -abs(kv[1]))[:5])
        lines.append(f"| {city} | {bd:,} | {cd:,} | {(cd - bd) / bd * 100:+.4f}% | {tot(c) - tot(b):+,} | {top or '-'} |"
                     + (f" {as_of.get(city, '-')} |" if archive else ""))
        rows.append({"city": city, "base": b, "cells": dict(c), "diff": diff})
    by_osm = collections.defaultdict(list)
    for k, v in pl.items():
        by_osm[v["osm"]].append(k)
    if pl:
        lines += ["", "## The same cities as Overture places (a boundary difference, not a counting one)", "",
                  "| city | Overture place | whole city (default) | Overture place (default) | diff |", "|---|---|---|---|---|"]
        for cp in p["cityParts"]:
            city = cp["city"]
            conf = next(c for c in run.read_json(run.CITIES_CONFIG)["cities"] if c["id"] == city)
            match = by_osm.get(f"r{conf['relation']}", [])
            if city not in base["cities"]:
                lines.append(f"| {city} | no count | | | |")
                continue
            b = {q: v.get("open") or 0 for q, v in base["cities"][city]["quests"].items()}
            if not match:
                lines.append(f"| {city} | none with r{conf['relation']} | {tot(b, disabled):,} | - | - |")
                continue
            o = sums[match[0]]
            lines.append(f"| {city} | {pl[match[0]]['name']} {match[0]} | {tot(b, disabled):,} | {tot(o, disabled):,} | "
                         f"{(tot(o, disabled) - tot(b, disabled)) / tot(b, disabled) * 100:+.3f}% |")
    counted = sum(1 for k in pl if sums[k])
    lines += ["", f"Places with a number: {counted:,} of {len(pl):,}"]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(out / "report.json", {"cities": rows, "places": {k: dict(v) for k, v in sums.items()}})
    print("\n".join(lines))


def main(argv=None) -> None:
    # the world's place names are in every script; a redirected Windows console is cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("places"); a.add_argument("--country", help="a country code; the world without"); a.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("plan"); a.add_argument("--grid", type=Path, required=True); a.add_argument("--out", type=Path, required=True)
    a.add_argument("--file-nodes", type=float, default=130e6); a.add_argument("--cell-nodes", type=float, default=15e6)
    a.add_argument("--cities", help="comma-separated city ids: the parts to check against, instead of a country's")
    a = sub.add_parser("cut"); a.add_argument("--pbf", type=Path, required=True); a.add_argument("--out", type=Path, required=True)
    a.add_argument("--keep-regions", action="store_true")
    a = sub.add_parser("notes"); a.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("count"); a.add_argument("--out", type=Path, required=True)
    a.add_argument("--engines", type=int, default=2); a.add_argument("--heap-gb", type=int, default=30)
    a.add_argument("--delete-cut", action="store_true", help="delete a file's .osm.pbf once it is counted")
    a.add_argument("--dump-ids", type=Path, help="lines type<TAB>id: each file writes these elements' matches to matches.tsv")
    a.add_argument("--only", help="comma-separated file ids: count only these (a canary first)")
    a.add_argument("--state", action="store_true",
                   help="the stream's seed: every file again with --dump-state to files/<f>/state.bin (out-state/, state-done.json)")
    a.add_argument("--give-up-h", type=float, default=2.0,
                   help="hours with none of ours running and no memory for one before the files left fail")
    a = sub.add_parser("baseline"); a.add_argument("--pbf", type=Path, required=True); a.add_argument("--out", type=Path, required=True)
    a.add_argument("--cities", required=True); a.add_argument("--heap-gb", type=int, default=40)
    a = sub.add_parser("report"); a.add_argument("--out", type=Path, required=True)
    a.add_argument("--archive", help="a date: hold the cities against their published snapshots of that day")
    o = ap.parse_args(argv)
    if o.cmd == "places":
        places(o.country, o.out)
    elif o.cmd == "plan":
        plan(o.grid, o.out, o.file_nodes, o.cell_nodes, o.cities.split(",") if o.cities else None)
    elif o.cmd == "cut":
        cut(o.pbf, o.out, o.keep_regions)
    elif o.cmd == "notes":
        notes(o.out)
    elif o.cmd == "count":
        count(o.out, o.engines, o.heap_gb, o.delete_cut, o.dump_ids, o.only.split(",") if o.only else None,
              o.give_up_h * 3600, o.state)
    elif o.cmd == "baseline":
        baseline(o.pbf, o.cities.split(","), o.out, o.heap_gb)
    elif o.cmd == "report":
        report(o.out, o.archive)


if __name__ == "__main__":
    main()
