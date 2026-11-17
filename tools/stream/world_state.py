"""The world's stream state (DESIGN.md, "The world state store"): the world seed's own files, one per plan.json file,
each sorted by (key, quest, kind) so a day's touched keys are found with searchsorted, and a manifest of each
file's rect, rows and key range.

    python tools/stream/world_state.py sort WORLD_DIR [--workers 4]
        sort every files/<f>/state.bin in place (atomically, a file at a time; a sorted file is skipped) and write
        WORLD_DIR/world-state.json, plus world-state-shared.npy: the keys found in more than one file
    python tools/stream/world_state.py find WORLD_DIR KEYS.npy
        how many of these keys each file holds, and the time it took
    python tools/stream/world_state.py subset WORLD_DIR TEST_DIR f34,f44,...
        copies of these files (state, sidecar, cities) and a plan of only them: a world to test on
    python tools/stream/world_state.py apply TEST_DIR --nodes D --diff N.osc.gz --today ISO
        one planet day, tier 1, as stream.py apply does it (the touched elements' last versions into a small PBF,
        node locations from D/nodes.idx plus D/overlay.pickle, which takes the diff), but through the world's cells
        (one engine run, every cell of the plan as its cities, each with its time zone) and into the files: every
        tier-1 row of a touched key dropped in every file, the engine's rows added to the file whose rect holds them
    python tools/stream/world_state.py check TEST_DIR --dump Y.bin
        the files at their clock against a whole count's dump of the same instant (europe-west's day dumps), on the
        elements the dump has inside the files' rects plus those the files have that the seed's dump had
"""
import argparse
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REC = np.dtype([("key", "<i8"), ("lat", "<i4"), ("lon", "<i4"), ("quest", "<u2"), ("flags", "u1"), ("kind", "u1"), ("due", "<i4")])
ORDER = ["key", "quest", "kind"]


def is_sorted(r: np.ndarray) -> bool:
    """sorted by (key, quest, kind): key never falls, and within a key the (quest, kind) pair never falls"""
    k = r["key"]
    dk = np.diff(k)
    if (dk < 0).any():
        return False
    same = dk == 0
    qk = r["quest"].astype(np.int32) * 256 + r["kind"]
    return not (same & (np.diff(qk) < 0)).any()


def sort_file(p: Path) -> dict:
    t = time.time()
    r = np.fromfile(p, REC)
    if len(r) and not is_sorted(r):
        r = np.sort(r, order=ORDER)
        tmp = p.with_suffix(".bin.sorting")
        r.tofile(tmp)
        os.replace(tmp, p)
        state = "sorted"
    else:
        state = "already sorted"
    k = r["key"]
    keys = np.unique(k)  # k is sorted: unique is a linear pass
    np.save(p.with_name("state-keys.npy"), keys)
    return {"id": p.parent.name, "rows": int(len(r)), "keys": int(len(keys)),
            "minKey": int(k[0]) if len(k) else None, "maxKey": int(k[-1]) if len(k) else None,
            "state": state, "seconds": round(time.time() - t, 1)}


def files_of(w: Path) -> list[dict]:
    return json.loads((w / "plan.json").read_text(encoding="utf-8"))["files"]


