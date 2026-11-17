"""Tier 2's cover for the whole world (DESIGN.md, "Release 1: the world day", step 3).

What tier2.cover does per city, done once for the planet in one global grid of CELL m cells, vectorised:

- the ground a day touched: a changed node's old and new place; a changed way's new segments and its old ones (old
  refs from `old_refs(wid)`, by default today's refs at yesterday's places: tier2's NO_WAY_INDEX); a closed way's
  box (a box over `cap_km2` marks its outline only, and is logged); a changed multipolygon's, street's or ferry
  route's member ways (`member_refs(wid)`), a multipolygon's box too; and the old position of every state row of
  every changed node, way and relation, whether or not its geometry was marked (a deleted way has no refs: its rows
  are how its quests are found);
- the marked cells padded by PAD, as runs along each grid row, split at the world plan's cell edges (plan.json
  files[].cells[].rect, [s, w, n, e]; the cells tile the globe with shared float edges), merged per plan cell with
  tier2.merge_rects in the cell's local metres, and back to degrees inside the cell;
- written for the engine: every rectangle a city `<cell>-<k>` with its cell's time zone and no country codes (gated
  by position, as every cell is), a boundary file as tier2.write_cities writes, `"box"` inline for `tilestore read`;
  and a parts dir with `<rectId>.json`: the cell's parts whose bbox meets the rectangle (place bboxes from the name
  layer's places.json, kept as a small npz; the counted cities' `osm-<city>` parts from plan.json's cityParts).

The grid: row i is CELL m of latitude, floor(lat * M_LAT / CELL); within a row a cell is CELL m of longitude at the
row's middle (the width taken at 85 degrees at most), counted from -180. Points along a segment are taken every
CELL / 2 m, as tier2's Cover.segment; a segment of over 100,000 steps or across the antimeridian marks its ends.

  python tools/stream/world_tier2.py time --diff N.osc.gz --plan W/plan.json --world W --nodes planet.loc --work DIR
      the cover of one planet day timed stage by stage (the node file read only), rectangles and km2 counted
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tier2 import M_LAT, CELL, PAD, RING, WANTED_REL, merge_rects  # noqa: E402

DLAT = CELL / M_LAT
MAX_COS_LAT = 85.0  # a cell's width is taken at 85 degrees at most, as the rings are (world_cells.padded)
I_OFF = 1 << 20  # row offset so codes stay positive: |i| <= 90 * M_LAT / CELL < 2**18
MAX_STEPS = 100_000
CAP_KM2 = 25.0
INVALID = 2147483647


# --- the grid ------------------------------------------------------------------------------------

def row_of(lat):
    return np.floor(np.asarray(lat, float) / DLAT).astype(np.int64)


def dlon_of(i):
    """a row's cell width in degrees of longitude"""
    mid = (np.asarray(i, float) + 0.5) * DLAT
    return DLAT / np.cos(np.radians(np.minimum(np.abs(mid), MAX_COS_LAT)))


def cells_of(lat, lon) -> np.ndarray:
    """the grid cells of these points as int64 codes (row + I_OFF) << 32 | column"""
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    ok = np.isfinite(lat) & np.isfinite(lon)
    lat, lon = lat[ok], lon[ok]
    i = row_of(lat)
    j = np.floor((lon + 180.0) / dlon_of(i)).astype(np.int64)
    return ((i + I_OFF) << 32) | j


def decode(codes):
    return (codes >> 32) - I_OFF, codes & 0xFFFFFFFF


