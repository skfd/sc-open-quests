"""Add a city by its OSM boundary relation. Python standard library only.

  python tools/add_city.py <relation> --region berlin --country-codes DE --time-zone Europe/Berlin \
      --population 3685265 [--population-source "..."] [--id berlin] [--name Berlin] [--out config/cities.json]

Fetches the relation from Overpass (`[out:json];relation(ID);out geom;`) and writes it, the bare element,
to data/boundaries/<relation>.json -- the same shape tools/import_farmland_cities.py wrote and
Polygon.fromOverpassJson reads. Prints the cities.json entry and puts it, replacing any entry with the
same id, into --out (config/cities.json), sorted by id. countryCodes must be what SC's boundaries give
the city (engine CountriesTest checks): ["CA","CA-ON"] in Ontario, but only ["DE"] in Germany.

adminLevel is the relation's admin_level tag; the relation must be boundary=administrative.

landAreaKm2: the ontario-farmland entries came from that project's areas.py -- shapely polygonize of the
outer (and role-less) ways minus the inner ways, measured with pyproj Geod(ellps="WGS84")
.geometry_area_perimeter, i.e. the geodesic area of the OSM boundary, water included. Here the same
polygon is measured without third-party packages: ways are stitched into rings by matching end
coordinates, each ring's area is the spherical excess on the authalic sphere after mapping latitudes to
authalic latitudes (an equal-area mapping of the WGS84 ellipsoid), and the result is the outer rings minus
the inner rings. On the Ontario boundaries it agrees with the stored figures to about 1e-6.

region is the Geofabrik extract id whose .pbf holds the city. If config/<region>.poly exists, the
relation's bounds must lie inside its bbox (else an error), and every boundary vertex is tested against
the polygon itself; vertices outside it are a warning with the largest distance.

Note that landAreaKm2 is the area of the OSM boundary as drawn: where a boundary runs out to sea (e.g.
Hamburg's Neuwerk ring, which takes in the Wadden Sea) it is far above the official land area.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERPASS = "https://overpass-api.de/api/interpreter"
USER_AGENT = "sc-open-quests/add_city (https://github.com/skfd/sc-open-quests)"

# WGS84
A = 6378137.0
F = 1 / 298.257223563
E2 = F * (2 - F)
E = math.sqrt(E2)


def fetch_relation(rel: int) -> dict:
    query = f"[out:json][timeout:180];relation({rel});out geom;"
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": query}).encode(),
                                 headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                doc = json.load(r)
            break
        except urllib.error.HTTPError as err:
            if err.code not in (429, 502, 503, 504) or attempt == 4:
                raise
            wait = 30 * (attempt + 1)
            print(f"Overpass {err.code}; retrying in {wait} s", file=sys.stderr)
            time.sleep(wait)
    rels = [e for e in doc.get("elements", []) if e.get("type") == "relation" and e.get("id") == rel]
    if not rels:
        sys.exit(f"Overpass returned no relation {rel}")
    return rels[0]


def _q(sin_phi: float) -> float:
    return (1 - E2) * (sin_phi / (1 - E2 * sin_phi * sin_phi)
                       - math.log((1 - E * sin_phi) / (1 + E * sin_phi)) / (2 * E))


QP = _q(1.0)
R_AUTHALIC = A * math.sqrt(QP / 2)


def authalic_lat(lat_deg: float) -> float:
    return math.asin(max(-1.0, min(1.0, _q(math.sin(math.radians(lat_deg))) / QP)))


def ring_area_m2(ring: list[tuple[float, float]]) -> float:
    """Unsigned area of a closed ring of (lat, lon) degrees: spherical excess on the authalic sphere."""
    total = 0.0
    pts = [(authalic_lat(lat), math.radians(lon)) for lat, lon in ring]
    for (b1, l1), (b2, l2) in zip(pts, pts[1:]):
        dl = l2 - l1
        if dl > math.pi:
            dl -= 2 * math.pi
        elif dl < -math.pi:
            dl += 2 * math.pi
        t1, t2 = math.tan(b1 / 2), math.tan(b2 / 2)
        total += 2 * math.atan2(math.tan(dl / 2) * (t1 + t2), 1 + t1 * t2)
    return abs(total) * R_AUTHALIC * R_AUTHALIC


def way_coords(m: dict) -> list[tuple[float, float]]:
    return [(p["lat"], p["lon"]) for p in m["geometry"]]


def stitch(ways: list[list[tuple[float, float]]], rel: int, what: str) -> list[list[tuple[float, float]]]:
    """Joins ways end to end (either direction) into closed rings."""
    pool = [w for w in ways if len(w) >= 2]
    rings = []
    while pool:
        ring = list(pool.pop())
        while ring[0] != ring[-1]:
            end = ring[-1]
            for i, w in enumerate(pool):
                if w[0] == end:
                    ring.extend(w[1:]); break
                if w[-1] == end:
                    ring.extend(reversed(w[:-1])); break
            else:
                sys.exit(f"relation {rel}: {what} ring does not close at {end}")
            pool.pop(i)
        rings.append(ring)
    return rings


def check_engine_parity(e: dict) -> None:
    """The engine's own check: every way end shared by an even number of way ends."""
    deg: dict[tuple[float, float], int] = {}
    for m in e["members"]:
        if m["type"] != "way":
            continue
        c = way_coords(m)
        for p in (c[0], c[-1]):
            deg[p] = deg.get(p, 0) + 1
    odd = sum(1 for v in deg.values() if v % 2)
    if odd:
        sys.exit(f"relation {e['id']}: {odd} open ring ends -- the engine would refuse it")


