"""Replay one day's minute diffs through the quests decided from the element alone (tier 1).

Every element version of the day that lies in a city box becomes its own element in a synthetic PBF
(a new id per version, the nodes its way refers to beside it), which the unchanged engine counts with
--dump-matches. The match set of each version, in stream order, gives the events; the state before the
day is the 11-08 dump, and the state after must equal the 11-09 dump.

Usage: replay.py build | events
"""
import gzip
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

import osmium

S = Path(__file__).parent
ROOT = S.parent.parent
FLIPS = ROOT / ".scratch" / "diff-flips"
STORE = Path.home() / "Code" / ".osm-data"
OLD_D, NEW_D = "2026-11-08", "2026-11-09"
OLD = str(STORE / "europe" / f"europe-{OLD_D}.osm.pbf")
NEW = str(STORE / "europe" / f"europe-{NEW_D}.osm.pbf")
NOTES = ROOT / "data" / "notes" / "planet-notes-261109-europe-west.jsonl"
NODE_BASE, WAY_BASE = 10**12, 10**11
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:6.0f} s] {msg}", flush=True)


def tiers():
    src = (ROOT / "engine/src/main/kotlin/ported/AreaQuests.kt").read_text(encoding="utf-8")
    area = set(re.findall(r"^\s+de\.westnordost[\w.]*\.(\w+),?\s*$", src, re.M))
    names = [q["name"] for q in json.loads((ROOT / "data/quests/v64.1.json").read_text(encoding="utf-8"))["quests"]]
    return {n for n in names if n not in area}, area


def boxes():
    with open(NOTES, encoding="utf-8") as f:
        return [(b[0] - 0.02, b[1] - 0.02, b[2] + 0.02, b[3] + 0.02) for b in json.loads(f.readline())["boxes"]]


BOXES = boxes()


def in_boxes(lat, lon):
    return any(w <= lon <= e and s <= lat <= n for w, s, e, n in BOXES)


def read_dump(path, tier1):
    """(type, id) -> set of tier-1 quests; and per key the aged flags"""
    m = defaultdict(set)
    aged = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if p[0] == "quest" or p[0] not in tier1:
                continue
            m[(p[1], int(p[2]))].add(p[0])
            aged[(p[0], p[1], int(p[2]))] = p[8] == "true"
    return m, aged


