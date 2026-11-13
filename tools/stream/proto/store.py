"""Step 5 of the stream: a node location store for the planet, and the versions before a day's stream.

  store.py ids                                   the element ids of the day's minute files -> ids.pickle
  store.py build --pbf X --store F [--half]      one pass over a history file: every node's last position
                                                 into F (dense_file_array), and the last version of every
                                                 stream element -> priors-<name>.pickle
  store.py verify --pbf X --store F              (pilot) the other half of the ids, read again, against F
  store.py diffs --store F --priors P            day diffs 5165..5170 applied to F and to the priors

Everything is written beside this file (.scratch/store, gitignored) unless a path is given.
"""
import argparse
import pickle
import sys
import threading
import time
from pathlib import Path

import osmium
import osmium.filter
import osmium.index

S = Path(__file__).parent
ROOT = S.parent.parent
REPLAY = ROOT / ".scratch" / "stream-replay"
STORE = Path.home() / "Code" / ".osm-data"
DAY_DIFFS = range(5165, 5171)  # 11-02T00Z (the history file) to 11-08T00Z (the stream's start)
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:6.0f} s] {msg}", flush=True)


def stream_ids():
    first, last, _, _ = map(int, (REPLAY / "range.txt").read_text().split())
    nodes, ways, rels = set(), set(), set()
    n = 0
    for seq in range(first, last + 1):
        for o in osmium.FileProcessor(str(REPLAY / "minute" / f"{seq}.osc.gz")):
            n += 1
            if o.is_node():
                nodes.add(o.id)
            elif o.is_way():
                ways.add(o.id)
            else:
                rels.add(o.id)
    log(f"stream {first}..{last}: {n:,} versions on {len(nodes):,} nodes, {len(ways):,} ways, {len(rels):,} relations")
    with open(S / "ids.pickle", "wb") as f:
        pickle.dump({"nodes": nodes, "ways": ways, "relations": rels}, f)


def load_ids(half=None):
    with open(S / "ids.pickle", "rb") as f:
        ids = pickle.load(f)
    if half is not None:
        ids = {k: {i for i in v if i % 2 == half} for k, v in ids.items()}
    return ids


class Priors:
    """The last version of each element that passes the id filters. A version with no tags or a
    deleted one holds no quest, so it only removes what an earlier version left."""

    def __init__(self):
        self.nodes = {}  # id -> (version, timestamp, tags, lat, lon)
        self.ways = {}   # id -> (version, timestamp, tags, refs)
        self.seen = [0, 0]
        self.last = time.time()
        self.where = ("", 0)

    def node(self, o):
        self.seen[0] += 1
        self.where = ("node", o.id)
        if o.visible and len(o.tags) and o.location.valid():
            self.nodes[o.id] = (o.version, o.timestamp, {t.k: t.v for t in o.tags}, o.location.lat, o.location.lon)
        else:
            self.nodes.pop(o.id, None)

    def way(self, o):
        self.seen[1] += 1
        self.where = ("way", o.id)
        if o.visible and len(o.tags) and len(o.nodes):
            self.ways[o.id] = (o.version, o.timestamp, {t.k: t.v for t in o.tags}, [n.ref for n in o.nodes])
        else:
            self.ways.pop(o.id, None)

    def relation(self, o):
        self.where = ("relation", o.id)


def watch(prior, store_path, stop):
    """A line a minute: the store file's size says how far the nodes are."""
    while not stop.wait(60):
        size = Path(store_path).stat().st_size if Path(store_path).exists() else 0
        log(f"  at {prior.where[0]} {prior.where[1]:,}; store {size / 2**30:.1f} GB; "
            f"callbacks {prior.seen[0]:,} nodes, {prior.seen[1]:,} ways; kept {len(prior.nodes):,} / {len(prior.ways):,}")


def filters(ids):
    nf = osmium.filter.IdFilter(ids["nodes"])
    nf.enable_for(osmium.osm.NODE)
    wf = osmium.filter.IdFilter(ids["ways"])
    wf.enable_for(osmium.osm.WAY)
    rf = osmium.filter.IdFilter([])
    rf.enable_for(osmium.osm.RELATION)
    return nf, wf, rf


def build(pbf, store_path, half, name):
    ids = load_ids(0 if half else None)
    log(f"filter: {len(ids['nodes']):,} nodes, {len(ids['ways']):,} ways{' (even ids only)' if half else ''}")
    idx = osmium.index.create_map(f"dense_file_array,{store_path}")
    lh = osmium.NodeLocationsForWays(idx)
    lh.apply_nodes_to_ways = False
    lh.ignore_errors()
    prior = Priors()
    stop = threading.Event()
    threading.Thread(target=watch, args=(prior, store_path, stop), daemon=True).start()
    t = time.time()
    # two readers: with the location handler in the chain the ways took twelve times as long (pilot)
    nf, wf, rf = filters(ids)
    osmium.apply(osmium.io.Reader(pbf, osmium.osm.NODE), lh, nf, prior)
    log(f"nodes in {time.time() - t:.0f} s; callbacks {prior.seen[0]:,}; tagged priors {len(prior.nodes):,}")
    t2 = time.time()
    osmium.apply(osmium.io.Reader(pbf, osmium.osm.WAY), wf, prior)
    log(f"ways in {time.time() - t2:.0f} s; callbacks {prior.seen[1]:,}; tagged priors {len(prior.ways):,}")
    stop.set()
    Path(str(store_path) + ".state").write_text("history file " + Path(pbf).name)
    log(f"pass over {Path(pbf).name} ({Path(pbf).stat().st_size / 2**30:.1f} GB) in {time.time() - t:.0f} s; "
        f"store {Path(store_path).stat().st_size / 2**30:.1f} GB; callbacks {prior.seen[0]:,} nodes, {prior.seen[1]:,} ways; "
        f"tagged priors {len(prior.nodes):,} nodes, {len(prior.ways):,} ways")
    with open(S / f"priors-{name}.pickle", "wb") as f:
        pickle.dump({"nodes": prior.nodes, "ways": prior.ways}, f)
    del idx
    log("done")