class Marks:
    """the marked cells, gathered in chunks, by kind for the stats"""

    def __init__(self):
        self.chunks: list[np.ndarray] = []
        self.by_kind = Counter()

    def add(self, codes: np.ndarray, kind: str):
        if len(codes):
            self.chunks.append(codes)
            self.by_kind[kind] += len(codes)

    def points(self, lat, lon, kind):
        self.add(cells_of(lat, lon), kind)

    def segments(self, seg: np.ndarray, kind: str, chunk: int = 2_000_000):
        """seg: (n, 4) lat1, lon1, lat2, lon2; points every CELL/2 m along each, ends included"""
        seg = seg[np.isfinite(seg).all(axis=1)]
        if not len(seg):
            return
        la1, lo1, la2, lo2 = seg.T
        mlat = (la1 + la2) / 2
        dy = (la2 - la1) * M_LAT
        dx = (lo2 - lo1) * M_LAT * np.cos(np.radians(np.minimum(np.abs(mlat), MAX_COS_LAT)))
        steps = np.maximum(1, (np.hypot(dx, dy) / (CELL / 2)).astype(np.int64) + 1)
        steps[(steps > MAX_STEPS) | (np.abs(lo2 - lo1) > 180)] = 1
        start = 0
        while start < len(seg):  # chunks of about `chunk` points
            c = np.cumsum(steps[start:] + 1)
            end = start + max(1, int(np.searchsorted(c, chunk)))
            st = steps[start:end]
            k = np.repeat(np.arange(start, end), st + 1)
            t = (np.arange(len(k)) - np.repeat(np.concatenate([[0], np.cumsum(st + 1)[:-1]]), st + 1)) / st[k - start]
            self.points(la1[k] + (la2[k] - la1[k]) * t, lo1[k] + (lo2[k] - lo1[k]) * t, kind)
            start = end

    def boxes(self, b: np.ndarray, kind: str, chunk: int = 4_000_000):
        """b: (n, 4) s, w, n, e; every cell of each box"""
        if not len(b):
            return
        i0, i1 = row_of(b[:, 0]), row_of(b[:, 2])
        rows = i1 - i0 + 1
        bi = np.repeat(np.arange(len(b)), rows)
        ri = i0[bi] + (np.arange(len(bi)) - np.repeat(np.concatenate([[0], np.cumsum(rows)[:-1]]), rows))
        dl = dlon_of(ri)
        j0 = np.floor((b[bi, 1] + 180.0) / dl).astype(np.int64)
        j1 = np.floor((b[bi, 3] + 180.0) / dl).astype(np.int64)
        n = j1 - j0 + 1
        start = 0
        while start < len(ri):
            c = np.cumsum(n[start:])
            end = start + max(1, int(np.searchsorted(c, chunk)))
            nn = n[start:end]
            rr = np.repeat(ri[start:end], nn)
            jj = np.repeat(j0[start:end], nn) + (np.arange(int(nn.sum())) - np.repeat(np.concatenate([[0], np.cumsum(nn)[:-1]]), nn))
            self.add(((rr + I_OFF) << 32) | jj, kind)
            start = end

    def codes(self) -> np.ndarray:
        return np.unique(np.concatenate(self.chunks)) if self.chunks else np.zeros(0, np.int64)


def box_km2(b: np.ndarray) -> np.ndarray:
    mlat = (b[:, 0] + b[:, 2]) / 2
    return (b[:, 2] - b[:, 0]) * M_LAT * (b[:, 3] - b[:, 1]) * M_LAT * np.cos(np.radians(np.minimum(np.abs(mlat), MAX_COS_LAT))) / 1e6


# --- node places ---------------------------------------------------------------------------------

class NodeFile:
    """the planet's node places, osmium's dense_file_array (8 bytes an id: lon, lat in 1e-7 degrees), read only and
    vectorised; `overlay` (id -> (lat, lon) or None) takes the day's changes, never written to the file"""

    def __init__(self, path: Path, overlay: dict | None = None):
        self.m = np.memmap(path, dtype="<i4", mode="r").reshape(-1, 2)
        self.overlay = overlay or {}

    def places(self, ids) -> np.ndarray:
        """(n, 2) lat, lon; NaN where unknown"""
        ids = np.asarray(ids, np.int64)
        out = np.full((len(ids), 2), np.nan)
        ok = (ids >= 0) & (ids < len(self.m))
        if ok.any():
            v = np.asarray(self.m[ids[ok]])
            good = v[:, 0] != INVALID
            sub = np.full((ok.sum(), 2), np.nan)
            sub[good, 0] = v[good, 1] / 1e7
            sub[good, 1] = v[good, 0] / 1e7
            out[ok] = sub
        if self.overlay:
            for k, nid in enumerate(ids.tolist()):
                if nid in self.overlay:
                    p = self.overlay[nid]
                    out[k] = p if p else (np.nan, np.nan)
        return out


class SparsePlaces:
    """a region's node places as stream.Locations keeps them (D/nodes.idx, sorted id u64, x i32, y i32, plus
    D/overlay.pickle), vectorised; `extra` (id -> (lat, lon) or None) goes over both"""

    def __init__(self, d: Path, extra: dict | None = None):
        import pickle
        a = np.memmap(Path(d) / "nodes.idx", dtype=[("id", "<u8"), ("x", "<i4"), ("y", "<i4")], mode="r")
        n = len(a)
        lo, hi = 0, n  # the file ends in unused zero slots: the first of them by bisection over id == 0
        while lo < hi:
            mid = (lo + hi) // 2
            if a["id"][mid] == 0:  # ids rise, then zeros to the end: the first zero
                hi = mid
            else:
                lo = mid + 1
        self.a = a[:lo]
        self.keys = np.asarray(self.a["id"]).astype(np.int64)
        with open(Path(d) / "overlay.pickle", "rb") as f:
            over = pickle.load(f)
        over.update(extra or {})
        self.oid = np.fromiter(over.keys(), np.int64, len(over))
        v = np.array([p if p else (np.nan, np.nan) for p in over.values()], float).reshape(-1, 2)
        order = np.argsort(self.oid)
        self.oid, self.ov = self.oid[order], v[order]

    def places(self, ids) -> np.ndarray:
        ids = np.asarray(ids, np.int64)
        out = np.full((len(ids), 2), np.nan)
        if len(self.keys) and len(ids):
            i = np.minimum(np.searchsorted(self.keys, ids), len(self.keys) - 1)
            hit = self.keys[i] == ids
            rows = self.a[i[hit]]
            out[hit, 0] = rows["y"] / 1e7
            out[hit, 1] = rows["x"] / 1e7
        if len(self.oid) and len(ids):
            i = np.minimum(np.searchsorted(self.oid, ids), len(self.oid) - 1)
            hit = self.oid[i] == ids
            out[hit] = self.ov[i[hit]]
        return out


