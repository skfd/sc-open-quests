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
import engine_room  # noqa: E402
import file_pool as FP  # noqa: E402
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
    tools = str(ROOT / "tools")
    if tools not in sys.path:      # once: this is called for every engine, and a pool's workers get sys.path whole
        sys.path.insert(0, tools)
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


def old_rows_of(w: Path, keys: np.ndarray, pool: int | None = None) -> np.ndarray:
    """rows_of_keys, the files read FP.FILE_POOL at a time (world_tier2.old_rows, the same rows in the same order:
    tests/test_file_pool.py); a pool of 1 is rows_of_keys itself"""
    pool = FP.FILE_POOL if pool is None else pool
    if pool <= 1:
        return rows_of_keys(w, keys)
    return T2.old_rows(w, keys, dtype=P.WREC, name=WS.WORLD_BIN, keys_name=WS.WORLD_KEYS, workers=pool)


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
    ctx: object = None  # store_context.DayContext: asked at D-1 here, at D in finish (None: the context is not used)
    heap_gb: int = 8
    engine: Path | None = None
    log: object = _log
    T: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)


def prepare(w: Path, store: Path, diff: Path, today: str, nodes: Path, work: Path, heap_gb: int = 8,
            engine: Path | None = None, log=_log, keep=None, use_context: bool = True) -> Day:
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
    T["places and old rows"] = time.time() - t
    ctx = None
    if use_context:
        # the store's answers at D-1 (DayContext.before, BEFORE the update: a generation's pairs go at the next
        # update): old tags, holding relations, containers, the roads under changed bridges, moved nodes' ways
        import store_context as SC
        t = time.time()
        ctx = SC.DayContext.before(EXE, store, g0, last_node, last_way, last_rel, old_places, work / "context",
                                   T2.contained_kind, T2.wanted_relation, log=log, over_road=T2.over_road)
        held = np.array(sorted(ctx.held_by(ctx.b)), np.int64)
        if len(held):  # a relation holding a changed way: its rows at its old quest point (its centre moves)
            keys = np.union1d(keys, held * 4 + 2)
        T["store context before"] = time.time() - t
    t = time.time()
    rows = old_rows_of(w, keys)
    T["places and old rows"] += time.time() - t
    log(f"old ways: {len(old_refs):,} of {len(last_way):,} found at generation {g0}; old rows {len(rows):,} of "
        f"{len(keys):,} changed keys")
    return Day(w, store, diff, today, meta["clock"], work, nodes, last_node, last_way, last_rel, old_refs, old_places,
               new_places, rows, g0, ctx, heap_gb, engine, log, T, {"changedKeys": int(len(keys)), "oldRows": int(len(rows))})


def save_day(day: Day, path: Path) -> None:
    """the prepared day on disk, so `finish` can be run again after the store's update (which takes generation D-1's
    way pairs away: `prepare` cannot run a second time). The node places are not saved (the planet's are a memmap of
    the whole node file): `load_day` opens them again from `day.nodes` with the diff's overlay."""
    import pickle
    state = {k: v for k, v in day.__dict__.items() if k not in ("old_places", "new_places", "log")}
    tmp = path.with_suffix(".writing")
    with open(tmp, "wb") as f:
        pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)


def load_day(path: Path, log=_log) -> Day:
    import pickle
    with open(path, "rb") as f:
        state = pickle.load(f)
    nodes = state["nodes"]
    overlay = {n: (v[4] if v[2] else None) for n, v in state["last_node"].items()}
    if nodes.is_file():
        old_places, new_places = T2.NodeFile(nodes), T2.NodeFile(nodes, overlay=overlay)
    else:
        old_places, new_places = T2.SparsePlaces(nodes), T2.SparsePlaces(nodes, extra=overlay)
    return Day(**state, old_places=old_places, new_places=new_places, log=log)


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


