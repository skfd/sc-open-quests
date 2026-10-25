"""Make small name-layer shards for the site's place browsing, per DATA-FORMAT.md "Places and parts".

    <overture-venv>/python tests/fixtures/places/make_places_fixture.py [division.parquet]

Reads the Overture divisions of the spike (CA and DE, data/overture/division.parquet, DuckDB) and
writes tests/fixtures/places/places/ (index.json and a few region files: Ontario and Prince Edward
Island, Berlin, Hamburg and Bremen; the index lists only those) and tests/fixtures/places/data/
(parts/toronto.json and toronto-parts.json, the `cities.toronto.parts` that make_test_site.py puts
into a copy of the real snapshot). Places are the contract's; the part counts are made up (seeded).
Region ids here are the region's place id; the site treats them as opaque.
"""
import json
import random
import sys
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/overture/division.parquet"
if not SRC.exists():   # worktrees have no data/; the main checkout does
    SRC = Path("C:/Users/kk/Code/sc-open-quests/data/overture/division.parquet")
AREA = SRC.with_name("division_area.parquet")
REGIONS = {"CA": ["CA-ON", "CA-PE"], "DE": ["DE-BE", "DE-HH", "DE-HB"]}
ST = {s: i for i, s in enumerate(["country", "dependency", "region", "county", "localadmin", "locality",
                                   "borough", "macrohood", "neighborhood", "microhood"])}
PART_SUBTYPES = {"borough", "locality", "macrohood", "neighborhood", "microhood"}
PARTS_OF = "toronto"
PARTS_MAX = 40

pid = lambda gers: gers.replace("-", "")[:12]
r4 = lambda v: round(v, 4)

c = duckdb.connect()
c.execute("LOAD spatial")
rows = c.execute(f"""
  SELECT id, names.primary, names.common['en'], subtype, country, region, parent_division_id,
         list_transform(hierarchies[1], lambda h: h.division_id),
         split_part((list_filter(sources, lambda x: x.dataset = 'OpenStreetMap')[1]).record_id, '@', 1),
         a.xmin, a.ymin, a.xmax, a.ymax
  FROM '{SRC.as_posix()}' d JOIN (SELECT division_id, min(bbox.xmin) xmin, min(bbox.ymin) ymin, max(bbox.xmax) xmax,
                                         max(bbox.ymax) ymax FROM '{AREA.as_posix()}' GROUP BY 1) a
    ON a.division_id = d.id""").fetchall()   # the bbox of the area, not of the label point
cities = json.load(open(ROOT / "config/cities.json", encoding="utf-8"))["cities"]
city_by_rel = {f"r{x['relation']}": x["id"] for x in cities}

by_gers = {r[0]: r for r in rows}
countries = {r[4]: r for r in rows if r[3] == "country"}
region_div = {r[5]: r for r in rows if r[3] == "region"}

# the counted city's own division, and the parts under it with an OSM source
city_gers = {city_by_rel[r[8]]: r[0] for r in rows if r[8] in city_by_rel and r[3] in ("locality", "county", "region")}
parts = []
tor = city_gers.get(PARTS_OF)
for r in sorted(rows, key=lambda r: r[1] or ""):
    if tor and r[0] != tor and tor in (r[7] or []) and r[3] in PART_SUBTYPES and r[8] and r[8][0] in "rw":
        parts.append(r)
parts = parts[:PARTS_MAX]
part_ids = {r[0] for r in parts}


def counted(r):
    if r[0] in part_ids:
        return f"{PARTS_OF}/{pid(r[0])}"
    cid = city_by_rel.get(r[8])
    return cid if cid and city_gers.get(cid) == r[0] else None


