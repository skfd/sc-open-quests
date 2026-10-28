"""Add the neighbourhoods ("parts") of counted cities, from Overture divisions and OSM geometry.

  .scratch/overture/.venv/Scripts/python tools/add_parts.py <city>... | --all
      [--overture-dir data/overture] [--dry-run]

Needs DuckDB (the Overture venv) and Docker (the name-ru-repair-osmium image, osmium-tool 1.18).

For each city of config/cities.json (DATA-FORMAT.md, "Places and parts"):

1. **The city's place** in Overture `division.parquet`: the division whose own OpenStreetMap source
   (`sources[]` with property "") is the city's relation, `r<relation>@<version>`. Where none is (Laval and
   Markham are mapped in Overture from another relation or a way), the division of the city's name, of
   subtype locality, localadmin or county, whose area's bbox overlaps the city boundary's bbox
   most (intersection over union at least 0.5).
2. **Its parts**: divisions whose `hierarchies` contain the place, of subtype borough, locality,
   macrohood, neighborhood or microhood, that have a `division_area`, and whose own source is an OSM
   relation or way (the owner chose OSM only; parts from Esri Community Maps or from OSM nodes are left
   out). Not the city's own relation. Id: the first 12 hex digits of the GERS id; the run fails if two
   parts share one.
3. **Geometry from OSM**, out of the region's newest extract in the shared store (run.latest_extract):
   per region one `osmium getid -r` of every part and one `osmium export --geometry-types=polygon`, so
   a part's polygon is OSM's as of that extract. A part osmium cannot build an area for (a broken
   multipolygon, a member outside the extract, a way that is not closed) is left out and reported.
4. **Inside the city**: the share of a part's area inside the city boundary, estimated on a 40 x 40
   grid of points over the part's bbox with the engine's even-odd test. Parts under 50% are dropped and
   reported (Overture's hierarchy puts them under the city, OSM draws them mostly elsewhere).

Writes config/parts/<city>.json (the registry) and data/boundaries/parts/<city>/<osm>.geojson (one
Feature per part, properties: osm, name and the OSM tags boundary, place, admin_level), replacing what
the city had; a city without parts gets no registry file. --dry-run selects and reports but writes
nothing and runs no osmium.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run  # noqa: E402

IMAGE = "name-ru-repair-osmium"
PART_SUBTYPES = ("borough", "locality", "macrohood", "neighborhood", "microhood")
PLACE_SUBTYPES = ("locality", "localadmin", "county")
PARTS_CONFIG = run.ROOT / "config" / "parts"
PARTS_GEOMETRY = run.ROOT / "data" / "boundaries" / "parts"
PLACES_CONFIG = run.ROOT / "config" / "places.json"
WORK = run.ROOT / ".scratch" / "add_parts"
MIN_INSIDE = 0.5
KEPT_TAGS = ("boundary", "place", "admin_level")


def place_id(gers: str) -> str:
    return gers.replace("-", "")[:12]


# --- Overture ------------------------------------------------------------------------------------

def connect(overture_dir: Path):
    import duckdb
    c = duckdb.connect()
    d = (overture_dir / "division.parquet").as_posix()
    a = (overture_dir / "division_area.parquet").as_posix()
    c.execute(f"""CREATE TABLE div AS SELECT id, names.primary AS name, names.common['en'] AS en, subtype,
        list_filter(sources, lambda x: x.property = '' AND x.dataset = 'OpenStreetMap')[1].record_id AS osm,
        flatten(list_transform(hierarchies, lambda h: list_transform(h, lambda e: e.division_id))) AS anc,
        bbox FROM '{d}'""")
    c.execute(f"""CREATE TABLE area AS SELECT division_id, min(bbox.xmin) AS xmin, min(bbox.ymin) AS ymin,
        max(bbox.xmax) AS xmax, max(bbox.ymax) AS ymax FROM '{a}' GROUP BY division_id""")
    return c


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    """Intersection over union of two (w, s, e, n) boxes."""
    w, s, e, n = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, e - w) * max(0.0, n - s)
    area = lambda x: (x[2] - x[0]) * (x[3] - x[1])
    return inter / (area(a) + area(b) - inter) if inter else 0.0


def find_place(c, city: dict) -> tuple[str, str]:
    """(GERS id, how it was found) of the city's division."""
    rows = c.execute("SELECT id FROM div WHERE osm LIKE ?", [f"r{city['relation']}@%"]).fetchall()
    if len(rows) == 1:
        return rows[0][0], "relation"
    if len(rows) > 1:
        raise SystemExit(f"{city['id']}: {len(rows)} divisions have r{city['relation']} as their source")
    box = run.city_bbox(run.ROOT / city["boundary"], city["relation"])
    rows = c.execute(f"""SELECT id, subtype, osm, xmin, ymin, xmax, ymax FROM div JOIN area ON division_id = id
        WHERE name = ? AND subtype IN {PLACE_SUBTYPES}""",
                     [city["name"]]).fetchall()
    scored = sorted(((iou(box, r[3:]), r) for r in rows), key=lambda t: -t[0])
    if not scored or scored[0][0] < 0.5:
        raise SystemExit(f"{city['id']}: no division by relation r{city['relation']}, and none named "
                         f"{city['name']!r} covers the city's bbox (best: {scored[:1]})")
    best = scored[0][1]
    return best[0], f"name and bbox (IoU {scored[0][0]:.2f}, {best[1]} {best[2]})"


