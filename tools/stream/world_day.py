"""One world day: the world state (WREC rows with places, world_state.py) moved from D-1 to D by a day's diff, every
quest (DESIGN.md, "Release 1: the world day"). The order is the store's:

  prepare(W, store, diff, D)   the diff read once; the old geometry of the changed ways looked up in generation D-1
                               (`tilestore ways`), which the store's next `update --prune-pairs` takes away; the node
                               places at D-1 and D; the state's rows of every changed key
  -- the store's update to D (planet_store_day.py's `update`, or `update_store` here in a rehearsal) --
  finish(day)                  the member ways of the changed relations at D; the cover (world_tier2) and its
                               rectangles; tier 1 (the touched elements through the engine with the cells and their
                               parts); tier 2 (the rectangles read from generations D-1 and D, the engine on each at its
                               own clock, only the recount's own changes applied: the delta form, here on WREC rows so
                               the place sets move with the records); notes (hidden flags at D, the note quests by the
                               engine); the counts per place at D; world.json's clock moves to D

`run` does all three for a rehearsal. The node places: a region's sparse index (stream.py nodes; its overlay moves with
each day) or the planet's dense node file, read only (the store's own `loc advance` moves it, after finish).
`check(W, oracle, work)` holds the state and its counts against a whole count of the same plan at D.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import notes_day as N  # noqa: E402
import place_counts as C  # noqa: E402
import placesets as P  # noqa: E402
import stream as S  # noqa: E402
import world_state as WS  # noqa: E402
import world_tier2 as T2  # noqa: E402

EXE = ROOT / "tilestore" / "target" / "release" / "tilestore.exe"
RING_M = 300.0
NOTE_QUEST = "OsmNoteQuestType"


def _log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def quiet(ahead_minutes: int = 0):
    """no engine starts in (or runs into) the daily update's window: world_cells.quiet"""
    sys.path.insert(0, str(ROOT / "tools"))
    import world_cells
    world_cells.quiet(ahead_minutes)


def files_of(w: Path) -> list[dict]:
    return json.loads((w / "plan.json").read_text(encoding="utf-8"))["files"]


def gens(store: Path) -> list[dict]:
    return json.loads((store / "store.json").read_text())["generations"]


def tilestore(*args, log=_log):
    t = time.time()
    r = subprocess.run([str(EXE), *map(str, args)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"tilestore {args[0]} failed ({r.returncode}): {r.stderr[-2000:]}")
    log(f"tilestore {args[0]}: {time.time() - t:.1f} s")
    return r


def way_lookup(store: Path, ids: np.ndarray, out: Path, rels: np.ndarray | None = None, gen: int | None = None,
               log=_log) -> dict[int, list[int]]:
    """ways' refs in a generation (`tilestore ways`): id -> refs, for those found"""
    out.mkdir(parents=True, exist_ok=True)
    if not len(ids):
        return {}
    np.save(out / "ids-in.npy", np.asarray(ids, np.int64))
    args = ["ways", "--store", store, "--ids", out / "ids-in.npy", "--out", out]
    if rels is not None and len(rels):
        np.save(out / "rels-in.npy", np.asarray(rels, np.int64))
        args += ["--rels", out / "rels-in.npy"]
    if gen is not None:
        args += ["--gen", gen]
    tilestore(*args, log=log)
    wid, how, offs, refs = (np.load(out / f"{n}.npy") for n in ("ids", "how", "offs", "refs"))
    return {int(w): refs[offs[i]:offs[i + 1]].tolist() for i, w in enumerate(wid.tolist()) if how[i]}


def rows_of_keys(w: Path, keys: np.ndarray) -> np.ndarray:
    """every state row (key, lat, lon) of these keys, from each file's world-keys.npy and world.bin"""
    keys = np.unique(np.asarray(keys, np.int64))
    out = []
    for f in files_of(w):
        d = w / "files" / f["id"]
        fk = np.load(d / WS.WORLD_KEYS)
        if not len(fk):
            continue
        i = np.minimum(np.searchsorted(fk, keys), len(fk) - 1)
        hit = keys[fk[i] == keys]
        if not len(hit):
            continue
        r = np.fromfile(d / WS.WORLD_BIN, P.WREC)
        sel = r[WS.in_keys(r["key"], hit)]
        o = np.zeros(len(sel), T2.ROWPOS)
        for n in T2.ROWPOS.names:
            o[n] = sel[n]
        out.append(o)
    return np.concatenate(out) if out else np.zeros(0, T2.ROWPOS)


@dataclass
class Day:
    w: Path
    store: Path
    diff: Path
    today: str
    prev: str
    work: Path
    nodes: Path
    last_node: dict
    last_way: dict
    last_rel: dict
    old_refs: dict
    old_places: object
    new_places: object
    old_rows: np.ndarray
    gen_before: int
    heap_gb: int = 8
    engine: Path | None = None
    log: object = _log
    T: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)


