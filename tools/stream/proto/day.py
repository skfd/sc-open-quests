"""Step 5 of the stream: one planet day of minute diffs through tier 1, on the location store.

  day.py prep                 tier-1 quests file, the world as one "city"
  day.py build --store F      the 1,415 minute files of 11-08 in order: every node version moves the store,
                              every way version reads its nodes' places from it at that minute. Writes
                              priors.osm.pbf (the version before the day of every touched element) and
                              versions.osm.pbf (every version of the day), each version its own element.
                              The store ends at 11-09; undo.pickle takes it back (restore).
  day.py restore --store F    the store back to 11-08T00Z
  day.py sample --store F --clip X.osm.pbf     every 50th node of a clip against the store
  day.py count                the engine over both files: the world (tier 1, gated by position, no notes,
                              UTC) and europe-west exactly as step 1 ran it
  day.py events               events of the world; the europe-west run against step 1's and the dumps

.scratch/store, gitignored. The engine is not changed.
"""
import argparse
import gzip
import json
import math
import os
import pickle
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from array import array
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import osmium
import osmium.index

S = Path(__file__).parent
ROOT = S.parent.parent
REPLAY = ROOT / ".scratch" / "stream-replay"
FLIPS = ROOT / ".scratch" / "diff-flips"
OLD_D, NEW_D = "2026-11-08", "2026-11-09"
NOTES = ROOT / "data" / "notes" / "planet-notes-261109-europe-west.jsonl"
NODE_BASE, WAY_BASE = 10**12, 10**11
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:6.0f} s] {msg}", flush=True)


