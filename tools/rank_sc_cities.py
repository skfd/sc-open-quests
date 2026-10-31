"""Rank cities by StreetComplete changesets in the planet changeset dump.

Usage:
  rank_sc_cities.py [--dump FILE] [--days 365] [--region europe] [--top 40] [--min-pop 50000]
                    [--release 2026-10-21.0] [--rescan] [--workers N]

Three steps, each cached so a rerun only redoes what changed:

scan    The dump (planet changesets-YYMMDD.osm.bz2, default: what `osm_extracts.py path changesets`
        prints) is a pbzip2 file: thousands of independent bz2 streams, sorted by changeset id and so by
        created_at. A binary search over byte offsets finds the first stream inside the window; the rest
        is decompressed in parallel and every changeset whose created_by starts with "StreetComplete"
        (case-sensitive, forks such as "StreetComplete_ee" included and kept apart by created_by) is kept.
        -> .scratch/rank/sc-changesets-YYMMDD.parquet (the whole world, window applied later).
cities  Candidate cities from Overture (data/overture/world): localities of class city or town with
        population >= --min-pop in the region. A locality that is only a node (Berlin, Hamburg, Wien,
        Praha, Köln, ...) borrows the area of its nearest county/localadmin/region ancestor of the same
        name -- that is how the city-states and German kreisfreie Städte come in. OVERRIDES adds the
        ones Overture has no area for at all (London: Greater London is not an Overture division).
stage1  Each changeset's bbox centre goes to the smallest candidate bbox that holds it (exclusive).
stage2  Exact: candidates in descending order of their inclusive bbox count (every centre in the bbox,
        an upper bound of the polygon count) get their land polygon from Overture's S3 release (cached
        in .scratch/rank/geom-<release>.parquet) and are recounted point-in-polygon, inclusively (a town
        inside a bigger counted city counts for both). It stops once the next bbox count is below the
        --top-th exact count, so the top N is exact for the candidate set.

Output: data/rank/sc-cities-<region>-<YYMMDD>.csv and .md. Cities already in config/cities.json
(matched by OSM relation) are marked "counted".
Needs duckdb, shapely 2, numpy, pyarrow; network for the Overture S3 geometry and Overpass (overrides).
The dump is untrusted data: it is only parsed with regular expressions, never executed.
"""
import argparse
import bz2
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / ".scratch" / "rank"
OVERTURE = ROOT / "data" / "overture" / "world"
MAGIC = b"BZh91AY&SY"
SC_TAG = re.compile(rb'k="created_by" v="StreetComplete')
ATTR = re.compile(rb'(\w+)="([^"]*)"')
TAG = re.compile(rb'<tag k="([^"]*)" v="([^"]*)"/>')

# --- regions ----------------------------------------------------------------------------------------

EU = "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split()
EUROPE = EU + ("IS LI NO CH GB AD MC SM VA AL BA ME MK RS XK UA MD BY "
               "FO GI IM JE GG AX SJ").split()
# Russia and Turkey: only their European parts. Russia west of 60 E (the Urals, roughly); Turkey's
# Thrace provinces and Istanbul (both shores: the province is one city).
PARTIAL = {"RU": {"max_lon": 60.0}, "TR": {"regions": ["TR-34", "TR-22", "TR-39", "TR-59"]}}
REGIONS = {"europe": (EUROPE, PARTIAL)}
EUROPE_BOX = (-32.0, 27.0, 70.0, 82.0)   # keeps the Azores, Madeira, the Canaries; drops overseas France

# Cities Overture has no area for. key: (country, locality name) -> OSM relation fetched from Overpass.
OVERRIDES = {("GB", "London"): 175342}   # Greater London; Overture's GB counties are the 33 boroughs
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
USER_AGENT = "sc-open-quests/rank_sc_cities (https://github.com/skfd/sc-open-quests)"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# --- scan -------------------------------------------------------------------------------------------