def prepare(w: Path, store: Path, diff: Path, today: str, nodes: Path, work: Path, heap_gb: int = 8,
            engine: Path | None = None, log=_log, keep=None) -> Day:
    """everything that needs the world at D-1: run it before the store's update. `keep(last_node, last_way,
    last_rel, old_places, new_places, old_refs)` narrows the diff (a rehearsal on a clip: `clip_keep`)"""
    meta = json.loads((w / WS.WORLD_META).read_text(encoding="utf-8"))
    if diff.name in meta["applied"]:
        raise SystemExit(f"{diff.name} applied before")
    work.mkdir(parents=True, exist_ok=True)
    T = {}
    t = time.time()
    last_node, last_way, last_rel, _ = S.read_diff(diff)
    T["read diff"] = time.time() - t
    log(f"{diff.name}: {len(last_node):,} nodes, {len(last_way):,} ways, {len(last_rel):,} relations; {T['read diff']:.0f} s")
    t = time.time()
    g0 = gens(store)[-1]["gen"]
    old_refs = way_lookup(store, np.fromiter(last_way, np.int64, len(last_way)), work / "ways-old",
                          rels=np.fromiter(last_rel, np.int64, len(last_rel)), log=log)
    T["old ways"] = time.time() - t
    t = time.time()
    overlay = {n: (v[4] if v[2] else None) for n, v in last_node.items()}
    if nodes.is_file():  # the planet's dense node file, read only
        old_places, new_places = T2.NodeFile(nodes), T2.NodeFile(nodes, overlay=overlay)
    else:  # a region's sparse index, at D-1 until this day saves its overlay
        old_places, new_places = T2.SparsePlaces(nodes), T2.SparsePlaces(nodes, extra=overlay)
    if keep is not None:  # a rehearsal on a clip: only what the clip's extract would hold of the planet's diff
        n0, w0, r0 = len(last_node), len(last_way), len(last_rel)
        last_node, last_way, last_rel = keep(last_node, last_way, last_rel, old_places, new_places, old_refs)
        overlay = {n: (v[4] if v[2] else None) for n, v in last_node.items()}
        if nodes.is_file():
            new_places = T2.NodeFile(nodes, overlay=overlay)
        else:
            new_places = T2.SparsePlaces(nodes, extra=overlay)
        log(f"kept for the clip: {len(last_node):,} of {n0:,} nodes, {len(last_way):,} of {w0:,} ways, "
            f"{len(last_rel):,} of {r0:,} relations")
    keys = T2.changed_keys(last_node, last_way, last_rel)
    rows = rows_of_keys(w, keys)
    T["places and old rows"] = time.time() - t
    log(f"old ways: {len(old_refs):,} of {len(last_way):,} found at generation {g0}; old rows {len(rows):,} of "
        f"{len(keys):,} changed keys")
    return Day(w, store, diff, today, meta["clock"], work, nodes, last_node, last_way, last_rel, old_refs, old_places,
               new_places, rows, g0, heap_gb, engine, log, T, {"changedKeys": int(len(keys)), "oldRows": int(len(rows))})