class DictPlaces:
    """node places from a mapping (tests, or a stream.Locations): get(id) -> (lat, lon) | None"""

    def __init__(self, get):
        self.get = get

    def places(self, ids) -> np.ndarray:
        out = np.full((len(ids), 2), np.nan)
        for k, nid in enumerate(np.asarray(ids).tolist()):
            p = self.get(nid)
            if p:
                out[k] = p
        return out


# --- the cover -----------------------------------------------------------------------------------

def _lines(refs_list, places) -> tuple[np.ndarray, list[np.ndarray]]:
    """every consecutive pair of each ref list as segments, and each line's points (for boxes)"""
    if not refs_list:
        return np.zeros((0, 4)), []
    lens = np.array([len(r) for r in refs_list])
    allrefs = np.fromiter((x for r in refs_list for x in r), np.int64, int(lens.sum()))
    pts = places.places(allrefs)
    offs = np.concatenate([[0], np.cumsum(lens)])
    lines = [pts[offs[k]:offs[k + 1]] for k in range(len(refs_list))]
    segs = []
    for g in lines:
        g = g[np.isfinite(g).all(axis=1)]  # a node unknown here drops out, its neighbours joined, as tier2's lists do
        if len(g) >= 2:
            segs.append(np.hstack([g[:-1], g[1:]]))
        elif len(g) == 1:
            segs.append(np.hstack([g, g]))
    return (np.vstack(segs) if segs else np.zeros((0, 4))), lines


def _closed_boxes(refs_list, lines) -> np.ndarray:
    out = []
    for r, g in zip(refs_list, lines):
        if len(r) >= 4 and r[0] == r[-1]:
            g = g[np.isfinite(g).all(axis=1)]
            if len(g):
                out.append((g[:, 0].min(), g[:, 1].min(), g[:, 0].max(), g[:, 1].max()))
    return np.array(out, float).reshape(-1, 4)


