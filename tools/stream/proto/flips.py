"""Which quest flips between two consecutive daily counts does the day's diff explain?

Reads the two --dump-matches files of count.sh, the planet day diff between them and both clips.
Buckets every flip (a quest on an element that opened or closed):
  self      the element itself is in the diff
  member    a node of the flipped way, or a member of the flipped relation, is in the diff
  aged      opened, agedOnly, element untouched: the clock did it
  near R    the nearest changed position is within R metres of the flipped element
  far       nothing changed within 1 km
"""
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import osmium

S = Path(__file__).parent
STORE = Path.home() / "Code" / ".osm-data"
OLD_D, NEW_D, DIFF = "2026-11-08", "2026-11-09", "5171"
OLD = str(STORE / "europe" / f"europe-{OLD_D}.osm.pbf")
NEW = str(STORE / "europe" / f"europe-{NEW_D}.osm.pbf")
OSC = str(STORE / "planet" / "diffs" / f"{DIFF}.osc.gz")
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:6.0f} s] {msg}", flush=True)


def read_matches(day):
    m = {}
    with open(S / f"matches-{day}.tsv", encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 9 or p[3] == "version":
                continue
            quest, typ, eid, version, _ts, city, lat, lon, aged = p[:9]
            m[(quest, typ, int(eid))] = (int(version), city, float(lat), float(lon), aged == "true")
    return m


old_m, new_m = read_matches(OLD_D), read_matches(NEW_D)
opened = {k: new_m[k] for k in new_m.keys() - old_m.keys()}
closed = {k: old_m[k] for k in old_m.keys() - new_m.keys()}
log(f"matches {len(old_m):,} -> {len(new_m):,}; opened {len(opened):,}, closed {len(closed):,}")
flips = [("opened", k, v) for k, v in opened.items()] + [("closed", k, v) for k, v in closed.items()]

# --- the day's diff: every changed id, new node positions, new way refs ------------------------
ch = {"node": set(), "way": set(), "relation": set()}
ch_node_pos = {}
ch_way_refs = {}
for o in osmium.FileProcessor(OSC):
    if o.is_node():
        ch["node"].add(o.id)
        if o.location.valid():
            ch_node_pos[o.id] = (o.location.lat, o.location.lon)
    elif o.is_way():
        ch["way"].add(o.id)
        ch_way_refs[o.id] = [n.ref for n in o.nodes]
    elif o.is_relation():
        ch["relation"].add(o.id)
log(f"diff {DIFF}: {len(ch['node']):,} nodes, {len(ch['way']):,} ways, {len(ch['relation']):,} relations (planet)")

flip_ways = {k[2] for _, k, _ in flips if k[1] == "way"}
flip_rels = {k[2] for _, k, _ in flips if k[1] == "relation"}


def ways_of(path, ids):
    out = {}
    if ids:
        for o in osmium.FileProcessor(path, osmium.osm.WAY).with_filter(osmium.filter.IdFilter(ids)):
            out[o.id] = [n.ref for n in o.nodes]
    return out


def rels_of(path, ids):
    out = {}
    if ids:
        for o in osmium.FileProcessor(path, osmium.osm.RELATION).with_filter(osmium.filter.IdFilter(ids)):
            out[o.id] = [(m.type, m.ref) for m in o.members]
    return out


def nodes_of(path, ids):
    out = {}
    if ids:
        for o in osmium.FileProcessor(path, osmium.osm.NODE).with_filter(osmium.filter.IdFilter(ids)):
            if o.location.valid():
                out[o.id] = (o.location.lat, o.location.lon)
    return out


want_ways = flip_ways | ch["way"]
old_ways, new_ways = ways_of(OLD, want_ways), ways_of(NEW, want_ways)
log(f"ways read: {len(old_ways):,} old, {len(new_ways):,} new (flipped or changed, inside the clip)")
old_rels, new_rels = rels_of(OLD, flip_rels), rels_of(NEW, flip_rels)
log(f"relations read: {len(old_rels):,} old, {len(new_rels):,} new")

want_nodes = set(ch["node"])
for refs in list(old_ways.values()) + list(new_ways.values()):
    want_nodes.update(refs)
old_pos, new_pos = nodes_of(OLD, want_nodes), nodes_of(NEW, want_nodes)
log(f"node positions: {len(old_pos):,} old, {len(new_pos):,} new")

# --- changed positions: changed nodes (old and new place), every node of a changed way ---------
CELL = 0.01
grid = defaultdict(list)


def add_point(p):
    grid[(int(math.floor(p[0] / CELL)), int(math.floor(p[1] / CELL)))].append(p)


n_points = 0
for nid in ch["node"]:
    for src in (old_pos, new_pos, ch_node_pos):
        p = src.get(nid)
        if p:
            add_point(p)
            n_points += 1
for wid in ch["way"]:
    for ways, pos in ((old_ways, old_pos), (new_ways, new_pos)):
        for ref in ways.get(wid, ()):
            p = pos.get(ref)
            if p:
                add_point(p)
                n_points += 1
log(f"changed positions inside the clip: {n_points:,}")


def metres(a, b):
    x = math.radians(b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2))
    y = math.radians(b[0] - a[0])
    return 6371008.8 * math.hypot(x, y)


