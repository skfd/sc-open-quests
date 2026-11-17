"""`tilestore context` against the clip it was cut from (DESIGN.md, "What tier 2 must recount, from the code").

  python tools/stream/tilecheck/ctxcmp.py --store S --clip X.osm.pbf --work DIR [--sample 50000] [--gen G]
      [--exe tilestore.exe]

The clip must be the generation's own day. Checks, each exact, read with pyosmium from the clip:
  ways: tags, refs and places of a sample (random ways, closed buildings, member ways of kept relations), the refs
    with an addr:* tag, and the kept relations holding each (kept: tagged, not one the app ignores: tilestore.py);
  relations: those holding relations' tags and members, and the box of their member ways' places;
  nodes: the tags of a sample of nodes (tagged and untagged) at their clip places;
  points: inside points of sampled closed buildings and small kept multipolygons must find that element (recall
    within the tile block), and every container found must hold its point by the clip's own geometry (precision),
    with the clip's tags and box.
Exits 1 on any difference."""
import argparse
import json
import random
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import osmium

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/stream"))
from tilestore import ignore_relation  # noqa: E402

NO = -(2 ** 31)


def tags_of(blob: bytes) -> dict:
    if not blob:
        return {}
    p = blob.decode().split("\0")
    return dict(zip(p[0::2], p[1::2]))


def unpack(d: Path, prefix: str, n: int):
    offs = np.load(d / f"{prefix}_toffs.npy")
    b = (d / f"{prefix}_tags.bin").read_bytes()
    return [tags_of(b[offs[i]:offs[i + 1]]) for i in range(n)]