def first_stream(f, off, size):
    """Offset of the first bz2 stream at or after off, and the created_at of its first changeset."""
    while off < size:
        f.seek(off)
        buf = f.read(1 << 22)
        i = buf.find(MAGIC)
        if i < 0:
            off += len(buf) - len(MAGIC)
            continue
        s = off + i
        f.seek(s)
        d = bz2.BZ2Decompressor()
        try:
            out = d.decompress(f.read(1 << 21))
        except OSError:          # magic bytes inside compressed data: keep looking
            off = s + 1
            continue
        m = re.search(rb'<changeset id="(\d+)" created_at="([^"]+)"', out)
        if m:
            return s, m.group(2).decode()
        off = s + 1
    return size, None


def find_start(path, since):
    """Byte offset of a stream a little before the first changeset created at/after `since`."""
    size = os.path.getsize(path)
    lo, hi = 0, size
    with open(path, "rb") as f:
        while hi - lo > (1 << 22):
            mid = (lo + hi) // 2
            s, ca = first_stream(f, mid, size)
            if ca is None or ca >= since:
                hi = mid
            else:
                lo = mid
        start, ca = first_stream(f, max(0, lo - (1 << 24)), size)   # 16 MB of margin
    if ca is not None and ca >= since:
        sys.exit(f"window start {since} is before the first stream checked ({ca}); scan from 0")
    return start, size, ca


def parse(elem):
    """One <changeset ...>...</changeset> element -> tuple, or None if not StreetComplete."""
    end = elem.find(b">")
    attrs = dict(ATTR.findall(elem[:end]))
    tags = dict(TAG.findall(elem[end:]))
    cb = tags.get(b"created_by", b"")
    if not cb.startswith(b"StreetComplete"):
        return None
    g = lambda k: attrs.get(k)
    fl = lambda k: float(g(k)) if g(k) is not None else None
    return (int(g(b"id")), g(b"created_at").decode(), int(g(b"uid") or -1),
            html.unescape(g(b"user").decode("utf-8", "replace")) if g(b"user") else None,
            int(g(b"num_changes") or 0), fl(b"min_lon"), fl(b"min_lat"), fl(b"max_lon"), fl(b"max_lat"),
            html.unescape(cb.decode("utf-8", "replace")),
            html.unescape(tags.get(b"StreetComplete:quest_type", b"").decode("utf-8", "replace")) or None)


def scan_text(data):
    """All StreetComplete changesets in a text that holds only whole <changeset> elements."""
    out = []
    for m in SC_TAG.finditer(data):
        s = data.rfind(b"<changeset ", 0, m.start())
        e = data.find(b"</changeset>", m.end())
        if s < 0 or e < 0:
            raise ValueError("SC tag outside a whole changeset element")
        r = parse(data[s:e])
        if r:
            out.append(r)
    return out


def scan_chunk(args):
    """Worker: the streams that start in [a, b). Returns (head, rows, tail) where head is the text
    before the first <changeset and tail the text from the last <changeset on."""
    path, a, b, size = args
    with open(path, "rb") as f:
        sa, _ = first_stream(f, a, size) if a else (0, None)
        sb, _ = first_stream(f, b, size) if b < size else (size, None)
        if sa >= sb:
            return b"", [], b"", 0
        f.seek(sa)
        raw = f.read(sb - sa)
    data = bz2.decompress(raw)
    i = data.find(b"<changeset ")
    j = data.rfind(b"<changeset ")
    if i < 0:
        return data, [], b"", len(data)
    return data[:i], scan_text(data[i:j]), data[j:], len(data)