def nearest(p):
    """Distance to the nearest changed position, or inf beyond about 1 km."""
    ci, cj = int(math.floor(p[0] / CELL)), int(math.floor(p[1] / CELL))
    span = 2  # 0.01 deg of longitude is 600-900 m here
    best = math.inf
    for i in range(ci - 1, ci + 2):
        for j in range(cj - span, cj + span + 1):
            for q in grid.get((i, j), ()):
                d = metres(p, q)
                if d < best:
                    best = d
    return best if best <= 1000 else math.inf


BUCKETS = [(20, "near 20 m"), (50, "near 50 m"), (200, "near 200 m"), (1000, "near 1 km")]
rows = Counter()
by_quest = defaultdict(Counter)
far = []
for direction, (quest, typ, eid), (version, city, lat, lon, aged) in flips:
    if eid in ch[typ]:
        b = "self"
    else:
        member = False
        pts = [(lat, lon)]
        if typ == "way":
            refs = set(old_ways.get(eid, ())) | set(new_ways.get(eid, ()))
            member = any(r in ch["node"] for r in refs)
            pts += [p for r in refs for p in (old_pos.get(r), new_pos.get(r)) if p]
        elif typ == "relation":
            mem = set(old_rels.get(eid, ())) | set(new_rels.get(eid, ()))
            member = any(ref in ch[{"n": "node", "w": "way", "r": "relation"}[t]] for t, ref in mem)
        if member:
            b = "member"
        elif direction == "opened" and aged:
            b = "aged"
        else:
            d = min(nearest(p) for p in pts)
            b = next((name for limit, name in BUCKETS if d <= limit), "far")
            if b == "far":
                far.append((direction, quest, typ, eid, city, lat, lon, aged))
    rows[(direction, b)] += 1
    by_quest[quest][b] += 1

order = ["self", "member", "aged"] + [n for _, n in BUCKETS] + ["far"]
out = []
out.append(f"europe-west, {OLD_D} -> {NEW_D}, diff {DIFF}")
out.append(f"matches {len(old_m):,} -> {len(new_m):,}; flips {len(flips):,} ({len(opened):,} opened, {len(closed):,} closed)")
out.append("")
out.append(f"{'bucket':<12}{'opened':>9}{'closed':>9}{'all':>9}{'share':>8}{'running':>9}")
run = 0
for b in order:
    o, c = rows[("opened", b)], rows[("closed", b)]
    run += o + c
    out.append(f"{b:<12}{o:>9,}{c:>9,}{o + c:>9,}{(o + c) / max(1, len(flips)):>8.1%}{run / max(1, len(flips)):>9.1%}")
out.append("")
out.append("quests with flips beyond 20 m of a change (not self, member or aged):")
for quest, c in sorted(by_quest.items(), key=lambda kv: -sum(v for k, v in kv[1].items() if k in ("near 50 m", "near 200 m", "near 1 km", "far"))):
    beyond = {k: v for k, v in c.items() if k in ("near 50 m", "near 200 m", "near 1 km", "far")}
    if beyond:
        out.append(f"  {quest:<34}{sum(c.values()):>7,} flips  " + ", ".join(f"{k} {v}" for k, v in beyond.items()))
out.append("")
out.append("flips within 20 m but not self or member, by quest:")
for quest, c in sorted(by_quest.items(), key=lambda kv: -kv[1]["near 20 m"])[:15]:
    if c["near 20 m"]:
        out.append(f"  {quest:<34}{c['near 20 m']:>7,}")
(S / "RESULT.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
with open(S / "far.tsv", "w", encoding="utf-8") as f:
    for r in far:
        f.write("\t".join(map(str, r)) + "\n")
print("\n".join(out))
log("done")