def engine_dump(day: Day, pbf: Path, out: Path, clock: str, cities: Path, parts: Path, area_pass: bool,
                extra_opts: str = "") -> Path:
    """one engine run, its state dump's path (thread-safe: the engine is passed, not set on `stream`)"""
    quiet(20)
    # in only when the commit charge holds this heap beside the engines alive (four died together on 2026-11-23)
    with engine_room.ROOM.engine(day.heap_gb, f"{out.parent.name}/{out.name}", day.log):
        return S.engine(pbf, out, clock, cities, "UTC", None, area_pass=area_pass, heap_gb=day.heap_gb, base=ROOT,
                        extra_opts=extra_opts, parts=parts, parts_cache=P.parts_cache(day.w), exe=day.engine)


def engine_rows(day: Day, pbf: Path, out: Path, clock: str, cities: Path, parts: Path, area_pass: bool,
                sets: P.PlaceSets, names: list[str], extra_opts: str = "", rects: bool = False) -> np.ndarray:
    return dump_rows(engine_dump(day, pbf, out, clock, cities, parts, area_pass, extra_opts), sets, names, rects)


# Tier 2's recount runs one engine per group of rectangles, not one for the day: on a planet day one run would hold
# 128,544 rectangles over about 290,000 km2 of padded map data. A group is one plan file's rectangles (their cells
# share the file's parts), cut further where its padded area passes T2_GROUP_KM2. Engines run T2_WORKERS at a time;
# their dumps are ingested in group order, so the place-set numbering does not depend on which engine ends first.
T2_GROUP_KM2 = float(os.environ.get("WORLD_T2_GROUP_KM2", "inf"))
T2_WORKERS = int(os.environ.get("WORLD_T2_WORKERS", "1"))


def padded_km2(box, ring_m: float = RING_M) -> float:
    """a rectangle city's box (s, w, n, e) grown by the map data's ring on every side, in km2"""
    s, w_, n, e = box
    lat = np.radians((s + n) / 2)
    pad = 2 * ring_m / 1000
    return float(((n - s) * 111.32 + pad) * ((e - w_) * 111.32 * np.cos(lat) + pad))


def rect_groups(cities: Path, out: Path, cap_km2: float = T2_GROUP_KM2, ring_m: float = RING_M) -> list[tuple[str, Path]]:
    """the rectangle cities (ids `f<N>c<M>-<k>`) split per plan file, a file cut where its padded area passes cap_km2;
    one cities file each under out/<group>/, in plan-file order"""
    import re
    by: dict[str, list] = defaultdict(list)
    for e in json.loads(cities.read_text(encoding="utf-8"))["cities"]:
        m = re.match(r"(f\d+)c", e["id"])
        if not m:
            raise SystemExit(f"{cities}: {e['id']} is not a rectangle city of a plan file")
        by[m.group(1)].append(e)
    groups: list[tuple[str, list]] = []
    for f in sorted(by, key=lambda s: int(s[1:])):
        chunks, cur, km2 = [], [], 0.0
        for e in by[f]:  # in the file's order, cell by cell
            a = padded_km2(e["box"], ring_m)
            if cur and km2 + a > cap_km2:
                chunks.append(cur)
                cur, km2 = [], 0.0
            cur.append(e)
            km2 += a
        chunks.append(cur)
        groups += [(f if len(chunks) == 1 else f"{f}-{i}", c) for i, c in enumerate(chunks)]
    res = []
    for gid, cs in groups:
        d = out / gid
        d.mkdir(parents=True, exist_ok=True)
        (d / "cities.json").write_text(json.dumps({"cities": cs}), encoding="utf-8")
        res.append((gid, d / "cities.json"))
    return res


# A group's map data goes once its engine has run (a planet day's is about 8 GB a date); WORLD_T2_KEEP_PBF=1 keeps it
# for a diagnosis (an engine run again on the same read).
T2_KEEP_PBF = os.environ.get("WORLD_T2_KEEP_PBF") == "1"


def _engine_then_drop(day: Day, pbf: Path, out: Path, clock: str, cities: Path, parts: Path, opts: str) -> Path:
    dump = engine_dump(day, pbf, out, clock, cities, parts, True, opts)
    if not T2_KEEP_PBF:
        pbf.unlink()
    return dump