def scan(dump, since, workers):
    t0 = time.time()
    start, size, ca = find_start(dump, since)
    log(f"scan: start at byte {start:,} of {size:,} ({100 * start / size:.1f}%), first created_at {ca}, "
        f"{time.time() - t0:.1f}s")
    step = 8 << 20
    bounds = list(range(start, size, step)) + [size]
    tasks = [(dump, a, b, size) for a, b in zip(bounds, bounds[1:])]
    rows, carry, nbytes = [], b"", 0
    with ProcessPoolExecutor(workers) as ex:
        for k, (head, rs, tail, n) in enumerate(ex.map(scan_chunk, tasks)):
            nbytes += n
            if k == 0:
                head = b""                    # the end of a changeset from before the margin
            joined = carry + head
            if joined.strip():
                rows += scan_text(joined)
            rows += rs
            carry = tail
            if k % 10 == 0:
                log(f"  {k + 1}/{len(tasks)} chunks, {len(rows):,} SC changesets, {nbytes / 1e9:.1f} GB text, "
                    f"{time.time() - t0:.0f}s")
    rows += scan_text(carry)
    log(f"scan: {len(rows):,} SC changesets since {ca}, {nbytes / 1e9:.1f} GB of XML, {time.time() - t0:.0f}s")
    return rows, time.time() - t0