def sort_all(w: Path, workers: int):
    t = time.time()
    plan = {f["id"]: f for f in files_of(w)}
    paths = [w / "files" / i / "state.bin" for i in plan]
    missing = [p for p in paths if not p.exists()]
    if missing:
        sys.exit(f"{len(missing)} files have no state.bin, e.g. {missing[0]}")
    out = []
    with ProcessPoolExecutor(workers) as ex:
        for n, m in enumerate(ex.map(sort_file, paths), 1):
            out.append(m)
            print(f"[{time.time() - t:6.0f} s] {n}/{len(paths)} {m['id']}: {m['rows']:,} rows, {m['keys']:,} keys, "
                  f"{m['state']} in {m['seconds']} s", flush=True)
    allk = np.concatenate([np.load(w / "files" / m["id"] / "state-keys.npy") for m in out])
    allk.sort()
    shared = np.unique(allk[1:][allk[1:] == allk[:-1]])
    np.save(w / "world-state-shared.npy", shared)
    manifest = {"record": "key i64, lat i32, lon i32, quest u16, flags u8, kind u8, due i32",
                "sortedBy": ORDER, "rows": sum(m["rows"] for m in out), "keys": int(len(allk)),
                "sharedKeys": int(len(shared)),
                "files": [{**m, "rect": plan[m["id"]]["rect"]} for m in out]}
    for m in manifest["files"]:
        m.pop("state"), m.pop("seconds")
    (w / "world-state.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"world state: {manifest['rows']:,} rows, {len(out)} files, {len(shared):,} keys in more than one file; "
          f"{time.time() - t:.0f} s", flush=True)


def find(w: Path, keys_path: Path):
    keys = np.unique(np.load(keys_path))
    t = time.time()
    hits = 0
    for f in json.loads((w / "world-state.json").read_text(encoding="utf-8"))["files"]:
        k = np.load(w / "files" / f["id"] / "state-keys.npy", mmap_mode="r")
        i = np.searchsorted(k, keys)
        hits += int((k[np.minimum(i, len(k) - 1)] == keys).sum()) if len(k) else 0
    print(f"{len(keys):,} keys: {hits:,} found in the files' key lists in {time.time() - t:.1f} s")


def in_keys(row_keys: np.ndarray, keys: np.ndarray) -> np.ndarray:
    """for rows sorted by key, which rows have a key among `keys` (sorted, unique): each key's run of rows marked
    by its two ends, one cumulative sum"""
    lo = np.searchsorted(row_keys, keys, "left")
    hi = np.searchsorted(row_keys, keys, "right")
    hit = hi > lo
    n = len(row_keys) + 1
    mark = np.bincount(lo[hit], minlength=n) - np.bincount(hi[hit], minlength=n)
    return np.cumsum(mark[:-1]) > 0


def route(rows: np.ndarray, files: list[dict]) -> tuple[list[np.ndarray], int]:
    """each row to the first file whose rect ([south, west, north, east]) holds its position; and how many fit none"""
    lat, lon = rows["lat"] / 1e7, rows["lon"] / 1e7
    left = np.ones(len(rows), bool)
    out = []
    for f in files:
        s, w, n, e = f["rect"]
        m = left & (lat >= s) & (lat <= n) & (lon >= w) & (lon <= e)
        out.append(np.nonzero(m)[0])
        left &= ~m
    return out, int(left.sum())


def order_code(r: np.ndarray) -> np.ndarray:
    """(key, quest, kind) as one int64 in the same order (keys stay under 2**39: node ids about 1.4e10, times 4)"""
    return (r["key"] << 24) | (r["quest"].astype(np.int64) << 8) | r["kind"].astype(np.int64)


def merge(kept: np.ndarray, add: np.ndarray) -> np.ndarray:
    """sorted rows plus a few more, sorted: the few inserted where they belong, not the whole table sorted again
    (a 25M-row file: 31 s to sort, about a second to merge)"""
    if not len(add):
        return kept
    if max(int(kept["key"].max(initial=0)), int(add["key"].max())) >= 1 << 39:
        sys.exit("a key past 2**39: order_code would wrap")
    add = add[np.argsort(order_code(add), kind="stable")]
    return np.insert(kept, np.searchsorted(order_code(kept), order_code(add), "right"), add)