def rect_rows(day: Day, cities: Path, parts: Path, gen: int, clock: str, stamp: str, which: str, out: Path,
              sets: P.PlaceSets, names: list[str], opts: str, workers: int = T2_WORKERS,
              cap_km2: float = T2_GROUP_KM2) -> tuple[np.ndarray, dict]:
    """the rectangles recounted on one generation of the store at one clock, group by group: each group's map data
    read on its own (`tilestore read`), its engines `workers` at a time, the rows ingested in group order"""
    from concurrent.futures import ThreadPoolExecutor
    gs = rect_groups(cities, out, cap_km2)
    st = {"groups": len(gs), "read s": 0.0, "pbf MB": 0.0}
    with ThreadPoolExecutor(max(1, workers)) as ex:
        futs = []
        for gid, cf in gs:  # reads one at a time (the reader uses the threads), engines start as their read lands
            pbf = cf.parent / f"{which}.osm.pbf"
            t = time.time()
            tilestore("read", "--store", day.store, "--gen", gen, "--cities", cf, "--base", ROOT, "--ring",
                      f"{RING_M:.0f}", "--out", pbf, "--stamp", stamp, log=day.log)
            st["read s"] += time.time() - t
            st["pbf MB"] += pbf.stat().st_size / 1e6
            futs.append((gid, pbf.stat().st_size / 1e6,
                         ex.submit(_engine_timed, day, pbf, cf.parent / which, clock, cf, parts, opts)))
        dumps = []
        for i, (gid, mb, f) in enumerate(futs, 1):  # a line per group: tier 2 was hours without one
            d, s = f.result()
            dumps.append(d)
            if day.log:
                day.log(f"tier 2 {which}: group {gid} ({mb:,.0f} MB) engine {s:.0f} s; {i} of {len(futs)} done")
    rows = [dump_rows(d, sets, names, rects=True) for d in dumps]
    st = {k: round(v, 1) if isinstance(v, float) else v for k, v in st.items()}
    return (np.unique(np.concatenate(rows)) if rows else np.zeros(0, P.WREC)), st


def _engine_timed(*args) -> tuple[Path, float]:
    t = time.time()
    return _engine_then_drop(*args), time.time() - t


def dump_rows(dump: Path, sets: P.PlaceSets, names: list[str], rects: bool = False) -> np.ndarray:
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


def _mix(x: np.ndarray) -> np.ndarray:
    """splitmix64's finaliser, on uint64 arrays (wrapping)"""
    x = x ^ (x >> np.uint64(30))
    x = x * np.uint64(0xBF58476D1CE4E5B9)
    x = x ^ (x >> np.uint64(27))
    x = x * np.uint64(0x94D049BB133111EB)
    return x ^ (x >> np.uint64(31))


