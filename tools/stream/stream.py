"""The stream prototype: a state of open quests kept current from OSM's diffs, held against full counts.

DESIGN.md, "The stream: its state". The state is what the engine's --dump-state wrote for the seed, kept in
memory as one sorted table (a region; the world's will not fit this way). A diff is applied by recounting only
the elements it touched, tier 1 only (the area pass off): every row of a touched element for a tier-1 quest
is replaced by what the engine says of its last version. Aging needs no event: a row waiting for its date is
open from its `due` on. Notes are left out of every comparison (the HIDDEN flag is kept, not used).

  stream.py nodes --clip X.osm.pbf --dir D
      the node locations of the seed's clip (sparse, D/nodes.idx); later changes go into D/overlay.pickle
  stream.py count --pbf X.osm.pbf --today ISO --cities C.json --zone Z --notes N.jsonl --dir D
      a whole clip counted with --dump-state (D/state.bin): the seed, or a day to check against
  stream.py seed --dump X.bin --dir D
      the state from a --dump-state file (the seed's clip counted whole)
  stream.py apply --dir D --diff N.osc.gz --today 2026-11-09T00:00:00Z --cities C.json --zone Europe/London
      one diff: the touched elements' last versions into a small PBF, through the engine, into the state
  stream.py check --dir D --dump Y.bin
      the state at its clock against a full count's --dump-state of the same instant

Prototype limits, each reported by `check`: a way whose nodes moved but which has no version itself keeps
its old position; relations are not recounted; tier 2 (the area quests) keeps the seed's rows.
"""
import argparse
import json
import os
import pickle
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine" / "build" / "install" / "sc-open-quests-engine" / "bin" / "sc-open-quests-engine.bat"
REC = np.dtype([("key", "<i8"), ("lat", "<i4"), ("lon", "<i4"), ("quest", "<u2"), ("flags", "u1"), ("kind", "u1"), ("due", "<i4")])
M_NOW, HIDDEN, MATCH, DUE = 1, 64, 0, 1
SYNTHETIC = 10**15  # way nodes in the small PBF: above every real node id
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:6.1f} s] {msg}", flush=True)