def memory():
    """peak private memory and peak working set of this process, MB (the working set counts the
    store's mapped pages)"""
    import ctypes
    import ctypes.wintypes as w

    class PMC(ctypes.Structure):
        _fields_ = [("cb", w.DWORD), ("PageFaultCount", w.DWORD)] + [(n, ctypes.c_size_t) for n in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
            "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
    c = PMC()
    c.cb = ctypes.sizeof(c)
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = w.HANDLE
    ps = ctypes.windll.psapi.GetProcessMemoryInfo
    ps.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD]
    ps(k.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return f"peak private memory {c.PeakPagefileUsage / 2**20:,.0f} MB, peak working set {c.PeakWorkingSetSize / 2**20:,.0f} MB, CPU {time.process_time():.0f} s"


def tiers():
    src = (ROOT / "engine/src/main/kotlin/ported/AreaQuests.kt").read_text(encoding="utf-8")
    area = set(re.findall(r"^\s+de\.westnordost[\w.]*\.(\w+),?\s*$", src, re.M))
    names = [q["name"] for q in json.loads((ROOT / "data/quests/v64.1.json").read_text(encoding="utf-8"))["quests"]]
    return {n for n in names if n not in area}, area


def prep():
    tier1, area = tiers()
    q = json.loads((ROOT / "data/quests/v64.1.json").read_text(encoding="utf-8"))
    q["quests"] = [x for x in q["quests"] if x["name"] in tier1 and x.get("kind") != "note"]
    q["questCount"] = len(q["quests"])
    # not to 180: the country lookup wraps a box's east edge at 180 to -180 and so takes the whole world for
    # a sliver on the antimeridian, which gates every country-limited quest wrongly
    E = 179.9999999
    ring = [(-90.0, -E), (-90.0, E), (90.0, E), (90.0, -E), (-90.0, -E)]
    (S / "world.json").write_text(json.dumps({
        "type": "relation", "id": 990000000,
        "bounds": {"minlat": -90.0, "minlon": -E, "maxlat": 90.0, "maxlon": E},
        "members": [{"type": "way", "ref": 990000000, "role": "outer",
                     "geometry": [{"lat": a, "lon": b} for a, b in ring]}],
        "tags": {"name": "world"}}))
    (S / "cities-world.json").write_text(json.dumps({"cities": [{
        "id": "world", "name": "world", "relation": 990000000, "adminLevel": 2, "countryCodes": None,
        "timeZone": "UTC", "population": 1, "landAreaKm2": 1.0,
        "boundary": ".scratch/store/world.json", "region": "world"}]}))
    log(f"{len(q['quests'])} tier-1 quests (the note quest and the {len(area)} area quests left out)")


class Refs:
    """A way's nodes as synthetic nodes: one per (node, place), so a node that moves within the day
    is in each way version where it was at that minute."""

    def __init__(self):
        self.sid = {}
        self.lat = array("d")
        self.lon = array("d")

    def of(self, nid, lat, lon):
        key = (nid, lat, lon)
        s = self.sid.get(key)
        if s is None:
            s = len(self.lat) + 1
            self.sid[key] = s
            self.lat.append(lat)
            self.lon.append(lon)
        return s


def place(idx, refs, wrefs, stats):
    """the way's refs as synthetic node ids, or None when a node has no place in the store"""
    out = []
    for r in wrefs:
        try:
            loc = idx.get(r)
        except KeyError:
            stats["missing"] += 1
            return None
        if not loc.valid():
            stats["missing"] += 1
            return None
        out.append(refs.of(r, loc.lat, loc.lon))
    stats["lookups"] += len(out)
    return out


def write_pbf(path, stamp, refs, nodes, ways):
    header = osmium.io.Header()
    header.set("osmosis_replication_timestamp", stamp)
    header.set("sorting", "Type_then_ID")
    w = osmium.SimpleWriter(str(path), header=header, overwrite=True)
    N = osmium.osm.mutable.Node
    for i in range(len(refs.lat)):
        w.add_node(N(id=i + 1, version=1, location=(refs.lon[i], refs.lat[i])))
    for sid, version, ts, tags, lat, lon in nodes:
        w.add_node(N(id=sid, version=version, timestamp=ts, tags=tags, location=(lon, lat)))
    for sid, version, ts, tags, srefs in ways:
        w.add_way(osmium.osm.mutable.Way(id=sid, version=version, timestamp=ts, tags=tags, nodes=srefs))
    w.close()
    log(f"wrote {path.name} ({path.stat().st_size / 1e6:.1f} MB): {len(refs.lat):,} way nodes, {len(nodes):,} nodes, {len(ways):,} ways")


def state_of(store):
    p = Path(str(store) + ".state")
    return p.read_text().strip() if p.exists() else "unknown"


def build(store):
    assert state_of(store) == "2026-11-08T00:00:00Z", f"the store is at {state_of(store)}; restore it first"
    first, last, _, _ = map(int, (REPLAY / "range.txt").read_text().split())
    idx = osmium.index.create_map(f"dense_file_array,{store}")
    with open(S / "priors-1108.pickle", "rb") as f:
        priors = pickle.load(f)

    # the versions before the day, placed where the store has them at 11-08T00Z
    t = time.time()
    refs, stats = Refs(), Counter()
    nodes, ways, index = [], [], []
    for n, (nid, (version, ts, tags, lat, lon)) in enumerate(sorted(priors["nodes"].items()), 1):
        nodes.append((NODE_BASE + n, version, ts, tags, lat, lon))
        index.append(("node", nid, version, NODE_BASE + n))
    n = 0
    for wid, (version, ts, tags, wrefs) in sorted(priors["ways"].items()):
        srefs = place(idx, refs, wrefs, stats)
        if srefs is None:
            index.append(("way", wid, version, "unplaced"))
            continue
        n += 1
        ways.append((WAY_BASE + n, version, ts, tags, srefs))
        index.append(("way", wid, version, WAY_BASE + n))
    log(f"priors: {len(nodes):,} tagged nodes, {len(ways):,} tagged ways placed with {stats['lookups']:,} lookups in "
        f"{time.time() - t:.0f} s; ways with a node the store lacks: {stats['missing']:,}")
    write_pbf(S / "priors.osm.pbf", f"{OLD_D}T00:00:00Z", refs, nodes, ways)
    with open(S / "priors-index.tsv", "w", encoding="utf-8") as f:
        for r in index:
            f.write("\t".join(map(str, r)) + "\n")
    del priors, nodes, ways, index

    # the day
    refs, stats = Refs(), Counter()
    nodes, ways, index = [], [], []
    undo_id, undo_lat, undo_lon = array("q"), array("d"), array("d")
    Loc = osmium.osm.Location
    n_all = Counter()
    kinds = Counter()
    slowest = (0.0, 0, 0)
    order_breaks = 0
    t_parse = t_set = t_get = 0.0
    nn = wn = 0
    t_day = time.time()
    for seq in range(first, last + 1):
        t = t_file = time.time()
        f_nodes, f_ways, gone = [], [], set()
        seen_way = False
        for o in osmium.FileProcessor(str(REPLAY / "minute" / f"{seq}.osc.gz")):
            if o.is_node():
                if seen_way:
                    order_breaks += 1
                valid = o.location.valid()
                f_nodes.append((o.id, o.version, o.visible, o.changeset, o.timestamp,
                                {t_.k: t_.v for t_ in o.tags} if len(o.tags) else None,
                                o.location.lat if valid else None, o.location.lon if valid else None))
            elif o.is_way():
                seen_way = True
                f_ways.append((o.id, o.version, o.visible, o.changeset, o.timestamp,
                               {t_.k: t_.v for t_ in o.tags} if len(o.tags) else None, [x.ref for x in o.nodes]))
            else:
                n_all["relation"] += 1
        t_parse += time.time() - t

        t = time.time()
        for nid, version, visible, cs, ts, tags, lat, lon in f_nodes:
            n_all["node"] += 1
            try:
                old = idx.get(nid)
                olat, olon = (old.lat, old.lon) if old.valid() else (math.nan, math.nan)
            except KeyError:
                olat = olon = math.nan
            undo_lat.append(olat)
            undo_lon.append(olon)
            undo_id.append(nid)
            alive = visible and lat is not None
            was = not math.isnan(olat)
            kinds["created" if alive and not was else "deleted" if was and not alive else
                  "neither before nor after" if not alive else
                  "same place" if abs(olat - lat) < 1e-9 and abs(olon - lon) < 1e-9 else "moved"] += 1
            if alive:
                idx.set(nid, Loc(lon, lat))
                gone.discard(nid)
            else:
                gone.add(nid)  # after this file's ways: a way version of the same minute may still name it
            sid = None
            if alive and tags:
                nn += 1
                sid = NODE_BASE + nn
                nodes.append((sid, version, ts, tags, lat, lon))
            index.append(("node", nid, version, seq, cs, int(visible), sid))
        t_set += time.time() - t

        t = time.time()
        for wid, version, visible, cs, ts, tags, wrefs in f_ways:
            n_all["way"] += 1
            sid = None
            if visible and tags and wrefs:
                srefs = place(idx, refs, wrefs, stats)
                if srefs is None:
                    sid = "unplaced"
                else:
                    wn += 1
                    sid = WAY_BASE + wn
                    ways.append((sid, version, ts, tags, srefs))
            index.append(("way", wid, version, seq, cs, int(visible), sid))
        t_get += time.time() - t
        t = time.time()
        for nid in gone:
            idx.set(nid, Loc())
        t_set += time.time() - t
        slowest = max(slowest, (time.time() - t_file, seq, len(f_nodes) + len(f_ways)))
        if (seq - first) % 200 == 199:
            log(f"  minute {seq - first + 1:,} of {last - first + 1:,}")
    log(f"the day in {time.time() - t_day:.0f} s: parsing {t_parse:.0f} s, node versions into the store (a read and a "
        f"write each) {t_set:.0f} s, ways placed {t_get:.0f} s with {stats['lookups']:,} lookups")
    log(f"versions {dict(n_all)}; tagged and alive: {len(nodes):,} nodes, {len(ways):,} ways; way versions with a node "
        f"the store lacks: {stats['missing']:,}; files with a node after a way: {order_breaks}")
    log(f"node versions against the store: {dict(kinds)}; the slowest minute file took {slowest[0]:.1f} s "
        f"(sequence {slowest[1]}, {slowest[2]:,} versions)")
    log(memory())
    Path(str(store) + ".state").write_text("2026-11-09 (the day replayed; undo.pickle takes it back)")
    del idx
    with open(S / "undo.pickle", "wb") as f:
        pickle.dump((undo_id, undo_lat, undo_lon), f)
    write_pbf(S / "versions.osm.pbf", f"{NEW_D}T00:00:00Z", refs, nodes, ways)
    with open(S / "index.tsv", "w", encoding="utf-8") as f:
        for r in index:
            f.write("\t".join(map(str, r)) + "\n")
    log("done")


def restore(store):
    with open(S / "undo.pickle", "rb") as f:
        undo_id, undo_lat, undo_lon = pickle.load(f)
    idx = osmium.index.create_map(f"dense_file_array,{store}")
    Loc = osmium.osm.Location
    for i in range(len(undo_id) - 1, -1, -1):  # backwards: the first write of a node is the one to end on
        lat = undo_lat[i]
        idx.set(undo_id[i], Loc() if math.isnan(lat) else Loc(undo_lon[i], lat))
    del idx
    Path(str(store) + ".state").write_text("2026-11-08T00:00:00Z")
    log(f"{len(undo_id):,} writes undone; the store is at 11-08T00Z")


def sample(store, clip, every=50):
    idx = osmium.index.create_map(f"dense_file_array,{store}")
    n = same = differ = absent = 0
    shown = 0
    t = time.time()
    for o in osmium.FileProcessor(clip, osmium.osm.NODE):
        n += 1
        if n % every:
            continue
        try:
            loc = idx.get(o.id)
            ok = loc.valid()
        except KeyError:
            ok = False
        if not ok:
            absent += 1
            if shown < 8:
                shown += 1
                log(f"  node {o.id} v{o.version}: not in the store")
        elif abs(loc.lat - o.location.lat) < 1e-9 and abs(loc.lon - o.location.lon) < 1e-9:
            same += 1
        else:
            differ += 1
            if shown < 8:
                shown += 1
                log(f"  node {o.id} v{o.version}: clip {o.location.lat},{o.location.lon} store {loc.lat},{loc.lon}")
    log(f"{Path(clip).name}, store at {state_of(store)}: every {every}th of {n:,} nodes in {time.time() - t:.0f} s: "
        f"same place {same:,}, another place {differ:,}, not in the store {absent:,}")


def engine(tag, pbf, quests, cities, today, notes, zone):
    out = S / f"out-{tag}"
    dump = S / f"matches-{tag}.tsv"
    names = ",".join(sorted(tiers()[0] - {"OsmNoteQuestType"}))
    if dump.exists():
        dump.unlink()
    args = ["powershell", "-NoProfile", "-File", str(ROOT / "engine" / "measure.ps1"), "count",
            "--pbf", str(pbf), "--quests", str(quests), "--cities", str(cities), "--out", str(out),
            "--today", today, "--dump-matches", str(dump), "--dump-quests", names]
    if notes:
        args += ["--notes", str(notes)]
    env = dict(os.environ, JAVA_OPTS=f"-Duser.timezone={zone} -Xmx30g -Dopenquests.areaPass=false")
    t = time.time()
    r = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True)
    tail = (r.stdout or "").strip().splitlines()[-3:]
    log(f"engine {tag}: exit {r.returncode} in {time.time() - t:.0f} s; {' | '.join(tail)}")
    (S / f"engine-{tag}.log").write_text((ROOT / "engine" / "out" / "run.log").read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    if r.returncode or not dump.exists():
        print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit(1)


def count():
    world, tier1q = S / "cities-world.json", ROOT / "data" / "quests" / "v64.1.json"
    west = ROOT / "data" / "cities" / "europe-west.json"
    engine("world-priors", S / "priors.osm.pbf", tier1q, world, f"{OLD_D}T00:00:00Z", None, "UTC")
    engine("world-versions", S / "versions.osm.pbf", tier1q, world, f"{NEW_D}T00:00:00Z", None, "UTC")
    engine("west-priors", S / "priors.osm.pbf", tier1q, west, f"{OLD_D}T00:00:00Z", NOTES, "Europe/London")
    engine("west-versions", S / "versions.osm.pbf", tier1q, west, f"{NEW_D}T00:00:00Z", NOTES, "Europe/London")


def read_dump(path, tier1=None):
    """(type, id) -> set of quests"""
    m = defaultdict(set)
    with open(path, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if p[0] == "quest" or (tier1 is not None and p[0] not in tier1):
                continue
            m[(p[1], int(p[2]))].add(p[0])
    return m


def changesets():
    out = {}
    for path in sorted((REPLAY / "changesets").glob("*.osm.gz")):
        with gzip.open(path, "rb") as f:
            try:
                root = ET.parse(f).getroot()
            except ET.ParseError:
                continue
        for cs in root.iter("changeset"):
            tags = {t.get("k"): t.get("v") for t in cs.iter("tag")}
            out[int(cs.get("id"))] = (tags.get("created_by", ""), tags.get("StreetComplete:quest_type"))
    return out


def stream_events(tag):
    """events of one engine pair: [(seq, changeset, quest, type, id, what)], versions per element, the
    state before the day per element, the state after it"""
    pri = read_dump(S / f"matches-{tag}-priors.tsv")
    syn = read_dump(S / f"matches-{tag}-versions.tsv")
    before = {}
    unplaced = set()
    with open(S / "priors-index.tsv", encoding="utf-8") as f:
        for line in f:
            typ, eid, version, sid = line.rstrip("\n").split("\t")
            if sid == "unplaced":
                unplaced.add((typ, int(eid)))
                continue
            m = pri.get((typ, int(sid)))
            if m:
                before[(typ, int(eid))] = m
    versions = defaultdict(list)
    with open(S / "index.tsv", encoding="utf-8") as f:
        for line in f:
            typ, eid, version, seq, cs, visible, sid = line.rstrip("\n").split("\t")
            key = (typ, int(eid))
            if sid == "unplaced":
                unplaced.add(key)
                continue
            matches = syn.get((typ, int(sid)), frozenset()) if sid != "None" else frozenset()
            versions[key].append((int(seq), int(version), int(cs), matches))
    ev = []
    after = {}
    for key, vs in versions.items():
        if key in unplaced:
            continue
        vs.sort()
        state = before.get(key, frozenset())
        for seq, version, cs, matches in vs:
            if matches != state:
                for q in matches - state:
                    ev.append((seq, cs, q, key[0], key[1], "opened"))
                for q in state - matches:
                    ev.append((seq, cs, q, key[0], key[1], "closed"))
                state = matches
        if state:
            after[key] = state
    return ev, versions, before, after, unplaced


def events():
    tier1, _ = tiers()
    L = []
    cs_info = changesets()
    log(f"{len(cs_info):,} changesets in the feed files")

    # the world
    ev, versions, before, after, unplaced = stream_events("world")
    first = int((REPLAY / "range.txt").read_text().split()[0])
    opened = sum(1 for e in ev if e[5] == "opened")
    net = Counter()
    for seq, cs, q, typ, eid, what in ev:
        net[(q, typ, eid)] += 1 if what == "opened" else -1
    net_flips = sum(1 for v in net.values() if v)
    L.append(f"the world, the minute diffs of {OLD_D}, tier 1 ({len(tier1) - 1} quests, no notes, one zone)")
    L.append(f"elements with a node or way version in the stream: {len(versions):,}; could not be placed: {len(unplaced):,}")
    L.append(f"open tier-1 quests on them before the day: {sum(len(v) for k, v in before.items() if k in versions):,}; after: {sum(len(v) for v in after.values()):,}")
    L.append(f"events: {len(ev):,} ({opened:,} opened, {len(ev) - opened:,} closed) on {len({(e[3], e[4]) for e in ev}):,} elements "
             f"from {len({e[1] for e in ev}):,} changesets; net flips {net_flips:,}; there and back within the day {len(ev) - net_flips:,}")
    per_min = Counter(e[0] for e in ev)
    L.append(f"minutes with an event: {len(per_min):,} of 1,415; most in one minute {max(per_min.values()):,}; median "
             f"{sorted(per_min.get(first + i, 0) for i in range(1415))[707]:,}")
    by_q = Counter((e[2], e[5]) for e in ev)
    tot = Counter()
    for (q, what), n in by_q.items():
        tot[q] += n
    L.append("")
    L.append("quests with the most events (opened / closed):")
    for q, n in tot.most_common(15):
        L.append(f"  {q:<36}{by_q[(q, 'opened')]:>8,}{by_q[(q, 'closed')]:>8,}")
    by_editor = Counter()
    for seq, cs, q, typ, eid, what in ev:
        editor = cs_info.get(cs, ("(changeset not in the feed files)", None))[0]
        by_editor[(re.split(r"[ /]", editor)[0] or "(none)", what)] += 1
    editors = Counter()
    for (e, what), n in by_editor.items():
        editors[e] += n
    L.append("")
    L.append("events by editor (opened / closed):")
    for e, n in editors.most_common(12):
        L.append(f"  {e:<36}{by_editor[(e, 'opened')]:>8,}{by_editor[(e, 'closed')]:>8,}")
    ev_by_cs = defaultdict(list)
    for e in ev:
        ev_by_cs[e[1]].append(e)
    cs_seen = set()
    for key, vs in versions.items():
        for seq, version, cs, matches in vs:
            cs_seen.add(cs)
    seen = closes = other_tier = 0
    misses = Counter()
    for cs, (editor, quest) in cs_info.items():
        if not quest or cs not in cs_seen:
            continue
        if quest not in tier1:
            other_tier += 1
            continue
        seen += 1
        if any(e[2] == quest and e[5] == "closed" for e in ev_by_cs.get(cs, ())):
            closes += 1
        else:
            misses[quest] += 1
    L.append("")
    L.append(f"StreetComplete changesets naming a tier-1 quest, with a node or way version in the stream: {seen:,}; "
             f"the stream shows that quest closing in {closes:,} ({100 * closes / max(seen, 1):.1f}%)")
    L.append(f"  (naming an area quest or an overlay, not replayed: {other_tier:,})")
    L.append(f"  not shown closing, by quest: {dict(misses.most_common(15))}")
    with open(S / "events-world.tsv", "w", encoding="utf-8") as f:
        f.write("minute_seq\tchangeset\tquest\ttype\tid\tevent\teditor\n")
        for e in sorted(ev):
            f.write("\t".join(map(str, e)) + "\t" + cs_info.get(e[1], ("", None))[0] + "\n")

    # europe-west, as step 1 ran it
    ev, versions, before, after, unplaced = stream_events("west")
    old = read_dump(FLIPS / f"matches-{OLD_D}.tsv", tier1)
    new = read_dump(FLIPS / f"matches-{NEW_D}.tsv", tier1)
    L.append("")
    L.append("europe-west with step 1's cities file and notes clip, on the same two files")
    touched = set(versions)
    b_diff = [(k, sorted(before.get(k, ())), sorted(old.get(k, ()))) for k in touched
              if set(before.get(k, ())) != old.get(k, set())]
    a_diff = [(k, sorted(after.get(k, ())), sorted(new.get(k, ()))) for k in touched
              if set(after.get(k, ())) != new.get(k, set())]
    in_old = sum(1 for k in touched if k in old)
    L.append(f"touched elements holding a tier-1 quest in the {OLD_D} dump: {in_old:,}; state before the day (the store's "
             f"prior version, clock {OLD_D}) differs from that dump on {len(b_diff)}")
    for k, mine, theirs in b_diff[:20]:
        L.append(f"  {k[0]} {k[1]}: prior version gives {mine}, dump has {theirs}")
    L.append(f"state after the day differs from the {NEW_D} dump on {len(a_diff)}")
    for k, mine, theirs in a_diff[:20]:
        L.append(f"  {k[0]} {k[1]}: stream gives {mine}, dump has {theirs}")
    step1 = set()
    with open(REPLAY / "events.tsv", encoding="utf-8") as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split("\t")
            step1.add((int(p[0]), int(p[1]), p[2], p[3], int(p[4]), p[5]))
    mine = set(ev)
    L.append(f"events: {len(ev):,}; step 1's: {len(step1):,}; in both: {len(mine & step1):,}; only here: {len(mine - step1):,}; "
             f"only in step 1: {len(step1 - mine):,}")
    for e in sorted(mine - step1)[:15]:
        L.append(f"  only here: {e}")
    for e in sorted(step1 - mine)[:15]:
        L.append(f"  only step 1: {e}")
    (S / "RESULT.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    log("done")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prep", "build", "restore", "sample", "count", "events"])
    ap.add_argument("--store")
    ap.add_argument("--clip")
    a = ap.parse_args()
    if a.cmd == "prep":
        prep()
    elif a.cmd == "build":
        build(a.store)
    elif a.cmd == "restore":
        restore(a.store)
    elif a.cmd == "sample":
        sample(a.store, a.clip)
    elif a.cmd == "count":
        count()
    else:
        events()
