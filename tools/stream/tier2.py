"""Tier 2 of the stream inside `apply`: the ground a day's diff touched, recounted whole, spliced into the state.

DESIGN.md, "The stream, tier 2" (the method, measured on one day) and "The stream: its state" (this wiring). Per
day: the ground touched, as cells of CELL m in each city's flat grid (a changed node's old and new place; a
changed way's old and new segments, a closed one's box too; a way that holds a changed node, the segments next
to it and its quest points; a changed multipolygon's, street's or ferry route's member ways; the old position
of every row the state holds for any of these), merged into rectangles, each counted as a city with a ring of
RING m of map data around it. Inside a rectangle and its own city, every row of the state (every quest, tier 1
too: that reaches relations and ways whose nodes moved) is replaced by the recount's.

The map data comes from `map_data(day, rects)`: here the day's clip, read whole by the engine. A world needs a
store that answers "what lies in these boxes at this day" instead; what it was asked is logged per day.

The way store: every way's node refs in the seed clip (D/ways.npz, from `stream.py ways`), plus the diffs' ways
since (D/ways-overlay.pickle), for old geometry and for "which ways hold this node".
"""
import json
import math
import os
import pickle
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

M_LAT = 111_320.0
CELL, PAD, RING = 50.0, 1, 300.0
WANTED_REL = ("multipolygon", "associatedStreet", "street")


# --- the way store -------------------------------------------------------------------------------

def build_ways(clip: Path, d: Path, log):
    import osmium
    from array import array
    ids, lens, refs = array("q"), array("q"), array("q")
    for w in osmium.FileProcessor(str(clip), osmium.osm.WAY):
        r = [n.ref for n in w.nodes]
        ids.append(w.id)
        lens.append(len(r))
        refs.extend(r)
    ids, lens, refs = (np.frombuffer(a, np.int64) for a in (ids, lens, refs))
    assert (np.diff(ids) > 0).all(), "the clip's ways are not sorted by id"
    offs = np.zeros(len(ids) + 1, np.int64)
    offs[1:] = np.cumsum(lens)
    way_of_ref = np.repeat(np.arange(len(ids), dtype=np.int32), lens)
    order = np.argsort(refs, kind="stable")
    np.savez(d / "ways.npz", ids=ids, offs=offs, refs=refs, by_ref=refs[order], ref_way=way_of_ref[order])
    with open(d / "ways-overlay.pickle", "wb") as f:
        pickle.dump({}, f)
    log(f"ways of {clip.name}: {len(ids):,} ways, {len(refs):,} refs")


class WayStore:
    def __init__(self, d: Path):
        z = np.load(d / "ways.npz")
        self.ids, self.offs, self.refs, self.by_ref, self.ref_way = z["ids"], z["offs"], z["refs"], z["by_ref"], z["ref_way"]
        self.d = d
        with open(d / "ways-overlay.pickle", "rb") as f:
            self.over: dict[int, list | None] = pickle.load(f)

    def refs_of(self, wid: int):
        if wid in self.over:
            return self.over[wid]
        i = int(np.searchsorted(self.ids, wid))
        if i < len(self.ids) and self.ids[i] == wid:
            return self.refs[self.offs[i]:self.offs[i + 1]].tolist()
        return None

    def parents(self, nids) -> set[int]:
        """the ways that hold any of these nodes now"""
        nids = np.unique(np.asarray(list(nids), np.int64))
        out: set[int] = set()
        if len(nids):
            lo, hi = np.searchsorted(self.by_ref, nids, "left"), np.searchsorted(self.by_ref, nids, "right")
            cnt = hi - lo
            if cnt.sum():
                idx = np.repeat(lo - np.concatenate([[0], np.cumsum(cnt)[:-1]]), cnt) + np.arange(cnt.sum())
                out = {w for w in self.ids[self.ref_way[idx]].tolist() if w not in self.over}
            ns = set(nids.tolist())
            out |= {w for w, r in self.over.items() if r and not ns.isdisjoint(r)}
        return out

    def update(self, last_way):
        for wid, (_, _, visible, _, refs) in last_way.items():
            self.over[wid] = refs if visible else None

    def save(self):
        with open(self.d / "ways-overlay.pickle", "wb") as f:
            pickle.dump(self.over, f, protocol=pickle.HIGHEST_PROTOCOL)