def evenodd(segs, lat, lon) -> bool:
    inside = False
    for y1, x1, y2, x2 in segs:
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def save_ids(p: Path, ids):
    np.save(p, np.asarray(ids, dtype="<i8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", type=Path, required=True)
    ap.add_argument("--clip", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--sample", type=int, default=50_000)
    ap.add_argument("--gen", type=int, default=-1)
    ap.add_argument("--exe", type=Path, default=ROOT / "tilestore/target/release/tilestore.exe")
    a = ap.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(7)
    t = time.time()

    # pass 1: way ids (closed buildings apart), kept relations' members and tags
    way_ids, buildings = [], []
    kept_ways: dict[int, list[int]] = {}
    rel_tags, rel_members = {}, {}
    for o in osmium.FileProcessor(str(a.clip), osmium.osm.WAY | osmium.osm.RELATION):
        if o.is_way():
            way_ids.append(o.id)
            n = len(o.nodes)
            if n >= 4 and o.nodes[0].ref == o.nodes[n - 1].ref and "building" in o.tags:
                buildings.append(o.id)
        else:
            tg = {x.k: x.v for x in o.tags}
            if not tg or ignore_relation(tg):
                continue
            rel_tags[o.id] = tg
            rel_members[o.id] = [(m.type, m.ref) for m in o.members]
            kept_ways[o.id] = [m.ref for m in o.members if m.type == "w"]
    holders = defaultdict(list)
    for r, ws in kept_ways.items():
        for w in ws:
            holders[w].append(r)
    print(f"pass 1: {len(way_ids):,} ways, {len(buildings):,} closed buildings, {len(rel_tags):,} kept relations, "
          f"{time.time() - t:.0f} s", flush=True)
    member_ways = list(holders)
    sample = set(rnd.sample(way_ids, min(a.sample, len(way_ids))))
    sample |= set(rnd.sample(member_ways, min(a.sample // 5, len(member_ways))))
    point_buildings = rnd.sample(buildings, min(3000, len(buildings)))
    sample |= set(point_buildings)
    small_mp = [r for r, tg in rel_tags.items() if tg.get("type") == "multipolygon"]
    mp_sample = rnd.sample(small_mp, min(3000, len(small_mp)))
    mp_ways = {w for r in mp_sample for w in kept_ways[r]}
    del way_ids

    # pass 2: the sampled ways' tags and refs (and the multipolygon sample's member ways)
    w_tags, w_refs = {}, {}
    for o in osmium.FileProcessor(str(a.clip), osmium.osm.WAY):
        if o.id in sample or o.id in mp_ways:
            w_tags[o.id] = {x.k: x.v for x in o.tags}
            w_refs[o.id] = [n.ref for n in o.nodes]
    need = {r for refs in w_refs.values() for r in refs}
    # pass 3: those nodes' places and tags, plus a node sample
    places, n_tags = {}, {}
    node_sample = []
    for o in osmium.FileProcessor(str(a.clip), osmium.osm.NODE):
        tagged = len(o.tags) > 0
        if o.id in need or (tagged and rnd.random() < 0.002) or rnd.random() < 0.0002:
            loc = o.location
            places[o.id] = (round(loc.lat * 1e7), round(loc.lon * 1e7)) if loc.valid() else None
            n_tags[o.id] = {x.k: x.v for x in o.tags}
            if o.id not in need or rnd.random() < 0.01:
                node_sample.append(o.id)
    print(f"passes 2-3: {len(w_refs):,} ways, {len(places):,} nodes, {time.time() - t:.0f} s", flush=True)

    # points: an inside point of each sampled building and multipolygon (the vertex mean, if inside; else skipped)
    def ring_segs(refs):
        pts = [places.get(r) for r in refs]
        return [(p[0], p[1], q[0], q[1]) for p, q in zip(pts, pts[1:]) if p and q]

    points, expect = [], []
    for w in point_buildings:
        if w not in w_refs:
            continue
        segs = ring_segs(w_refs[w])
        pts = [places.get(r) for r in w_refs[w][:-1] if places.get(r)]
        if not pts or not segs:
            continue
        la = sum(p[0] for p in pts) / len(pts) + 0.37
        lo = sum(p[1] for p in pts) / len(pts) + 0.41
        la, lo = int(la), int(lo)
        if evenodd(segs, la, lo):
            points.append((la, lo))
            expect.append((1, w))
    for r in mp_sample:
        segs = [s for w in kept_ways[r] if w in w_refs for s in ring_segs(w_refs[w])]
        outer = [w for mt, w in rel_members[r] if mt == "w" and w in w_refs]
        if not segs or not outer:
            continue
        pts = [places.get(x) for x in w_refs[outer[0]][:-1] if places.get(x)]
        if not pts:
            continue
        la, lo = int(sum(p[0] for p in pts) / len(pts) + 0.37), int(sum(p[1] for p in pts) / len(pts) + 0.41)
        if evenodd(segs, la, lo):
            points.append((la, lo))
            expect.append((2, r))

    # vertices: a node of each sampled building; every closed way of the clip with it as a vertex (a scan of all ways)
    vsample = sorted({w_refs[w][1] for w in point_buildings if w in w_refs and places.get(w_refs[w][1])})[:2000]
    vset = set(vsample)
    v_oracle = defaultdict(set)
    for o in osmium.FileProcessor(str(a.clip), osmium.osm.WAY):
        nd = o.nodes
        n = len(nd)
        if n >= 4 and nd[0].ref == nd[n - 1].ref:
            for x in nd:
                if x.ref in vset:
                    v_oracle[x.ref].add(o.id)
    print(f"vertex scan: {len(vsample):,} nodes, {time.time() - t:.0f} s", flush=True)
    node_sample = [n for n in node_sample if n not in vset] + vsample

    # the query
    ways = sorted(sample)
    rels = sorted({r for w in ways for r in holders.get(w, [])})
    save_ids(a.work / "ways.npy", ways)
    save_ids(a.work / "rels.npy", rels)
    save_ids(a.work / "nodes.npy", node_sample)
    save_ids(a.work / "node_places.npy", [x for n in node_sample for x in (places[n] or (NO, NO))])
    save_ids(a.work / "points.npy", [x for p in points for x in p])
    out = a.work / "out"
    cmd = [str(a.exe), "context", "--store", str(a.store), "--gen", str(a.gen), "--ways", str(a.work / "ways.npy"),
           "--rels", str(a.work / "rels.npy"), "--nodes", str(a.work / "nodes.npy"),
           "--node-places", str(a.work / "node_places.npy"), "--points", str(a.work / "points.npy"), "--out", str(out)]
    tq = time.time()
    subprocess.run(cmd, check=True)
    print(f"query: {time.time() - tq:.1f} s; {json.loads((out / 'context.json').read_text())}", flush=True)

    bad = []
    # ways
    ids = np.load(out / "w_ids.npy")
    how, offs, refs = np.load(out / "w_how.npy"), np.load(out / "w_offs.npy"), np.load(out / "w_refs.npy")
    lat, lon = np.load(out / "w_lat7.npy"), np.load(out / "w_lon7.npy")
    wt = unpack(out, "w", len(ids))
    aoffs, anodes = np.load(out / "w_aoffs.npy"), np.load(out / "w_anodes.npy")
    hoffs, hrels = np.load(out / "w_hoffs.npy"), np.load(out / "w_hrels.npy")
    for i, w in enumerate(ids.tolist()):
        if w not in w_refs:
            if how[i] != 0:
                bad.append(("way not in clip, found in the store", w))
            continue  # a sampled relation member outside the clip: absent in both
        if how[i] == 0:
            bad.append(("way absent", w))
            continue
        r = refs[offs[i]:offs[i + 1]].tolist()
        if r != w_refs[w]:
            bad.append(("refs", w))
        if wt[i] != w_tags[w]:
            bad.append(("way tags", w))
        pl = [places.get(x) for x in w_refs[w]]
        got = list(zip(lat[offs[i]:offs[i + 1]].tolist(), lon[offs[i]:offs[i + 1]].tolist()))
        if [p for p in pl] != [tuple(g) for g in got]:
            bad.append(("places", w))
        want_a = sorted({x for x in w_refs[w] if any(k.startswith("addr:") for k in n_tags.get(x, {}))})
        if sorted(set(anodes[aoffs[i]:aoffs[i + 1]].tolist())) != want_a:
            bad.append(("addr nodes", w, want_a, anodes[aoffs[i]:aoffs[i + 1]].tolist()))
        # as sets: a relation can list the same way twice
        if how[i] == 1 and set(hrels[hoffs[i]:hoffs[i + 1]].tolist()) != set(holders.get(w, [])):
            bad.append(("holding relations", w))
    n_ways_bad = len(bad)
    # relations
    rids = np.load(out / "r_ids.npy")
    rfound, rt = np.load(out / "r_found.npy"), unpack(out, "r", len(rids))
    moffs, mtype, mref = np.load(out / "r_moffs.npy"), np.load(out / "r_mtype.npy"), np.load(out / "r_mref.npy")
    rbox = np.load(out / "r_box.npy").reshape(-1, 4)
    tchar = {0: "n", 1: "w", 2: "r"}
    for i, r in enumerate(rids.tolist()):
        if not rfound[i]:
            bad.append(("relation not found", r))
            continue
        if rt[i] != rel_tags[r]:
            bad.append(("relation tags", r))
        m = [(tchar[t], x) for t, x in zip(mtype[moffs[i]:moffs[i + 1]].tolist(), mref[moffs[i]:moffs[i + 1]].tolist())]
        if m != rel_members[r]:
            bad.append(("relation members", r))
        ws = kept_ways.get(r, [])
        if ws and all(w in w_refs for w in ws):
            pts = [places[x] for w in ws for x in w_refs[w] if places.get(x)]
            want_box = [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]
            if rbox[i].tolist() != want_box:
                bad.append(("relation box", r, want_box, rbox[i].tolist()))
    n_rels_bad = len(bad) - n_ways_bad
    # nodes
    nids, nfound = np.load(out / "n_ids.npy"), np.load(out / "n_found.npy")
    nt = unpack(out, "n", len(nids))
    for i, n in enumerate(nids.tolist()):
        want = n_tags.get(n, {})
        if places.get(n) is None:
            continue
        if nfound[i] == 0 or (nfound[i] == 1) != bool(want) or nt[i] != want:
            bad.append(("node tags", n, int(nfound[i])))
    voffs, vways = np.load(out / "n_voffs.npy"), np.load(out / "n_vways.npy")
    for i, n in enumerate(nids.tolist()):
        if n in vset and set(vways[voffs[i]:voffs[i + 1]].tolist()) != v_oracle[n]:
            bad.append(("vertex of", n, sorted(v_oracle[n]), vways[voffs[i]:voffs[i + 1]].tolist()))
    n_nodes_bad = len(bad) - n_ways_bad - n_rels_bad
    # points
    poffs, pkind, pid = np.load(out / "p_offs.npy"), np.load(out / "p_kind.npy"), np.load(out / "p_id.npy")
    ekind, eid, ebox = np.load(out / "e_kind.npy"), np.load(out / "e_id.npy"), np.load(out / "e_box.npy").reshape(-1, 4)
    et = unpack(out, "e", len(eid))
    el = {(int(k), int(x)): (b.tolist(), tg) for k, x, b, tg in zip(ekind, eid, ebox, et)}
    missed = precision_bad = checked = 0
    for i, (p, ex) in enumerate(zip(points, expect)):
        got = set(zip(pkind[poffs[i]:poffs[i + 1]].tolist(), pid[poffs[i]:poffs[i + 1]].tolist()))
        if ex not in got:
            missed += 1
            bad.append(("point missed", ex))
        for k, x in got:
            if k == 1 and x in w_refs:
                checked += 1
                if not evenodd(ring_segs(w_refs[x]), *p) or el[(k, x)][1] != w_tags[x]:
                    precision_bad += 1
                    bad.append(("point precision way", x))
            elif k == 2 and x in kept_ways and all(w in w_refs for w in kept_ways[x]):
                checked += 1
                segs = [s for w in kept_ways[x] for s in ring_segs(w_refs[w])]
                if not evenodd(segs, *p) or el[(k, x)][1] != rel_tags[x]:
                    precision_bad += 1
                    bad.append(("point precision relation", x))
    print(f"ways {len(ids):,}: {n_ways_bad} differ; relations {len(rids):,}: {n_rels_bad} differ; nodes {len(nids):,}: "
          f"{n_nodes_bad} differ (tags and the closed ways of {len(vsample):,} vertices); points {len(points):,} ({sum(1 for e in expect if e[0] == 1):,} buildings, "
          f"{sum(1 for e in expect if e[0] == 2):,} multipolygons): {missed} missed, {checked:,} containers rechecked, "
          f"{precision_bad} wrong")
    (a.work / "bad.json").write_text(json.dumps(bad, default=str), encoding="utf-8")
    from collections import Counter
    print("differences by kind:", dict(Counter(b[0] for b in bad)))
    for b in bad[:30]:
        print("  ", b)
    print("ctxcmp: " + ("all equal" if not bad else f"{len(bad)} differences"), f"({time.time() - t:.0f} s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