def cover(last_node: dict, last_way: dict, last_rel: dict, old_places, new_places, old_rows: np.ndarray | None,
          old_refs=None, member_refs=None, cap_km2: float = CAP_KM2, log=print, box_clip=None):
    """the cells a day touched. last_*: stream.read_diff's; old_places / new_places: node places at D-1 and D (a
    NodeFile, or DictPlaces); old_rows: the state's rows (lat, lon in 1e-7) of every changed key; old_refs(wid) and
    member_refs(wid): a way's refs at D-1 and at D (None when unknown). Returns (codes, stats)."""
    t0 = time.time()
    marks = Marks()
    stats = Counter()
    secs = {}
    # changed nodes: old and new place
    nid = np.fromiter(last_node, np.int64, len(last_node))
    if len(nid):
        old = old_places.places(nid)
        new = np.array([v[4] if v[4] else (np.nan, np.nan) for v in last_node.values()], float).reshape(-1, 2)
        marks.points(old[:, 0], old[:, 1], "node")
        marks.points(new[:, 0], new[:, 1], "node")
    stats["changed nodes"] = len(nid)
    secs["nodes"] = time.time() - t0

    # changed ways: new segments (at D), old segments (old refs at D-1)
    t = time.time()
    new_refs = [v[4] if v[2] and v[4] else [] for v in last_way.values()]
    if old_refs is None:
        old_list = new_refs  # NO_WAY_INDEX: today's refs at yesterday's places
    else:
        old_list = [old_refs(w) or [] for w in last_way]
    nseg, nlines = _lines(new_refs, new_places)
    oseg, olines = _lines(old_list, old_places)
    marks.segments(nseg, "way")
    marks.segments(oseg, "way")
    boxes = np.vstack([_closed_boxes(new_refs, nlines), _closed_boxes(old_list, olines)])
    stats["changed ways"] = len(last_way)
    stats["deleted ways"] = sum(1 for v in last_way.values() if not v[2])
    secs["ways"] = time.time() - t

    # changed relations: member ways of the wanted kinds, a multipolygon's box
    t = time.time()
    rel_refs: list[list[int]] = []
    mp_spans: list[tuple[int, int]] = []  # a multipolygon's member ways: rel_refs[a:b]
    skipped = Counter()
    for rid, (visible, tags, members) in last_rel.items():
        typ = tags.get("type", "")
        if not visible:
            continue
        if not (typ in WANTED_REL or tags.get("route") == "ferry"):
            skipped[typ or "(none)"] += 1
            continue
        refs = []
        for mt, ref in members:
            if mt == "w":
                r = member_refs(ref) if member_refs else (last_way[ref][4] if ref in last_way and last_way[ref][2] else None)
                if r:
                    refs.append(r)
        if not refs:
            stats["wanted relations, no member geometry"] += 1
            continue
        if typ == "multipolygon":
            mp_spans.append((len(rel_refs), len(rel_refs) + len(refs)))
        rel_refs += refs
        stats["wanted relations"] += 1
    rseg, rlines = _lines(rel_refs, new_places)
    marks.segments(rseg, "relation")
    mp_boxes = []
    for a, b in mp_spans:
        g = np.vstack(rlines[a:b])
        g = g[np.isfinite(g).all(axis=1)]
        if len(g):
            mp_boxes.append((g[:, 0].min(), g[:, 1].min(), g[:, 0].max(), g[:, 1].max()))
    if mp_boxes:
        boxes = np.vstack([boxes, np.array(mp_boxes, float)])
    secs["relations"] = time.time() - t

    # closed ways' and multipolygons' boxes, capped
    t = time.time()
    if len(boxes) and box_clip is not None:  # (a test against tier2, which fills a box only inside its cities' boxes)
        cut = []
        for s, w, n, e in box_clip:
            c = np.column_stack([np.maximum(boxes[:, 0], s), np.maximum(boxes[:, 1], w),
                                 np.minimum(boxes[:, 2], n), np.minimum(boxes[:, 3], e)])
            cut.append(c[(c[:, 0] <= c[:, 2]) & (c[:, 1] <= c[:, 3])])
        boxes = np.vstack(cut)
    if len(boxes):
        boxes = np.unique(boxes, axis=0)  # a way's old and new ring are often the same
        area = box_km2(boxes)
        big = area > cap_km2
        stats["closed boxes"] = int(len(boxes))
        stats["closed boxes over the cap (outline only)"] = int(big.sum())
        if big.any():
            log(f"world tier 2: {int(big.sum())} closed-way boxes over {cap_km2} km2 marked by outline only, largest {area.max():.0f} km2")
        marks.boxes(boxes[~big], "box")
    secs["boxes"] = time.time() - t

    # the old position of every row of every changed key
    t = time.time()
    if old_rows is not None and len(old_rows):
        marks.points(old_rows["lat"] / 1e7, old_rows["lon"] / 1e7, "old row")
        stats["old rows"] = int(len(old_rows))
    secs["old rows"] = time.time() - t
    t = time.time()
    codes = marks.codes()
    secs["unique"] = time.time() - t
    stats["marked cells"] = int(len(codes))
    log(f"world tier 2 cover: {dict(stats)}; marks by kind {dict(marks.by_kind)}; relation types skipped "
        f"{dict(skipped.most_common(6))}; seconds {({k: round(v, 1) for k, v in secs.items()})}")
    return codes, stats, secs


# --- rectangles ----------------------------------------------------------------------------------

def plan_cells(plan: dict) -> list[dict]:
    """every cell of the plan with its file: id, file, rect (s, w, n, e), timeZone"""
    return [{"id": c["id"], "file": f["id"], "rect": tuple(c["rect"]), "timeZone": c["timeZone"]}
            for f in plan["files"] for c in f["cells"]]


def runs_of(codes: np.ndarray, pad: int = PAD) -> np.ndarray:
    """the marked cells padded by `pad` cells all round, as runs along each row: (n, 4) s, w, n, e in degrees"""
    if not len(codes):
        return np.zeros((0, 4))
    i, j = decode(codes)
    d = np.arange(-pad, pad + 1)
    pi = np.repeat(i[:, None] + d[None, :], len(d), axis=1).ravel()
    pj = np.tile(j[:, None] + d[None, :], (1, len(d))).ravel()
    ok = pj >= 0
    c = np.unique(((pi[ok] + I_OFF) << 32) | pj[ok])
    start = np.concatenate([[True], np.diff(c) != 1])
    s_idx = np.flatnonzero(start)
    e_idx = np.concatenate([s_idx[1:], [len(c)]]) - 1
    ri, rj0 = decode(c[s_idx])
    _, rj1 = decode(c[e_idx])
    dl = dlon_of(ri)
    return np.column_stack([ri * DLAT, rj0 * dl - 180.0, (ri + 1) * DLAT, (rj1 + 1) * dl - 180.0])


