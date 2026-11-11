"""Build the name layer, docs/places/, from Overture divisions (DATA-FORMAT.md, "Places and parts").

Usage:
  places.py build [--src DIR] [--out docs/places] [--report FILE]

DIR holds division.parquet and division_area.parquet as tools/overture_pull.py writes them
(default: data/overture/world). Only divisions that have a division_area become places. Counted
cities (config/cities.json) are matched by OSM relation, else by name inside the city's bounds;
counted parts come from config/parts/<city>.json when it exists. Needs duckdb (the .scratch/overture
venv) and the engine (its `regionids` command); everything else is the standard library. The input is
untrusted data: it is only read.

Countries are StreetComplete's (DESIGN.md, "Countries in the place index: StreetComplete's, not ours"):
a place goes under every country SC's boundaries name at its label point, and under Overture's own
`country` unless that is a placeholder (`X?`); a region, county or anything below also goes under every
country of the places below it, so each chain is whole. Under a country that is not its own, a place
sits in its Overture region, or inside its own country's root when that root is itself under the
country (United States > Puerto Rico > San Juan; Palestine > Gaza Strip > Gaza). Places no source files
under a country are left out.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBTYPES = ["country", "dependency", "region", "county", "localadmin", "locality",
            "borough", "macrohood", "neighborhood", "microhood"]
ST = {s: i for i, s in enumerate(SUBTYPES)}
NO_REGION = "_"


def place_id(gers):
    """First 12 hex digits of the GERS id, dashes removed."""
    pid = gers.replace("-", "")[:12].lower()
    if not re.fullmatch(r"[0-9a-f]{12}", pid):
        raise ValueError(f"not a GERS id: {gers!r}")
    return pid


def r4(v):
    v = round(v, 4)
    return 0.0 if v == 0 else v


# --- reading -------------------------------------------------------------------------------------

def read_divisions(src):
    """Rows of every division that has an area, as dicts. DuckDB does the heavy lifting."""
    import duckdb
    src = str(src).replace("\\", "/")
    con = duckdb.connect()
    q = f"""
    WITH area AS (
      SELECT division_id,
        coalesce(min(bbox.xmin) FILTER (WHERE class = 'land'), min(bbox.xmin)) AS xmin,
        coalesce(min(bbox.ymin) FILTER (WHERE class = 'land'), min(bbox.ymin)) AS ymin,
        coalesce(max(bbox.xmax) FILTER (WHERE class = 'land'), max(bbox.xmax)) AS xmax,
        coalesce(max(bbox.ymax) FILTER (WHERE class = 'land'), max(bbox.ymax)) AS ymax
      FROM read_parquet('{src}/division_area.parquet') GROUP BY division_id
    ),
    d AS (
      SELECT id, names."primary" AS name, names.common['en'] AS en, subtype, country, parent_division_id AS parent,
        coalesce(list_filter(hierarchies, lambda h: list_contains([x.division_id for x in h], parent_division_id))[1],
                 hierarchies[1]) AS h,
        [s.record_id for s in sources if s.dataset = 'OpenStreetMap' AND s.record_id IS NOT NULL] AS osm,
        (bbox.xmin + bbox.xmax) / 2 AS lx, (bbox.ymin + bbox.ymax) / 2 AS ly
      FROM read_parquet('{src}/division.parquet')
    )
    SELECT d.id, d.name, d.en, d.subtype, d.country, d.parent,
      [x.division_id for x in d.h] AS anc, [x.subtype for x in d.h] AS anc_st, d.osm,
      area.xmin, area.ymin, area.xmax, area.ymax, d.lx, d.ly
    FROM d JOIN area ON area.division_id = d.id
    """
    # a division's own bbox is its label point, rounded outwards to float32: its centre is the point
    cols = ["gers", "name", "en", "subtype", "country", "parent", "anc", "anc_st", "osm",
            "xmin", "ymin", "xmax", "ymax", "lx", "ly"]
    return [dict(zip(cols, r)) for r in con.execute(q).fetchall()]


# --- countries: StreetComplete's ----------------------------------------------------------------

def placeholder(cc):
    """Overture's stand-ins for areas it gives no country (XW West Bank, XU Kunashir, ...); XK is Kosovo."""
    return not cc or (len(cc) == 2 and cc[0] == "X" and cc != "XK")


def sc_countries(ids):
    """SC's region ids at a point -> its countries: a code's part before the hyphen (UA-43 is Ukraine)."""
    return sorted({i.split("-")[0] for i in ids})


RING_KM = 3     # how far around a label point SC's boundaries are asked again (border noise, below)
RING_POINTS = 8