# --- the cities and the cover --------------------------------------------------------------------

def city_infos(cities: Path):
    from shapely.geometry import Polygon
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from world_cells import boundary_rings
    base = cities.resolve().parents[2]
    out = []
    for c in json.loads(cities.read_text(encoding="utf-8"))["cities"]:
        bj = json.loads((base / c["boundary"]).read_text(encoding="utf-8"))
        b = bj["bounds"]
        geom = None
        for r in boundary_rings(bj):  # even-odd over the rings, as the engine tests a city
            p = Polygon(r).buffer(0)
            geom = p if geom is None else geom.symmetric_difference(p)
        out.append(dict(c, box=(b["minlat"], b["minlon"], b["maxlat"], b["maxlon"]), lat0=b["minlat"], lon0=b["minlon"],
                        mlon=M_LAT * math.cos(math.radians((b["minlat"] + b["maxlat"]) / 2)), geom=geom))
    return out


class Cover:
    """cells of one city's flat grid"""

    def __init__(self, city, cell=CELL):
        self.c, self.cell = city, cell
        s, w, n, e = city["box"]
        self.max_i = int((n - s) * M_LAT / cell) + 1
        self.max_j = int((e - w) * city["mlon"] / cell) + 1
        self.cells: dict[tuple[int, int], str] = {}
        self.by_element = Counter()

    def ij(self, p):
        return (int(math.floor((p[0] - self.c["lat0"]) * M_LAT / self.cell)),
                int(math.floor((p[1] - self.c["lon0"]) * self.c["mlon"] / self.cell)))

    def mark(self, i, j, kind, element):
        if 0 <= i <= self.max_i and 0 <= j <= self.max_j and (i, j) not in self.cells:
            self.cells[(i, j)] = kind
            self.by_element[element] += 1

    def point(self, p, kind, element):
        self.mark(*self.ij(p), kind, element)

    def segment(self, p, q, kind, element):
        d = math.hypot((q[0] - p[0]) * M_LAT, (q[1] - p[1]) * self.c["mlon"])
        steps = max(1, int(d / (self.cell / 2)) + 1)
        if steps > 100_000:  # a segment far longer than a city: its ends suffice
            steps = 1
        for k in range(steps + 1):
            t = k / steps
            self.point((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t), kind, element)

    def line(self, pts, kind, element):
        for p, q in zip(pts, pts[1:]):
            self.segment(p, q, kind, element)

    def bbox(self, pts, kind, element):
        i0, j0 = self.ij((min(p[0] for p in pts), min(p[1] for p in pts)))
        i1, j1 = self.ij((max(p[0] for p in pts), max(p[1] for p in pts)))
        for i in range(max(0, i0), min(self.max_i, i1) + 1):
            for j in range(max(0, j0), min(self.max_j, j1) + 1):
                self.mark(i, j, kind, element)

    def near(self, pts):
        s, w, n, e = self.c["box"]
        return any(s - 0.02 <= p[0] <= n + 0.02 and w - 0.03 <= p[1] <= e + 0.03 for p in pts)


def quest_points(pts):
    """half-length point and, for a closed line, the polygon centroid (SC takes one or the other)"""
    out = []
    lengths = [math.hypot(b[0] - a[0], (b[1] - a[1]) * 0.63) for a, b in zip(pts, pts[1:])]
    half, run = sum(lengths) / 2, 0.0
    for (a, b), dd in zip(zip(pts, pts[1:]), lengths):
        if run + dd >= half and dd > 0:
            t = (half - run) / dd
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            break
        run += dd
    if len(pts) >= 4 and pts[0] == pts[-1]:
        a2 = cx = cy = 0.0
        for (y0, x0), (y1, x1) in zip(pts, pts[1:]):
            f = x0 * y1 - x1 * y0
            a2 += f
            cx += (x0 + x1) * f
            cy += (y0 + y1) * f
        if a2:
            out.append((cy / (3 * a2), cx / (3 * a2)))
    return out