def save_rows(rows, path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    cols = ["id", "created_at", "uid", "user", "num_changes", "min_lon", "min_lat", "max_lon", "max_lat",
            "created_by", "quest_type"]
    t = pa.table({c: [r[i] for r in rows] for i, c in enumerate(cols)})
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(t, path)


# --- cities -----------------------------------------------------------------------------------------

def fold(s):
    s = unicodedata.normalize("NFKD", s or "").lower()
    return "".join(c for c in s if not unicodedata.combining(c))


BAD_ANCESTOR = re.compile(r"^(landkreis|kreis|okres|powiat|district|county|arrondissement|provincia|province|"
                          r"comarca|regionalverband|departement|département|bezirk|region|städteregion|"
                          r"landkreis|amt|verwaltungsgemeinschaft|samtgemeinde|verbandsgemeinde)\b")


def same_name(loc, anc):
    """Does an ancestor's name name the same city? København ~ Københavns Kommune, Αθήνα ~ Δήμος
    Αθηναίων, Edinburgh ~ City of Edinburgh; but not Bad Kreuznach ~ Landkreis Bad Kreuznach."""
    a, b = fold(loc), fold(anc)
    if a == b:
        return True
    if BAD_ANCESTOR.match(b):
        return False
    stem = a[:max(4, len(a) - 2)]
    if " " in a:
        return stem in b
    return any(w.startswith(stem) for w in re.split(r"[\s\-/']+", b))


def load_cities(region, min_pop, con):
    """Candidate cities: one row per area division."""
    ccs, partial = REGIONS[region]
    src = str(OVERTURE).replace("\\", "/")
    allcc = ccs + list(partial)
    inlist = ",".join(f"'{c}'" for c in allcc)
    con.execute(f"""
      CREATE OR REPLACE TABLE area AS
      SELECT division_id, any_value(subtype) AS subtype,
        min(bbox.xmin) AS xmin, min(bbox.ymin) AS ymin, max(bbox.xmax) AS xmax, max(bbox.ymax) AS ymax
      FROM read_parquet('{src}/division_area.parquet') WHERE class = 'land' AND country IN ({inlist})
      GROUP BY division_id""")
    con.execute(f"""
      CREATE OR REPLACE TABLE dv AS
      SELECT id, names."primary" AS name, subtype, class, country, region, population,
        [s.record_id for s in sources if s.dataset = 'OpenStreetMap' AND s.record_id LIKE 'r%'][1] AS rel,
        [x.division_id for x in hierarchies[1]] AS anc, bbox.xmin AS lon, bbox.ymin AS lat
      FROM read_parquet('{src}/division.parquet') WHERE country IN ({inlist})""")
    locs = con.execute(f"""
      SELECT id, name, country, region, population, rel, anc, lon, lat FROM dv
      WHERE subtype = 'locality' AND class IN ('city', 'town') AND coalesce(population, 0) >= {min_pop}
      ORDER BY population DESC""").fetchall()
    divs = {r[0]: r for r in con.execute(
        "SELECT id, name, subtype, rel, population FROM dv WHERE subtype IN ('county','localadmin','region','locality')"
    ).fetchall()}
    areas = {r[0]: r[1:] for r in con.execute("SELECT * FROM area").fetchall()}
    cities, unresolved = {}, []
    for lid, name, cc, reg, pop, rel, anc, lon, lat in locs:
        if cc in partial:
            p = partial[cc]
            if "max_lon" in p and lon > p["max_lon"]:
                continue
            if "regions" in p and reg not in p["regions"]:
                continue
        via, aid = "own", None
        if lid in areas:
            aid = lid
        elif (cc, name) in OVERRIDES:
            via, aid = "override", f"r{OVERRIDES[(cc, name)]}"
        else:
            for a in reversed(anc[:-1] if anc and anc[-1] == lid else anc or []):
                d = divs.get(a)
                if d is None or d[2] == "locality":
                    continue
                if d[2] == "country":
                    break
                if a in areas and same_name(name, d[1]):
                    via, aid = f"{d[2]} {d[1]}", a
                    break
        if aid is None:
            unresolved.append((name, cc, pop))
            continue
        if aid in cities:                    # two localities, one area: keep the bigger one's name
            continue
        arel = rel if via == "own" else (aid if via == "override" else divs[aid][3])
        cities[aid] = dict(area_id=aid, name=name, country=cc, population=pop, via=via,
                           rel=int(arel.split("@")[0][1:]) if arel else None,
                           bbox=areas.get(aid, (None,) * 5)[1:] if via != "override" else None)
    return cities, unresolved


def overpass_geom(rel):
    """A boundary relation's area as a shapely geometry, via Overpass, cached."""
    import shapely
    from shapely.ops import polygonize, unary_union
    p = SCRATCH / f"rel-{rel}.json"
    if not p.exists():
        q = f"[out:json][timeout:120];rel({rel});out geom;"
        for k, url in enumerate(OVERPASS * 2):
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(),
                                         headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    body = r.read()
                json.loads(body)["elements"][0]
                break
            except Exception as e:
                log(f"overpass {url}: {e}")
                time.sleep(5 * k)
        else:
            sys.exit(f"relation {rel}: every Overpass endpoint failed")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
    e = json.loads(p.read_text(encoding="utf-8"))["elements"][0]
    lines = {"outer": [], "inner": []}
    for m in e["members"]:
        if m["type"] == "way" and m.get("role") in lines:
            lines[m["role"]].append(shapely.LineString([(g["lon"], g["lat"]) for g in m["geometry"]]))
    outer = unary_union(list(polygonize(unary_union(lines["outer"]))))
    inner = unary_union(list(polygonize(unary_union(lines["inner"])))) if lines["inner"] else None
    return outer.difference(inner) if inner is not None else outer


def overture_geoms(ids, countries, release, con):
    """Land polygons of Overture divisions as shapely geometries, from S3, cached per release."""
    import shapely
    cache = SCRATCH / f"geom-{release}.parquet"
    have = {}
    if cache.exists():
        for i, w in con.execute(f"SELECT division_id, wkb FROM '{cache.as_posix()}'").fetchall():
            have[i] = w
    need = [i for i in ids if i not in have]
    if need:
        t0 = time.time()
        con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
        base = f"s3://overturemaps-us-west-2/release/{release}/theme=divisions/type=division_area/*"
        idl = ",".join(f"'{i}'" for i in need)
        ccl = ",".join(f"'{c}'" for c in countries)
        rows = con.execute(f"""
          SELECT division_id, ST_AsWKB(ST_Union_Agg(geometry))
          FROM read_parquet('{base}', hive_partitioning=1)
          WHERE country IN ({ccl}) AND class = 'land' AND division_id IN ({idl})
          GROUP BY division_id""").fetchall()
        for i, w in rows:
            have[i] = bytes(w)
        log(f"stage2: fetched {len(rows)} of {len(need)} polygons from Overture {release}, {time.time() - t0:.0f}s")
        import pyarrow as pa
        import pyarrow.parquet as pq
        cache.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.table({"division_id": list(have), "wkb": list(have.values())}), cache)
    return {i: shapely.from_wkb(have[i]) for i in ids if i in have}