def group_prints(a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """per (element, quest) code, in code order: the codes and a fingerprint of the group's rows as a multiset (row
    count and two sums of a 64-bit hash of each row's bytes). Two groups with the same fingerprint hold the same rows
    but for a hash collision (about 2**-128): `groups` without a Python object per row (a planet day's recount is
    tens of millions of rows a date)"""
    if not len(a):
        return np.zeros(0, np.int64), np.zeros((0, 3), np.uint64)
    n = len(a)
    words = np.zeros((n, 32), np.uint8)
    words[:, :a.dtype.itemsize] = np.ascontiguousarray(a).view(np.uint8).reshape(n, a.dtype.itemsize)
    words = words.view(np.uint64)  # (n, 4)
    with np.errstate(over="ignore"):
        hs = []
        for seed in (0x9E3779B97F4A7C15, 0xD1B54A32D192ED03):
            h = np.full(n, seed, np.uint64)
            for j in range(words.shape[1]):
                h = _mix(h ^ words[:, j])
            hs.append(h)
    c = codes_of(a)
    o = np.argsort(c, kind="stable")
    cs = c[o]
    starts = np.flatnonzero(np.concatenate([[True], cs[1:] != cs[:-1]]))
    fp = np.zeros((len(starts), 3), np.uint64)
    fp[:, 0] = np.diff(np.append(starts, n)).astype(np.uint64)
    with np.errstate(over="ignore"):
        for k, h in enumerate(hs):
            fp[:, k + 1] = np.add.reduceat(h[o], starts)
    return cs[starts], fp


def changed_groups(old: np.ndarray, new: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """the (element, quest) codes whose rows differ between the two recounts, sorted; and for each, whether the old
    and the new recount hold the group at all"""
    co, fo = group_prints(old)
    cn, fn = group_prints(new)
    both, io, in_ = np.intersect1d(co, cn, assume_unique=True, return_indices=True)
    differ = both[(fo[io] != fn[in_]).any(axis=1)]
    cand = np.union1d(np.union1d(np.setdiff1d(co, cn, assume_unique=True), np.setdiff1d(cn, co, assume_unique=True)),
                      differ)
    return cand, np.isin(cand, co), np.isin(cand, cn)


def delta_w(w: Path, old: np.ndarray, new: np.ndarray, files: list[dict], added: dict[str, set],
            T: dict | None = None) -> dict:
    """tier2.delta on the world's WREC files: per (element, quest), the recount's change from D-1 to D applied; a group
    the recount changed but the state lacks is kept out (a recount-vs-whole disagreement), as tier2.delta does.
    T: the day's seconds, given the delta's own parts (the changed groups, the first pass over the files that finds
    what the state holds, the second that rewrites them, and of the second the writes alone)"""
    T = {} if T is None else T
    t = time.time()
    cand, has_old, has_new = changed_groups(old, new)
    T["tier 2 delta: changed groups"] = time.time() - t
    t = time.time()
    held: set[int] = set()
    if len(cand):
        for f in files:
            fc = codes_of(np.fromfile(w / "files" / f["id"] / WS.WORLD_BIN, P.WREC))
            held |= set(fc[np.isin(fc, cand)].tolist())
    T["tier 2 delta: first pass"] = time.time() - t
    st = Counter()
    put, gone = set(), set()
    for c, ho, hn in zip(cand.tolist(), has_old.tolist(), has_new.tolist()):
        if not ho:
            put.add(c); st["added"] += 1
            if c in held:
                st["added, the state had it"] += 1
        elif not hn:
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
    t = time.time()
    wrote = 0.0
    for f, idx in zip(files, parts):
        p = w / "files" / f["id"] / WS.WORLD_BIN
        r = np.fromfile(p, P.WREC)
        drop = np.isin(codes_of(r), both)
        if not drop.any() and not len(idx):
            continue
        st["rows dropped"] += int(drop.sum())
        r = WS.merge(r[~drop], add[idx])
        tw = time.time()
        WS.write_rows(p, r)
        wrote += time.time() - tw
        added[f["id"]] |= set(codes_of(add[idx]).tolist())
    T["tier 2 delta: second pass"] = time.time() - t
    T["tier 2 delta: rewrite"] = wrote
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


NOTES_PREV = "notes-prev.jsonl"  # the union clip of the dump before a refresh: the day's D-1 side of the hidden flags


def notes_until(w: Path) -> str:
    """the newest comment of the dump the world's notes clips were cut from: notes are known up to then"""
    with open(w / "files" / files_of(w)[0]["id"] / "notes.jsonl", encoding="utf-8") as fh:
        return json.loads(fh.readline())["until"]


def refresh_notes(w: Path, dump: Path, log=_log, gate_clips: list[dict] | None = None) -> None:
    """every plan file's notes clip cut again from a newer dump (each file's bbox.poly, one pass), the union clip
    rebuilt. The old union clip is kept as NOTES_PREV until the day is done: a note the newer dump no longer holds
    (hidden by a moderator) must still count as open at D-1, or its rows keep their hidden flag. The gate's clips go
    too; with `gate_clips` (world_gate.gate_clips: the entries world_gate would ask clip_notes for) they are cut
    in this same pass and put in place of the old ones, so the gate does not decompress the dump a second time
    (99 s on 11-25); without, world_gate makes them again from the newer dump, as it does any that is missing."""
    files = files_of(w)
    gate_clips = gate_clips or []
    cfg = w / "notes-refresh.json"
    cfg.write_text(json.dumps({"clips": [{"poly": str(w / "files" / f["id"] / "bbox.poly"),
                                          "out": str(w / "files" / f["id"] / "notes.jsonl.new")} for f in files]
                               + [dict(c, out=c["out"] + ".new") for c in gate_clips]}),
                   encoding="utf-8")
    t = time.time()
    subprocess.run([sys.executable, str(ROOT / "tools/clip_notes.py"), str(dump), "--config", str(cfg)], check=True,
                   cwd=ROOT)
    for f in files:
        d = w / "files" / f["id"]
        with open(d / "notes.jsonl.new", encoding="utf-8") as fh:
            if json.loads(fh.readline())["source"] != dump.name:
                raise SystemExit(f"{d / 'notes.jsonl.new'} is not from {dump.name}")
    for c in gate_clips:
        with open(c["out"] + ".new", encoding="utf-8") as fh:
            if json.loads(fh.readline())["source"] != dump.name:
                raise SystemExit(f"{c['out']}.new is not from {dump.name}")
    allc = w / "notes-all.jsonl"
    if allc.exists() and not (w / NOTES_PREV).exists():
        os.replace(allc, w / NOTES_PREV)
    for f in files:  # all clips cut: now put in place
        d = w / "files" / f["id"]
        os.replace(d / "notes.jsonl.new", d / "notes.jsonl")
    for p in [allc, allc.with_name(allc.name + ".table.npz"), *(w / "gate-notes").glob("*.jsonl")]:
        p.unlink(missing_ok=True)
    for c in gate_clips:  # the old ones are gone, whatever their names: now this dump's
        os.replace(c["out"] + ".new", c["out"])
    cfg.unlink()
    world_notes(w)
    log(f"notes: the world's clips cut again from {dump.name} (until {notes_until(w)}) in {time.time() - t:.0f} s")


def counts_at(w: Path, clock: str, sets: P.PlaceSets, names: list[str], work: Path, engine: Path | None = None,
              heap_gb: int = 8, T: dict | None = None) -> Path:
    """the counts per place and per cell at the clock (W/counts/<day>/): the state's rows through place_counts, the
    note quests counted by the engine over the notes alone (notes_day.note_quests) added per place and per cell.
    T: the day's seconds, given this step's own parts (the note engines, the sets' save, the files counted, the save)"""
    T = {} if T is None else T
    t_engines = time.time()
    # one engine run per plan file, its cells and its parts (all of a world's parts in one run do not fit: Europe
    # alone has 502,597 part entries); each note is in one cell, so the files' counts add up
    nq = {"cities": {}, "parts": Counter()}

    def one(f):
        d = w / "files" / f["id"]
        quiet(5)
        with engine_room.ROOM.engine(heap_gb, f"notes/{f['id']}"):
            return N.note_quests(d / "cities.json", d / "notes.jsonl", clock, work / f["id"], parts=d / "parts",
                                 engine=engine, heap_gb=heap_gb, parts_cache=P.parts_cache(w))

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max(1, T2_WORKERS)) as ex:
        for r in ex.map(one, files_of(w)):  # in file order: the sums do not depend on which run ends first
            nq["cities"].update(r["cities"])
            nq["parts"].update(r["parts"])
    T["counts: note engines"] = time.time() - t_engines
    if NOTE_QUEST not in names:
        names.append(NOTE_QUEST)
    qi = names.index(NOTE_QUEST)
    vec = lambda n: np.array([n] + [0] * (len(C.MEASURES) - 1), np.int64)  # noqa: E731
    extra = [(sets.part(f"city:{cid}"), qi, vec(v["quests"])) for cid, v in nq["cities"].items() if v["quests"]]
    extra += [(sets.part(pid), qi, vec(n)) for pid, n in nq["parts"].items() if n]
    t = time.time()
    sets.save()
    T["counts: sets save"] = time.time() - t
    t = time.time()
    paths = [w / "files" / f["id"] / WS.WORLD_BIN for f in files_of(w)]
    codes_c, sums = C.count_files(paths, P.WREC, S.minute(clock), sets.sets, len(names), extra=extra)
    T["counts: count files"] = time.time() - t
    t = time.time()
    cdir = w / "counts" / clock[:10]
    C.write(cdir, codes_c, sums, len(names), clock, names, sets.parts)
    T["counts: save"] = time.time() - t
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

    # the store's answers at D (after the update, before `compact`), and the cover's hooks from both days
    hooks = {"old_refs": old_refs, "member_refs": member_refs}
    if day.ctx is not None:
        t = time.time()
        day.ctx.after(EXE, day.store, g1, day.new_places, day.work / "context", log=log)
        h = day.ctx.hooks(T2.container_kind)
        h.pop("member_refs")  # the members looked up above (the diff's own refs first), as before
        h["old_refs"] = old_refs
        hooks.update(h)
        T["store context after"] = time.time() - t

    # the cover and its rectangles (the old rows are the state's before tier 1 replaced any)
    t = time.time()
    codes, cstats, secs = T2.cover(day.last_node, day.last_way, day.last_rel, day.old_places, day.new_places,
                                   day.old_rows, log=log, **hooks)
    T["cover"] = time.time() - t
    t2w = day.work / "t2"
    t2w.mkdir(parents=True, exist_ok=True)
    np.save(t2w / "codes.npy", codes)
    TT = {}
    # the places' bboxes are kept beside places.json, not in the day's work: 395 MB of JSON is not parsed every day
    rinfo = T2.after_cover(codes, plan_path, w, t2w, ROOT, w / "places.json", TT, log=log,
                           bbox_cache=w / "place-bboxes.npz")
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
    T["tier 1: small pbf"] = time.time() - t
    t1 = time.time()
    # one engine run per plan file over the same small PBF (its cells and parts; elements outside them are skipped),
    # T2_WORKERS at a time; the dumps ingested in file order, so the place-set numbering does not depend on which
    # engine ends first
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max(1, T2_WORKERS)) as ex:
        futs = [ex.submit(engine_dump, day, t1w / "touched.osm.pbf", t1w / f["id"], day.today,
                          w / "files" / f["id"] / "cities.json", w / "files" / f["id"] / "parts", False) for f in files]
        dumps1 = [f_.result() for f_ in futs]
    T["tier 1: engines"] = time.time() - t1
    t1 = time.time()
    new1 = (np.concatenate([dump_rows(d_, sets, names) for d_ in dumps1]) if files else np.zeros(0, P.WREC))
    new1 = np.unique(new1)
    tier1 = WS.tier1_mask(names)
    new1 = new1[tier1[new1["quest"]]]
    touched = np.unique(np.concatenate([np.fromiter(day.last_node, np.int64, len(day.last_node)) * 4,
                                        np.fromiter(day.last_way, np.int64, len(day.last_way)) * 4 + 1]))
    parts, unrouted1 = WS.route(new1, files)
    T["tier 1: ingest"] = time.time() - t1
    t1 = time.time()
    d1 = a1 = 0
    for f, idx in zip(files, parts):
        d_, a_ = WS.replace_in_file(w / "files" / f["id"] / WS.WORLD_BIN, touched, tier1, new1[idx], dtype=P.WREC,
                                    keys_name=WS.WORLD_KEYS)
        d1, a1 = d1 + d_, a1 + a_
        if len(idx):
            added[f["id"]] |= set(codes_of(new1[idx]).tolist())
    T["tier 1: rewrite"] = time.time() - t1
    T["tier 1"] = time.time() - t
    log(f"tier 1: {d1:,} rows of touched elements dropped, {a1:,} added; {unrouted1:,} in no file; {dict(pst)}")

    # tier 2: the rectangles on D-1 at D-1's clock and on D at D's, the delta into the files
    t = time.time()
    cities, rparts = t2w / "cities.json", t2w / "parts"
    opts = f"-Dopenquests.areaPaddingM={RING_M:.0f}"
    t2s = {}
    if rinfo["rectangles"]:
        # group by group (rect_groups), D-1 first: its rows are ingested before D's, as when the day was one run
        old, gst_old = rect_rows(day, cities, rparts, day.gen_before, day.prev, day.prev, "old", t2w / "groups",
                                 sets, names, opts)
        new, gst_new = rect_rows(day, cities, rparts, g1, day.today, day.today, "new", t2w / "groups", sets, names, opts)
        T["tier 2 reads"] = gst_old["read s"] + gst_new["read s"]
        T["tier 2 engine"] = time.time() - t - T["tier 2 reads"]
        log(f"tier 2 groups: {gst_old['groups']}, map data {gst_old['pbf MB']:,.0f} MB at D-1 and "
            f"{gst_new['pbf MB']:,.0f} MB at D")
        t = time.time()
        t2s = delta_w(w, old, new, files, added, T)
        T["tier 2 delta"] = time.time() - t
        log(f"tier 2: {rinfo['rectangles']:,} rectangles, {rinfo['rectKm2']:,} km2; recount rows {len(old):,} at D-1, "
            f"{len(new):,} at D; {t2s}")
    t = time.time()
    sets.save()
    T["sets save"] = time.time() - t

    # notes at D: hidden flags (only rows at notes that opened or closed, and the day's new rows), note quests
    t = time.time()
    clip = world_notes(w)
    # notes_day.hidden_files: the clip as a cached table, only files a changed note position or new rows reach,
    # in parallel, flags written in place (the same rule and result as hidden_step file by file)
    fresh = [np.unique(np.fromiter(added[f["id"]], np.int64, len(added[f["id"]]))) if added[f["id"]] else None
             for f in files]
    prev_clip = w / NOTES_PREV  # the clip of the dump before a refresh, if this is the day after one
    nst = Counter(N.hidden_files([w / "files" / f["id"] / WS.WORLD_BIN for f in files], [f["rect"] for f in files],
                                 P.WREC, N.notes_table(clip), day.today, day.prev, fresh,
                                 prev_table=N.notes_table(prev_clip) if prev_clip.exists() else None))
    T["notes"] = time.time() - t
    t = time.time()
    counts_at(w, day.today, sets, names, day.work / "notes", day.engine, day.heap_gb, T)
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
    t = time.time()
    tf = w / "touched.npy"
    keys = T2.changed_keys(day.last_node, day.last_way, day.last_rel)
    np.save(tf, np.union1d(np.load(tf), keys) if tf.exists() else keys)
    rf = w / "rects.npy"
    rn = np.load(t2w / "rects.npy") if (t2w / "rects.npy").exists() else np.zeros((0, 5))
    np.save(rf, np.concatenate([np.load(rf), rn]) if rf.exists() else rn)
    # timed after day.json and world.json were written: in the day's log line and the record returned, not in them
    T["touched and rects"] = time.time() - t
    rec["seconds"]["touched and rects"] = round(T["touched and rects"], 1)
    log(f"day {day.today[:10]} done: {json.dumps(rec['seconds'])}")
    return rec