def build():
    first, last, _, _ = map(int, (S / "range.txt").read_text().split())
    tier1, _ = tiers()
    old_keys = set(read_dump(FLIPS / f"matches-{OLD_D}.tsv", tier1)[0])
    log(f"{len(old_keys):,} elements hold a tier-1 quest on {OLD_D}")

    node_pos = {}       # id -> last position seen in the stream
    node_versions = []  # (seq, id, version, visible, changeset, ts, tags, lat, lon)
    way_versions = []   # (seq, id, version, visible, changeset, ts, tags, refs)
    relations = Counter()
    n_all = Counter()
    for seq in range(first, last + 1):
        for o in osmium.FileProcessor(str(S / "minute" / f"{seq}.osc.gz")):
            if o.is_node():
                n_all["node"] += 1
                valid = o.location.valid()
                lat, lon = (o.location.lat, o.location.lon) if valid else (None, None)
                if valid and o.visible:
                    node_pos[o.id] = (lat, lon)
                if (valid and in_boxes(lat, lon)) or ("node", o.id) in old_keys:
                    node_versions.append((seq, o.id, o.version, o.visible, o.changeset, o.timestamp,
                                          {t.k: t.v for t in o.tags}, lat, lon))
            elif o.is_way():
                n_all["way"] += 1
                way_versions.append((seq, o.id, o.version, o.visible, o.changeset, o.timestamp,
                                     {t.k: t.v for t in o.tags}, [n.ref for n in o.nodes]))
            elif o.is_relation():
                n_all["relation"] += 1
                relations[o.id] += 1
    log(f"stream {first}..{last}: {dict(n_all)}; node versions in the boxes {len(node_versions):,}")

    refs = set()
    for v in way_versions:
        refs.update(v[7])
    missing = refs - node_pos.keys()
    pos = {}
    for path in (OLD, NEW):  # the newer file wins
        for o in osmium.FileProcessor(path, osmium.osm.NODE).with_filter(osmium.filter.IdFilter(missing)):
            if o.location.valid():
                pos[o.id] = (o.location.lat, o.location.lon)
    pos.update(node_pos)
    log(f"way node positions: {len(refs):,} wanted, {len(refs & pos.keys()):,} found")

    kept_ways, dropped = [], 0
    for v in way_versions:
        key = ("way", v[1])
        if not v[3]:  # deleted: no refs
            if key in old_keys:
                kept_ways.append(v)
            continue
        located = [pos.get(r) for r in v[7]]
        touches = any(p and in_boxes(*p) for p in located)
        if touches and all(located):
            kept_ways.append(v)
        elif touches or key in old_keys:
            dropped += 1
            if key in old_keys:
                kept_ways.append(v[:7] + (None,))  # cannot be placed: reported
    log(f"way versions in the boxes {len(kept_ways):,}; {dropped} with a node that could not be placed")

    # the synthetic file
    ref_nodes = set()
    for v in kept_ways:
        if v[3] and v[7]:
            ref_nodes.update(v[7])
    header = osmium.io.Header()
    header.set("osmosis_replication_timestamp", f"{NEW_D}T00:00:00Z")
    header.set("sorting", "Type_then_ID")
    out = S / "versions.osm.pbf"
    index = []  # synthetic id -> the version it stands for
    w = osmium.SimpleWriter(str(out), header=header, overwrite=True)
    for nid in sorted(ref_nodes):
        w.add_node(osmium.osm.mutable.Node(id=nid, version=1, location=(pos[nid][1], pos[nid][0])))
    n = 0
    for v in node_versions:
        seq, nid, version, visible, cs, ts, tags, lat, lon = v
        sid = None
        if visible and tags:
            n += 1
            sid = NODE_BASE + n
            w.add_node(osmium.osm.mutable.Node(id=sid, version=version, timestamp=ts, tags=tags, location=(lon, lat)))
        index.append(("node", nid, version, seq, cs, visible, sid))
    n = 0
    for v in kept_ways:
        seq, wid, version, visible, cs, ts, tags, wrefs = v
        sid = None
        if visible and tags and wrefs:
            n += 1
            sid = WAY_BASE + n
            w.add_way(osmium.osm.mutable.Way(id=sid, version=version, timestamp=ts, tags=tags, nodes=wrefs))
        index.append(("way", wid, version, seq, cs, visible, sid if wrefs is not None or not visible else "unplaced"))
    w.close()
    with open(S / "index.tsv", "w", encoding="utf-8") as f:
        for r in index:
            f.write("\t".join(map(str, r)) + "\n")
    (S / "relations.json").write_text(json.dumps({"versions": sum(relations.values()), "ids": list(relations)}))
    log(f"wrote {out.name} ({out.stat().st_size / 1e6:.1f} MB): {len(ref_nodes):,} reference nodes, {len(index):,} versions indexed")


def changesets():
    """id -> (created_by, quest_type) from the changeset feed files"""
    out = {}
    for path in sorted((S / "changesets").glob("*.osm.gz")):
        with gzip.open(path, "rb") as f:
            try:
                root = ET.parse(f).getroot()
            except ET.ParseError:
                continue
        for cs in root.iter("changeset"):
            tags = {t.get("k"): t.get("v") for t in cs.iter("tag")}
            out[int(cs.get("id"))] = (tags.get("created_by", ""), tags.get("StreetComplete:quest_type"))
    return out