def clip_keep(polygon: Path):
    """the part of a planet diff a clip's extract (osmium, complete ways) would hold: nodes inside the polygon at D-1
    or D; ways with a node inside at D, or that the clip store held at D-1, and all their nodes; relations with a kept
    member or held before (approximated by a kept member: the store's relation lookup is not asked)"""
    import shapely
    from shapely.geometry import shape
    gj = json.loads(Path(polygon).read_text(encoding="utf-8"))
    geom = (shapely.union_all([shape(f["geometry"]) for f in gj["features"]]) if "features" in gj
            else shape(gj.get("geometry", gj)))
    shapely.prepare(geom)

    def inside(p):
        ok = np.isfinite(p).all(axis=1)
        out = np.zeros(len(p), bool)
        if ok.any():
            out[ok] = shapely.contains_xy(geom, p[ok, 1], p[ok, 0])
        return out

    def keep(last_node, last_way, last_rel, old_places, new_places, old_refs):
        nid = np.fromiter(last_node, np.int64, len(last_node))
        kn = set(nid[inside(new_places.places(nid)) | inside(old_places.places(nid))].tolist())
        # every way's refs at once: one place lookup and one polygon test, reduced per way
        wids = list(last_way)
        lens = np.array([len(last_way[w_][4] or []) for w_ in wids], np.int64)
        allrefs = np.fromiter((r for w_ in wids for r in (last_way[w_][4] or [])), np.int64, int(lens.sum()))
        hit = inside(new_places.places(allrefs)) if len(allrefs) else np.zeros(0, bool)
        starts = np.concatenate([[0], np.cumsum(lens)[:-1]]) if len(lens) else np.zeros(0, np.int64)
        any_in = np.zeros(len(wids), bool)
        nz = lens > 0
        if nz.any():
            any_in[nz] = np.maximum.reduceat(hit, starts[nz])
        kw = set()
        for k, wid in enumerate(wids):
            if any_in[k] or wid in old_refs:
                kw.add(wid)
                kn.update(r for r in (last_way[wid][4] or []) if r in last_node)
        kr = {rid for rid, (_, _, ms) in last_rel.items()
              if any((t == "n" and r in kn) or (t == "w" and (r in kw or r in old_refs)) for t, r in ms)}
        return ({n: last_node[n] for n in kn}, {w_: last_way[w_] for w_ in kw}, {r: last_rel[r] for r in kr})

    return keep


def update_store(day: Day, before_clip: Path | None = None, polygon: Path | None = None, before_loc: Path | None = None):
    """the store's own update to D (a rehearsal's; on the planet planet_store_day.py does it)"""
    t = time.time()
    args = ["update", "--store", day.store, "--diff", day.diff, "--day", day.today[:10], "--prune-pairs"]
    args += ["--before", before_clip] if before_clip else ["--before-loc", before_loc]
    args += ["--polygon", polygon] if polygon else ["--world"]
    tilestore(*args, log=day.log)
    day.T["store update"] = time.time() - t


# --- the engine and the rows ----------------------------------------------------------------------------------

def rect_to_cell(rows: np.ndarray, sets: P.PlaceSets) -> np.ndarray:
    """a rectangle city's pseudo part `city:<cell>-<k>` (the engine adds each city holding a record) as its cell's
    `city:<cell>`, so a cell's totals keep coming from one part"""
    import re
    u = np.unique(rows["place"])
    m = {}
    for s_ in u.tolist():
        ids = sets.ids_of(s_)
        new = [re.sub(r"^(city:.+)-\d+$", r"\1", i) for i in ids]
        m[s_] = s_ if new == ids else sets.intern(new)
    if any(k != v for k, v in m.items()):
        lut_k = np.array(list(m), np.uint32)
        lut_v = np.array([m[k] for k in m.keys()], np.uint32)
        rows["place"] = lut_v[np.searchsorted(lut_k, rows["place"])]
    return rows


def engine_rows(day: Day, pbf: Path, out: Path, clock: str, cities: Path, parts: Path, area_pass: bool,
                sets: P.PlaceSets, names: list[str], extra_opts: str = "", rects: bool = False) -> np.ndarray:
    quiet(20)
    eng = day.engine
    saved = S.ENGINE
    if eng:
        S.ENGINE = eng
    try:
        dump = S.engine(pbf, out, clock, cities, "UTC", None, area_pass=area_pass, heap_gb=day.heap_gb, base=ROOT,
                        extra_opts=extra_opts, parts=parts)
    finally:
        S.ENGINE = saved
    side = json.loads(Path(str(dump) + ".json").read_text(encoding="utf-8"))
    n0 = len(names)
    rows = WS.renumber(P.ingest(dump, sets), side["quests"], names)
    if len(names) != n0:
        raise SystemExit("the engine's quests are not the seed's")
    if rects:
        rows = rect_to_cell(rows, sets)
    rows = np.unique(rows)
    notes_q = [i for i, n in enumerate(names) if n == NOTE_QUEST]
    return rows[~np.isin(rows["quest"], notes_q)] if notes_q else rows


def codes_of(r: np.ndarray) -> np.ndarray:
    return r["key"] * 1024 + r["quest"].astype(np.int64)