def run(w: Path, store: Path, diff: Path, today: str, nodes: Path, work: Path, before_clip: Path | None = None,
        polygon: Path | None = None, before_loc: Path | None = None, heap_gb: int = 8, engine: Path | None = None,
        log=_log, compact: bool = True, keep=None, use_context: bool = True) -> dict:
    day = prepare(w, store, diff, today, nodes, work, heap_gb, engine, log, keep=keep, use_context=use_context)
    update_store(day, before_clip, polygon, before_loc)
    rec = finish(day)
    if compact:
        tilestore("compact", "--store", store, "--min-dead", "0.25", log=log)
    return rec


# --- the check against a whole count ---------------------------------------------------------------------------

def check(w: Path, oracle: Path, work: Path, log=_log, polygon: Path | None = None) -> dict:
    """the state at its clock against the oracle's whole count of the same plan at the same instant (its files'
    state.bin and .places, and their snapshots): every row, records and place sets, split by cause; and every
    count per place and per cell, open and agedOnly, note quests included"""
    t = time.time()
    outside = None
    if polygon is not None:  # a rehearsal on a clip: rows outside its polygon are the clip's edge, not the stream
        import shapely
        from shapely.geometry import shape
        gj = json.loads(Path(polygon).read_text(encoding="utf-8"))
        geom = shapely.union_all([shape(f["geometry"]) for f in gj["features"]]) if "features" in gj else shape(gj)
        shapely.prepare(geom)

        def outside(lat, lon):
            return not shapely.contains_xy(geom, lon, lat)
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

    clock_min = S.minute(meta["clock"])
    SETTINGS = (1, 4, 16)  # M_NOW, M_05, M_2; each one's aged bit is the next one up

    def at_clock(v_):
        """a group as it counts at the clock: a date that has come is an open, aged match at its setting (no
        setting bit is the default), merged into the group's match row; dates still to come kept as they are.
        The engine at D writes such a quest as a match, the stream keeps the date it was given: the same count."""
        match = {}
        later = []
        for la_, lo_, fl, kd, du, pl in v_:
            if kd == 1 and du <= clock_min:
                st_ = (fl & 21) or 1
                kd, fl = 0, (fl & 64) | st_ | (st_ << 1)
            if kd == 0:
                k_ = (la_, lo_, pl)
                match[k_] = match.get(k_, 0) | fl
            else:
                later.append((la_, lo_, fl, kd, du, pl))
        return tuple(sorted([(la_, lo_, fl, 0, 0, pl) for (la_, lo_, pl), fl in match.items()] + later))

    def small(R):
        sel = R[np.isin(gcode(R), diff_codes)]
        out = defaultdict(list)
        for key, q, la_, lo_, fl, kd, du, pl in sel.tolist():
            out[(key, q)].append((la_, lo_, fl, kd, du, pl))
        return {k: at_clock(v_) for k, v_ in out.items()}

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
        def default(v_):  # what the site counts: the default setting's open match (and its aged bit), not hidden
            return tuple(sorted((r[0], r[1], r[2] & 3, r[5]) for r in v_ if r[3] == 0 and r[2] & 1 and not r[2] & 64)) if v_ else ()

        if x == y:
            continue  # equal once both are at the clock: a date the stream kept, the same count
        if outside is not None and outside(lat, lon):
            c = "outside the clip's polygon (a clip-edge difference, not the stream's)"
        elif x and y and strip(x) == strip(y):
            c = "hidden flag only"
        elif x and y and noplace(x) == noplace(y):
            c = "place set only"
        else:
            c = ("only in state" if y is None else "only in whole count" if x is None else "different") + \
                (", touched key" if key in touched else "") + (", in a rectangle" if in_rect(lat, lon) else "")
            if default(x) == default(y):
                c += " (not at the default setting)"
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
    cities_diff = [r for r in cdiff if r[0].startswith("osm-")]  # the counted cities' own outlines: inside the clip
    cells_open = {k: v for k, v in want.items() if k[0].startswith("city:")}
    tot_w = sum(cells_open.values())
    tot_g = sum(v[0] for k, v in got.items() if k[0].startswith("city:"))
    res = {"clock": meta["clock"], "stateRows": int(len(A)), "wholeRows": int(len(B)), "groups": n_groups,
           "groupsDifferent": int(sum(causes.values())), "causes": dict(causes.most_common()),
           "countsCompared": len(set(want) | set(got)), "countsDifferent": len(cdiff),
           "cityCountsCompared": len([k for k in set(want) | set(got) if k[0].startswith("osm-")]),
           "cityCountsDifferent": len(cities_diff), "worstCityCounts": cities_diff[:30],
           "openAllCells": {"whole": tot_w, "state": tot_g}, "worstCounts": cdiff[:30], "examples": examples,
           "seconds": round(time.time() - t, 1)}
    work.mkdir(parents=True, exist_ok=True)
    (work / "check.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    log(f"check {meta['clock'][:10]}: {res['groupsDifferent']:,} (element, quest) groups differ of "
        f"{n_groups:,}: {res['causes']}; counts {len(cdiff):,} of {res['countsCompared']:,} differ "
        f"(the 32 cities' own: {len(cities_diff):,} of {res['cityCountsCompared']:,}); "
        f"all cells open: whole {tot_w:,}, state {tot_g:,}")
    return res