def split_by_cells(runs: np.ndarray, cells: list[dict]) -> dict[int, np.ndarray]:
    """each run clipped to every plan cell it overlaps: cell index -> (n, 4) s, w, n, e. Cells are binned by whole
    degrees; a run inside one bin is clipped to that bin's cells only."""
    if not len(runs):
        return {}
    rect = np.array([c["rect"] for c in cells], float)
    bins: dict[tuple[int, int], list[int]] = defaultdict(list)
    for k, (s, w, n, e) in enumerate(rect):
        for a in range(int(math.floor(s)), int(math.ceil(n))):
            for b in range(int(math.floor(w)), int(math.ceil(e))):
                bins[(a, b)].append(k)
    out: dict[int, list[np.ndarray]] = defaultdict(list)
    fa, fb = np.floor(runs[:, 0]).astype(int), np.floor(runs[:, 1]).astype(int)
    ga = np.floor(np.nextafter(runs[:, 2], -np.inf)).astype(int)
    gb = np.floor(np.nextafter(runs[:, 3], -np.inf)).astype(int)
    one = (fa == ga) & (fb == gb)

    def clip(sub: np.ndarray, ks):
        for k in ks:
            s, w, n, e = rect[k]
            c = np.column_stack([np.maximum(sub[:, 0], s), np.maximum(sub[:, 1], w),
                                 np.minimum(sub[:, 2], n), np.minimum(sub[:, 3], e)])
            keep = (c[:, 0] < c[:, 2]) & (c[:, 1] < c[:, 3])
            if keep.any():
                out[k].append(c[keep])

    idx = np.flatnonzero(one)
    if len(idx):
        key = fa[idx].astype(np.int64) * 1000 + fb[idx]
        order = np.argsort(key, kind="stable")
        idx, key = idx[order], key[order]
        for grp in np.split(idx, np.flatnonzero(np.diff(key)) + 1):
            ks = bins.get((int(fa[grp[0]]), int(fb[grp[0]])), [])
            if len(ks) == 1:
                out[ks[0]].append(runs[grp])  # the bin lies inside that one cell (the cells tile the globe)
            else:
                clip(runs[grp], ks)
    for r in np.flatnonzero(~one):
        s, w, n, e = runs[r]
        ks = np.flatnonzero((rect[:, 0] < n) & (rect[:, 2] > s) & (rect[:, 1] < e) & (rect[:, 3] > w))
        clip(runs[r:r + 1], ks)
    return {k: np.vstack(v) for k, v in out.items()}


def merge_in_cell(rs: np.ndarray, cell_rect, ring: float = RING) -> np.ndarray:
    """tier2.merge_rects in the cell's local metres, back to degrees, inside the cell"""
    s0, w0, n0, e0 = cell_rect
    mlon = M_LAT * math.cos(math.radians(min(abs((s0 + n0) / 2), MAX_COS_LAT)))
    m = np.column_stack([(rs[:, 0] - s0) * M_LAT, (rs[:, 1] - w0) * mlon, (rs[:, 2] - s0) * M_LAT, (rs[:, 3] - w0) * mlon])
    merged = np.array(merge_rects([tuple(r) for r in m.tolist()], ring), float).reshape(-1, 4)
    d = np.column_stack([s0 + merged[:, 0] / M_LAT, w0 + merged[:, 1] / mlon, s0 + merged[:, 2] / M_LAT, w0 + merged[:, 3] / mlon])
    d[:, 0] = np.maximum(d[:, 0], s0)
    d[:, 1] = np.maximum(d[:, 1], w0)
    d[:, 2] = np.minimum(d[:, 2], n0)
    d[:, 3] = np.minimum(d[:, 3], e0)
    return d[np.lexsort((d[:, 1], d[:, 0]))]


BLOCK_DEG = 0.5  # runs are merged within blocks of this many degrees: a planet cell of 71,228 runs took 283 s whole