def merge_rects(rects, ring):
    """greedy: two rectangles become their bounding box when that box with its ring is no larger than the two
    with theirs. rects: (y0, x0, y1, x1) in metres"""
    def cost(r):
        return (r[2] - r[0] + 2 * ring) * (r[3] - r[1] + 2 * ring)

    bucket = max(4 * ring, 400.0)
    live = dict(enumerate(rects))
    index = defaultdict(set)

    def keys(r):
        for a in range(int((r[0] - ring) // bucket), int((r[2] + ring) // bucket) + 1):
            for b in range(int((r[1] - ring) // bucket), int((r[3] + ring) // bucket) + 1):
                yield a, b

    for k, r in live.items():
        for key in keys(r):
            index[key].add(k)
    work = list(live)
    nxt = len(rects)
    while work:
        k = work.pop()
        if k not in live:
            continue
        r = live[k]
        best = None
        for key in keys(r):
            for o in index[key]:
                if o == k:
                    continue
                q = live[o]
                u = (min(r[0], q[0]), min(r[1], q[1]), max(r[2], q[2]), max(r[3], q[3]))
                gain = cost(r) + cost(q) - cost(u)
                if gain >= 0 and (best is None or gain > best[0]):
                    best = (gain, o, u)
        if best:
            _, o, u = best
            for dead in (k, o):
                for key in keys(live[dead]):
                    index[key].discard(dead)
                del live[dead]
            live[nxt] = u
            for key in keys(u):
                index[key].add(nxt)
            work.append(nxt)
            nxt += 1
    return list(live.values())


def cover(infos, rows, last_node, last_way, last_rel, old_pos, locs, ways: WayStore, log):
    """the ground the day touched, per city; `ways` still holds yesterday's refs (updated here, after the old
    geometry is read). Returns the covers and the keys whose rows were marked."""
    covers = [Cover(c) for c in infos]
    boxes = np.array([c["box"] for c in infos])
    stats = Counter()

    def near_idx(lat, lon):
        return [k for k, (s, w, n, e) in enumerate(boxes) if s - 0.02 <= lat <= n + 0.02 and w - 0.03 <= lon <= e + 0.03]

    def old_loc(r):
        return old_pos[r] if r in old_pos else locs.get(r)

    # changed nodes, old and new place (vectorised pre-filter: near some city's box)
    nid = np.fromiter(last_node, np.int64, len(last_node))
    pts = np.array([[*(old_pos.get(n) or (np.nan, np.nan)), *(last_node[n][4] or (np.nan, np.nan))] for n in nid.tolist()]).reshape(-1, 4)
    near = np.zeros(len(nid), bool)
    for s, w, n, e in boxes:
        for la, lo in ((0, 1), (2, 3)):
            near |= (pts[:, la] >= s - 0.02) & (pts[:, la] <= n + 0.02) & (pts[:, lo] >= w - 0.03) & (pts[:, lo] <= e + 0.03)
    near_nodes = set(nid[near].tolist())
    for n in near_nodes:
        for p in (old_pos.get(n), last_node[n][4]):
            if p:
                for k in near_idx(*p):
                    covers[k].point(p, "node", ("node", n))
    stats["changed nodes near a city"] = len(near_nodes)

    # changed ways, old and new segments
    marked_ways = set()

    def roughly_near(p):  # within about 30 km of a city's box: a way reaching into a city from further is missed
        return p is not None and any(s - 0.3 <= p[0] <= n + 0.3 and w - 0.45 <= p[1] <= e + 0.45 for s, w, n, e in boxes)

    for wid, (_, _, visible, tags, refs) in last_way.items():
        old_refs = ways.refs_of(wid)
        if not ((refs and roughly_near(locs.get(refs[0]))) or (old_refs and roughly_near(old_loc(old_refs[0])))):
            continue
        geoms = []
        if visible and refs:
            geoms.append([p for p in (locs.get(r) for r in refs) if p])
        if old_refs:
            geoms.append([p for p in (old_loc(r) for r in old_refs) if p])
        hit = False
        for g in geoms:
            if not g:
                continue
            ks = set(near_idx(*g[0])) | set(near_idx(*g[-1])) | set(near_idx(*g[len(g) // 2]))
            for k in ks:
                hit = True
                covers[k].line(g, "way", ("way", wid))
                if len(g) >= 4 and g[0] == g[-1]:
                    covers[k].bbox(g, "way", ("way", wid))
        if hit:
            marked_ways.add(wid)
    stats["changed ways near a city"] = len(marked_ways)

    # ways that hold a changed node (not in the diff): the segments next to it, old and new, and quest points
    parents = ways.parents(near_nodes) - set(last_way)
    for wid in parents:
        refs = ways.refs_of(wid)
        if not refs:
            continue
        new_g = [locs.get(r) for r in refs]
        old_g = [old_loc(r) for r in refs]
        ks = set()
        for g in (new_g, old_g):
            for p in g:
                if p:
                    ks |= set(near_idx(*p))
                    break
        for k in ks:
            cov = covers[k]
            for g in (new_g, old_g):
                for i, r in enumerate(refs):
                    if r in near_nodes and g[i]:
                        for j in (i - 1, i + 1):
                            if 0 <= j < len(refs) and g[j]:
                                cov.segment(g[i], g[j], "parent", ("way", wid))
                for p in quest_points([p for p in g if p]):
                    cov.point(p, "parent", ("way", wid))
    stats["ways holding a changed node"] = len(parents)

    ways.update(last_way)

    # changed relations: a multipolygon's, a street's or a ferry route's member ways (new), a multipolygon's box
    rel_marked, skipped = set(), Counter()
    for rid, (visible, tags, members) in last_rel.items():
        typ = tags.get("type", "")
        if not visible:
            continue
        if not (typ in WANTED_REL or tags.get("route") == "ferry"):
            skipped[typ or "(none)"] += 1
            continue
        mgeo = []
        for t, ref in members:
            if t == "w":
                r = ways.refs_of(ref)
                if r:
                    g = [p for p in (locs.get(x) for x in r) if p]
                    if len(g) >= 2:
                        mgeo.append(g)
        allp = [p for g in mgeo for p in g]
        if not allp:
            continue
        ks = {k for g in mgeo for k in set(near_idx(*g[0])) | set(near_idx(*g[-1]))}
        for k in ks:
            rel_marked.add(rid)
            for g in mgeo:
                covers[k].line(g, "relation", ("relation", rid))
            if typ == "multipolygon":
                covers[k].bbox(allp, "relation", ("relation", rid))
    stats["changed relations near a city"] = len(rel_marked)

    # the old position of every row of these elements
    keys = np.unique(np.concatenate([np.array(sorted(near_nodes), np.int64) * 4,
                                     np.array(sorted(marked_ways | parents), np.int64) * 4 + 1,
                                     np.array(sorted(rel_marked | set(last_rel)), np.int64) * 4 + 2]))
    sel = rows[np.isin(rows["key"], keys)]
    seen = set()
    for la, lo, k in zip((sel["lat"] * 1e-7).tolist(), (sel["lon"] * 1e-7).tolist(), sel["key"].tolist()):
        if (la, lo) in seen:
            continue
        seen.add((la, lo))
        for c in near_idx(la, lo):
            covers[c].point((la, lo), "old row", (("node", "way", "relation")[k & 3], k >> 2))
    stats["old row positions"] = len(seen)
    log(f"tier 2 cover: {dict(stats)}; relation types skipped {dict(skipped.most_common(6))}")
    return covers, stats


def rectangles(covers, ring=RING, pad=PAD):
    """per city: the touched cells padded, as row runs, merged; (s, w, n, e) in degrees"""
    out = []
    for cov in covers:
        c, cell = cov.c, cov.cell
        core = set()
        for (i, j) in cov.cells:
            for di in range(-pad, pad + 1):
                for dj in range(-pad, pad + 1):
                    core.add((i + di, j + dj))
        by_row = defaultdict(list)
        for i, j in core:
            by_row[i].append(j)
        runs = []
        for i, js in by_row.items():
            js.sort()
            start = prev = js[0]
            for j in js[1:] + [None]:
                if j is None or j != prev + 1:
                    runs.append((i * cell, start * cell, (i + 1) * cell, (prev + 1) * cell))
                    start = j
                prev = j
        rects = [(c["lat0"] + r[0] / M_LAT, c["lon0"] + r[1] / c["mlon"], c["lat0"] + r[2] / M_LAT, c["lon0"] + r[3] / c["mlon"])
                 for r in merge_rects(runs, ring)]
        out.append(sorted(rects))
    return out


def write_cities(infos, rects, work: Path, base: Path) -> Path:
    """each rectangle as a city of the unchanged engine: its own city's country codes and time zone"""
    cells = work / "cells"
    cells.mkdir(parents=True, exist_ok=True)
    for f in cells.glob("*.json"):
        f.unlink()
    rid = 970_000_000
    eng = []
    for c, rs in zip(infos, rects):
        for k, (s, w, n, e) in enumerate(rs):
            cid = f"{c['id']}-{k}"
            ring = [{"lat": s, "lon": w}, {"lat": s, "lon": e}, {"lat": n, "lon": e}, {"lat": n, "lon": w}, {"lat": s, "lon": w}]
            bpath = cells / f"{cid}.json"
            bpath.write_text(json.dumps({"type": "relation", "id": rid, "bounds": {"minlat": s, "minlon": w, "maxlat": n, "maxlon": e},
                                         "members": [{"type": "way", "ref": rid, "role": "outer", "geometry": ring}],
                                         "tags": {"name": cid}}), encoding="utf-8")
            eng.append({"id": cid, "name": cid, "relation": rid, "adminLevel": 2, "countryCodes": c["countryCodes"],
                        "timeZone": c["timeZone"], "population": 1, "landAreaKm2": 1.0,
                        "boundary": Path(os.path.relpath(bpath, base)).as_posix(), "region": "tier2"})
            rid += 1
    f = work / "cities.json"
    f.write_text(json.dumps({"cities": eng}, indent=1), encoding="utf-8")
    return f


def regions(infos, rects):
    """per city: its own outline cut to its rectangles (shapely), or None"""
    from shapely.geometry import box
    from shapely.ops import unary_union
    out = []
    for c, rs in zip(infos, rects):
        out.append(c["geom"].intersection(unary_union([box(w, s, e, n) for s, w, n, e in rs])) if rs else None)
    return out


def inside(rows, regs) -> np.ndarray:
    import shapely
    mask = np.zeros(len(rows), bool)
    lat, lon = rows["lat"] * 1e-7, rows["lon"] * 1e-7
    for g in regs:
        if g is None or g.is_empty:
            continue
        x0, y0, x1, y1 = g.bounds
        cand = np.flatnonzero((lon >= x0) & (lon <= x1) & (lat >= y0) & (lat <= y1) & ~mask)
        if len(cand):
            shapely.prepare(g)
            mask[cand[shapely.contains_xy(g, lon[cand], lat[cand])]] = True
    return mask


def map_data(day_clip: Path, rects) -> Path:
    """the map data of the rectangles (with their ring) at the day: here the day's clip, read whole"""
    return day_clip


def engine_area_log(log_path: Path) -> dict:
    nodes = ways = runs = 0
    secs = 0.0
    text = log_path.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"^area: \S+\s+([\d.]+) s\s+\(map data [\d.]+ s: (\d+) nodes, (\d+) ways", text, re.M):
        secs += float(m[1]); nodes += int(m[2]); ways += int(m[3]); runs += 1
    p = re.search(r"pass ([\d.]+) s, total ([\d.]+) s", text)
    return {"areaRuns": runs, "areaSeconds": round(secs, 1), "nodesRead": nodes, "waysRead": ways,
            "pass": float(p[1]) if p else None}