def land_area_km2(e: dict) -> tuple[float, int, int]:
    outer, inner = [], []
    for m in e["members"]:
        if m["type"] != "way" or not m.get("geometry"):
            continue
        role = m.get("role", "")
        if role in ("outer", ""):
            outer.append(way_coords(m))
        elif role == "inner":
            inner.append(way_coords(m))
        else:
            sys.exit(f"relation {e['id']}: way {m['ref']} has role {role!r}; the engine would count it as boundary")
    o = stitch(outer, e["id"], "outer")
    i = stitch(inner, e["id"], "inner")
    area = sum(map(ring_area_m2, o)) - sum(map(ring_area_m2, i))
    return area / 1e6, len(o), len(i)


def read_poly(path: Path) -> list[tuple[bool, list[tuple[float, float]]]]:
    """Sections of an osmosis .poly as (is_hole, [(lat, lon), ...])."""
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    sections, cur, hole = [], None, False
    for ln in lines[1:]:
        if not ln:
            continue
        if cur is None:
            if ln == "END":
                break
            cur, hole = [], ln.startswith("!")
        elif ln == "END":
            sections.append((hole, cur)); cur = None
        else:
            lon, lat = map(float, ln.split()[:2])
            cur.append((lat, lon))
    return sections


def inside(lat: float, lon: float, ring: list[tuple[float, float]]) -> bool:
    c = False
    j = len(ring) - 1
    for i in range(len(ring)):
        (yi, xi), (yj, xj) = ring[i], ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def check_region(e: dict, poly: Path) -> str:
    sections = read_poly(poly)
    outer = [pts for hole, pts in sections if not hole]
    lats = [p[0] for s in outer for p in s]
    lons = [p[1] for s in outer for p in s]
    bb = e["bounds"]
    if not (min(lats) <= bb["minlat"] and bb["maxlat"] <= max(lats)
            and min(lons) <= bb["minlon"] and bb["maxlon"] <= max(lons)):
        sys.exit(f"relation {e['id']}: bounds {bb} not inside {poly.name} bbox "
                 f"{min(lats)},{min(lons)} .. {max(lats)},{max(lons)}")
    outside = []
    for m in e["members"]:
        if m["type"] != "way":
            continue
        for lat, lon in way_coords(m):
            n = sum(inside(lat, lon, s) for _, s in sections)  # even-odd over all sections, holes included
            if n % 2 == 0:
                outside.append(min(dist_to_ring_m(lat, lon, s) for _, s in sections))
    if outside:
        # Geofabrik's poly is a simplified outline; a vertex a few metres over it only loses that sliver
        return (f"WARNING: inside {poly.name} bbox, but {len(outside)} boundary vertices lie outside the poly, "
                f"at most {max(outside):.1f} m")
    return f"inside {poly.name} (bbox and every vertex)"


def dist_to_ring_m(lat: float, lon: float, ring: list[tuple[float, float]]) -> float:
    """Distance from a point to a ring's edges, in metres on a local flat projection."""
    k = math.cos(math.radians(lat)) * 111320
    best = math.inf
    for (y1, x1), (y2, x2) in zip(ring, ring[1:] + ring[:1]):
        ax, ay = (x1 - lon) * k, (y1 - lat) * 111320
        dx, dy = (x2 - x1) * k, (y2 - y1) * 111320
        t = max(0.0, min(1.0, -(ax * dx + ay * dy) / ((dx * dx + dy * dy) or 1)))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("relation", type=int)
    ap.add_argument("--region", required=True, help="Geofabrik extract id holding the city, e.g. berlin")
    ap.add_argument("--country-codes", required=True, help="comma-separated, e.g. DE,DE-BE")
    ap.add_argument("--time-zone", required=True)
    ap.add_argument("--population", type=int, required=True)
    ap.add_argument("--population-source")
    ap.add_argument("--id")
    ap.add_argument("--name")
    ap.add_argument("--out", type=Path, default=ROOT / "config/cities.json")
    a = ap.parse_args()

    e = fetch_relation(a.relation)
    tags = e.get("tags", {})
    print(f"relation {a.relation}: name={tags.get('name')!r} admin_level={tags.get('admin_level')} "
          f"boundary={tags.get('boundary')} wikidata={tags.get('wikidata')}", file=sys.stderr)
    if tags.get("boundary") != "administrative":
        sys.exit(f"relation {a.relation} is not boundary=administrative")
    if not tags.get("admin_level", "").isdigit():
        sys.exit(f"relation {a.relation} has no numeric admin_level")
    check_engine_parity(e)
    km2, n_outer, n_inner = land_area_km2(e)
    print(f"  {n_outer} outer / {n_inner} inner rings, {km2:.3f} km2", file=sys.stderr)
    poly = ROOT / "config" / f"{a.region}.poly"
    if poly.exists():
        print("  " + check_region(e, poly), file=sys.stderr)
    else:
        print(f"  no {poly.relative_to(ROOT)} to check against", file=sys.stderr)

    name = a.name or tags["name"]
    entry = {
        "id": a.id or slug(name),
        "name": name,
        "relation": a.relation,
        "adminLevel": int(tags["admin_level"]),
        "countryCodes": a.country_codes.split(","),
        "timeZone": a.time_zone,
        "population": a.population,
        "landAreaKm2": km2,
        "boundary": f"data/boundaries/{a.relation}.json",
        "region": a.region,
    }
    if a.population_source:
        entry["populationSource"] = a.population_source

    (ROOT / "data/boundaries" / f"{a.relation}.json").write_text(json.dumps(e), encoding="utf-8")
    doc = json.loads(a.out.read_text(encoding="utf-8")) if a.out.exists() else {"cities": []}
    doc["cities"] = sorted([c for c in doc["cities"] if c["id"] != entry["id"]] + [entry], key=lambda c: c["id"])
    a.out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(entry, indent=2))


if __name__ == "__main__":
    main()