def blocks_of(rs: np.ndarray, cell_rect, block: float = BLOCK_DEG) -> list[tuple[tuple, np.ndarray]]:
    """a cell's runs clipped to blocks of `block` degrees (inside the cell): [(block rect, runs)]"""
    s0, w0, n0, e0 = cell_rect
    bs0 = np.floor(rs[:, 0] / block).astype(np.int64)
    bs1 = np.floor(np.nextafter(rs[:, 2], -np.inf) / block).astype(np.int64)
    bw0 = np.floor(rs[:, 1] / block).astype(np.int64)
    bw1 = np.floor(np.nextafter(rs[:, 3], -np.inf) / block).astype(np.int64)
    nlat, nlon = bs1 - bs0 + 1, bw1 - bw0 + 1
    reps = nlat * nlon
    k = np.repeat(np.arange(len(rs)), reps)
    off = np.arange(int(reps.sum())) - np.repeat(np.concatenate([[0], np.cumsum(reps)[:-1]]), reps)
    bi = bs0[k] + off // nlon[k]
    bj = bw0[k] + off % nlon[k]
    lo_s, lo_w = np.maximum(bi * block, s0), np.maximum(bj * block, w0)
    hi_n, hi_e = np.minimum((bi + 1) * block, n0), np.minimum((bj + 1) * block, e0)
    c = np.column_stack([np.maximum(rs[k, 0], lo_s), np.maximum(rs[k, 1], lo_w), np.minimum(rs[k, 2], hi_n), np.minimum(rs[k, 3], hi_e)])
    keep = (c[:, 0] < c[:, 2]) & (c[:, 1] < c[:, 3])
    c, bi, bj = c[keep], bi[keep], bj[keep]
    lo_s, lo_w, hi_n, hi_e = lo_s[keep], lo_w[keep], hi_n[keep], hi_e[keep]
    key = (bi << 32) + (bj & 0xFFFFFFFF)
    order = np.argsort(key, kind="stable")
    out = []
    for g in np.split(order, np.flatnonzero(np.diff(key[order])) + 1):
        i = g[0]
        out.append(((lo_s[i], lo_w[i], hi_n[i], hi_e[i]), c[g]))
    return out


def _merge_job(args):
    k, rs, rect, ring = args
    t = time.time()
    return k, merge_in_cell(rs, rect, ring), time.time() - t


def rectangles(codes: np.ndarray, cells: list[dict], ring: float = RING, pad: int = PAD, log=None,
               workers: int | None = None) -> dict[int, np.ndarray]:
    """cell index -> its rectangles (s, w, n, e), merged; the cells merged in parallel processes (merge_rects is plain
    Python: one process took 718 s for a planet day's 1.85M runs), the largest first"""
    t = time.time()
    runs = runs_of(codes, pad)
    t1 = time.time()
    split = split_by_cells(runs, cells)
    t2 = time.time()
    jobs = [(k, brs, brect, ring) for k, rs in split.items() for brect, brs in blocks_of(rs, cells[k]["rect"])]
    jobs.sort(key=lambda j: -len(j[1]))
    workers = workers if workers is not None else max(1, min(len(jobs), (os.cpu_count() or 2) - 2))
    got: dict[int, list[np.ndarray]] = defaultdict(list)
    slow = (None, 0.0, 0)
    if workers > 1 and len(runs) > 20_000:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(workers) as ex:
            results = ex.map(_merge_job, jobs, chunksize=1)  # largest first, one at a time: chunks would bunch them
            for (k, r, s), j in zip(results, jobs):
                got[k].append(r)
                if s > slow[1]:
                    slow = (cells[k]["id"], s, len(j[1]))
    else:
        for j in jobs:
            k, r, s = _merge_job(j)
            got[k].append(r)
            if s > slow[1]:
                slow = (cells[k]["id"], s, len(j[1]))
    out = {}
    for k in sorted(got):
        d = np.vstack(got[k])
        out[k] = d[np.lexsort((d[:, 1], d[:, 0]))]
    if log:
        log(f"world tier 2 rectangles: {len(runs):,} runs ({t1 - t:.1f} s), split into {len(split)} cells ({t2 - t1:.1f} s), "
            f"{len(jobs):,} blocks merged to {sum(len(r) for r in out.values()):,} ({time.time() - t2:.1f} s, {workers} "
            f"processes; slowest block in {slow[0]}: {slow[2]:,} runs in {slow[1]:.1f} s)")
    return out


def rect_km2(rects: dict[int, np.ndarray]) -> float:
    return float(sum(box_km2(r).sum() for r in rects.values())) if rects else 0.0


# --- the engine's files --------------------------------------------------------------------------

def place_bboxes(places_json: Path, npz: Path) -> tuple[np.ndarray, np.ndarray]:
    """the name layer's places as (sorted ids, bbox w, s, e, n), cached as an npz"""
    if npz.exists() and npz.stat().st_mtime >= places_json.stat().st_mtime:
        z = np.load(npz)
        return z["ids"], z["bbox"]
    d = json.loads(places_json.read_text(encoding="utf-8"))["places"]
    ids = np.array([p["id"] for p in d])
    bbox = np.array([p.get("bbox") or (np.nan,) * 4 for p in d], float)
    order = np.argsort(ids)
    ids, bbox = ids[order], bbox[order]
    npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez(npz, ids=ids, bbox=bbox)
    return ids, bbox


class PartBoxes:
    """a part id's bbox (w, s, e, n): the name layer's places, plus the plan's osm-<city> parts"""

    def __init__(self, ids: np.ndarray, bbox: np.ndarray, city_parts: list[dict]):
        self.ids, self.bbox = ids, bbox
        self.extra = {c["id"]: tuple(c["bbox"]) for c in city_parts if c.get("bbox")}

    def of(self, pids: list[str]) -> np.ndarray:
        out = np.full((len(pids), 4), np.nan)
        arr = np.array(pids)
        if len(arr) and len(self.ids):
            i = np.minimum(np.searchsorted(self.ids, arr), len(self.ids) - 1)
            hit = self.ids[i] == arr
            out[hit] = self.bbox[i[hit]]
        for k, p in enumerate(pids):
            if p in self.extra:
                out[k] = self.extra[p]
        return out