def groups(a: np.ndarray) -> dict[int, tuple]:
    g = defaultdict(list)
    for c, b in zip(codes_of(a).tolist(), (a[i].tobytes() for i in range(len(a)))):
        g[c].append(b)
    return {c: tuple(sorted(v)) for c, v in g.items()}


def delta_w(w: Path, old: np.ndarray, new: np.ndarray, files: list[dict], added: dict[str, set]) -> dict:
    """tier2.delta on the world's WREC files: per (element, quest), the recount's change from D-1 to D applied; a group
    the recount changed but the state lacks is kept out (a recount-vs-whole disagreement), as tier2.delta does"""
    go, gn = groups(old), groups(new)
    cand = np.array([c for c in go.keys() | gn.keys() if go.get(c) != gn.get(c)], np.int64)
    held: set[int] = set()
    if len(cand):
        for f in files:
            fc = codes_of(np.fromfile(w / "files" / f["id"] / WS.WORLD_BIN, P.WREC))
            held |= set(fc[np.isin(fc, cand)].tolist())
    st = Counter()
    put, gone = set(), set()
    for c in cand.tolist():
        o, n = go.get(c), gn.get(c)
        if o is None:
            put.add(c); st["added"] += 1
            if c in held:
                st["added, the state had it"] += 1
        elif n is None:
            gone.add(c); st["removed"] += 1
            if c not in held:
                st["removed, the state lacked it"] += 1
        elif c in held:
            put.add(c); st["changed"] += 1
        else:
            st["changed, the state lacked it (kept out)"] += 1
    if not put and not gone:
        return dict(st)
    put_a = np.fromiter(put, np.int64, len(put))
    both = np.fromiter(put | gone, np.int64, len(put | gone))
    add = new[np.isin(codes_of(new), put_a)]
    parts, unrouted = WS.route(add, files)
    st["rows added"], st["unrouted"] = len(add), unrouted
    for f, idx in zip(files, parts):
        p = w / "files" / f["id"] / WS.WORLD_BIN
        r = np.fromfile(p, P.WREC)
        drop = np.isin(codes_of(r), both)
        if not drop.any() and not len(idx):
            continue
        st["rows dropped"] += int(drop.sum())
        r = WS.merge(r[~drop], add[idx])
        WS.write_rows(p, r)
        added[f["id"]] |= set(codes_of(add[idx]).tolist())
    return dict(st)


def world_notes(w: Path) -> Path:
    """every file's notes clip as one (notes in several files' boxes once), for the hidden flags and the note quests"""
    out = w / "notes-all.jsonl"
    if out.exists():
        return out
    header, seen, lines = None, set(), []
    for f in files_of(w):
        with open(w / "files" / f["id"] / "notes.jsonl", encoding="utf-8") as fh:
            h = fh.readline()
            header = header or h
            for line in fh:
                if line.strip():
                    nid = json.loads(line)["id"]
                    if nid not in seen:
                        seen.add(nid)
                        lines.append(line if line.endswith("\n") else line + "\n")
    hd = json.loads(header)
    hd.update({"notes": len(lines), "bbox": None, "poly": "the union of the plan files' clips"})
    tmp = out.with_suffix(".writing")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(hd) + "\n")
        fh.writelines(lines)
    os.replace(tmp, out)
    return out


def counts_at(w: Path, clock: str, sets: P.PlaceSets, names: list[str], work: Path, engine: Path | None = None,
              heap_gb: int = 8) -> Path:
    """the counts per place and per cell at the clock (W/counts/<day>/): the state's rows through place_counts, the
    note quests counted by the engine over the notes alone (notes_day.note_quests) added per place and per cell"""
    # one engine run per plan file, its cells and its parts (all of a world's parts in one run do not fit: Europe
    # alone has 502,597 part entries); each note is in one cell, so the files' counts add up
    nq = {"cities": {}, "parts": Counter()}
    for f in files_of(w):
        d = w / "files" / f["id"]
        quiet(5)
        r = N.note_quests(d / "cities.json", d / "notes.jsonl", clock, work / f["id"], parts=d / "parts", engine=engine,
                          heap_gb=heap_gb)
        nq["cities"].update(r["cities"])
        nq["parts"].update(r["parts"])
    if NOTE_QUEST not in names:
        names.append(NOTE_QUEST)
    qi = names.index(NOTE_QUEST)
    vec = lambda n: np.array([n] + [0] * (len(C.MEASURES) - 1), np.int64)  # noqa: E731
    extra = [(sets.part(f"city:{cid}"), qi, vec(v["quests"])) for cid, v in nq["cities"].items() if v["quests"]]
    extra += [(sets.part(pid), qi, vec(n)) for pid, n in nq["parts"].items() if n]
    sets.save()
    paths = [w / "files" / f["id"] / WS.WORLD_BIN for f in files_of(w)]
    codes_c, sums = C.count_files(paths, P.WREC, S.minute(clock), sets.sets, len(names), extra=extra)
    cdir = w / "counts" / clock[:10]
    C.write(cdir, codes_c, sums, len(names), clock, names, sets.parts)
    return cdir


