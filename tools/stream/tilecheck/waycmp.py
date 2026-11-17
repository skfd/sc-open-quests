"""`tilestore ways` against the clip it was cut from: refs and every ref's place, way for way.

  python tools/stream/tilecheck/waycmp.py --store S --clip X.osm.pbf --work DIR [--sample 100000] [--gen G]
      [--exe tilestore.exe] [--members-only]

Reads the clip with pyosmium (each way's refs; the places of the sampled ways' nodes), samples ways (half of them
member ways of relations, so the relation side is exercised), adds 1,000 ids no way has, runs `tilestore ways` with
the relations of the sampled member ways as --rels, and compares. Exits 1 on any difference. The clip must be the
store generation's own day (generation 0 of a cut, or a day's clip for a later generation)."""
import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import osmium

ROOT = Path(__file__).resolve().parents[3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", type=Path, required=True)
    ap.add_argument("--clip", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--sample", type=int, default=100_000)
    ap.add_argument("--gen", type=int, default=-1)
    ap.add_argument("--exe", type=Path, default=ROOT / "tilestore/target/release/tilestore.exe")
    ap.add_argument("--rels-only", action="store_true",
                    help="only member ways, found through the relation store alone (TILESTORE_WAYS_RELS_ONLY=1)")
    a = ap.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    t = time.time()
    way_refs: dict[int, list[int]] = {}
    member_of: dict[int, int] = {}
    for o in osmium.FileProcessor(str(a.clip), osmium.osm.WAY | osmium.osm.RELATION):
        if o.is_way():
            way_refs[o.id] = [n.ref for n in o.nodes]
        else:
            for m in o.members:
                if m.type == "w":
                    member_of.setdefault(m.ref, o.id)
    print(f"clip: {len(way_refs):,} ways, {len(member_of):,} member ways, {time.time() - t:.0f} s", flush=True)
    rnd = random.Random(7)
    members = [w for w in member_of if w in way_refs]
    half = a.sample // 2
    sample = rnd.sample(members, min(a.sample if a.rels_only else half, len(members)))
    rest = [] if a.rels_only else rnd.sample(sorted(way_refs), a.sample - len(sample))
    sample = sorted(set(sample) | set(rest))
    absent = []
    top = max(way_refs)
    while len(absent) < 1000:
        x = rnd.randrange(1, top + 10**9)
        if x not in way_refs:
            absent.append(x)
    ids = np.array(sample + absent, dtype=np.int64)
    rnd.shuffle(ids)  # asked in no order
    np.save(a.work / "ids.npy", ids)
    rels = np.array(sorted({member_of[w] for w in sample if w in member_of}), dtype=np.int64)
    np.save(a.work / "rels.npy", rels)
    need = {r for w in sample for r in way_refs[w]}
    t = time.time()
    place = {}
    for n in osmium.FileProcessor(str(a.clip), osmium.osm.NODE):
        if n.id in need:
            place[n.id] = (n.location.y, n.location.x)
    print(f"clip: {len(place):,} of {len(need):,} nodes placed, {time.time() - t:.0f} s", flush=True)
    out = a.work / "out"
    t = time.time()
    subprocess.run([str(a.exe), "ways", "--store", str(a.store), "--gen", str(a.gen), "--ids", str(a.work / "ids.npy"),
                    "--rels", str(a.work / "rels.npy"), "--out", str(out)], check=True,
                   env={**__import__("os").environ, **({"TILESTORE_WAYS_RELS_ONLY": "1"} if a.rels_only else {})})
    print(f"tilestore ways: {time.time() - t:.1f} s; {(out / 'ways.json').read_text()}", flush=True)
    got_ids, how, offs = np.load(out / "ids.npy"), np.load(out / "how.npy"), np.load(out / "offs.npy")
    refs, lat, lon = np.load(out / "refs.npy"), np.load(out / "lat7.npy"), np.load(out / "lon7.npy")
    assert (got_ids == ids).all()
    bad = 0
    hows = {0: 0, 1: 0, 2: 0}
    for i, w in enumerate(ids.tolist()):
        hows[int(how[i])] += 1
        r = refs[offs[i]:offs[i + 1]].tolist()
        if w not in way_refs:
            if how[i] != 0 or r:
                bad += 1
                print(f"way {w}: no such way in the clip, the store gives {len(r)} refs (how {how[i]})")
            continue
        if how[i] == 0:
            if a.rels_only:  # the relation store keeps member ways of the relations the tile rule keeps only
                continue
            bad += 1
            print(f"way {w}: absent in the store")
            continue
        if r != way_refs[w]:
            bad += 1
            print(f"way {w}: refs differ ({len(r)} against {len(way_refs[w])})")
            continue
        want = [place.get(n, (np.iinfo(np.int32).min,) * 2) for n in r]
        g = list(zip(lat[offs[i]:offs[i + 1]].tolist(), lon[offs[i]:offs[i + 1]].tolist()))
        if g != want:
            bad += 1
            k = next(j for j in range(len(g)) if g[j] != want[j])
            print(f"way {w}: node {r[k]} at {g[k]}, the clip {want[k]}")
        if bad > 50:
            print("... stopping at 50")
            break
    print(f"{len(ids):,} asked ({len(sample):,} ways, {len(absent):,} absent ids); how {hows}; "
          f"{'EQUAL' if not bad else f'{bad} DIFFER'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