def replace_in_file(p: Path, drop: np.ndarray, quest_mask: np.ndarray, add: np.ndarray, dtype=REC,
                    keys_name: str = "state-keys.npy") -> tuple[int, int]:
    """drop the rows of these keys whose quest is in quest_mask, add these rows, keep the file sorted; written only
    when it changes. Returns (rows dropped, rows added). dtype WREC for the world day's files (world.bin)."""
    r = np.fromfile(p, dtype)
    gone = in_keys(r["key"], drop) & quest_mask[r["quest"]]
    if not gone.any() and not len(add):
        return 0, 0
    r = merge(r[~gone], add)
    tmp = p.with_suffix(".bin.writing")
    r.tofile(tmp)
    os.replace(tmp, p)
    k = r["key"]
    np.save(p.with_name(keys_name), k[np.concatenate([[True], k[1:] != k[:-1]])] if len(k) else k)  # sorted: no np.unique sort
    return int(gone.sum()), int(len(add))


def subset(src: Path, dst: Path, ids: list[str], link: bool = False):
    """copies (or, with link, hard links: the files are only ever replaced whole, never written in place, so a link
    keeps the source as it was) of these files and a plan of only them; "all" for every file"""
    import shutil
    plan = json.loads((src / "plan.json").read_text(encoding="utf-8"))
    if ids == ["all"]:
        ids = [f["id"] for f in plan["files"]]
    plan["files"] = [f for f in plan["files"] if f["id"] in ids]
    if len(plan["files"]) != len(ids):
        sys.exit(f"not all of {ids} are in the plan")
    for f in plan["files"]:
        d = dst / "files" / f["id"]
        d.mkdir(parents=True, exist_ok=True)
        for name in ("state.bin", "state.bin.json", "cities.json", "state-keys.npy"):
            if not (d / name).exists():
                (os.link if link else shutil.copyfile)(src / "files" / f["id"] / name, d / name)
    (dst / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    side = json.loads((dst / "files" / ids[0] / "state.bin.json").read_text(encoding="utf-8"))
    meta = {"clock": side["asOf"], "quests": side["quests"], "applied": [], "days": [], "source": str(src)}
    (dst / "world-stream.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"{dst}: {len(ids)} files copied, clock {meta['clock']}")


def world_cities(w: Path) -> Path:
    """every cell of the plan as one engine city (their boundaries are relative to the repo, as the count wrote them)"""
    cities = []
    for f in json.loads((w / "plan.json").read_text(encoding="utf-8"))["files"]:
        cities += json.loads((w / "files" / f["id"] / "cities.json").read_text(encoding="utf-8"))["cities"]
    out = w / "world-cities.json"
    out.write_text(json.dumps({"cities": cities}), encoding="utf-8")
    return out


def tier1_mask(names: list[str]) -> np.ndarray:
    import stream as S
    area = S.area_quests()
    return np.array([n not in area and n != "OsmNoteQuestType" for n in names] + [False] * 8)


def apply(w: Path, nodes_dir: Path, diff: Path, today: str):
    import stream as S
    meta = json.loads((w / "world-stream.json").read_text(encoding="utf-8"))
    if diff.name in meta["applied"]:
        print(f"{diff.name} applied before")
        return
    t0 = time.time()
    last_node, last_way, _, _ = S.read_diff(diff)
    S.log(f"{diff.name}: {len(last_node):,} nodes, {len(last_way):,} ways with a version")
    # a directory: a region's sparse index and overlay (stream.py nodes); a file: the planet's dense store, kept in place
    locs = S.DenseLocations(nodes_dir) if nodes_dir.is_file() else S.Locations(nodes_dir)
    for nid, (_, _, alive, _, loc) in last_node.items():
        locs.overlay[nid] = loc if alive else None
    work = w / "work"
    work.mkdir(exist_ok=True)
    unplaced: list[int] = []
    stats = S.write_small_pbf(work / "touched.osm.pbf", today, last_node, last_way, locs, unplaced)
    S.log(f"small PBF: {dict(stats)}")
    dump = S.engine(work / "touched.osm.pbf", work, today, world_cities(w), "UTC", None, area_pass=False,
                    heap_gb=16, base=S.ROOT)
    names = meta["quests"]
    new = S.read_dump(dump, names)
    if names != meta["quests"]:
        sys.exit("the engine's quests are not the seed's")
    tier1 = tier1_mask(names)
    new = new[tier1[new["quest"]]]
    touched = np.unique(np.concatenate([np.fromiter(last_node, np.int64, len(last_node)) * 4,
                                        np.fromiter(last_way, np.int64, len(last_way)) * 4 + 1]))
    files = json.loads((w / "plan.json").read_text(encoding="utf-8"))["files"]
    parts, unrouted = route(new, files)
    t = time.time()
    dropped = added = 0
    for f, idx in zip(files, parts):
        d, a = replace_in_file(w / "files" / f["id"] / "state.bin", touched, tier1, new[idx])
        dropped, added = dropped + d, added + a
    S.log(f"files: {dropped:,} tier-1 rows of touched elements dropped, {added:,} added; {unrouted:,} new rows in no "
          f"file's rect; {time.time() - t:.0f} s")
    locs.save()
    meta["clock"] = today
    meta["applied"].append(diff.name)
    meta["days"].append({"diff": diff.name, "today": today, "rowsDropped": dropped, "rowsAdded": added,
                         "unrouted": unrouted, "waysNotPlaced": len(unplaced), "seconds": round(time.time() - t0, 1)})
    (w / "world-stream.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    tf = w / "touched.npy"
    np.save(tf, np.union1d(np.load(tf), touched) if tf.exists() else touched)


# --- the world day's files: WREC rows with their places (placesets.py, place_counts.py) -------------------------

WORLD_BIN, WORLD_KEYS, WORLD_META = "world.bin", "world-keys.npy", "world.json"


def renumber(rows: np.ndarray, own: list[str], names: list[str]) -> np.ndarray:
    """rows' quest numbers from a dump's own list (its sidecar) to `names`, extended in place"""
    for q in own:
        if q not in names:
            names.append(q)
    rows["quest"] = np.array([names.index(q) for q in own], np.uint16)[rows["quest"]]
    return rows


def write_rows(p: Path, rows: np.ndarray, keys_name: str = WORLD_KEYS):
    tmp = p.with_suffix(".bin.writing")
    rows.tofile(tmp)
    os.replace(tmp, p)
    k = rows["key"]
    np.save(p.with_name(keys_name), k[np.concatenate([[True], k[1:] != k[:-1]])] if len(k) else k)


def seed_w(w: Path, dump_name: str = "state.bin"):
    """every plan file's count dump (`world_cells.py count --state` with parts: files/<f>/state.bin and its .places)
    as files/<f>/world.bin, WREC rows with world place sets, sorted by (key, quest, kind); WORLD/place-sets.json; and
    WORLD/world.json (clock = the dumps' asOf, the quests, the days applied)"""
    import placesets as P
    t = time.time()
    sets = P.PlaceSets(w / "place-sets.json")
    names: list[str] = []
    clock = None
    total = 0
    for f in files_of(w):
        d = w / "files" / f["id"]
        dump = d / dump_name
        side = json.loads(Path(str(dump) + ".json").read_text(encoding="utf-8"))
        clock = clock or side["asOf"]
        if side["asOf"] != clock:
            sys.exit(f"{dump}: asOf {side['asOf']}, the others {clock}")
        if not Path(str(dump) + ".places").exists():
            sys.exit(f"{dump}: no place sets (count it with an engine that writes <state>.places)")
        rows = renumber(P.ingest(dump, sets), side["quests"], names)
        rows = np.sort(np.unique(rows), order=ORDER)
        write_rows(d / WORLD_BIN, rows)
        total += len(rows)
        print(f"[{time.time() - t:6.0f} s] {f['id']}: {len(rows):,} rows", flush=True)
    sets.save()
    meta = {"clock": clock, "quests": names, "applied": [], "days": [], "record": "placesets.WREC",
            "placeSets": "place-sets.json"}
    (w / WORLD_META).write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"world seed: {total:,} rows, {len(sets.sets):,} place sets, {len(sets.parts):,} places; {time.time() - t:.0f} s")


def world_parts(w: Path) -> Path:
    """every cell's parts file in one directory (hard links), as the engine's --parts reads them by city id"""
    out = w / "work" / "parts"
    out.mkdir(parents=True, exist_ok=True)
    for f in files_of(w):
        for src in (w / "files" / f["id"] / "parts").glob("*.json"):
            if not (out / src.name).exists():
                os.link(src, out / src.name)
    return out


def apply_w(w: Path, nodes_dir: Path, diff: Path, today: str, readonly: bool = False, heap_gb: int = 16):
    """apply (tier 1) on the WREC files: the engine run on the touched elements has every cell as a city and their
    parts, so its rows come with their place sets; the planet store's node file opened read-only with `readonly`"""
    import placesets as P
    import stream as S
    meta = json.loads((w / WORLD_META).read_text(encoding="utf-8"))
    if diff.name in meta["applied"]:
        print(f"{diff.name} applied before")
        return
    t0 = time.time()
    last_node, last_way, _, _ = S.read_diff(diff)
    S.log(f"{diff.name}: {len(last_node):,} nodes, {len(last_way):,} ways with a version")
    locs = S.DenseLocations(nodes_dir, readonly=readonly) if nodes_dir.is_file() else S.Locations(nodes_dir)
    for nid, (_, _, alive, _, loc) in last_node.items():
        locs.overlay[nid] = loc if alive else None
    work = w / "work"
    work.mkdir(exist_ok=True)
    unplaced: list[int] = []
    stats = S.write_small_pbf(work / "touched.osm.pbf", today, last_node, last_way, locs, unplaced)
    S.log(f"small PBF: {dict(stats)}")
    dump = S.engine(work / "touched.osm.pbf", work, today, world_cities(w), "UTC", None, area_pass=False,
                    heap_gb=heap_gb, base=S.ROOT, parts=world_parts(w), parts_cache=P.parts_cache(w))
    sets = P.PlaceSets(w / "place-sets.json")
    names = meta["quests"]
    n0 = len(names)
    side = json.loads(Path(str(dump) + ".json").read_text(encoding="utf-8"))
    new = renumber(P.ingest(dump, sets), side["quests"], names)
    if len(names) != n0:
        sys.exit("the engine's quests are not the seed's")
    new = np.unique(new)
    tier1 = tier1_mask(names)
    new = new[tier1[new["quest"]]]
    touched = np.unique(np.concatenate([np.fromiter(last_node, np.int64, len(last_node)) * 4,
                                        np.fromiter(last_way, np.int64, len(last_way)) * 4 + 1]))
    files = files_of(w)
    parts, unrouted = route(new, files)
    dropped = added = 0
    for f, idx in zip(files, parts):
        d_, a_ = replace_in_file(w / "files" / f["id"] / WORLD_BIN, touched, tier1, new[idx], dtype=P.WREC,
                                 keys_name=WORLD_KEYS)
        dropped, added = dropped + d_, added + a_
    sets.save()
    locs.save()
    S.log(f"files: {dropped:,} tier-1 rows of touched elements dropped, {added:,} added; {unrouted:,} in no file's rect")
    meta["clock"] = today
    meta["applied"].append(diff.name)
    meta["days"].append({"diff": diff.name, "today": today, "rowsDropped": dropped, "rowsAdded": added,
                         "unrouted": unrouted, "waysNotPlaced": len(unplaced), "seconds": round(time.time() - t0, 1)})
    (w / WORLD_META).write_text(json.dumps(meta, indent=1), encoding="utf-8")


def counts_w(w: Path, clock: str | None = None, out: Path | None = None):
    """the counts per place and per cell (`city:<id>`) at the clock (default: the state's), into out (default
    WORLD/counts/): place_counts.write"""
    import place_counts as C
    import placesets as P
    import stream as S
    meta = json.loads((w / WORLD_META).read_text(encoding="utf-8"))
    sets = P.PlaceSets(w / "place-sets.json")
    clock = clock or meta["clock"]
    names = meta["quests"]
    t = time.time()
    paths = [w / "files" / f["id"] / WORLD_BIN for f in files_of(w)]
    rows = sum(p.stat().st_size for p in paths) // P.WREC.itemsize
    codes, sums = C.count_files(paths, P.WREC, S.minute(clock), sets.sets, len(names))
    C.write(out or w / "counts", codes, sums, len(names), clock, names, sets.parts)
    secs = time.time() - t
    print(f"counts at {clock}: {rows:,} rows, {len(codes):,} (place, quest) pairs; {secs:.1f} s "
          f"({secs / max(rows, 1) * 1e6:.2f} s per million rows)")


def check(w: Path, dump: Path) -> int:
    """tier 1 against a whole count of the same instant, every field (the note bit aside), as stream.rows_check
    compares a region's state, on the dump's elements inside the files' rects and the files' elements
    the seed's dump had. Returns the number of differences."""
    import stream as S
    meta = json.loads((w / "world-stream.json").read_text(encoding="utf-8"))
    names = meta["quests"]
    ref = S.read_dump(dump, names)
    side = json.loads(Path(str(dump) + ".json").read_text(encoding="utf-8"))
    if side["asOf"] != meta["clock"]:
        sys.exit(f"the dump is at {side['asOf']}, the files at {meta['clock']}")
    at = S.minute(meta["clock"])
    tier1 = tier1_mask(names)
    ref = ref[tier1[ref["quest"]]]
    files = json.loads((w / "plan.json").read_text(encoding="utf-8"))["files"]
    parts, _ = route(ref, files)
    ref = ref[np.concatenate(parts)]
    near = [f for f, i in zip(files, parts) if len(i)]  # only the files the count reaches: the world's would not fit
    st = np.concatenate([np.fromfile(w / "files" / f["id"] / "state.bin", REC) for f in near])
    st = st[tier1[st["quest"]]]
    seed_keys = np.load(w / "seed-keys.npy") if (w / "seed-keys.npy").exists() else np.zeros(0, np.int64)
    universe = np.union1d(np.unique(ref["key"]), seed_keys)
    st = st[np.isin(st["key"], universe)]

    def norm(r):
        """every row as the count writes it at the clock: a waiting row whose date has come (in its setting: the
        default, 0.5 or 2) becomes that setting's open-and-aged bits on the element's match, as stream.rows_check
        does; then matches as (key, quest, flags without the note bit, position) and the rows still waiting as
        (key, quest, setting, due, position)"""
        code = r["key"] * 1024 + r["quest"].astype(np.int64)
        setting = np.where(r["flags"] & 63 == 0, S.M_NOW, r["flags"] & 63)
        m, dmask = r["kind"] == S.MATCH, r["kind"] == S.DUE
        flags = {}
        for c, f, la, lo in zip(code[m].tolist(), (r["flags"][m] & 63).tolist(), r["lat"][m].tolist(), r["lon"][m].tolist()):
            flags[c] = [f, la, lo]
        came = dmask & (r["due"] <= at)
        for c, s, la, lo in zip(code[came].tolist(), setting[came].tolist(), r["lat"][came].tolist(), r["lon"][came].tolist()):
            e = flags.setdefault(c, [0, la, lo])
            e[0] |= s | {S.M_NOW: 2, 4: 8, 16: 32}[s]
        matches = {(c, f, la, lo) for c, (f, la, lo) in flags.items()}
        wt = dmask & ~came
        waiting = set(zip(code[wt].tolist(), setting[wt].tolist(), r["due"][wt].tolist(), r["lat"][wt].tolist(),
                          r["lon"][wt].tolist()))
        return matches, waiting

    sm, sw = norm(st)
    rm, rw = norm(ref)
    touched = np.load(w / "touched.npy") if (w / "touched.npy").exists() else np.zeros(0, np.int64)
    tset = set(touched.tolist())
    name = lambda c: ("n", "w", "r")[(c >> 10) & 3] + str(c >> 12) + " " + names[c & 1023]  # noqa: E731
    kinds = lambda xs: dict(Counter(("n", "w", "r")[(x[0] >> 10) & 3] + (" touched" if (x[0] >> 10) in tset else " untouched") for x in xs))  # noqa: E731
    print(f"world files at {meta['clock']} against {dump}: {len(universe):,} elements compared")
    total = 0
    for label, a_, b_ in (("matches", sm, rm), ("waiting", sw, rw)):
        xa, xb = a_ - b_, b_ - a_
        # the same row at another position: a way whose nodes moved while it kept its version (tier 1 does not see
        # it; tier 2's recount does), or a relation (tier 1 does not recount relations)
        moved = {x[:-2] for x in xa} & {x[:-2] for x in xb}
        ra = [x for x in xa if x[:-2] not in moved]
        rb = [x for x in xb if x[:-2] not in moved]
        total += len(xa) + len(xb)
        print(f"tier 1 {label}: files {len(a_):,}, count {len(b_):,}; equal but for the position {len(moved):,} "
              f"{kinds(list(moved))}; only in the files {len(ra):,} {kinds(ra)}; only in the count {len(rb):,} {kinds(rb)}")
        if ra or rb:
            print(f"  e.g. files {[(name(x[0]),) + x[1:] for x in sorted(ra)[:3]]} / count {[(name(x[0]),) + x[1:] for x in sorted(rb)[:3]]}")
    return total


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sort")
    s.add_argument("world", type=Path)
    s.add_argument("--workers", type=int, default=4)
    f = sub.add_parser("find")
    f.add_argument("world", type=Path)
    f.add_argument("keys", type=Path)
    b = sub.add_parser("subset")
    b.add_argument("world", type=Path)
    b.add_argument("test", type=Path)
    b.add_argument("ids")
    b.add_argument("--link", action="store_true")
    p = sub.add_parser("apply")
    p.add_argument("world", type=Path)
    p.add_argument("--nodes", type=Path, required=True)
    p.add_argument("--diff", type=Path, required=True)
    p.add_argument("--today", required=True)
    p.add_argument("--places", action="store_true", help="the WREC files (world.bin) and their place sets")
    p.add_argument("--readonly-nodes", action="store_true", help="never write the node file (the planet store's)")
    sd = sub.add_parser("seed")
    sd.add_argument("world", type=Path)
    sd.add_argument("--dump", default="state.bin", help="each file's dump name under files/<f>/")
    ct = sub.add_parser("counts")
    ct.add_argument("world", type=Path)
    ct.add_argument("--clock", help="ISO instant; default the state's")
    ct.add_argument("--out", type=Path)
    c = sub.add_parser("check")
    c.add_argument("world", type=Path)
    c.add_argument("--dump", type=Path, required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if a.cmd == "sort":
        sort_all(a.world, a.workers)
    elif a.cmd == "find":
        find(a.world, a.keys)
    elif a.cmd == "subset":
        subset(a.world, a.test, a.ids.split(","), a.link)
    elif a.cmd == "apply":
        if a.places:
            apply_w(a.world, a.nodes, a.diff, a.today, a.readonly_nodes)
        else:
            apply(a.world, a.nodes, a.diff, a.today)
    elif a.cmd == "seed":
        seed_w(a.world, a.dump)
    elif a.cmd == "counts":
        counts_w(a.world, a.clock, a.out)
    else:
        sys.exit(1 if check(a.world, a.dump) else 0)


if __name__ == "__main__":
    main()