def region_geom(region, release, con):
    """The region's land, simplified to ~1 km, for the region-wide total only. Russia is cut at 60 E;
    Turkey is its PARTIAL provinces."""
    import shapely
    cache = SCRATCH / f"region-{region}-{release}.wkb"
    if not cache.exists():
        t0 = time.time()
        ccs, partial = REGIONS[region]
        con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
        base = f"s3://overturemaps-us-west-2/release/{release}/theme=divisions/type=division_area/*"
        whole = ccs + [c for c, p in partial.items() if "max_lon" in p]
        regs = [r for p in partial.values() for r in p.get("regions", [])]
        rids = [r[0] for r in con.execute(
            "SELECT id FROM dv WHERE subtype = 'region' AND region IN (" + ",".join(f"'{r}'" for r in regs) + ")"
        ).fetchall()] if regs else []
        cond = f"(subtype IN ('country', 'dependency') AND country IN ({','.join(repr(c) for c in whole)}))"
        if rids:
            cond += f" OR division_id IN ({','.join(repr(r) for r in rids)})"
        rows = con.execute(f"""
          SELECT country, ST_AsWKB(ST_SimplifyPreserveTopology(geometry, 0.01))
          FROM read_parquet('{base}', hive_partitioning=1) WHERE class = 'land' AND ({cond})""").fetchall()
        parts = []
        for cc, w in rows:
            g = shapely.from_wkb(bytes(w))
            p = partial.get(cc, {})
            if "max_lon" in p:
                g = g.intersection(shapely.box(-180, -90, p["max_lon"], 90))
            parts.append(g)
        g = shapely.union_all(parts).intersection(shapely.box(*EUROPE_BOX))   # no overseas France
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(shapely.to_wkb(g))
        log(f"region: {len(rows)} country/province polygons from Overture {release}, {time.time() - t0:.0f}s")
    return shapely.from_wkb(cache.read_bytes())


# --- ranking ----------------------------------------------------------------------------------------

def dump_default():
    out = subprocess.run([sys.executable, str(ROOT.parent / "osm-extracts" / "osm_extracts.py"), "path",
                          "changesets"], capture_output=True, text=True)
    p = out.stdout.strip()
    if out.returncode or not p.endswith(".osm.bz2"):
        sys.exit(f"no changeset dump: {out.stdout}{out.stderr}")
    return p