def region_file(code):
    reg = region_div[code]
    members = [r for r in rows if r[5] == code and r[3] != "country"]
    ids = {r[0] for r in members}
    depth = lambda r: len(r[7] or [])
    members.sort(key=lambda r: (depth(r), r[1] or "", r[0]))     # parents before children
    index = {}
    out = []
    for r in members:
        if r[0] == reg[0]:
            parent = -1
        else:
            parent = None
            chain = [r[6]] + list(reversed((r[7] or [])[:-1]))     # parent_division_id, then hierarchies up
            for a in chain:
                if a in index:
                    parent = index[a]
                    break
            if parent is None:
                parent = index.get(reg[0], -1)
        en = r[2] if r[2] and r[2] != r[1] else None
        index[r[0]] = len(out)
        out.append([pid(r[0]), r[1], ST[r[3]], parent, r4(r[9]), r4(r[10]), r4(r[11]), r4(r[12]), en, counted(r)])
    assert len({p[0] for p in out}) == len(out), "two places share an id"
    return pid(reg[0]), reg, out


out_places = HERE / "places"
index = {"schema": 1, "overture": json.load(open(ROOT / "config/places.json"))["overture"], "countries": []}
for cc, codes in REGIONS.items():
    co = countries[cc]
    entry = {"id": pid(co[0]), "name": co[1], "cc": cc.lower(),
             "bbox": [r4(co[9]), r4(co[10]), r4(co[11]), r4(co[12])], "regions": []}
    for code in codes:
        rid, reg, places = region_file(code)
        f = f"{cc.lower()}/{rid}.json"
        (out_places / cc.lower()).mkdir(parents=True, exist_ok=True)
        with open(out_places / f, "w", encoding="utf-8", newline="\n") as fh:
            fh.write('{"schema":1,"region":"%s","places":[\n' % rid)
            fh.write(",\n".join(json.dumps(p, ensure_ascii=False, separators=(",", ":")) for p in places))
            fh.write("\n]}\n")
        entry["regions"].append({"id": rid, "name": reg[1], "file": f, "n": len(places)})
    entry["regions"].sort(key=lambda r: r["name"] or "")
    index["countries"].append(entry)
index["countries"].sort(key=lambda c: c["name"])
with open(out_places / "index.json", "w", encoding="utf-8", newline="\n") as fh:
    json.dump(index, fh, ensure_ascii=False, indent=1)
    fh.write("\n")

# parts of Toronto: the published names, and made-up counts for the snapshot copy
out_data = HERE / "data"
(out_data / "parts").mkdir(parents=True, exist_ok=True)
names = {"schema": 1, "city": PARTS_OF, "parts": [
    {"id": pid(r[0]), "name": r[1], "en": r[2] if r[2] and r[2] != r[1] else None, "subtype": r[3],
     "bbox": [r4(r[9]), r4(r[10]), r4(r[11]), r4(r[12])]} for r in parts]}
with open(out_data / f"parts/{PARTS_OF}.json", "w", encoding="utf-8", newline="\n") as fh:
    json.dump(names, fh, ensure_ascii=False, indent=1)
    fh.write("\n")
snap = sorted((ROOT / "docs/data/ontario/snapshots").glob("*.json"))
city_quests = json.load(open(snap[-1], encoding="utf-8"))["cities"][PARTS_OF]["quests"]
rng = random.Random(7)
counts = {}
for i, r in enumerate(parts):
    share = rng.uniform(0.002, 0.03)
    q = {}
    if i != 3:   # one part with nothing open, kept as {}
        for name, v in sorted(city_quests.items()):
            n = round(v["open"] * share * rng.uniform(0.3, 1.7))
            if n:
                q[name] = n
    counts[pid(r[0])] = q
with open(out_data / f"{PARTS_OF}-parts.json", "w", encoding="utf-8", newline="\n") as fh:
    json.dump(counts, fh, sort_keys=True, separators=(",", ":"))
    fh.write("\n")
print("places:", {c["cc"]: [(r["name"], r["n"]) for r in c["regions"]] for c in index["countries"]})
print("counted cities:", sorted(city_gers), " parts of", PARTS_OF + ":", len(parts))