def ring(lon, lat, km=RING_KM, n=RING_POINTS):
    """n points km around (lon, lat), north first, clockwise."""
    dlat = km / 111.32
    dlon = km / (111.32 * max(math.cos(math.radians(lat)), 0.01))
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        y = max(-90.0, min(90.0, lat + dlat * math.cos(a)))
        x = (lon + dlon * math.sin(a) + 180) % 360 - 180
        out.append((x, y))
    return out


def regionids(points):
    """SC's region ids at each (lon, lat), from the engine's `regionids`."""
    sys.path.insert(0, str(ROOT))
    import run
    if run.engine_is_stale():
        run.build_engine()
    with tempfile.TemporaryDirectory() as tmp:
        pts, out = Path(tmp) / "points.tsv", Path(tmp) / "codes.tsv"
        with open(pts, "w", encoding="utf-8", newline="\n") as f:
            for i, (x, y) in enumerate(points):
                f.write(f"{i}\t{x!r}\t{y!r}\n")
        subprocess.run([str(run.ENGINE_BAT), "regionids", "--in", str(pts), "--out", str(out)],
                       cwd=ROOT, env=run.engine_env(), check=True)
        got = [None] * len(points)
        for line in out.read_text(encoding="utf-8").splitlines():
            i, ids = line.split("\t")
            got[int(i)] = [x for x in ids.split(",") if x]
        return got


def attach_sc(rows):
    """r["sc"]: SC's region ids at each place's label point. r["ring"]: SC's countries at RING_POINTS
    points RING_KM around it, for the places SC files only under countries other than Overture's own
    (the border-noise test in `countries`)."""
    for r, ids in zip(rows, regionids([(r["lx"], r["ly"]) for r in rows])):
        r["sc"] = ids
    odd = [r for r in rows if r["sc"] and not placeholder(r["country"])
           and r["country"] not in sc_countries(r["sc"])]
    got = regionids([pt for r in odd for pt in ring(r["lx"], r["ly"])])
    for k, r in enumerate(odd):
        r["ring"] = [sc_countries(ids) for ids in got[k * RING_POINTS:(k + 1) * RING_POINTS]]


def on_the_line(r):
    """Border noise: SC files the place's point only under other countries, but files ground within
    RING_KM of it under the place's own (Overture's) country. The point sits on SC's simplified border
    (a Northern Irish townland SC puts in Ireland, a Quebec village in Vermont), and the place is kept
    in its own country only. A place SC files in another country all around (Tifariti, Matsu) or
    under both (Crimea, Puerto Rico, Gibraltar) is not touched."""
    return any(r["country"] in cs for cs in r.get("ring") or [])


def countries(rows, by_gers):
    """r["cs"]: the countries a place is filed under. Without r["sc"] (no lookup), Overture's alone."""
    for r in rows:
        own = set(sc_countries(r["sc"])) if "sc" in r and not on_the_line(r) else set()
        if not placeholder(r["country"]):
            own.add(r["country"])
        r["cs"] = own
    for r in rows:   # a chain is whole: everything from the region down holds its descendants' countries
        for a in r["anc"] or []:
            up = by_gers.get(a)
            if up is not None and up is not r and up["st"] >= ST["region"]:
                up["cs"] |= r["cs"]
    for r in rows:
        r["cs"] = sorted(r["cs"])


# --- building ------------------------------------------------------------------------------------

def assign(rows):
    """Give every place its id, parent (nearest ancestor with an area) and file (cc, region id)."""
    by_gers = {}
    seen = {}
    for r in rows:
        if r["gers"] in by_gers:
            raise SystemExit(f"duplicate GERS id {r['gers']}")
        r["id"] = place_id(r["gers"])
        if r["id"] in seen:
            raise SystemExit(f"place id {r['id']} is shared by {seen[r['id']]} and {r['gers']}")
        seen[r["id"]] = r["gers"]
        r["st"] = ST.get(r["subtype"])
        if r["st"] is None:
            raise SystemExit(f"unknown subtype {r['subtype']!r} on {r['gers']}")
        by_gers[r["gers"]] = r
    for r in rows:
        anc = [a for a in (r["anc"] or []) if a != r["gers"]]  # root first, the place itself last
        chain = list(reversed(anc))
        if r["parent"] and r["parent"] not in chain:
            chain.insert(0, r["parent"])
        r["up"] = next((by_gers[a] for a in chain if a in by_gers), None)
        region = None
        if r["subtype"] == "region":
            region = r
        else:
            for a, st in zip(r["anc"] or [], r["anc_st"] or []):
                if st == "region" and a != r["gers"]:
                    region = by_gers.get(a)  # None when the region has no area
        if region is not None and region["country"] != r["country"]:
            region = None
        r["region"] = region
    countries(rows, by_gers)
    homes = country_roots(rows)
    for r in rows:
        r["files"] = []
        home = homes.get(r["country"])
        for cc in r["cs"]:
            if cc != r["country"] and home is not None and cc in home["cs"]:
                key = home["id"]   # inside its own country's root, itself under cc
            else:
                key = r["region"]["id"] if r["region"] else NO_REGION
            r["files"].append((cc, key))
    return by_gers