def dump_date(path):
    with open(path, "rb") as f:
        head = bz2.BZ2Decompressor().decompress(f.read(1 << 18))[:2000].decode()
    m = re.search(r'timestamp="([^"]+)"', head)
    return dt.datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--region", default="europe", choices=sorted(REGIONS))
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--min-pop", type=int, default=50000)
    ap.add_argument("--release", default="2026-10-21.0")
    ap.add_argument("--rescan", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--out", default=str(ROOT / "data" / "rank"))
    a = ap.parse_args(argv)

    import duckdb
    import numpy as np
    import shapely

    dump = a.dump or dump_default()
    m = re.search(r"changesets-(\d{6})\.osm\.bz2$", dump)
    tag = m.group(1) if m else "dump"
    until = dump_date(dump)
    since = until - dt.timedelta(days=a.days)
    since_s, until_s = since.strftime("%Y-%m-%dT%H:%M:%SZ"), until.strftime("%Y-%m-%dT%H:%M:%SZ")
    log(f"dump {dump}, window {since_s} .. {until_s}")

    cache = SCRATCH / f"sc-changesets-{tag}.parquet"
    timing = {}
    meta_p = cache.with_suffix(".json")
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    if a.rescan or not cache.exists() or meta.get("since", "9") > since_s:
        rows, timing["scan"] = scan(dump, since_s, a.workers)
        save_rows(rows, cache)
        meta = {"since": since_s, "dump": dump, "scan_seconds": round(timing["scan"], 1)}
        meta_p.write_text(json.dumps(meta, indent=1))
    else:
        log(f"scan: cached {cache} (took {meta.get('scan_seconds')}s)")
        timing["scan"] = meta.get("scan_seconds")

    con = duckdb.connect()
    t0 = time.time()
    con.execute(f"""
      CREATE TABLE cs AS SELECT *, (min_lon + max_lon) / 2 AS lon, (min_lat + max_lat) / 2 AS lat,
        created_by LIKE 'StreetComplete %' OR created_by = 'StreetComplete' AS main
      FROM '{cache.as_posix()}'
      WHERE created_at >= '{since_s}' AND created_at < '{until_s}'""")
    world = con.execute("""SELECT count(*), count(*) FILTER (WHERE min_lon IS NULL), sum(num_changes),
                           count(DISTINCT uid) FROM cs""").fetchone()
    forks = con.execute("""SELECT regexp_extract(created_by, '^(\\S+)'), count(*) FROM cs
                           GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    log(f"window: {world[0]:,} SC changesets in the world ({world[1]:,} without bbox), {world[3]:,} mappers; "
        f"by app: {forks}")

    cities, unresolved = load_cities(a.region, a.min_pop, con)
    # cities already on the site: count the relation the site counts (Bremen: the county r62559, not
    # Overture's locality r2088648), under the site's name
    counted = {(c["relation"]): c for c in json.loads((ROOT / "config/cities.json").read_text(encoding="utf-8"))["cities"]}
    ccodes = set(REGIONS[a.region][0]) | set(REGIONS[a.region][1])
    for rel, c in counted.items():
        cc = c["countryCodes"][0][:2]
        if cc not in ccodes:
            continue
        hit = con.execute(f"""SELECT dv.id, area.xmin, area.ymin, area.xmax, area.ymax FROM dv JOIN area ON area.division_id = dv.id
                              WHERE split_part(dv.rel, '@', 1) = 'r{rel}' LIMIT 1""").fetchone()
        if not hit:
            log(f"counted city {c['name']} r{rel}: no Overture area")
            continue
        for k in [k for k, v in cities.items() if v["country"] == cc and fold(v["name"]) == fold(c["name"])]:
            del cities[k]
        cities[hit[0]] = dict(area_id=hit[0], name=c["name"], country=cc, population=c.get("population"),
                              via="counted relation", rel=rel, bbox=hit[1:])
    # overrides: bbox from the relation geometry
    over_geom = {}
    for aid, c in cities.items():
        if c["via"] == "override":
            g = overpass_geom(int(aid[1:]))
            over_geom[aid] = g
            c["bbox"] = tuple(g.bounds)
    log(f"cities: {len(cities)} candidates (min pop {a.min_pop:,}); {len(unresolved)} localities without an "
        f"area, biggest: {sorted(unresolved, key=lambda r: -(r[2] or 0))[:12]}")

    import pandas as pd
    cdf = pd.DataFrame([dict(area_id=k, xmin=c["bbox"][0], ymin=c["bbox"][1], xmax=c["bbox"][2],
                             ymax=c["bbox"][3]) for k, c in cities.items()])
    cdf["barea"] = (cdf.xmax - cdf.xmin) * (cdf.ymax - cdf.ymin)
    con.register("cdf", cdf)
    # explode candidate bboxes into 1-degree cells to make the containment join an equi-join
    con.execute("""
      CREATE TABLE cand AS SELECT c.*, cx, cy FROM cdf c,
        range(floor(xmin)::INT, floor(xmax)::INT + 1) t1(cx), range(floor(ymin)::INT, floor(ymax)::INT + 1) t2(cy)""")
    con.execute("""
      CREATE TABLE hit AS SELECT cs.id, cand.area_id, cand.barea FROM cs JOIN cand
        ON floor(cs.lon)::INT = cand.cx AND floor(cs.lat)::INT = cand.cy
        AND cs.lon BETWEEN cand.xmin AND cand.xmax AND cs.lat BETWEEN cand.ymin AND cand.ymax
      WHERE cs.lon IS NOT NULL""")
    agg = lambda src: f"""SELECT area_id, count(*) AS cs, sum(num_changes) AS edits, count(DISTINCT uid) AS mappers,
                          count(*) FILTER (WHERE NOT main) AS forks
                          FROM {src} JOIN cs USING (id) GROUP BY area_id"""
    s1 = {r[0]: r[1:] for r in con.execute(agg(
        "(SELECT id, arg_min(area_id, barea) AS area_id FROM hit GROUP BY id)")).fetchall()}
    incl = {r[0]: r[1:] for r in con.execute(agg("hit")).fetchall()}
    timing["stage1"] = time.time() - t0
    in_cities = con.execute("SELECT count(DISTINCT id) FROM hit").fetchone()[0]
    log(f"stage1: {in_cities:,} SC changesets in some candidate bbox, {timing['stage1']:.1f}s")

    # stage 2
    t0 = time.time()
    pts = con.execute("SELECT id, lon, lat, num_changes, uid, main, quest_type FROM cs WHERE lon IS NOT NULL").fetchnumpy()
    qt = pd.Series(pts["quest_type"]).fillna("?")
    order = sorted(cities, key=lambda k: -incl.get(k, (0,))[0])
    forced = [k for k, v in cities.items() if v["rel"] in counted]
    exact, quests, geoms_all, done, batch, bound = {}, {}, {}, 0, 120, None
    ccs = REGIONS[a.region][0] + list(REGIONS[a.region][1])

    def count(ids):
        geoms = overture_geoms([i for i in ids if not i.startswith("r")], ccs, a.release, con)
        geoms.update({i: over_geom[i] for i in ids if i in over_geom})
        for i in ids:
            g = geoms.get(i)
            if g is None:
                log(f"stage2: no polygon for {cities[i]['name']} {i}")
                continue
            geoms_all[i] = g
            x0, y0, x1, y1 = g.bounds
            sel = (pts["lon"] >= x0) & (pts["lon"] <= x1) & (pts["lat"] >= y0) & (pts["lat"] <= y1)
            idx = np.nonzero(sel)[0]
            shapely.prepare(g)
            inside = idx[shapely.contains_xy(g, pts["lon"][idx], pts["lat"][idx])]
            exact[i] = (len(inside), int(pts["num_changes"][inside].sum()), len(np.unique(pts["uid"][inside])),
                        int((~pts["main"][inside]).sum()))
            vc = qt.iloc[inside].value_counts()
            quests[i] = "; ".join(f"{q} {100 * n / max(1, len(inside)):.0f}%" for q, n in vc.head(3).items())

    while done < len(order):
        kth = sorted((v[0] for v in exact.values()), reverse=True)[a.top - 1] if len(exact) >= a.top else -1
        if incl.get(order[done], (0,))[0] < kth:
            bound = (incl.get(order[done], (0,))[0], kth)
            break
        count(order[done:done + batch])
        done += batch
    count([k for k in forced if k not in exact])
    log(f"stage2: stopped after {len(exact)} polygons: next bbox count {bound[0] if bound else '-'} < "
        f"#{a.top} exact count {bound[1] if bound else '-'}")
    # which evaluated city holds another's representative point (a town inside a bigger city)
    inside_of = {}
    for i, g in geoms_all.items():
        p = g.representative_point()
        for j, h in geoms_all.items():
            if j != i and h.area > g.area and h.contains(p):
                inside_of[i] = cities[j]["name"]
    timing["stage2"] = time.time() - t0
    log(f"stage2: {len(exact)} polygons counted, {timing['stage2']:.0f}s")

    t0 = time.time()
    rg = region_geom(a.region, a.release, con)
    shapely.prepare(rg)
    inreg = shapely.contains_xy(rg, pts["lon"], pts["lat"])
    region_total = (int(inreg.sum()), int(pts["num_changes"][inreg].sum()), len(np.unique(pts["uid"][inreg])),
                    int((~pts["main"][inreg]).sum()))
    timing["region"] = time.time() - t0
    log(f"region {a.region}: {region_total[0]:,} SC changesets ({region_total[3]:,} forks), "
        f"{region_total[2]:,} mappers; world {world[0]:,}; {timing['region']:.0f}s")

    rows = []
    for i, v in exact.items():
        c = cities[i]
        s1v = s1.get(i, (0, 0, 0, 0))
        rows.append(dict(
            city=c["name"], country=c["country"], osm_relation=c["rel"], population=c["population"],
            sc_changesets=v[0], edits=v[1], mappers=v[2], fork_changesets=v[3],
            per_1k=round(1000 * v[0] / c["population"], 1) if c["population"] else None,
            stage1_changesets=s1v[0], stage1_bbox_inclusive=incl.get(i, (0,))[0],
            counted="yes" if c["rel"] in counted else "", inside=inside_of.get(i, ""),
            top_quests=quests.get(i, ""), area_from=c["via"], overture_area_id=i))
    rows.sort(key=lambda r: -r["sc_changesets"])
    for k, r in enumerate(rows, 1):
        r["rank"] = k
    res = pd.DataFrame(rows)
    # stage-1 rank for the comparison
    s1rank = {k: n for n, (k, _) in enumerate(sorted(s1.items(), key=lambda kv: -kv[1][0]), 1)}
    res["stage1_rank"] = [s1rank.get(r["overture_area_id"]) for r in rows]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    base = out / f"sc-cities-{a.region}-{tag}"
    cols = ["rank", "city", "country", "osm_relation", "population", "sc_changesets", "edits", "mappers",
            "per_1k", "fork_changesets", "stage1_changesets", "stage1_rank", "stage1_bbox_inclusive", "counted",
            "inside", "top_quests", "area_from", "overture_area_id"]
    res[cols].to_csv(base.with_suffix(".csv"), index=False, encoding="utf-8")
    res["osm_relation"] = res["osm_relation"].astype("Int64")
    top = pd.concat([res.head(a.top), res.iloc[a.top:][res.iloc[a.top:]["counted"] == "yes"]])
    s1top = {k for k, _ in sorted(s1.items(), key=lambda kv: -kv[1][0])[:a.top]}
    both = len(s1top & set(res.head(a.top)["overture_area_id"]))
    diff = (res.head(a.top)["sc_changesets"] - res.head(a.top)["stage1_changesets"]) / res.head(a.top)["sc_changesets"]
    cmp_line = (f"Stage 1 vs exact: {both} of the exact top {a.top} are in the stage-1 top {a.top}; per city the stage-1 "
                f"count differs from the exact one by median {100 * diff.abs().median():.0f}%, "
                f"max {100 * diff.abs().max():.0f}%.")
    log(cmp_line)
    md = [f"# StreetComplete changesets per city, {a.region}, {since_s[:10]} .. {until_s[:10]}", "",
          f"Dump changesets-{tag}. SC changesets in the window: {world[0]:,} worldwide "
          f"({world[3]:,} mappers), {region_total[0]:,} in {a.region} ({region_total[2]:,} mappers); "
          f"StreetComplete_ee and other forks included ({region_total[3]:,} in {a.region}).", "",
          "Exact counts: changeset bbox centre inside the city's land polygon (Overture), each city on its own, "
          f"so a town inside a bigger city counts for both. Stage 1: the centre goes to the smallest candidate "
          f"bbox (localities of class city/town, population >= {a.min_pop:,}). \"counted\": already on the site.", "",
          cmp_line, "",
          "| # | city | country | OSM relation | population | SC changesets | edits | mappers | per 1k people "
          "| stage 1 (rank) | |",
          "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for r in top.to_dict("records"):
        md.append(f"| {r['rank']} | {r['city']} | {r['country']} | {'' if pd.isna(r['osm_relation']) else r['osm_relation']} | "
                  f"{r['population']:,} | {r['sc_changesets']:,} | {r['edits']:,} | {r['mappers']:,} | "
                  f"{r['per_1k'] if r['per_1k'] is not None else ''} | {r['stage1_changesets']:,} "
                  f"({r['stage1_rank'] or '-'}) | {'counted' if r['counted'] else ''}"
                  f"{(' inside ' + r['inside']) if r['inside'] else ''} |")
    base.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log(f"wrote {base}.csv/.md; timing {timing}")
    print("\n".join(md))


if __name__ == "__main__":
    main()