def find_parts(c, city: dict, gers: str) -> list[dict]:
    rows = c.execute(f"""SELECT id, name, en, subtype, osm FROM div
        WHERE list_contains(anc, ?) AND id <> ? AND subtype IN {PART_SUBTYPES}
          AND id IN (SELECT division_id FROM area)
          AND regexp_matches(osm, '^[rw][0-9]+@')
        ORDER BY id""", [gers, gers]).fetchall()
    parts = []
    for gid, name, en, subtype, osm in rows:
        osm = osm.split("@")[0]
        if osm == f"r{city['relation']}":
            continue
        parts.append({"id": place_id(gid), "gers": gid, "name": name,
                      "en": en if en and en != name else None, "subtype": subtype, "osm": osm})
    return parts


# --- osmium --------------------------------------------------------------------------------------

def osmium(*args: str) -> None:
    """osmium in the Docker image, the shared store read-only at /osm and the work dir at /out."""
    WORK.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "--rm", "--entrypoint", "osmium", "-v", f"{run.OSM_DATA_DIR}:/osm:ro",
           "-v", f"{WORK}:/out", IMAGE, *args]
    subprocess.run(cmd, check=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})


def export_region(region: dict, osm_ids: set[str]) -> tuple[str, dict[str, dict]]:
    """{"r123": GeoJSON Feature} for the ids osmium could build an area for, from the region's newest
    extract; and that extract's file name."""
    pbf, _ = run.latest_extract(region)
    inside = f"/osm/{pbf.parent.name}/{pbf.name}"
    rid = region["id"]
    (WORK / f"{rid}.ids").parent.mkdir(parents=True, exist_ok=True)
    (WORK / f"{rid}.ids").write_text("".join(f"{i}\n" for i in sorted(osm_ids)), encoding="ascii", newline="\n")
    run.log(f"{rid}: osmium getid {len(osm_ids)} objects from {pbf.name}")
    osmium("getid", "-r", "--overwrite", "-i", f"/out/{rid}.ids", inside, "-o", f"/out/{rid}.osm.pbf")
    osmium("export", "--overwrite", "--geometry-types=polygon", "-a", "type,id", "-f", "geojsonseq",
           f"/out/{rid}.osm.pbf", "-o", f"/out/{rid}.geojsonseq")
    out = {}
    with open(WORK / f"{rid}.geojsonseq", encoding="utf-8") as f:
        for line in f:
            line = line.strip().lstrip("\x1e")
            if not line:
                continue
            feat = json.loads(line)
            p = feat["properties"]
            key = {"way": "w", "relation": "r"}[p["@type"]] + str(p["@id"])
            if key in osm_ids:
                out[key] = feat
    return pbf.name, out


# --- inside the city -----------------------------------------------------------------------------