class LastSeen:
    def __init__(self):
        self.nodes = {}  # id -> (visible, lat, lon) of the last version

    def node(self, o):
        self.nodes[o.id] = (o.visible and o.location.valid(), o.location.lat if o.location.valid() else None,
                            o.location.lon if o.location.valid() else None)

    def way(self, o):
        pass

    def relation(self, o):
        pass


def verify(pbf, store_path):
    """The odd ids were never let through the filter while the store was built. Read them now and
    hold the store against their last version: last version wins, a deleted node reads as absent."""
    ids = load_ids(1)
    seen = LastSeen()
    nf = osmium.filter.IdFilter(ids["nodes"])
    nf.enable_for(osmium.osm.NODE)
    t = time.time()
    osmium.apply(osmium.io.Reader(pbf, osmium.osm.NODE), nf, seen)
    log(f"second pass (nodes only, no store) in {time.time() - t:.0f} s: {len(seen.nodes):,} odd stream nodes in {Path(pbf).name}")
    idx = osmium.index.create_map(f"dense_file_array,{store_path}")
    ok = wrong = dead_ok = dead_wrong = 0
    t = time.time()
    for nid, (alive, lat, lon) in seen.nodes.items():
        try:
            loc = idx.get(nid)
            got = (loc.lat, loc.lon) if loc.valid() else None
        except KeyError:
            got = None
        if alive:
            if got is not None and abs(got[0] - lat) < 1e-9 and abs(got[1] - lon) < 1e-9:
                ok += 1
            else:
                wrong += 1
                if wrong <= 5:
                    log(f"  node {nid}: file {lat},{lon} store {got}")
        else:
            if got is None:
                dead_ok += 1
            else:
                dead_wrong += 1
                if dead_wrong <= 5:
                    log(f"  deleted node {nid}: store {got}")
    log(f"{len(seen.nodes):,} lookups in {time.time() - t:.1f} s: alive and equal {ok:,}, alive and different {wrong:,}; "
        f"deleted and absent {dead_ok:,}, deleted but present {dead_wrong:,}")


def diffs(store_path, priors_path):
    ids = load_ids()
    with open(priors_path, "rb") as f:
        p = pickle.load(f)
    prior = Priors()
    prior.nodes, prior.ways = p["nodes"], p["ways"]
    idx = osmium.index.create_map(f"dense_file_array,{store_path}")
    lh = osmium.NodeLocationsForWays(idx)
    lh.apply_nodes_to_ways = False
    lh.ignore_errors()
    for seq in DAY_DIFFS:
        t = time.time()
        before = tuple(prior.seen)
        path = str(STORE / "planet" / "diffs" / f"{seq}.osc.gz")
        osmium.apply(osmium.io.Reader(path), lh, *filters(ids), prior)
        # a deletion in a replication file carries the node's last place, and the handler stores it:
        # empty the slot of every node whose last version in the file is a deletion
        gone = {}
        for o in osmium.FileProcessor(path, osmium.osm.NODE):
            gone[o.id] = not o.visible
        emptied = 0
        for nid, dead in gone.items():
            if dead:
                idx.set(nid, osmium.osm.Location())
                emptied += 1
        log(f"  {emptied:,} deleted nodes emptied")
        log(f"day diff {seq} in {time.time() - t:.0f} s; stream elements in it: {prior.seen[0] - before[0]:,} node versions, "
            f"{prior.seen[1] - before[1]:,} way versions")
    with open(S / "priors-1108.pickle", "wb") as f:
        pickle.dump({"nodes": prior.nodes, "ways": prior.ways}, f)
    del idx
    Path(str(store_path) + ".state").write_text("2026-11-08T00:00:00Z")
    log(f"priors at 11-08T00Z: {len(prior.nodes):,} tagged nodes, {len(prior.ways):,} tagged ways")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["ids", "build", "verify", "diffs"])
    ap.add_argument("--pbf")
    ap.add_argument("--store")
    ap.add_argument("--priors")
    ap.add_argument("--half", action="store_true")
    ap.add_argument("--name", default="pass")
    a = ap.parse_args()
    if a.cmd == "ids":
        stream_ids()
    elif a.cmd == "build":
        build(a.pbf, a.store, a.half, a.name)
    elif a.cmd == "verify":
        verify(a.pbf, a.store)
    else:
        diffs(a.store, a.priors)