def events():
    tier1, _ = tiers()
    old, _ = read_dump(FLIPS / f"matches-{OLD_D}.tsv", tier1)
    new, new_aged = read_dump(FLIPS / f"matches-{NEW_D}.tsv", tier1)
    syn, _ = read_dump(S / "matches-versions.tsv", tier1)
    log(f"dumps read: {len(old):,} / {len(new):,} elements with tier-1 quests; {len(syn):,} versions match")

    versions = defaultdict(list)
    unplaced = set()
    with open(S / "index.tsv", encoding="utf-8") as f:
        for line in f:
            typ, eid, version, seq, cs, visible, sid = line.rstrip("\n").split("\t")
            key = (typ, int(eid))
            if sid == "unplaced":
                unplaced.add(key)
                continue
            matches = syn.get((typ, int(sid)), set()) if sid != "None" else set()
            versions[key].append((int(seq), int(version), int(cs), matches))
    log(f"{len(versions):,} elements with a version in the boxes; {len(unplaced)} could not be placed")

    cs_info = changesets()
    ev = []  # (seq, changeset, quest, type, id, opened/closed)
    wrong = []
    for key, vs in versions.items():
        if key in unplaced:
            continue
        vs.sort()
        state = old.get(key, set())
        for seq, version, cs, matches in vs:
            for q in matches - state:
                ev.append((seq, cs, q, key[0], key[1], "opened"))
            for q in state - matches:
                ev.append((seq, cs, q, key[0], key[1], "closed"))
            state = matches
        if state != new.get(key, set()):
            wrong.append((key, sorted(state - new.get(key, set())), sorted(new.get(key, set()) - state)))

    # measured tier-1 flips, and which of them the stream should explain
    measured = set()
    for key in old.keys() | new.keys():
        for q in old.get(key, set()) ^ new.get(key, set()):
            measured.add((q, key[0], key[1]))
    touched = {m for m in measured if (m[1], m[2]) in versions}
    untouched = measured - touched
    aged = {m for m in untouched if new_aged.get(m)}
    net = Counter()
    for seq, cs, q, typ, eid, what in ev:
        net[(q, typ, eid)] += 1 if what == "opened" else -1
    net_flips = {k for k, v in net.items() if v != 0}
    surplus = len(ev) - len(net_flips)

    rel = json.loads((S / "relations.json").read_text())
    rel_measured = sum(1 for m in measured if m[1] == "relation")
    out = []
    out.append(f"europe-west, the minute diffs of {OLD_D}, tier 1 ({len(tier1)} quests)")
    out.append(f"elements with a version in the city boxes: {len(versions):,}; events: {len(ev):,} "
               f"({sum(1 for e in ev if e[5] == 'opened'):,} opened, {sum(1 for e in ev if e[5] == 'closed'):,} closed) "
               f"from {len({e[1] for e in ev}):,} changesets")
    out.append("")
    out.append(f"measured tier-1 flips {OLD_D} -> {NEW_D}: {len(measured):,}")
    out.append(f"  on an element the stream touched: {len(touched):,}")
    out.append(f"  untouched, opened as agedOnly:    {len(aged):,}")
    out.append(f"  untouched, other (notes, ...):    {len(untouched - aged):,}  {sorted(untouched - aged)[:8]}")
    out.append(f"stream's net flips: {len(net_flips):,}; equal to the measured ones on touched elements: "
               f"{len(net_flips & touched):,}; stream only: {len(net_flips - touched):,}; measured only: {len(touched - net_flips):,}")
    out.append(f"events beyond the net (opened and closed again within the day): {surplus:,}")
    out.append(f"elements whose final state differs from the {NEW_D} dump: {len(wrong)}")
    for key, extra, lack in wrong[:25]:
        out.append(f"  {key[0]} {key[1]}: stream has {extra}, dump has {lack}")
    out.append(f"relations: {rel['versions']:,} versions in the stream, not replayed; measured relation flips: {rel_measured}")
    out.append("")
    by_editor = Counter()
    for seq, cs, q, typ, eid, what in ev:
        editor = cs_info.get(cs, ("(changeset not in the feed files)", None))[0]
        by_editor[(re.split(r"[ /]", editor)[0] or "(none)", what)] += 1
    out.append("events by editor (opened / closed):")
    editors = Counter()
    for (e, what), n in by_editor.items():
        editors[e] += n
    for e, n in editors.most_common(10):
        out.append(f"  {e:<28}{by_editor[(e, 'opened')]:>6}{by_editor[(e, 'closed')]:>6}")
    # the second check: a StreetComplete changeset names the quest it answered
    sc = [(cs, info[1]) for cs, info in cs_info.items() if info[1]]
    ev_by_cs = defaultdict(list)
    for e in ev:
        ev_by_cs[e[1]].append(e)
    cs_in_boxes = defaultdict(set)
    for key, vs in versions.items():
        for seq, version, cs, matches in vs:
            cs_in_boxes[cs].add(key)
    seen = closes = 0
    misses = Counter()
    for cs, quest in sc:
        if cs not in cs_in_boxes or quest not in tier1:
            continue
        seen += 1
        if any(e[2] == quest and e[5] == "closed" for e in ev_by_cs.get(cs, ())):
            closes += 1
        else:
            misses[quest] += 1
    out.append("")
    out.append(f"StreetComplete changesets with a tier-1 quest_type and an element in the boxes: {seen}; "
               f"the stream shows that quest closing in {closes}")
    if misses:
        out.append(f"  not shown closing: {dict(misses.most_common(12))}")
    (S / "RESULT.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    with open(S / "events.tsv", "w", encoding="utf-8") as f:
        f.write("minute_seq\tchangeset\tquest\ttype\tid\tevent\teditor\n")
        for e in sorted(ev):
            f.write("\t".join(map(str, e)) + "\t" + cs_info.get(e[1], ("", None))[0] + "\n")
    print("\n".join(out))
    log("done")


if __name__ == "__main__":
    {"build": build, "events": events}[sys.argv[1]]()