class Rings:
    """Even-odd point-in-polygon over loose segments (lat, lon), in latitude bands, as the engine's
    Polygon."""

    def __init__(self, segs: list[tuple[float, float, float, float]]):
        self.segs = segs
        lats = [v for s in segs for v in (s[0], s[2])]
        lons = [v for s in segs for v in (s[1], s[3])]
        self.box = (min(lons), min(lats), max(lons), max(lats))
        self.n = max(1, min(4096, len(segs) // 4))
        self.h = (self.box[3] - self.box[1]) / self.n or 1e-9
        self.bands: list[list[int]] = [[] for _ in range(self.n)]
        for i, (y1, _, y2, _) in enumerate(segs):
            for k in range(self.band(min(y1, y2)), self.band(max(y1, y2)) + 1):
                self.bands[k].append(i)

    def band(self, lat: float) -> int:
        return min(self.n - 1, max(0, int((lat - self.box[1]) / self.h)))

    def contains(self, lat: float, lon: float) -> bool:
        w, s, e, n = self.box
        if not (s <= lat <= n and w <= lon <= e):
            return False
        inside = False
        for i in self.bands[self.band(lat)]:
            y1, x1, y2, x2 = self.segs[i]
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                inside = not inside
        return inside

    @staticmethod
    def of_geojson(geometry: dict) -> "Rings":
        polys = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        segs = []
        for poly in polys:
            for ring in poly:
                for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
                    segs.append((y1, x1, y2, x2))
        return Rings(segs)

    @staticmethod
    def of_boundary(path: Path, relation: int) -> "Rings":
        root = run.read_json(path)
        rel = next(e for e in root.get("elements", [root]) if e.get("type") == "relation" and e.get("id") == relation)
        segs = []
        for m in rel["members"]:
            if m["type"] != "way":
                continue
            pts = m["geometry"]
            for a, b in zip(pts, pts[1:]):
                segs.append((a["lat"], a["lon"], b["lat"], b["lon"]))
        return Rings(segs)


def inside_share(part: Rings, city: Rings, steps: int = 40) -> float:
    w, s, e, n = part.box
    pts = [(s + (n - s) * (i + 0.5) / steps, w + (e - w) * (j + 0.5) / steps)
           for i in range(steps) for j in range(steps)]
    pts = [p for p in pts if part.contains(*p)] or [(seg[0], seg[1]) for seg in part.segs]
    return sum(city.contains(*p) for p in pts) / len(pts)


# --- main ----------------------------------------------------------------------------------------

def write_city(city_id: str, overture: str, parts: list[dict], features: dict[str, dict]) -> None:
    geo_dir = PARTS_GEOMETRY / city_id
    if geo_dir.exists():
        shutil.rmtree(geo_dir)
    registry = PARTS_CONFIG / f"{city_id}.json"
    if not parts:
        registry.unlink(missing_ok=True)
        return
    geo_dir.mkdir(parents=True)
    for p in parts:
        feat = features[p["osm"]]
        tags = feat["properties"]
        props = {"osm": p["osm"], "name": tags.get("name")}
        props.update({k: tags[k] for k in KEPT_TAGS if k in tags})
        path = geo_dir / f"{p['osm']}.geojson"
        p["geometry"] = path.relative_to(run.ROOT).as_posix()
        text = json.dumps({"type": "Feature", "properties": props, "geometry": feat["geometry"]},
                          ensure_ascii=False, separators=(",", ":"))
        path.write_text(text + "\n", encoding="utf-8", newline="\n")
    PARTS_CONFIG.mkdir(parents=True, exist_ok=True)
    lines = ",\n".join("  " + json.dumps({k: p[k] for k in ("id", "gers", "name", "en", "subtype", "osm", "geometry")},
                                         ensure_ascii=False) for p in parts)
    registry.write_text(f'{{"schema": 1, "city": {json.dumps(city_id)}, "overture": {json.dumps(overture)}, '
                        f'"parts": [\n{lines}\n]}}\n', encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cities", nargs="*")
    ap.add_argument("--all", action="store_true", help="every city of config/cities.json")
    ap.add_argument("--overture-dir", type=Path, default=run.ROOT / "data" / "overture")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    all_cities = {c["id"]: c for c in run.read_json(run.CITIES_CONFIG)["cities"]}
    ids = sorted(all_cities) if args.all else args.cities
    if not ids:
        ap.error("name cities or --all")
    unknown = [i for i in ids if i not in all_cities]
    if unknown:
        ap.error(f"not in config/cities.json: {', '.join(unknown)}")
    overture = run.read_json(PLACES_CONFIG)["overture"]
    c = connect(args.overture_dir)
    regions = {r["id"]: r for r in run.regions()}

    selected: dict[str, list[dict]] = {}
    for cid in ids:
        city = all_cities[cid]
        gers, how = find_place(c, city)
        parts = find_parts(c, city, gers)
        selected[cid] = parts
        if how != "relation":
            run.log(f"{cid}: place {place_id(gers)} found by {how}")
    seen: dict[str, str] = {}
    for cid, parts in selected.items():
        for p in parts:
            other = seen.setdefault(p["id"], p["gers"])
            if other != p["gers"]:
                raise SystemExit(f"place id {p['id']} is shared by {other} and {p['gers']}")
    if args.dry_run:
        for cid, parts in selected.items():
            run.log(f"{cid}: {len(parts)} candidate parts")
        return 0

    by_region: dict[str, list[str]] = defaultdict(list)
    for cid in ids:
        by_region[all_cities[cid]["region"]].append(cid)
    report = []
    for rid, cids in by_region.items():
        wanted = {p["osm"] for cid in cids for p in selected[cid]}
        features: dict[str, dict] = {}
        extract = None
        if wanted:
            extract, features = export_region(regions[rid], wanted)
        for cid in cids:
            city = all_cities[cid]
            city_rings = Rings.of_boundary(run.ROOT / city["boundary"], city["relation"])
            kept, missing, outside = [], [], []
            for p in selected[cid]:
                feat = features.get(p["osm"])
                if feat is None:
                    missing.append(p)
                    continue
                share = inside_share(Rings.of_geojson(feat["geometry"]), city_rings)
                if share < MIN_INSIDE:
                    outside.append((p, share))
                    continue
                kept.append(p)
            kept.sort(key=lambda p: (p["name"] or "", p["id"]))
            write_city(cid, overture, kept, features)
            kinds = defaultdict(int)
            for p in kept:
                b = features[p["osm"]]["properties"].get("boundary") or features[p["osm"]]["properties"].get("place") or "-"
                kinds[b] += 1
            report.append(f"{cid}: {len(kept)} parts ({dict(sorted(kinds.items()))})"
                          + (f" from {extract}" if extract else ""))
            for p in missing:
                report.append(f"  no OSM area: {p['osm']} {p['name']} ({p['subtype']}, {p['id']})")
            for p, share in outside:
                report.append(f"  dropped, {share:.0%} inside: {p['osm']} {p['name']} ({p['subtype']}, {p['id']})")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
