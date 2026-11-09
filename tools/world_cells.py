"""A country counted as cells, every Overture place getting a number by position: the world-count
prototype (DESIGN.md, "The whole world: measured and proposed"; "Germany as cells: the world prototype").

  .scratch/overture/.venv/Scripts/python tools/world_cells.py places  --country DE --out DIR
  python tools/world_cells.py plan     --grid DIR/nodegrid.json --out DIR [--file-nodes 130e6] [--cell-nodes 15e6]
  python tools/world_cells.py cut      --pbf germany.osm.pbf --out DIR
  python tools/world_cells.py notes    --out DIR
  python tools/world_cells.py count    --out DIR [--engines 2] [--heap-gb 30]
  python tools/world_cells.py baseline --pbf germany.osm.pbf --cities berlin,hamburg,... --out DIR
  python tools/world_cells.py report   --out DIR

`nodegrid.json` comes from the engine (`sc-open-quests-engine nodegrid --pbf ... --out ...`). Everything
is written under DIR (a scratch folder); nothing the pipeline or the site reads changes.

- **places**: every division of the country in Overture (config/places.json's release, data/overture/)
  that has an area and whose own source is an OSM relation or way (the owner's rule, 2026-10-24), its
  land area where it has one, as one GeoJSON file each: DIR/places.json and DIR/geo/<placeId>.geojson.
- **plan**: the node grid cut, k-d style at the weighted median of the longer side, first into files of
  at most --file-nodes nodes, then each file into cells of at most --cell-nodes. The cells tile the grid's
  bounding box exactly (shared edges are the same floats, and the engine's even-odd test is half-open,
  so a point on an edge is in exactly one cell), so every element's centre is in one cell. Writes
  DIR/plan.json, per file DIR/files/<f>/cities.json (each cell a "city" with a rectangle boundary) and
  DIR/files/<f>/parts/<cell>.json (every place whose bbox meets the cell, plus the counted cities' own
  OSM polygons as parts "osm-<city>", for the check against whole-city counts).
- **cut**: one `osmium extract` (docker image name-ru-repair-osmium) with a bbox output per file: the
  file's cells padded by PAD_M, strategy smart, so a cell's 1 km ring (AreaPass.AREA_PADDING_M) and its
  multipolygons are whole.
- **notes**: the store's newest notes dump clipped to the grid's bounding box (tools/clip_notes.py).
- **count**: the engine over each file with its cells and parts, --engines at once, largest first.
- **baseline**: the counted cities as whole cities over the same country file, notes clip and quests.
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

PAD_M = 2000.0  # around a file's cells: more than the engine's 1 km ring
OVERTURE = ROOT / "data" / "overture"
TIME_ZONES = {"DE": "Europe/Berlin"}


def rel(p: Path) -> str:
    return p.resolve().relative_to(ROOT).as_posix()


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


# --- places --------------------------------------------------------------------------------------

def places(country: str, out: Path) -> None:
    import duckdb
    con = duckdb.connect()
    con.sql("LOAD spatial")
    src = OVERTURE.as_posix()
    q = f"""
    WITH d AS (
      SELECT id, names."primary" AS name, subtype, parent_division_id AS parent,
        [s.record_id FOR s IN sources IF s.dataset = 'OpenStreetMap' AND s.property = ''] AS own
      FROM read_parquet('{src}/division.parquet') WHERE country = ?
    ), a AS (
      SELECT division_id, class, geometry, bbox FROM read_parquet('{src}/division_area.parquet') WHERE country = ?
    ), pick AS (
      SELECT a.*, row_number() OVER (PARTITION BY division_id ORDER BY (class = 'land') DESC) AS k FROM a
    )
    SELECT d.id, d.name, d.subtype, d.parent, d.own[1] AS osm, ST_AsGeoJSON(p.geometry) AS g,
           p.bbox.xmin, p.bbox.ymin, p.bbox.xmax, p.bbox.ymax
    FROM d JOIN pick p ON p.division_id = d.id AND p.k = 1
    WHERE len(d.own) > 0 AND (d.own[1] LIKE 'r%' OR d.own[1] LIKE 'w%')
    ORDER BY d.id
    """
    rows = con.execute(q, [country, country]).fetchall()
    geo = out / "geo"
    geo.mkdir(parents=True, exist_ok=True)
    result, seen, skipped = [], set(), collections.Counter()
    for gers, name, subtype, parent, osm, g, xmin, ymin, xmax, ymax in rows:
        pid = gers.replace("-", "")[:12].lower()
        if pid in seen:
            raise SystemExit(f"place id {pid} twice")
        seen.add(pid)
        gj = json.loads(g)
        if gj["type"] not in ("Polygon", "MultiPolygon"):
            skipped[gj["type"]] += 1
            continue
        (geo / f"{pid}.geojson").write_text(json.dumps(gj), encoding="utf-8")
        result.append({"id": pid, "gers": gers, "name": name, "subtype": subtype, "parent": parent,
                       "osm": osm.split("@")[0], "bbox": [xmin, ymin, xmax, ymax],
                       "geometry": rel(geo / f"{pid}.geojson")})
    write_json(out / "places.json", {"country": country, "overture": read_json(ROOT / "config/places.json")["overture"],
                                     "places": result})
    by = collections.Counter(p["subtype"] for p in result)
    print(f"{len(result)} places ({dict(by)}); skipped geometries {dict(skipped)}")


# --- plan ----------------------------------------------------------------------------------------

def kd(grid: dict, step: float, rect: tuple[int, int, int, int], limit: float) -> list[tuple[int, int, int, int]]:
    """Split rect (r0, r1, c0, c1, inclusive square indices) until each part holds at most limit nodes."""
    r0, r1, c0, c1 = rect
    total = sum(n for (r, c), n in grid.items() if r0 <= r <= r1 and c0 <= c <= c1)
    if total <= limit or (r0 == r1 and c0 == c1):
        return [rect]
    lat = (r0 + r1 + 1) / 2 * step
    tall = (r1 - r0 + 1) >= (c1 - c0 + 1) * math.cos(math.radians(lat))
    if tall and r0 == r1:
        tall = False
    if not tall and c0 == c1:
        tall = True
    lo, hi = (r0, r1) if tall else (c0, c1)
    marg = collections.Counter()
    for (r, c), n in grid.items():
        if r0 <= r <= r1 and c0 <= c <= c1:
            marg[r if tall else c] += n
    acc, cut = 0, lo
    for k in range(lo, hi):  # cut after k: halves lo..k and k+1..hi
        acc += marg[k]
        cut = k
        if acc >= total / 2:
            break
    a, b = ((r0, cut, c0, c1), (cut + 1, r1, c0, c1)) if tall else ((r0, r1, c0, cut), (r0, r1, cut + 1, c1))
    return kd(grid, step, a, limit) + kd(grid, step, b, limit)


def rect_nodes(grid, rect):
    r0, r1, c0, c1 = rect
    return sum(n for (r, c), n in grid.items() if r0 <= r <= r1 and c0 <= c <= c1)


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


def city_parts(country: str, out: Path) -> list[dict]:
    """The counted cities of the country, each as a GeoJSON MultiPolygon of its own boundary file."""
    res = []
    for c in run.read_json(run.CITIES_CONFIG)["cities"]:
        if country not in c["countryCodes"]:
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


def plan(grid_path: Path, out: Path, file_nodes: float, cell_nodes: float) -> None:
    g = read_json(grid_path)
    step = g["step"]
    grid = {(r, c): n for r, c, n in g["cells"]}
    rows = [r for r, _ in grid]
    cols = [c for _, c in grid]
    whole = (min(rows), max(rows), min(cols), max(cols))
    pl = read_json(out / "places.json")
    country = pl["country"]
    tz = TIME_ZONES[country]
    extra = city_parts(country, out)
    places_ = pl["places"] + extra

    def deg(rect):  # (s, w, n, e): k * step, the same float for a shared edge
        r0, r1, c0, c1 = rect
        return r0 * step, c0 * step, (r1 + 1) * step, (c1 + 1) * step

    files = []
    for fi, frect in enumerate(sorted(kd(grid, step, whole, file_nodes), key=lambda r: -rect_nodes(grid, r))):
        fid = f"f{fi}"
        d = out / "files" / fid
        (d / "cells").mkdir(parents=True, exist_ok=True)
        (d / "parts").mkdir(parents=True, exist_ok=True)
        cities, cells = [], []
        for ci, crect in enumerate(kd(grid, step, frect, cell_nodes)):
            s, w, n, e = deg(crect)
            cid = f"{fid}c{ci}"
            rid = 980000000 + fi * 10000 + ci
            ring = [{"lat": s, "lon": w}, {"lat": s, "lon": e}, {"lat": n, "lon": e}, {"lat": n, "lon": w}, {"lat": s, "lon": w}]
            bpath = d / "cells" / f"{cid}.json"
            write_json(bpath, {"type": "relation", "id": rid, "bounds": {"minlat": s, "minlon": w, "maxlat": n, "maxlon": e},
                               "members": [{"type": "way", "ref": rid, "role": "outer", "geometry": ring}],
                               "tags": {"name": cid}})
            cities.append({"id": cid, "name": cid, "relation": rid, "adminLevel": 2, "countryCodes": [country],
                           "timeZone": tz, "population": 1, "landAreaKm2": 1.0, "boundary": rel(bpath), "region": fid})
            ps = [{"id": p["id"], "geometry": p["geometry"]} for p in places_
                  if p["bbox"][0] <= e and p["bbox"][2] >= w and p["bbox"][1] <= n and p["bbox"][3] >= s]
            write_json(d / "parts" / f"{cid}.json", {"schema": 1, "city": cid, "parts": ps})
            cells.append({"id": cid, "rect": [s, w, n, e], "nodes": rect_nodes(grid, crect), "parts": len(ps)})
        write_json(d / "cities.json", {"cities": cities})
        s, w, n, e = deg(frect)
        dlat = PAD_M / 111_320.0
        dlon = PAD_M / (111_320.0 * math.cos(math.radians(max(abs(s), abs(n)))))
        files.append({"id": fid, "rect": [s, w, n, e], "bbox": [w - dlon, s - dlat, e + dlon, n + dlat],
                      "nodes": rect_nodes(grid, frect), "cells": cells})
    s, w, n, e = deg(whole)
    write_json(out / "plan.json", {"country": country, "timeZone": tz, "step": step, "nodes": g["nodes"],
                                   "bbox": [w, s, e, n], "cityParts": extra, "files": files})
    for f in files:
        print(f"{f['id']}: {f['nodes'] / 1e6:.0f}M nodes, {len(f['cells'])} cells "
              f"({min(c['nodes'] for c in f['cells']) / 1e6:.1f}-{max(c['nodes'] for c in f['cells']) / 1e6:.1f}M), "
              f"{sum(c['parts'] for c in f['cells'])} part entries")
    print(f"{len(files)} files, {sum(len(f['cells']) for f in files)} cells")


# --- cut -----------------------------------------------------------------------------------------

def cut(pbf: Path, out: Path) -> None:
    p = read_json(out / "plan.json")
    cutdir = out / "cut"
    cutdir.mkdir(exist_ok=True)
    # null copies the input's value: the engine refuses a file without its replication timestamp
    header = {k: None for k in ("osmosis_replication_timestamp", "osmosis_replication_sequence_number",
                                "osmosis_replication_base_url", "timestamp")}
    cfg = {"directory": "/out", "extracts": [
        {"output": f"{f['id']}.osm.pbf", "output_format": "pbf", "bbox": f["bbox"], "output_header": header}
        for f in p["files"]]}
    write_json(cutdir / "extract.json", cfg)
    t = time.time()
    cmd = ["docker", "run", "--rm", "--name", f"world-cells-cut-{os.getpid()}",
           "-v", f"{pbf.parent.resolve()}:/in:ro", "-v", f"{cutdir.resolve()}:/out", "--entrypoint", "osmium",
           "name-ru-repair-osmium", "extract", "-c", "/out/extract.json", "-s", "smart", "--overwrite",
           f"/in/{pbf.name}"]
    r = subprocess.run(cmd, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    if r.returncode:
        raise SystemExit(f"osmium extract failed: {r.returncode}")
    print(f"cut {len(p['files'])} files in {time.time() - t:.0f} s")


# --- notes ---------------------------------------------------------------------------------------

def notes(out: Path) -> None:
    p = read_json(out / "plan.json")
    w, s, e, n = p["bbox"]
    poly = out / "bbox.poly"
    poly.write_text(f"bbox\n1\n   {w} {s}\n   {e} {s}\n   {e} {n}\n   {w} {n}\n   {w} {s}\nEND\nEND\n")
    dump = run.notes_dump()
    clip = out / "notes.jsonl"
    subprocess.run([sys.executable, str(ROOT / "tools/clip_notes.py"), str(dump), "--poly", str(poly), "--out", str(clip)],
                   check=True)
    print(f"notes from {dump.name}")


# --- count ---------------------------------------------------------------------------------------

def engine(args: list[str], tz: str, heap_gb: int, log: Path) -> tuple[int, float]:
    env = run.engine_env(tz)  # no heap=True: the -Xmx below is what two engines at once can each have
    env["JAVA_OPTS"] = (env.get("JAVA_OPTS", "") + f" -Xmx{heap_gb}g").strip()
    t = time.time()
    with open(log, "w", encoding="utf-8") as f:
        r = subprocess.run([str(run.ENGINE_BAT), *args], cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT)
    return r.returncode, time.time() - t


def count(out: Path, engines: int, heap_gb: int) -> None:
    p = read_json(out / "plan.json")
    quests = run.newest_quests_file()
    notes_clip = out / "notes.jsonl"

    def one(f):
        d = out / "files" / f["id"]
        if (d / "done.json").exists():
            return f["id"], "done before"
        pbf = out / "cut" / f"{f['id']}.osm.pbf"
        code, secs = engine(["count", "--pbf", str(pbf), "--quests", rel(quests), "--cities", rel(d / "cities.json"),
                             "--out", rel(d / "out"), "--notes", rel(notes_clip), "--parts", rel(d / "parts")],
                            p["timeZone"], heap_gb, d / "log.txt")
        if code:
            return f["id"], f"FAILED ({code}), see {d / 'log.txt'}"
        write_json(d / "done.json", {"wallSeconds": round(secs, 1)})
        return f["id"], f"{secs:.0f} s"

    t = time.time()
    with ThreadPoolExecutor(engines) as ex:  # plan.json lists the largest file first
        for fid, msg in ex.map(one, p["files"]):
            print(f"{fid}: {msg}", flush=True)
    print(f"count: {time.time() - t:.0f} s with {engines} engine(s) at once")


def baseline(pbf: Path, cities: list[str], out: Path, heap_gb: int) -> None:
    p = read_json(out / "plan.json")
    conf = [c for c in run.read_json(run.CITIES_CONFIG)["cities"] if c["id"] in cities]
    conf = [{**c, "region": "baseline"} for c in conf]
    d = out / "baseline"
    write_json(d / "cities.json", {"cities": conf})
    quests = run.newest_quests_file()
    code, secs = engine(["count", "--pbf", str(pbf), "--quests", rel(quests), "--cities", rel(d / "cities.json"),
                         "--out", rel(d / "out"), "--notes", rel(out / "notes.jsonl")], p["timeZone"], heap_gb, d / "log.txt")
    print(f"baseline: exit {code}, {secs:.0f} s")


# --- report --------------------------------------------------------------------------------------

def snapshot(d: Path) -> dict:
    return read_json(next(iter(sorted((d / "out" / "snapshots").glob("*.json")))))


def report(out: Path) -> None:
    p = read_json(out / "plan.json")
    pl = {x["id"]: x for x in read_json(out / "places.json")["places"]}
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
    base = snapshot(out / "baseline")
    lines = [f"# {p['country']} as cells: {len(p['files'])} files, {sum(len(f['cells']) for f in p['files'])} cells, "
             f"{p['nodes'] / 1e6:.0f}M nodes", ""]

    def tot(qs, leave=()):
        return sum(n for q, n in qs.items() if q not in leave)

    lines.append(f"Every open quest in the cells: {tot(cell_total):,}; app default: {tot(cell_total, disabled):,}")
    country = [k for k, v in pl.items() if v["subtype"] == "country"]
    for k in country:
        lines.append(f"Country place {pl[k]['name']} ({k}): every {tot(sums[k]):,}, default {tot(sums[k], disabled):,}")
    lines += ["", "## Counted cities: cells (OSM polygon as a part) against the whole-city count, same file", "",
              "| city | whole city (default) | cells (default) | diff | every quest diff | quests that differ |",
              "|---|---|---|---|---|---|"]
    rows = []
    for cp in p["cityParts"]:
        city = cp["city"]
        b = {q: v.get("open") or 0 for q, v in base["cities"][city]["quests"].items()}
        c = sums[cp["id"]]
        bd, cd = tot(b, disabled), tot(c, disabled)
        diff = {q: c.get(q, 0) - b.get(q, 0) for q in set(b) | set(c) if c.get(q, 0) != b.get(q, 0)}
        top = ", ".join(f"{q} {v:+d}" for q, v in sorted(diff.items(), key=lambda kv: -abs(kv[1]))[:5])
        lines.append(f"| {city} | {bd:,} | {cd:,} | {(cd - bd) / bd * 100:+.4f}% | {tot(c) - tot(b):+,} | {top or '-'} |")
        rows.append({"city": city, "base": b, "cells": dict(c), "diff": diff})
    lines += ["", "## The same cities as Overture places (a boundary difference, not a counting one)", "",
              "| city | Overture place | whole city (default) | Overture place (default) | diff |", "|---|---|---|---|---|"]
    for cp in p["cityParts"]:
        city = cp["city"]
        conf = next(c for c in run.read_json(run.CITIES_CONFIG)["cities"] if c["id"] == city)
        match = [k for k, v in pl.items() if v["osm"] == f"r{conf['relation']}"]
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
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("places"); a.add_argument("--country", required=True); a.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("plan"); a.add_argument("--grid", type=Path, required=True); a.add_argument("--out", type=Path, required=True)
    a.add_argument("--file-nodes", type=float, default=130e6); a.add_argument("--cell-nodes", type=float, default=15e6)
    a = sub.add_parser("cut"); a.add_argument("--pbf", type=Path, required=True); a.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("notes"); a.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("count"); a.add_argument("--out", type=Path, required=True)
    a.add_argument("--engines", type=int, default=2); a.add_argument("--heap-gb", type=int, default=30)
    a = sub.add_parser("baseline"); a.add_argument("--pbf", type=Path, required=True); a.add_argument("--out", type=Path, required=True)
    a.add_argument("--cities", required=True); a.add_argument("--heap-gb", type=int, default=40)
    a = sub.add_parser("report"); a.add_argument("--out", type=Path, required=True)
    o = ap.parse_args(argv)
    if o.cmd == "places":
        places(o.country, o.out)
    elif o.cmd == "plan":
        plan(o.grid, o.out, o.file_nodes, o.cell_nodes)
    elif o.cmd == "cut":
        cut(o.pbf, o.out)
    elif o.cmd == "notes":
        notes(o.out)
    elif o.cmd == "count":
        count(o.out, o.engines, o.heap_gb)
    elif o.cmd == "baseline":
        baseline(o.pbf, o.cities.split(","), o.out, o.heap_gb)
    elif o.cmd == "report":
        report(o.out)


if __name__ == "__main__":
    main()