def minute(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() // 60)


def area_quests() -> set[str]:
    src = (ROOT / "engine/src/main/kotlin/ported/AreaQuests.kt").read_text(encoding="utf-8")
    return set(re.findall(r"^\s+de\.westnordost[\w.]*\.(\w+),?\s*$", src, re.M))


def read_dump(path: Path, names: list[str]) -> np.ndarray:
    """a --dump-state file with its quests renumbered to `names` (extended in place), duplicates dropped"""
    a = np.fromfile(path, REC)
    own = json.loads(Path(str(path) + ".json").read_text(encoding="utf-8"))["quests"]
    for q in own:
        if q not in names:
            names.append(q)
    a["quest"] = np.array([names.index(q) for q in own], dtype=np.uint16)[a["quest"]]
    return np.unique(a)


class State:
    def __init__(self, d: Path):
        self.d = d
        self.meta = json.loads((d / "state.json").read_text(encoding="utf-8"))
        self.names: list[str] = self.meta["quests"]
        self.rows = np.load(d / "rows.npy")

    @staticmethod
    def create(d: Path, rows: np.ndarray, names: list[str], clock: str):
        d.mkdir(parents=True, exist_ok=True)
        np.save(d / "rows.npy", np.sort(rows, order=["key", "quest", "kind"]))
        (d / "state.json").write_text(json.dumps({"clock": clock, "quests": names, "applied": []}, indent=1), encoding="utf-8")

    def save(self):
        np.save(self.d / "rows.npy", np.sort(self.rows, order=["key", "quest", "kind"]))
        self.meta["quests"] = self.names
        (self.d / "state.json").write_text(json.dumps(self.meta, indent=1), encoding="utf-8")

    def tier1(self) -> np.ndarray:
        area = area_quests()
        return np.array([n not in area and n != "OsmNoteQuestType" for n in self.names] + [False] * 8)


def open_codes(rows: np.ndarray, at_min: int, quest_mask: np.ndarray) -> np.ndarray:
    """(key, quest) as one int64 for every row open at `at_min` among the quests in quest_mask"""
    # a date for the default setting: flags M_NOW, or no setting bit at all (dumps before the 0.5 and 2 dates)
    default = (rows["flags"] & 63 == 0) | (rows["flags"] & M_NOW > 0)
    is_open = ((rows["kind"] == MATCH) & (rows["flags"] & M_NOW > 0)) | ((rows["kind"] == DUE) & (rows["due"] <= at_min) & default)
    r = rows[is_open & quest_mask[rows["quest"]]]
    return np.unique(r["key"] * 1024 + r["quest"])


# --- nodes ---------------------------------------------------------------------------------------

def nodes(clip: Path, d: Path):
    import osmium
    import osmium.index
    d.mkdir(parents=True, exist_ok=True)
    idx_path = d / "nodes.idx"
    if idx_path.exists():
        idx_path.unlink()
    idx = osmium.index.create_map(f"sparse_file_array,{idx_path}")
    lh = osmium.NodeLocationsForWays(idx)
    lh.apply_nodes_to_ways = False
    t = time.time()
    osmium.apply(osmium.io.Reader(str(clip), osmium.osm.NODE), lh)
    del idx
    with open(d / "overlay.pickle", "wb") as f:
        pickle.dump({}, f)
    log(f"node locations of {clip.name} in {time.time() - t:.0f} s: {idx_path.stat().st_size / 2**30:.2f} GiB")


class Locations:
    """the clip's node locations (never written: a sparse file must stay sorted) plus the changes since"""

    def __init__(self, d: Path):
        import osmium.index
        self.idx = osmium.index.create_map(f"sparse_file_array,{d / 'nodes.idx'}")
        self.d = d
        with open(d / "overlay.pickle", "rb") as f:
            self.overlay: dict[int, tuple[float, float] | None] = pickle.load(f)

    def get(self, nid: int):
        if nid in self.overlay:
            return self.overlay[nid]
        try:
            loc = self.idx.get(nid)
        except KeyError:
            return None
        return (loc.lat, loc.lon) if loc.valid() else None

    def save(self):
        with open(self.d / "overlay.pickle", "wb") as f:
            pickle.dump(self.overlay, f)


# --- apply ---------------------------------------------------------------------------------------

def read_diff(path: Path):
    """the last version of every node and way in the diff (a day diff is sorted by type, id, version)"""
    import osmium
    last_node, last_way, relations = {}, {}, 0
    for o in osmium.FileProcessor(str(path)):
        if o.is_node():
            ok = o.visible and o.location.valid()
            last_node[o.id] = (o.version, o.timestamp, ok, {t.k: t.v for t in o.tags},
                               (o.location.lat, o.location.lon) if ok else None)
        elif o.is_way():
            last_way[o.id] = (o.version, o.timestamp, o.visible, {t.k: t.v for t in o.tags}, [n.ref for n in o.nodes])
        else:
            relations += 1
    return last_node, last_way, relations


def write_small_pbf(path: Path, stamp: str, last_node, last_way, locs: Locations, unplaced: list | None = None) -> Counter:
    import osmium
    stats = Counter()
    syn: dict[tuple[float, float], int] = {}
    ways = []
    for wid in sorted(last_way):
        version, ts, visible, tags, refs = last_way[wid]
        if not (visible and tags and refs):
            continue
        srefs = []
        for r in refs:
            p = locs.get(r)
            if p is None:
                stats["ways with a node not placed"] += 1
                if unplaced is not None:
                    unplaced.append(wid)
                srefs = None
                break
            s = syn.get(p)
            if s is None:
                s = syn[p] = SYNTHETIC + len(syn)
            srefs.append(s)
        if srefs is None:
            continue
        ways.append((wid, version, ts, tags, srefs))
    header = osmium.io.Header()
    header.set("osmosis_replication_timestamp", stamp)
    header.set("sorting", "Type_then_ID")
    w = osmium.SimpleWriter(str(path), header=header, overwrite=True)
    N = osmium.osm.mutable.Node
    for nid in sorted(last_node):
        version, ts, alive, tags, loc = last_node[nid]
        if alive and tags:
            w.add_node(N(id=nid, version=version, timestamp=ts, tags=tags, location=(loc[1], loc[0])))
            stats["tagged nodes"] += 1
    for (lat, lon), s in sorted(syn.items(), key=lambda kv: kv[1]):
        w.add_node(N(id=s, version=1, location=(lon, lat)))
    for wid, version, ts, tags, srefs in ways:
        w.add_way(osmium.osm.mutable.Way(id=wid, version=version, timestamp=ts, tags=tags, nodes=srefs))
    w.close()
    stats["tagged ways"] = len(ways)
    return stats


def engine(pbf: Path, out: Path, today: str, cities: Path, zone: str, notes: Path | None, area_pass: bool,
           heap_gb: int = 8, quests: Path | None = None) -> Path:
    # the engine runs where the cities file's data is (its boundaries are relative paths; data/ is not all in git)
    pbf, out, cities = pbf.resolve(), out.resolve(), cities.resolve()
    notes = notes.resolve() if notes else None
    base = cities.parents[2]
    quests = (quests or sorted((base / "data" / "quests").glob("v*.json"))[-1]).resolve()
    dump = out / "state.bin"
    out.mkdir(parents=True, exist_ok=True)
    args = [str(ENGINE), "count", "--pbf", str(pbf), "--quests", str(quests), "--cities", str(cities),
            "--out", str(out / "out"), "--today", today, "--dump-state", str(dump)]
    if notes:
        args += ["--notes", str(notes)]
    env = dict(os.environ, JAVA_HOME=os.environ.get("JAVA_HOME", r"C:\Program Files\Android\Android Studio\jbr"),
               JAVA_OPTS=f"-Duser.timezone={zone} -Duser.language=en -Duser.country=CA -Xmx{heap_gb}g"
                         + ("" if area_pass else " -Dopenquests.areaPass=false"))
    t = time.time()
    with open(out / "engine.log", "w", encoding="utf-8") as f:
        r = subprocess.run(args, cwd=base, env=env, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        sys.exit(f"engine failed ({r.returncode}), see {out / 'engine.log'}")
    log(f"engine over {pbf.name} in {time.time() - t:.1f} s")
    return dump


def apply(d: Path, diff: Path, today: str, cities: Path, zone: str, notes: Path | None):
    st = State(d)
    if diff.name in st.meta["applied"]:
        log(f"{diff.name} applied before")
        return
    t = time.time()
    last_node, last_way, relations = read_diff(diff)
    log(f"{diff.name}: {len(last_node):,} nodes, {len(last_way):,} ways with a version; {relations:,} relation versions (not recounted); "
        f"read in {time.time() - t:.0f} s")
    t = time.time()
    locs = Locations(d)
    for nid, (_, _, alive, _, loc) in last_node.items():
        locs.overlay[nid] = loc if alive else None
    work = d / "work"
    work.mkdir(exist_ok=True)
    unplaced: list[int] = []
    stats = write_small_pbf(work / "touched.osm.pbf", today, last_node, last_way, locs, unplaced)
    log(f"small PBF in {time.time() - t:.0f} s: {dict(stats)}")
    dump = engine(work / "touched.osm.pbf", work, today, cities, zone, notes, area_pass=False)
    new = read_dump(dump, st.names)

    tier1 = st.tier1()
    before = open_codes(st.rows, minute(st.meta["clock"]), tier1)
    touched = np.unique(np.concatenate([np.fromiter(last_node, np.int64, len(last_node)) * 4,
                                        np.fromiter(last_way, np.int64, len(last_way)) * 4 + 1]))
    drop = np.isin(st.rows["key"], touched) & tier1[st.rows["quest"]]
    st.rows = np.concatenate([st.rows[~drop], new[tier1[new["quest"]]]])
    after = open_codes(st.rows, minute(today), tier1)
    opened, closed = np.setdiff1d(after, before).size, np.setdiff1d(before, after).size
    st.meta["clock"] = today
    st.meta["applied"].append(diff.name)
    st.meta.setdefault("days", []).append({"diff": diff.name, "today": today, "rowsDropped": int(drop.sum()),
                                           "rowsAdded": int(len(new)), "opened": int(opened), "closed": int(closed),
                                           "seconds": round(time.time() - T0, 1), **{k: int(v) for k, v in stats.items()}})
    st.save()
    locs.save()
    # every key a diff touched so far, and the ways that could not be placed: check splits its differences by them
    for name, keys in (("touched", touched), ("unplaced", np.array(unplaced, np.int64) * 4 + 1)):
        f = d / f"{name}.npy"
        np.save(f, np.union1d(np.load(f), keys) if f.exists() else np.unique(keys))
    log(f"state at {today}: {int(drop.sum()):,} rows of touched elements replaced by {len(new):,}; tier 1 opened {opened:,}, "
        f"closed {closed:,} (aging included); {len(st.rows):,} rows; {time.time() - T0:.0f} s in all")


# --- seed and check ------------------------------------------------------------------------------

def seed(dump: Path, d: Path):
    names: list[str] = []
    rows = read_dump(dump, names)
    clock = json.loads(Path(str(dump) + ".json").read_text(encoding="utf-8"))["asOf"]
    State.create(d, rows, names, clock)
    log(f"seed {dump}: {len(rows):,} rows ({int((rows['kind'] == DUE).sum()):,} waiting for a date), clock {clock}")


def check(d: Path, dump: Path):
    st = State(d)
    ref = read_dump(dump, st.names)
    clock = json.loads(Path(str(dump) + ".json").read_text(encoding="utf-8"))["asOf"]
    assert minute(clock) == minute(st.meta["clock"]), f"the state is at {st.meta['clock']}, the dump at {clock}"
    at = minute(clock)
    tier1 = st.tier1()
    tier2 = ~tier1
    tier2[[i for i, n in enumerate(st.names) if n == "OsmNoteQuestType"]] = False
    lines = [f"state {d} at {clock} against {dump}", ""]
    for name, mask in (("tier 1", tier1), ("tier 2 (kept from the seed)", tier2)):
        a, b = open_codes(st.rows, at, mask), open_codes(ref, at, mask)
        only_s, only_r = np.setdiff1d(a, b), np.setdiff1d(b, a)
        lines.append(f"{name}: state {a.size:,} open, full count {b.size:,}; equal {a.size - only_s.size:,}; "
                     f"only in the state {only_s.size:,}; only in the count {only_r.size:,}")
        for label, codes in (("only in the state", only_s), ("only in the count", only_r)):
            if not codes.size:
                continue
            keys = codes // 1024
            touched = np.load(d / "touched.npy") if (d / "touched.npy").exists() else np.zeros(0, np.int64)
            unplaced = np.load(d / "unplaced.npy") if (d / "unplaced.npy").exists() else np.zeros(0, np.int64)
            rel = (keys & 3) == 2
            unpl = np.isin(keys, unplaced) & ~rel
            tch = np.isin(keys, touched) & ~rel & ~unpl
            lines.append(f"  {label}: a relation {int(rel.sum()):,}; a way not placed {int(unpl.sum()):,}; "
                         f"an element a diff touched {int(tch.sum()):,}; untouched {int((~rel & ~unpl & ~tch).sum()):,}")
            types = Counter(("node", "way", "relation")[int(k) & 3] for k in keys)
            quests = Counter(st.names[int(q)] for q in codes % 1024).most_common(8)
            lines.append(f"  {label}: by type {dict(types)}; by quest {quests}")
            lines.append(f"    e.g. {[(('n', 'w', 'r')[int(c // 1024) & 3] + str(int(c // 1024) >> 2), st.names[int(c % 1024)]) for c in codes[:6]]}")
    lines += rows_check(st, ref, tier1, d)
    text = "\n".join(lines)
    print(text)
    (d / f"check-{clock[:10]}.txt").write_text(text + "\n", encoding="utf-8")


def rows_check(st: State, ref: np.ndarray, tier1: np.ndarray, d: Path) -> list[str]:
    """tier 1, every row and every field, not only the open set: the position, the variant bits, the due date.
    A state row waiting for a date that has come is the count's open match (M_NOW, and M_AGED: it opened by
    age). The 0.5 and 2 variants have no dates, so their bits are told apart. The note flag is reported apart
    too: apply's runs have no notes clip, so a row keeps the seed's flag until its element is edited."""
    at = minute(st.meta["clock"])
    touched = np.load(d / "touched.npy") if (d / "touched.npy").exists() else np.zeros(0, np.int64)
    a, b = st.rows[tier1[st.rows["quest"]]], ref[tier1[ref["quest"]]]
    code = lambda r: r["key"] * 1024 + r["quest"].astype(np.int64)
    def setting(r):  # a date's setting bit; none in dumps before the 0.5 and 2 dates: the default
        f = r["flags"] & 63
        return np.where(f == 0, M_NOW, f)

    ma, da = a[a["kind"] == MATCH].copy(), a[a["kind"] == DUE]
    came_n = 0
    for bit, aged in ((M_NOW, 2), (4, 8), (16, 32)):
        came = da[(setting(da) == bit) & (da["due"] <= at)]
        came_n += len(came)
        ma["flags"][np.isin(code(ma), code(came))] |= bit | aged
        extra = came[~np.isin(code(came), code(ma))].copy()
        extra["kind"], extra["flags"] = MATCH, (extra["flags"] & HIDDEN) | bit | aged
        ma = np.concatenate([ma, extra])
    da = da[da["due"] > at]
    mb, db = b[b["kind"] == MATCH], b[b["kind"] == DUE]
    dcode = lambda r: code(r) * 64 + setting(r)
    name = lambda k, q: ("n", "w", "r")[int(k) & 3] + str(int(k) >> 2) + " " + st.names[int(q)]
    out = [f"tier 1, every row: matches state {len(ma):,} / count {len(mb):,}; waiting for a date state {len(da):,} / count {len(db):,} "
           f"({came_n:,} of the state's dates have come and count as matches)"]

    def sides(label, x, y):
        cfn = code if label == "match" else dcode
        code_, cx, cy = cfn, cfn(x), cfn(y)
        for side, r, other in (("only in the state", x, cy), ("only in the count", y, cx)):
            r = r[~np.isin(code_(r), other)]
            if len(r):
                now = (r["flags"] & M_NOW) > 0 if label == "match" else np.zeros(len(r), bool)
                el = r["key"]
                out.append(f"  {label} {side}: {len(r):,} (open now {int(now.sum()):,}, only at 0.5 or 2 {int((~now).sum()):,}); "
                           f"a relation {int(((el & 3) == 2).sum()):,}; touched {int(np.isin(el, touched).sum()):,}; by quest "
                           f"{Counter(st.names[int(q)] for q in r['quest']).most_common(4)}; e.g. {[name(k, q) for k, q in zip(el[:4], r['quest'][:4])]}")
        both, ix, iy = np.intersect1d(cx, cy, return_indices=True)
        return x[ix], y[iy]

    ra, rb = sides("match", ma, mb)
    moved = (ra["lat"] != rb["lat"]) | (ra["lon"] != rb["lon"])
    if moved.any():
        dy = (ra["lat"][moved] - rb["lat"][moved]) * 1e-7 * 111_320
        dx = (ra["lon"][moved] - rb["lon"][moved]) * 1e-7 * 111_320 * np.cos(np.radians(rb["lat"][moved] * 1e-7))
        m = np.hypot(dx, dy)
        el = ra["key"][moved]
        out.append(f"  match in both, position differs: {int(moved.sum()):,} (touched {int(np.isin(el, touched).sum()):,}; "
                   f"by type {dict(Counter(('node', 'way', 'relation')[int(k) & 3] for k in el))}); metres: median {np.median(m):.1f}, "
                   f"90% {np.percentile(m, 90):.1f}, max {m.max():.0f}; over 10 m {int((m > 10).sum()):,}, over 100 m {int((m > 100).sum()):,}; "
                   f"e.g. {[name(k, q) for k, q in zip(el[:4], ra['quest'][moved][:4])]}")
    else:
        out.append("  match in both, position differs: 0")
    for label, mask in (("M_NOW", 1), ("aged-only at default", 2), ("the 0.5 and 2 bits", 60)):
        n = int(((ra["flags"] ^ rb["flags"]) & mask > 0).sum())
        out.append(f"  match in both, {label} differs: {n:,}")
    n = int(((ra["flags"] ^ rb["flags"]) & HIDDEN > 0).sum())
    out.append(f"  match in both, note flag differs (not an error): {n:,}")
    xa, xb = sides("waiting", da, db)
    out.append(f"  waiting in both, date differs: {int((xa['due'] != xb['due']).sum()):,}; position differs: "
               f"{int(((xa['lat'] != xb['lat']) | (xa['lon'] != xb['lon'])).sum()):,}")
    return out


def tsv(dump: Path, old: Path):
    """the open, unhidden records of a --dump-state against an older engine's --dump-matches of the same clip
    (its quests only): nothing but the new option may differ, and notes when the notes clips differ"""
    names: list[str] = []
    a = read_dump(dump, names)
    T = {"node": 0, "way": 1, "relation": 2}
    old_set, quests = set(), set()
    with open(old, encoding="utf-8") as f:
        next(f)
        for line in f:
            q, t, i = line.split("	", 3)[:3]
            old_set.add((int(i) * 4 + T[t], q))
            quests.add(q)
    sel = a[(a["kind"] == MATCH) & (a["flags"] & M_NOW > 0)]
    hidden = {(int(k), names[q]) for k, q, fl in zip(sel["key"], sel["quest"], sel["flags"]) if fl & HIDDEN and names[q] in quests}
    new_set = {(int(k), names[q]) for k, q, fl in zip(sel["key"], sel["quest"], sel["flags"]) if not fl & HIDDEN and names[q] in quests}
    only_new, only_old = new_set - old_set, old_set - new_set
    print(f"{dump} against {old}: {len(new_set):,} open and unhidden, {len(old_set):,} in the old dump; "
          f"only new {len(only_new):,}, only old {len(only_old):,} (of those hidden by a note in the new run: {len(only_old & hidden):,})")
    for k in list(only_new)[:5] + list(only_old - hidden)[:5]:
        print("   ", k)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["nodes", "count", "seed", "apply", "check", "tsv"])
    ap.add_argument("--tsv", type=Path)
    ap.add_argument("--pbf", type=Path)
    ap.add_argument("--heap-gb", type=int, default=30)
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--clip", type=Path)
    ap.add_argument("--dump", type=Path)
    ap.add_argument("--diff", type=Path)
    ap.add_argument("--today")
    ap.add_argument("--cities", type=Path)
    ap.add_argument("--zone", default="UTC")
    ap.add_argument("--notes", type=Path)
    o = ap.parse_args()
    if o.cmd == "nodes":
        nodes(o.clip, o.dir)
    elif o.cmd == "count":
        engine(o.pbf, o.dir, o.today, o.cities, o.zone, o.notes, area_pass=True, heap_gb=o.heap_gb)
    elif o.cmd == "seed":
        seed(o.dump, o.dir)
    elif o.cmd == "apply":
        apply(o.dir, o.diff, o.today, o.cities, o.zone, o.notes)
    elif o.cmd == "tsv":
        tsv(o.dump, o.tsv)
    else:
        check(o.dir, o.dump)