def write_engine_files(rects: dict[int, np.ndarray], cells: list[dict], world: Path, work: Path, base: Path,
                       boxes: PartBoxes) -> tuple[Path, Path, dict]:
    """work/cities.json (every rectangle a city), work/cells/<id>.json (its boundary), work/parts/<id>.json (the
    cell's parts whose bbox meets it; a part with no known bbox is kept). Returns (cities file, parts dir, stats)."""
    cdir, pdir = work / "cells", work / "parts"
    for d in (cdir, pdir):
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*.json"):
            f.unlink()
    rid = 970_000_000
    eng = []
    st = Counter()
    for k, rs in rects.items():
        cell = cells[k]
        pf = world / "files" / cell["file"] / "parts" / f"{cell['id']}.json"
        entries = json.loads(pf.read_text(encoding="utf-8"))["parts"] if pf.exists() else []
        pb = boxes.of([e["id"] for e in entries]) if entries else np.zeros((0, 4))
        unknown = ~np.isfinite(pb).all(axis=1)
        st["part entries without a bbox (kept)"] += int(unknown.sum())
        for j, (s, w, n, e) in enumerate(rs.tolist()):
            cid = f"{cell['id']}-{j}"
            ring = [{"lat": s, "lon": w}, {"lat": s, "lon": e}, {"lat": n, "lon": e}, {"lat": n, "lon": w}, {"lat": s, "lon": w}]
            bpath = cdir / f"{cid}.json"
            bpath.write_text(json.dumps({"type": "relation", "id": rid, "bounds": {"minlat": s, "minlon": w, "maxlat": n, "maxlon": e},
                                         "members": [{"type": "way", "ref": rid, "role": "outer", "geometry": ring}],
                                         "tags": {"name": cid}}), encoding="utf-8")
            eng.append({"id": cid, "name": cid, "relation": rid, "adminLevel": 2, "countryCodes": None,
                        "timeZone": cell["timeZone"], "population": 1, "landAreaKm2": 1.0,
                        "boundary": Path(os.path.relpath(bpath, base)).as_posix(), "region": "tier2", "box": [s, w, n, e]})
            if entries:
                meet = unknown | ((pb[:, 0] <= e) & (pb[:, 2] >= w) & (pb[:, 1] <= n) & (pb[:, 3] >= s))
                ps = [entries[x] for x in np.flatnonzero(meet)]
                if ps:
                    (pdir / f"{cid}.json").write_text(json.dumps({"schema": 1, "city": cid, "parts": ps}), encoding="utf-8")
                    st["rectangles with parts"] += 1
                    st["part entries"] += len(ps)
            rid += 1
    cf = work / "cities.json"
    cf.write_text(json.dumps({"cities": eng}), encoding="utf-8")
    st["rectangles"] = len(eng)
    st["cells"] = len(rects)
    return cf, pdir, dict(st)


# --- the state's old rows ------------------------------------------------------------------------

ROWPOS = np.dtype([("key", "<i8"), ("lat", "<i4"), ("lon", "<i4")])


def old_rows(world: Path, keys: np.ndarray, dtype=None, name: str = "state.bin", workers: int = 4) -> np.ndarray:
    """every row of these keys in the world state's files (each sorted by key, with its state-keys.npy): key, lat,
    lon only. A file holding none of the keys is not read."""
    from concurrent.futures import ThreadPoolExecutor
    from world_state import REC, in_keys
    dtype = dtype or REC
    keys = np.unique(np.asarray(keys, np.int64))
    files = json.loads((world / "plan.json").read_text(encoding="utf-8"))["files"]

    def one(f):
        d = world / "files" / f["id"]
        kf = d / "state-keys.npy"
        hit = keys
        if kf.exists():
            fk = np.load(kf)
            if not len(fk):
                return None
            i = np.minimum(np.searchsorted(fk, keys), len(fk) - 1)
            hit = keys[fk[i] == keys]
            if not len(hit):
                return None
        r = np.fromfile(d / name, dtype=dtype)
        sel = r[in_keys(r["key"], hit)]
        out = np.zeros(len(sel), dtype=ROWPOS)
        for n in ROWPOS.names:
            out[n] = sel[n]
        return out

    with ThreadPoolExecutor(workers) as ex:
        parts = [p for p in ex.map(one, files) if p is not None]
    return np.concatenate(parts) if parts else np.zeros(0, dtype=ROWPOS)