def finish(day: Day) -> dict:
    """everything after the store holds D (both generations readable: run before `compact`)"""
    w, log, T = day.w, day.log, day.T
    meta = json.loads((w / WS.WORLD_META).read_text(encoding="utf-8"))
    names = meta["quests"]
    files = files_of(w)
    plan_path = w / "plan.json"
    sets = P.PlaceSets(w / "place-sets.json")
    g1 = gens(day.store)[-1]["gen"]
    assert g1 != day.gen_before, "the store has not moved to D: update it between prepare and finish"
    # the changed relations' member ways at D (the cover takes the ones the area quests read)
    t = time.time()
    members = np.unique(np.array([ref for _, (_, _, ms) in day.last_rel.items() for typ, ref in ms if typ == "w"], np.int64))
    new_members = way_lookup(day.store, members, day.work / "ways-new",
                             rels=np.fromiter(day.last_rel, np.int64, len(day.last_rel)), log=log)
    T["member ways"] = time.time() - t

    def old_refs(wid):
        return day.old_refs.get(wid)

    def member_refs(wid):
        v = day.last_way.get(wid)
        if v is not None:
            return v[4] if v[2] else None
        return new_members.get(wid)

    # the cover and its rectangles (the old rows are the state's before tier 1 replaced any)
    t = time.time()
    codes, cstats, secs = T2.cover(day.last_node, day.last_way, day.last_rel, day.old_places, day.new_places,
                                   day.old_rows, old_refs=old_refs, member_refs=member_refs, log=log)
    T["cover"] = time.time() - t
    t2w = day.work / "t2"
    t2w.mkdir(parents=True, exist_ok=True)
    np.save(t2w / "codes.npy", codes)
    TT = {}
    rinfo = T2.after_cover(codes, plan_path, w, t2w, ROOT, w / "places.json", TT, log=log)
    T["rectangles"] = TT.get("rectangles", 0)
    T["engine files"] = TT.get("engine files", 0)
    added: dict[str, set] = defaultdict(set)

    # tier 1: the touched elements' last versions through the engine, every cell a city with its parts
    t = time.time()
    locs = S.DenseLocations(day.nodes, readonly=True) if day.nodes.is_file() else S.Locations(day.nodes)
    for nid, (_, _, alive, _, loc) in day.last_node.items():
        locs.overlay[nid] = loc if alive else None
    unplaced: list[int] = []
    t1w = day.work / "t1"
    t1w.mkdir(parents=True, exist_ok=True)
    pst = S.write_small_pbf(t1w / "touched.osm.pbf", day.today, day.last_node, day.last_way, locs, unplaced)
    # one engine run per plan file over the same small PBF (its cells and parts; elements outside them are skipped)
    new1 = np.concatenate([engine_rows(day, t1w / "touched.osm.pbf", t1w / f["id"], day.today,
                                       w / "files" / f["id"] / "cities.json", w / "files" / f["id"] / "parts", False,
                                       sets, names) for f in files]) if files else np.zeros(0, P.WREC)
    new1 = np.unique(new1)
    tier1 = WS.tier1_mask(names)
    new1 = new1[tier1[new1["quest"]]]
    touched = np.unique(np.concatenate([np.fromiter(day.last_node, np.int64, len(day.last_node)) * 4,
                                        np.fromiter(day.last_way, np.int64, len(day.last_way)) * 4 + 1]))
    parts, unrouted1 = WS.route(new1, files)
    d1 = a1 = 0
    for f, idx in zip(files, parts):
        d_, a_ = WS.replace_in_file(w / "files" / f["id"] / WS.WORLD_BIN, touched, tier1, new1[idx], dtype=P.WREC,
                                    keys_name=WS.WORLD_KEYS)
        d1, a1 = d1 + d_, a1 + a_
        if len(idx):
            added[f["id"]] |= set(codes_of(new1[idx]).tolist())
    T["tier 1"] = time.time() - t
    log(f"tier 1: {d1:,} rows of touched elements dropped, {a1:,} added; {unrouted1:,} in no file; {dict(pst)}")

    # tier 2: the rectangles on D-1 at D-1's clock and on D at D's, the delta into the files
    t = time.time()
    cities, rparts = t2w / "cities.json", t2w / "parts"
    opts = f"-Dopenquests.areaPaddingM={RING_M:.0f}"
    t2s = {}
    if rinfo["rectangles"]:
        tilestore("read", "--store", day.store, "--gen", day.gen_before, "--cities", cities, "--base", ROOT, "--ring",
                  f"{RING_M:.0f}", "--out", t2w / "old.osm.pbf", "--stamp", day.prev, log=log)
        tilestore("read", "--store", day.store, "--gen", g1, "--cities", cities, "--base", ROOT, "--ring", f"{RING_M:.0f}",
                  "--out", t2w / "new.osm.pbf", "--stamp", day.today, log=log)
        T["tier 2 reads"] = time.time() - t
        t = time.time()
        old = engine_rows(day, t2w / "old.osm.pbf", t2w / "old", day.prev, cities, rparts, True, sets, names, opts, rects=True)
        new = engine_rows(day, t2w / "new.osm.pbf", t2w / "new", day.today, cities, rparts, True, sets, names, opts, rects=True)
        T["tier 2 engine"] = time.time() - t
        t = time.time()
        t2s = delta_w(w, old, new, files, added)
        T["tier 2 delta"] = time.time() - t
        log(f"tier 2: {rinfo['rectangles']:,} rectangles, {rinfo['rectKm2']:,} km2; recount rows {len(old):,} at D-1, "
            f"{len(new):,} at D; {t2s}")
    sets.save()

    # notes at D: hidden flags (only rows at notes that opened or closed, and the day's new rows), note quests
    t = time.time()
    clip = world_notes(w)
    cd = N.load_clip(clip)
    nst = Counter()
    for f in files:
        p = w / "files" / f["id"] / WS.WORLD_BIN
        r = np.fromfile(p, P.WREC)
        fresh = np.isin(codes_of(r), np.fromiter(added[f["id"]], np.int64, len(added[f["id"]]))) if added[f["id"]] else None
        before = r["flags"].copy()
        s = N.hidden_step(r, cd, day.today, prev_clock=day.prev, fresh=fresh)
        nst["flagsChanged"] += s["flagsChanged"]
        nst["rowsTouched"] += s["rowsTouched"]
        if (r["flags"] != before).any():
            WS.write_rows(p, r)
    T["notes"] = time.time() - t
    t = time.time()
    counts_at(w, day.today, sets, names, day.work / "notes", day.engine, day.heap_gb)
    T["counts and note quests"] = time.time() - t

    locs.save()  # a region's overlay moves to D (the planet's node file is read only: the store moves it)
    meta["clock"] = day.today
    meta["quests"] = names
    meta["applied"].append(day.diff.name)
    rec = {"diff": day.diff.name, "today": day.today, **day.stats, "tier1": {"dropped": d1, "added": a1, "unrouted": unrouted1,
           "waysNotPlaced": len(unplaced)}, "cover": {k: int(v) for k, v in cstats.items()},
           "rectangles": {k: rinfo[k] for k in ("markedCells", "rectangles", "rectKm2", "rectKm2Quantiles")},
           "tier2": t2s, "notes": dict(nst), "seconds": {k: round(v, 1) for k, v in T.items()}}
    meta["days"].append(rec)
    (w / WS.WORLD_META).write_text(json.dumps(meta, indent=1), encoding="utf-8")
    (day.work / "day.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    # what the check splits differences by: every key a day touched, every rectangle
    tf = w / "touched.npy"
    keys = T2.changed_keys(day.last_node, day.last_way, day.last_rel)
    np.save(tf, np.union1d(np.load(tf), keys) if tf.exists() else keys)
    rf = w / "rects.npy"
    rn = np.load(t2w / "rects.npy") if (t2w / "rects.npy").exists() else np.zeros((0, 5))
    np.save(rf, np.concatenate([np.load(rf), rn]) if rf.exists() else rn)
    log(f"day {day.today[:10]} done: {json.dumps(rec['seconds'])}")
    return rec


def run(w: Path, store: Path, diff: Path, today: str, nodes: Path, work: Path, before_clip: Path | None = None,
        polygon: Path | None = None, before_loc: Path | None = None, heap_gb: int = 8, engine: Path | None = None,
        log=_log, compact: bool = True, keep=None) -> dict:
    day = prepare(w, store, diff, today, nodes, work, heap_gb, engine, log, keep=keep)
    update_store(day, before_clip, polygon, before_loc)
    rec = finish(day)
    if compact:
        tilestore("compact", "--store", store, "--min-dead", "0.25", log=log)
    return rec


# --- the check against a whole count ---------------------------------------------------------------------------

def check(w: Path, oracle: Path, work: Path, log=_log) -> dict:
    """the state at its clock against the oracle's whole count of the same plan at the same instant (its files'
    state.bin and .places, and their snapshots): every row, records and place sets, split by cause; and every
    count per place and per cell, open and agedOnly, note quests included"""
    t = time.time()
    meta = json.loads((w / WS.WORLD_META).read_text(encoding="utf-8"))
    names = meta["quests"]
    sets = P.PlaceSets(w / "place-sets.json")
    osets = P.PlaceSets(work / "oracle-sets.json")
    files = files_of(w)
    state = np.concatenate([np.fromfile(w / "files" / f["id"] / WS.WORLD_BIN, P.WREC) for f in files])
    orows = []
    clock = None
    for f in files:
        dump = oracle / "files" / f["id"] / "state.bin"
        side = json.loads(Path(str(dump) + ".json").read_text(encoding="utf-8"))
        clock = clock or side["asOf"]
        orows.append(WS.renumber(P.ingest(dump, osets), side["quests"], list(names)))
    orows = np.concatenate(orows)
    if clock != meta["clock"]:
        raise SystemExit(f"oracle at {clock}, state at {meta['clock']}")
    # the two sides with place sets as canonical ids (each side numbers its own sets), deduplicated; rows that appear
    # on one side only found by sorting both together as bytes; only their (element, quest) groups go to Python
    canon_ids: dict[tuple, int] = {}

    def lut(sets_):
        return np.array([canon_ids.setdefault(tuple(sorted(sets_.ids_of(i))), len(canon_ids)) for i in range(len(sets_.sets))],
                        np.int32)

    CR = np.dtype([("key", "<i8"), ("quest", "<i4"), ("lat", "<i4"), ("lon", "<i4"), ("flags", "<i4"), ("kind", "<i4"),
                   ("due", "<i4"), ("pl", "<i4")])

    def canon(r, lt):
        o = np.zeros(len(r), CR)
        for n in ("key", "quest", "lat", "lon", "flags", "kind", "due"):
            o[n] = r[n]
        o["pl"] = lt[r["place"]]
        return np.unique(o)

    A, B = canon(state, lut(sets)), canon(orows, lut(osets))
    del state
    allr = np.concatenate([A, B])
    v = allr.view(f"V{CR.itemsize}")
    order = np.argsort(v, kind="stable")
    vs = v[order]
    eq = vs[1:] == vs[:-1]
    paired = np.zeros(len(vs), bool)
    paired[:-1] |= eq
    paired[1:] |= eq
    single = order[~paired]
    gcode = lambda r: r["key"] * 1024 + r["quest"].astype(np.int64)  # noqa: E731
    diff_codes = np.unique(gcode(allr[single]))
    n_groups = len(np.union1d(gcode(A), gcode(B)))
    inv = {i: t for t, i in canon_ids.items()}

    def small(R):
        sel = R[np.isin(gcode(R), diff_codes)]
        out = defaultdict(list)
        for key, q, la_, lo_, fl, kd, du, pl in sel.tolist():
            out[(key, q)].append((la_, lo_, fl, kd, du, pl))
        return {k: tuple(sorted(v_)) for k, v_ in out.items()}

    a, b = small(A), small(B)
    del allr, v, vs
    touched = set(np.load(w / "touched.npy").tolist()) if (w / "touched.npy").exists() else set()
    rects = np.load(w / "rects.npy") if (w / "rects.npy").exists() else np.zeros((0, 5))
    HID = 64

    def in_rect(lat, lon):
        if not len(rects):
            return False
        return bool(((rects[:, 1] <= lat) & (lat <= rects[:, 3]) & (rects[:, 2] <= lon) & (lon <= rects[:, 4])).any())

    def strip(v_):
        return tuple((la_, lo_, fl & ~HID, kd, du, pl) for la_, lo_, fl, kd, du, pl in v_) if v_ else v_

    def noplace(v_):
        return tuple(r[:5] for r in v_) if v_ else v_

    def show(v_):
        return [r[:5] + (inv[r[5]],) for r in v_] if v_ else v_

    causes = Counter()
    examples = defaultdict(list)
    for k in a.keys() | b.keys():
        x, y = a.get(k), b.get(k)
        if x == y:
            continue
        key, q = k
        r0 = (x or y)[0]
        lat, lon = r0[0] / 1e7, r0[1] / 1e7
        if x and y and strip(x) == strip(y):
            c = "hidden flag only"
        elif x and y and noplace(x) == noplace(y):
            c = "place set only"
        elif x and y and {r[:2] for r in x} == {r[:2] for r in y} and {r[3] for r in x} != {r[3] for r in y}:
            c = "a date (match vs due)"
        else:
            c = ("only in state" if y is None else "only in whole count" if x is None else "different") + \
                (", touched key" if key in touched else "") + (", in a rectangle" if in_rect(lat, lon) else "")
        causes[c] += 1
        if len(examples[c]) < 8:
            examples[c].append({"key": key, "type": "nwr"[key & 3], "id": key >> 2, "quest": names[q] if q < len(names) else q,
                                "at": [round(lat, 6), round(lon, 6)], "state": show(x), "whole": show(y)})
    # counts: per (place, quest) open and agedOnly, against the oracle's snapshots summed over its cells
    cdir = w / "counts" / meta["clock"][:10]
    cz = np.load(cdir / "counts.npz")
    cj = json.loads((cdir / "counts.json").read_text(encoding="utf-8"))
    mi = {m: i for i, m in enumerate(cj["measures"])}
    got = {}
    for p_, q_, m_ in zip(cz["part"].tolist(), cz["quest"].tolist(), cz["m"].tolist()):
        got[(cj["parts"][p_], cj["quests"][q_])] = (m_[mi["open"]], m_[mi["agedOnly"]])
    want = Counter()
    want_aged = Counter()
    for f in files:
        snap = json.loads(next(iter(sorted((oracle / "files" / f["id"] / "out-state" / "snapshots").glob("*.json")))).read_text(encoding="utf-8"))
        for cid, c in snap["cities"].items():
            for qn, v in (c.get("quests") or {}).items():
                want[(f"city:{cid}", qn)] += v.get("open", 0)
                want_aged[(f"city:{cid}", qn)] += v.get("agedOnly", 0)
            for pid, qs in (c.get("parts") or {}).items():
                for qn, n in qs.items():
                    want[(pid, qn)] += n
            for pid, qs in (c.get("partsAged") or {}).items():
                for qn, n in qs.items():
                    want_aged[(pid, qn)] += n
    cdiff = []
    for k in set(want) | set(got) | set(want_aged):
        g = got.get(k, (0, 0))
        if g[0] != want.get(k, 0) or g[1] != want_aged.get(k, 0):
            cdiff.append((k[0], k[1], want.get(k, 0), g[0], want_aged.get(k, 0), g[1]))
    cdiff.sort(key=lambda r: -abs(r[2] - r[3]))
    cells_open = {k: v for k, v in want.items() if k[0].startswith("city:")}
    tot_w = sum(cells_open.values())
    tot_g = sum(v[0] for k, v in got.items() if k[0].startswith("city:"))
    res = {"clock": meta["clock"], "stateRows": int(len(A)), "wholeRows": int(len(B)), "groups": n_groups,
           "groupsDifferent": int(sum(causes.values())), "causes": dict(causes.most_common()),
           "countsCompared": len(set(want) | set(got)), "countsDifferent": len(cdiff),
           "openAllCells": {"whole": tot_w, "state": tot_g}, "worstCounts": cdiff[:30], "examples": examples,
           "seconds": round(time.time() - t, 1)}
    work.mkdir(parents=True, exist_ok=True)
    (work / "check.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    log(f"check {meta['clock'][:10]}: {res['groupsDifferent']:,} (element, quest) groups differ of "
        f"{n_groups:,}: {res['causes']}; counts {len(cdiff):,} of {res['countsCompared']:,} differ; "
        f"all cells open: whole {tot_w:,}, state {tot_g:,}")
    return res