def country_roots(rows):
    """Overture country -> the place that stands for it: its country division, else a dependency."""
    roots = {}
    for r in sorted(rows, key=lambda r: (r["st"], r["gers"])):
        if r["st"] in (0, 1) and r["country"] not in roots and r.get("region") is None:
            roots[r["country"]] = r
    return roots


def sort_key(r):
    return (r["st"], (r["name"] or "").casefold(), r["id"])


def english(m, cc=None):
    """A place's English name for the site, when it differs from its own: Overture's. No home-made
    romanisation (DESIGN.md, "Other touchy things"); Wikidata's English label is still to come."""
    return m["en"] if m["en"] and m["en"] != m["name"] else None


def build(rows, counted):
    """-> (index dict, {path: file dict}, stats)."""
    by_gers = assign(rows)
    homes = country_roots(rows)
    files = {}
    for r in rows:
        for f in r["files"]:
            files.setdefault(f, []).append(r)
    # the place that heads a country in the index: its own root, filed at its top
    roots = {cc: r for cc, r in homes.items() if (cc, NO_REGION) in r["files"]}
    out, stats = {}, {"orphans": 0, "noRoot": []}
    countries = {}
    for (cc, reg), members in files.items():
        if reg == NO_REGION:
            root = roots.get(cc)
            if root is None:
                stats["noRoot"].append(cc)
        else:
            root = next((m for m in members if m["id"] == reg), None)
            if root is None:
                raise SystemExit(f"{cc}/{reg}: the file's root is not filed under {cc}")
        inside = {m["gers"] for m in members}
        kids = {}
        tops = []
        for m in members:
            if m is root:
                continue
            up = m["up"]
            if up is not None and up["gers"] in inside and up is not m:
                kids.setdefault(up["gers"], []).append(m)
            else:
                tops.append(m)
        order = []
        def walk(m):
            order.append(m)
            for k in sorted(kids.get(m["gers"], []), key=sort_key):
                walk(k)
        if root is not None:
            walk(root)
        for t in sorted(tops, key=sort_key):
            walk(t)
        if len(order) != len(members):  # a cycle in parents: keep what is left, at the top
            done = {id(m) for m in order}
            for m in sorted((m for m in members if id(m) not in done), key=sort_key):
                order.append(m)
        idx = {m["gers"]: i for i, m in enumerate(order)}
        places = []
        for i, m in enumerate(order):
            up = m["up"]
            p = idx.get(up["gers"], -1) if (up is not None and m is not root) else -1
            if p >= i:
                p = -1
            if p == -1 and m is not root:
                stats["orphans"] += 1
            places.append([m["id"], m["name"], m["st"], p, r4(m["xmin"]), r4(m["ymin"]),
                           r4(m["xmax"]), r4(m["ymax"]), english(m, cc), counted.get(m["id"])])
        out[f"{cc.lower()}/{reg}.json"] = {"schema": 1, "region": reg, "places": places}
        entry = {"id": reg, "name": None if reg == NO_REGION else root["name"],
                 "file": f"{cc.lower()}/{reg}.json", "n": len(places)}
        if reg != NO_REGION and english(root, cc):
            entry["en"] = english(root, cc)
        countries.setdefault(cc, []).append(entry)
    index_countries = []
    for cc, regs in countries.items():
        root = roots.get(cc)
        regs.sort(key=lambda e: (e["name"] is not None, (e.get("en") or e["name"] or "").casefold(), e["id"]))
        index_countries.append({
            "id": root["id"] if root else None, "name": root["name"] if root else cc, "cc": cc,
            **({"en": english(root, cc)} if root and english(root, cc) else {}),
            "bbox": [r4(root[k]) for k in ("xmin", "ymin", "xmax", "ymax")] if root else None,
            "regions": regs})
    index_countries.sort(key=lambda c: ((c.get("en") or c["name"] or "").casefold(), c["cc"]))
    return index_countries, out, stats


# --- counted cities ------------------------------------------------------------------------------

def fold(s):
    s = unicodedata.normalize("NFKD", s or "").casefold()
    return "".join(ch for ch in s if ch.isalnum())


def city_bounds(city):
    """The city's own bounds from its committed boundary file, or None."""
    p = ROOT / city.get("boundary", "")
    if not city.get("boundary") or not p.is_file():
        return None
    b = json.loads(p.read_text(encoding="utf-8")).get("bounds")
    return b and (b["minlon"], b["minlat"], b["maxlon"], b["maxlat"])