def changed_keys(last_node, last_way, last_rel) -> np.ndarray:
    return np.unique(np.concatenate([np.fromiter(last_node, np.int64, len(last_node)) * 4,
                                     np.fromiter(last_way, np.int64, len(last_way)) * 4 + 1,
                                     np.fromiter(last_rel, np.int64, len(last_rel)) * 4 + 2]))


# --- one day, timed ------------------------------------------------------------------------------

def day(diff: Path, plan_path: Path, world: Path, nodes: Path, work: Path, base: Path, places_json: Path,
        old_refs=None, member_refs=None, cap_km2: float = CAP_KM2, log=print) -> dict:
    """the cover of one day and the engine's files for it, every stage timed (the node file is read only)"""
    import stream as S
    T = {}
    t = time.time()
    last_node, last_way, last_rel, _ = S.read_diff(diff)
    T["read diff"] = time.time() - t
    log(f"{diff.name}: {len(last_node):,} nodes, {len(last_way):,} ways, {len(last_rel):,} relations; {T['read diff']:.0f} s")
    t = time.time()
    old_places = NodeFile(nodes)
    new_places = NodeFile(nodes, overlay={n: (v[4] if v[2] else None) for n, v in last_node.items()})
    keys = changed_keys(last_node, last_way, last_rel)
    rows = old_rows(world, keys)
    T["old rows"] = time.time() - t
    log(f"old rows: {len(rows):,} of {len(keys):,} changed keys; {T['old rows']:.0f} s")
    codes, stats, secs = cover(last_node, last_way, last_rel, old_places, new_places, rows, old_refs, member_refs, cap_km2, log)
    T["cover"] = sum(secs.values())
    np.save(work / "codes.npy", codes)  # the marked cells: `rects` redoes the stages after the cover from them
    out = after_cover(codes, plan_path, world, work, base, places_json, T, log)
    out = {"diff": diff.name, "changedKeys": int(len(keys)), "oldRows": int(len(rows)), **{k: int(v) for k, v in stats.items()},
           **out, "coverSeconds": {k: round(v, 1) for k, v in secs.items()}}
    (work / "day.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def after_cover(codes, plan_path: Path, world: Path, work: Path, base: Path, places_json: Path, T: dict, log=print) -> dict:
    t = time.time()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    cells = plan_cells(plan)
    rects = rectangles(codes, cells, log=log)
    T["rectangles"] = time.time() - t
    t = time.time()
    ids, bbox = place_bboxes(places_json, work.parent / "place-bboxes.npz")
    boxes = PartBoxes(ids, bbox, plan.get("cityParts") or [])
    cf, pdir, wst = write_engine_files(rects, cells, world, work, base, boxes)
    T["engine files"] = time.time() - t
    n = sum(len(r) for r in rects.values())
    areas = np.concatenate([box_km2(r) for r in rects.values()]) if rects else np.zeros(0)
    np.save(work / "rects.npy", np.array([(k, *r) for k, rs in rects.items() for r in rs.tolist()], float).reshape(-1, 5))
    return {"markedCells": int(len(codes)), "rectangles": n, "cellsWithRectangles": len(rects),
            "rectKm2": round(float(areas.sum()), 1),
            "rectKm2Quantiles": [round(float(x), 3) for x in (np.quantile(areas, [0.5, 0.9, 0.99, 1.0]) if n else [])],
            "files": wst, "seconds": {k: round(v, 1) for k, v in T.items()}}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("time")
    a.add_argument("--diff", type=Path, required=True)
    a.add_argument("--plan", type=Path, required=True)
    a.add_argument("--world", type=Path, required=True)
    a.add_argument("--nodes", type=Path, required=True)
    a.add_argument("--work", type=Path, required=True)
    a.add_argument("--base", type=Path, default=Path.cwd())
    a.add_argument("--places", type=Path, default=Path(".scratch/world-places/world/places.json"))
    a.add_argument("--cap-km2", type=float, default=CAP_KM2)
    b = sub.add_parser("rects", help="the stages after the cover again, from a `time` run's work/codes.npy")
    b.add_argument("--plan", type=Path, required=True)
    b.add_argument("--world", type=Path, required=True)
    b.add_argument("--work", type=Path, required=True)
    b.add_argument("--base", type=Path, default=Path.cwd())
    b.add_argument("--places", type=Path, default=Path(".scratch/world-places/world/places.json"))
    o = ap.parse_args()
    o.work.mkdir(parents=True, exist_ok=True)
    if o.cmd == "time":
        r = day(o.diff, o.plan, o.world, o.nodes, o.work, o.base.resolve(), o.places, cap_km2=o.cap_km2)
    else:
        r = after_cover(np.load(o.work / "codes.npy"), o.plan, o.world, o.work, o.base.resolve(), o.places, {})
    print(json.dumps(r, indent=1))


if __name__ == "__main__":
    main()
