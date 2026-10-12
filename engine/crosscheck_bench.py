"""Independent cross-check of the Kotlin spike with pyosmium (spike only).

1. Counts AddBenchBackrest-matching *nodes* in the spike bbox and in the Toronto polygon, with the
   filter logic hand-written in Python.
2. Counts AddBusStopShelter nodes in Toronto (exercises `older` with America/Toronto dates).
3. Compares version and timestamp of every node in out/spike-matches.tsv against pyosmium, to
   check the PBF DenseInfo delta decoding and date_granularity handling.
"""
import datetime as dt
import json
import re
from zoneinfo import ZoneInfo

import osmium

PBF = "C:/Users/kk/Code/toronto-streets-osm/data/osm/ontario-latest.osm.pbf"
BOUNDARIES = "C:/Users/kk/Code/ontario-farmland/cache/boundaries.json"
BBOX = (43.58, -79.64, 43.86, -79.11)

rel = next(e for e in json.load(open(BOUNDARIES))["elements"] if e["id"] == 324211)
segs = []
for m in rel["members"]:
    if m["type"] == "way":
        g = m["geometry"]
        segs += [(g[i]["lat"], g[i]["lon"], g[i + 1]["lat"], g[i + 1]["lon"]) for i in range(len(g) - 1)]


def in_city(lat, lon):
    inside = False
    for y1, x1, y2, x2 in segs:
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def bench_backrest(t):
    return (t.get("amenity") == "bench"
            and t.get("area") in (None, "no")
            and "backrest" not in t
            and "bench:type" not in t
            and t.get("seasonal") in (None, "no")
            and t.get("access") not in ("private", "no"))


bbox_n = city_n = 0
fp = osmium.FileProcessor(PBF, osmium.osm.NODE).with_filter(osmium.filter.TagFilter(("amenity", "bench")))
for n in fp:
    t = dict(n.tags)
    if not bench_backrest(t):
        continue
    lat, lon = n.location.lat, n.location.lon
    if BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]:
        bbox_n += 1
    if in_city(lat, lon):
        city_n += 1
print(f"pyosmium AddBenchBackrest nodes: bbox={bbox_n} toronto={city_n}")

TZ = ZoneInfo("America/Toronto")
# RelativeDate: now minus (4 * 365.25 * 24) hours in the system zone, then the date
cutoff = (dt.datetime.now(TZ) - dt.timedelta(hours=int(4 * 365.25 * 24))).date()
CHECK_KEYS = ["shelter:check_date", "check_date:shelter", "shelter:lastcheck", "lastcheck:shelter",
              "shelter:last_checked", "last_checked:shelter"]


def check_date(v):
    m = re.fullmatch(r"([0-9]{4})-([0-9]{2})(?:-([0-9]{2}))?", v or "")
    if not m:
        return None
    try:
        return dt.date(int(m[1]), int(m[2]), int(m[3] or 1))
    except ValueError:
        return None


def shelter_quest(t, edited):
    if not (t.get("public_transport") == "platform"
            or (t.get("highway") == "bus_stop" and t.get("public_transport") != "stop_position")
            or t.get("highway") == "hitchhiking"):
        return False
    if t.get("physically_present") == "no" or t.get("naptan:BusStopType") == "HAR":
        return False
    if t.get("access") in ("no", "private") or "covered" in t:
        return False
    if t.get("location") in ("underground", "indoor") or t.get("indoor") == "yes" or t.get("tunnel") == "yes":
        return False
    if "level" in t:
        try:
            if float(t["level"]) < 0:
                return False
        except ValueError:
            return False  # SC: unparsable number -> `level >= 0` is false
    if "shelter" not in t:
        return True
    if edited.astimezone(TZ).date() < cutoff:
        return True
    return any((d := check_date(t.get(k))) is not None and d < cutoff for k in CHECK_KEYS)


shelter_n = 0
fp = osmium.FileProcessor(PBF, osmium.osm.NODE).with_filter(
    osmium.filter.KeyFilter("highway", "public_transport"))
for n in fp:
    lat, lon = n.location.lat, n.location.lon
    if not (43.57 <= lat <= 43.86 and -79.64 <= lon <= -79.11):
        continue
    if shelter_quest(dict(n.tags), n.timestamp) and in_city(lat, lon):
        shelter_n += 1
print(f"pyosmium AddBusStopShelter nodes: toronto={shelter_n} (cutoff {cutoff})")

kotlin = {}
for line in list(open("out/spike-matches.tsv"))[1:]:
    q, typ, id_, ver, ts = line.split("\t")[:5]
    if typ == "node":
        kotlin[int(id_)] = (int(ver), int(ts))
seen = mismatch = 0
fp = osmium.FileProcessor(PBF, osmium.osm.NODE).with_filter(osmium.filter.IdFilter(kotlin.keys()))
for n in fp:
    seen += 1
    ver, ts = kotlin[n.id]
    py_ts = int(n.timestamp.timestamp() * 1000)
    if (ver, ts) != (n.version, py_ts):
        mismatch += 1
        if mismatch <= 5:
            print("mismatch", n.id, (ver, ts), (n.version, py_ts))
print(f"node version/timestamp check: {seen} of {len(kotlin)} matched nodes found, {mismatch} mismatches")

# same for ways (non-dense Info path)
kotlin_ways = {}
for line in list(open("out/spike-matches.tsv"))[1:]:
    q, typ, id_, ver, ts = line.split("\t")[:5]
    if typ == "way":
        kotlin_ways[int(id_)] = (int(ver), int(ts))
seen = mismatch = 0
fp = osmium.FileProcessor(PBF, osmium.osm.WAY).with_filter(osmium.filter.IdFilter(kotlin_ways.keys()))
for w in fp:
    seen += 1
    if kotlin_ways[w.id] != (w.version, int(w.timestamp.timestamp() * 1000)):
        mismatch += 1
print(f"way version/timestamp check: {seen} of {len(kotlin_ways)} matched ways found, {mismatch} mismatches")