def match_cities(rows, cities):
    """-> ({place id: counted}, [report lines]). Every city is matched or reported as missing."""
    by_rel = {}
    for r in rows:
        for rec in r["osm"] or []:
            m = re.fullmatch(r"r(\d+)(@.*)?", rec)
            if m:
                by_rel.setdefault(int(m.group(1)), []).append(r)
    counted, report = {}, []
    for c in cities:
        cc = next((x for x in c.get("countryCodes", []) if "-" not in x), None)
        hits = [r for r in by_rel.get(c["relation"], []) if cc is None or r["country"] == cc]
        how = "relation"
        if not hits:
            how = "name+bbox"
            b = city_bounds(c)
            name = fold(c["name"])
            def inside(r):
                if b is None:
                    return False
                cx, cy = (r["xmin"] + r["xmax"]) / 2, (r["ymin"] + r["ymax"]) / 2
                bx, by = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                return (b[0] <= cx <= b[2] and b[1] <= cy <= b[3]
                        and r["xmin"] <= bx <= r["xmax"] and r["ymin"] <= by <= r["ymax"])
            hits = [r for r in rows if r["country"] == cc and r["st"] >= 3
                    and name in (fold(r["name"]), fold(r["en"])) and inside(r)]
        if not hits:
            report.append(f"{c['id']}: NOT FOUND (r{c['relation']})")
            continue
        # several divisions can cite one relation (a county and its locality): the finest wins
        hit = sorted(hits, key=lambda r: (-r["st"], r["id"]))[0]
        if hit["id"] in counted:
            report.append(f"{c['id']}: {hit['id']} already counted as {counted[hit['id']]}")
            continue
        counted[hit["id"]] = c["id"]
        others = "" if len(hits) == 1 else " (also " + ", ".join(f"{h['id']} {h['subtype']}" for h in hits if h is not hit) + ")"
        report.append(f"{c['id']}: {hit['id']} {hit['subtype']} {hit['name']!r} by {how}{others}")
    for c in cities:
        p = ROOT / "config" / "parts" / f"{c['id']}.json"
        if p.is_file():
            for part in json.loads(p.read_text(encoding="utf-8")).get("parts", []):
                counted.setdefault(part["id"], f"{c['id']}/{part['id']}")
    return counted, report


# --- writing -------------------------------------------------------------------------------------

def dumps_rows(head, key, rows):
    """A JSON object with one array row per line: compact, and diffs stay readable."""
    j = lambda v: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    pre = j(head)[:-1] + ("," if head else "") + j(key) + ":[\n"
    return pre + ",\n".join(j(r) for r in rows) + "\n]}\n"


def write(out_dir, overture, index_countries, files):
    out_dir = Path(out_dir)
    if out_dir.exists():
        for p in sorted(out_dir.rglob("*.json"), reverse=True):
            p.unlink()
    for rel, f in files.items():
        p = out_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(dumps_rows({"schema": 1, "region": f["region"]}, "places", f["places"]),
                     encoding="utf-8", newline="\n")
    (out_dir / "index.json").write_text(
        dumps_rows({"schema": 1, "overture": overture}, "countries", index_countries),
        encoding="utf-8", newline="\n")
    for d in sorted((p for p in out_dir.iterdir() if p.is_dir()), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--src", default=str(ROOT / "data" / "overture" / "world"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "places"))
    ap.add_argument("--report", help="write the city matching report here too")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # place names on a cp1252 console
    overture = json.loads((ROOT / "config" / "places.json").read_text(encoding="utf-8"))["overture"]
    cities = json.loads((ROOT / "config" / "cities.json").read_text(encoding="utf-8"))["cities"]
    rows = read_divisions(a.src)
    print(f"{len(rows)} divisions with an area", flush=True)
    attach_sc(rows)
    assign(rows)
    for r in rows:
        if not r["files"]:   # neither SC nor Overture names a country there (Senkaku, the Spratlys)
            print(f"left out, no country: {r['gers']} {r['subtype']} {r['name']!r}")
    moved = sum(1 for r in rows if r["cs"] != ([] if placeholder(r["country"]) else [r["country"]]))
    print(f"filed differently from Overture's country: {moved}; under two or more countries: "
          f"{sum(1 for r in rows if len(r['cs']) > 1)}", flush=True)
    counted, report = match_cities(rows, cities)
    index_countries, files, stats = build(rows, counted)
    write(a.out, overture, index_countries, files)
    found = sum(1 for l in report if "NOT FOUND" not in l and "already" not in l)
    print(f"{len(files)} files, {len(index_countries)} countries; cities matched {found}/{len(cities)}; "
          f"places with no parent in their file {stats['orphans']}; countries with no root {stats['noRoot']}")
    text = "\n".join(report) + "\n"
    if a.report:
        Path(a.report).write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
