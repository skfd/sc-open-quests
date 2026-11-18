"""What the world cover needs from the store around a day's changes (`tilestore context`; DESIGN.md, "What tier 2 must
recount, from the code"): the four gaps of the big-polygon rule closed from the store, not from indexes of our own.

A day asks the store three times, in the order the store allows (a generation's way and relation pairs go at the next
`update --prune-pairs`, its tile index at `compact`):

  before = DayContext.before(exe, store, gen_d1, last_node, last_way, last_rel, old_places, work)
      at D-1, BEFORE the day's update: every changed way's old refs, places and tags, the refs carrying an address,
      the relations holding it; every changed relation's old tags and members; every changed node that existed the
      day before: its old tags and the closed ways it was a vertex of; then the old places of the nodes a container
      reads (by old or new tags): the closed ways and multipolygons holding them
  after = before.after(exe, store, gen_d, new_places, work)
      at D, after the update (before `compact`): the same for the new state, and the changed relations' member ways
  hooks = after.hooks()   # keyword arguments for world_tier2.cover

The hooks: old_refs, old_tags, member_refs, address_nodes (every ref with an address among the changed ways' old and
new rings, and the changed nodes' own), old_node_tags, extra_candidates (container boxes: relations holding a changed
way, the containers of a changed contained node, the areas a changed address node is a vertex of).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

NO = -(2 ** 31)
ADDR_PREFIX = "addr:"


def _tags(blob: bytes) -> dict:
    if not blob:
        return {}
    p = blob.decode("utf-8", "replace").split("\0")
    return dict(zip(p[0::2], p[1::2]))


def _unpack_tags(d: Path, prefix: str) -> list[dict]:
    offs = np.load(d / f"{prefix}_toffs.npy")
    b = (d / f"{prefix}_tags.bin").read_bytes()
    return [_tags(b[offs[i]:offs[i + 1]]) for i in range(len(offs) - 1)]


def _line(lat7, lon7) -> np.ndarray:
    """(k, 2) degrees, a place the payload lacked as NaN"""
    g = np.column_stack([lat7, lon7]).astype(float)
    g[(lat7 == NO) | (lon7 == NO)] = np.nan
    return g / 1e7


def _geo(d: Path, prefix: str) -> dict[int, dict]:
    """a context output's ways with geometry (prefix v: vertex ways, x: crossing ways): id -> {line, tags}"""
    if not (d / f"{prefix}_ids.npy").exists():
        return {}
    ids, offs = np.load(d / f"{prefix}_ids.npy"), np.load(d / f"{prefix}_offs.npy")
    lat, lon = np.load(d / f"{prefix}_lat7.npy"), np.load(d / f"{prefix}_lon7.npy")
    tags = _unpack_tags(d, prefix)
    return {w: {"line": _line(lat[offs[i]:offs[i + 1]], lon[offs[i]:offs[i + 1]]), "tags": tags[i]}
            for i, w in enumerate(ids.tolist())}


def _segments_e7(lines) -> np.ndarray:
    """consecutive placed points of each line as '<i8' lat7, lon7, lat7, lon7 rows (for --crossing)"""
    out = []
    for g in lines:
        g = g[np.isfinite(g).all(axis=1)]
        if len(g) >= 2:
            out.append(np.hstack([g[:-1], g[1:]]))
    if not out:
        return np.zeros((0, 4), np.int64)
    return np.round(np.vstack(out) * 1e7).astype(np.int64)


def _cross_points(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """the points where line a's segments cross line b's (degrees, (k, 2); NaN places dropped), touching included"""
    a, b = a[np.isfinite(a).all(axis=1)], b[np.isfinite(b).all(axis=1)]
    if len(a) < 2 or len(b) < 2:
        return np.zeros((0, 2))
    p, r = a[:-1][:, None, :], (a[1:] - a[:-1])[:, None, :]
    q, s_ = b[:-1][None, :, :], (b[1:] - b[:-1])[None, :, :]
    rxs = r[..., 0] * s_[..., 1] - r[..., 1] * s_[..., 0]
    qp = q - p
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (qp[..., 0] * s_[..., 1] - qp[..., 1] * s_[..., 0]) / rxs
        u = (qp[..., 0] * r[..., 1] - qp[..., 1] * r[..., 0]) / rxs
    # parallel segments (rxs 0) are left out: a road along a bridge's own segment is not a road under it
    hit = (rxs != 0) & (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1)
    i, j = np.nonzero(hit)
    return (p[i, 0] + t[i, j][:, None] * r[i, 0]).reshape(-1, 2)


def _quest_points(g: np.ndarray) -> np.ndarray:
    """a line's half-length point and, closed, its centroid (world_tier2._quest_points for one line)"""
    import world_tier2 as W
    return W._quest_points([g])


BOX_PAD = 1e-7  # degrees: a crossing found by _cross_points lies on both segments, so on both lines' boxes


def line_boxes(lines: list[np.ndarray]) -> np.ndarray:
    """(n, 4) min lat, min lon, max lat, max lon of each line's known places; NaN for a line with fewer than two"""
    out = np.full((len(lines), 4), np.nan)
    for i, g in enumerate(lines):
        g = g[np.isfinite(g).all(axis=1)]
        if len(g) >= 2:
            out[i] = (g[:, 0].min(), g[:, 1].min(), g[:, 0].max(), g[:, 1].max())
    return out


def crossing_box(road: np.ndarray, others: list[np.ndarray], boxes: np.ndarray | None = None) -> tuple | None:
    """the box of a road's quest point(s) and every point where it crosses one of `others`: one rectangle city holding
    both, so its area pass's map data (ways with a node in its padded box) holds the crossing bridge (AddMaxHeight).
    `boxes` (line_boxes(others)) leaves out the others whose box does not meet the road's: the same answer, without
    testing every road against every bridge (a planet day has about 10^5 changed roads and 10^4 bridges)"""
    if boxes is not None and len(others):
        rb = line_boxes([road])[0]
        if not np.isfinite(rb).all():
            return None
        with np.errstate(invalid="ignore"):
            near = ((boxes[:, 0] <= rb[2] + BOX_PAD) & (boxes[:, 2] >= rb[0] - BOX_PAD) &
                    (boxes[:, 1] <= rb[3] + BOX_PAD) & (boxes[:, 3] >= rb[1] - BOX_PAD))
        others = [others[i] for i in np.flatnonzero(near)]
    pts = [x for o in others for x in _cross_points(road, o)]
    if not pts:
        return None
    pts = np.vstack([np.array(pts), _quest_points(road)])
    pts = pts[np.isfinite(pts).all(axis=1)]
    return (pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()) if len(pts) else None


BRIDGE_KEYS = ("bridge", "building", "man_made")
ROAD_UNDER = "road under a bridge (AddMaxHeight)"


def _box_deg(b) -> tuple | None:
    if b[0] == NO:
        return None
    return (b[0] / 1e7, b[1] / 1e7, b[2] / 1e7, b[3] / 1e7)


class Context:
    """one `tilestore context` output directory, read into dicts"""

    def __init__(self, d: Path):
        self.d = Path(d)
        self.stats = json.loads((self.d / "context.json").read_text()) if (self.d / "context.json").exists() else {}
        self.ways: dict[int, dict] = {}
        self.rels: dict[int, dict] = {}
        self.nodes: dict[int, dict] = {}
        self.points: list[list[tuple[int, int]]] = []
        self.elements: dict[tuple[int, int], dict] = {}
        d = self.d
        if (d / "w_ids.npy").exists():
            ids, how = np.load(d / "w_ids.npy"), np.load(d / "w_how.npy")
            offs, refs = np.load(d / "w_offs.npy"), np.load(d / "w_refs.npy")
            lat, lon = np.load(d / "w_lat7.npy"), np.load(d / "w_lon7.npy")
            ao, an = np.load(d / "w_aoffs.npy"), np.load(d / "w_anodes.npy")
            ho, hr = np.load(d / "w_hoffs.npy"), np.load(d / "w_hrels.npy")
            tags = _unpack_tags(d, "w")
            for i, w in enumerate(ids.tolist()):
                if how[i] == 0:
                    continue
                a, b = offs[i], offs[i + 1]
                self.ways[w] = {"refs": refs[a:b].tolist(), "lat7": lat[a:b], "lon7": lon[a:b], "tags": tags[i],
                                "addr": an[ao[i]:ao[i + 1]].tolist(),
                                # holding relations are known only from a tile (how 1), not from the relation store
                                "held_by": hr[ho[i]:ho[i + 1]].tolist() if how[i] == 1 else None}
        if (d / "r_ids.npy").exists():
            ids, found = np.load(d / "r_ids.npy"), np.load(d / "r_found.npy")
            mo, mt, mr = np.load(d / "r_moffs.npy"), np.load(d / "r_mtype.npy"), np.load(d / "r_mref.npy")
            box = np.load(d / "r_box.npy").reshape(-1, 4)
            tags = _unpack_tags(d, "r")
            for i, r in enumerate(ids.tolist()):
                if found[i]:
                    self.rels[r] = {"tags": tags[i],
                                    "members": [("nwr"[t], x) for t, x in zip(mt[mo[i]:mo[i + 1]].tolist(),
                                                                              mr[mo[i]:mo[i + 1]].tolist())],
                                    "box": _box_deg(box[i])}
        if (d / "n_ids.npy").exists():
            ids, found = np.load(d / "n_ids.npy"), np.load(d / "n_found.npy")
            vo, vw = np.load(d / "n_voffs.npy"), np.load(d / "n_vways.npy")
            tags = _unpack_tags(d, "n")
            for i, n in enumerate(ids.tolist()):
                # tags None: the store does not hold the node where it was said to be (outside a clip's polygon)
                self.nodes[n] = {"tags": tags[i] if found[i] == 1 else ({} if found[i] == 2 else None),
                                 "vertex_of": vw[vo[i]:vo[i + 1]].tolist()}
        if (d / "p_offs.npy").exists():
            po, pk, pid = np.load(d / "p_offs.npy"), np.load(d / "p_kind.npy"), np.load(d / "p_id.npy")
            self.points = [list(zip(pk[po[i]:po[i + 1]].tolist(), pid[po[i]:po[i + 1]].tolist())) for i in range(len(po) - 1)]
        if (d / "e_id.npy").exists():
            ek, ei, eb = np.load(d / "e_kind.npy"), np.load(d / "e_id.npy"), np.load(d / "e_box.npy").reshape(-1, 4)
            tags = _unpack_tags(d, "e")
            for k, x, b, tg in zip(ek.tolist(), ei.tolist(), eb, tags):
                self.elements[(k, x)] = {"box": _box_deg(b), "tags": tg}
        # --rel-geometry: each relation's member ways; --vertex-ways and --crossing: ways with their geometry
        self.rel_lines: dict[int, list[np.ndarray]] = {}
        if (d / "r_woffs.npy").exists():
            wo, po = np.load(d / "r_woffs.npy"), np.load(d / "rw_poffs.npy")
            lat, lon = np.load(d / "rw_lat7.npy"), np.load(d / "rw_lon7.npy")
            rids = np.load(d / "r_ids.npy")
            for i, r in enumerate(rids.tolist()):
                self.rel_lines[r] = [_line(lat[po[k]:po[k + 1]], lon[po[k]:po[k + 1]]) for k in range(wo[i], wo[i + 1])]
        self.vertex_ways = _geo(d, "v")
        self.crossing = _geo(d, "x")


def run_context(exe: Path, store: Path, gen: int, out: Path, ways=None, rels=None, nodes=None, node_places=None,
                points=None, around: int = 1, log=print, rel_geometry: bool = False, vertex_ways: bool = False,
                crossing: np.ndarray | None = None, crossing_keys=("highway",)) -> Context:
    """`tilestore context` with these inputs (id lists; node_places and points as (lat, lon) degree arrays; crossing
    as '<i8' lat7, lon7, lat7, lon7 rows)"""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    args = [str(exe), "context", "--store", str(store), "--gen", str(gen), "--out", str(out), "--around", str(around)]
    if rel_geometry:
        args.append("--rel-geometry")
    if vertex_ways:
        args.append("--vertex-ways")

    def put(name, arr):
        p = out / f"in-{name}.npy"
        np.save(p, np.ascontiguousarray(arr, dtype="<i8"))
        return str(p)

    if ways is not None and len(ways):
        args += ["--ways", put("ways", np.asarray(sorted(set(ways)), np.int64))]
    if rels is not None and len(rels):
        args += ["--rels", put("rels", np.asarray(sorted(set(rels)), np.int64))]
    if nodes is not None and len(nodes):
        pl = np.asarray(node_places, float).reshape(-1, 2)
        e7 = np.where(np.isfinite(pl), np.round(pl * 1e7), NO).astype(np.int64)
        args += ["--nodes", put("nodes", np.asarray(nodes, np.int64)), "--node-places", put("node_places", e7.reshape(-1))]
    if points is not None and len(points):
        pt = np.asarray(points, float).reshape(-1, 2)
        pt = pt[np.isfinite(pt).all(axis=1)]
        args += ["--points", put("points", np.round(pt * 1e7).astype(np.int64).reshape(-1))]
    if crossing is not None and len(crossing):
        args += ["--crossing", put("crossing", np.asarray(crossing, np.int64).reshape(-1))]
        for k in crossing_keys:
            args += ["--crossing-key", k]
    r = subprocess.run(args, capture_output=True, text=True)
    (out / "context.log").write_text(r.stderr or "", encoding="utf-8")
    if r.returncode:
        raise RuntimeError(f"tilestore context failed ({r.returncode}): see {out / 'context.log'}")
    c = Context(out)
    log(f"store context at generation {gen}: {c.stats}")
    return c


class DayContext:
    """the store's answers for one day: `before` at D-1 and `after` at D"""

    def __init__(self, last_node, last_way, last_rel, contained_kind, wanted_relation):
        self.last_node, self.last_way, self.last_rel = last_node, last_way, last_rel
        self.contained_kind, self.wanted_relation = contained_kind, wanted_relation
        self.b: Context | None = None
        self.bp: Context | None = None
        self.a: Context | None = None
        self.contained: list[int] = []
        # fork P3: what the diff does not show but whose quests move: the relations holding a changed way, the roads
        # crossing a changed bridge, the untouched ways of a moved node (bx at D-1, ax at D)
        self.bx: Context | None = None
        self.ax: Context | None = None
        self.bxb: Context | None = None  # the bridges crossing the changed roads, at D-1 and at D
        self.axb: Context | None = None
        self.bridges: dict[str, list[np.ndarray]] = {}  # the changed bridges' lines, "b" at D-1 and "a" at D
        self.roads: dict[str, dict[int, np.ndarray]] = {}  # the changed roads' lines
        self.moved: np.ndarray = np.zeros(0, np.int64)
        self.held: set[int] = set()
        self.over_road = None

    def _over_lines(self, c: Context) -> list[np.ndarray]:
        """the changed ways that can pass over a road, as the store holds them in context c (old or new tags)"""
        out = []
        for w, v in self.last_way.items():
            cw = c.ways.get(w) if c else None
            if cw and (self.over_road(cw["tags"]) or (v[2] and self.over_road(v[3]))):
                out.append(_line(cw["lat7"], cw["lon7"]))
        return out

    def _road_lines(self, c: Context) -> dict[int, np.ndarray]:
        """the changed highways (old or new tags), as the store holds them in context c"""
        out = {}
        for w, v in self.last_way.items():
            cw = c.ways.get(w) if c else None
            if cw and ("highway" in cw["tags"] or (v[2] and "highway" in v[3])):
                out[w] = _line(cw["lat7"], cw["lon7"])
        return out

    def _crossings(self, exe, store, gen, work: Path, when: str, c: Context, log):
        """the roads crossing the changed bridges and the bridges crossing the changed roads, in context c's
        generation: (roads ctx with --vertex-ways and moved nodes is the caller's; this asks the bridge side)"""
        self.bridges[when] = self._over_lines(c)
        self.roads[when] = self._road_lines(c)
        segs = _segments_e7(list(self.roads[when].values()))
        return run_context(exe, store, gen, Path(work) / f"{'before' if when == 'b' else 'after'}-xb", crossing=segs,
                           crossing_keys=BRIDGE_KEYS, log=log) if len(segs) else None

    def held_by(self, c: Context | None) -> set[int]:
        return {r for w in self.last_way for r in ((c.ways.get(w) or {}).get("held_by") or [])} if c else set()

    @classmethod
    def before(cls, exe, store, gen, last_node, last_way, last_rel, old_places, work: Path, contained_kind,
               wanted_relation, log=print, over_road=None) -> "DayContext":
        dc = cls(last_node, last_way, last_rel, contained_kind, wanted_relation)
        dc.over_road = over_road
        # nodes that existed the day before: every changed node but a new one (version 1)
        old_n = np.array([n for n, v in last_node.items() if v[0] > 1], np.int64)
        op = old_places.places(old_n) if len(old_n) else np.zeros((0, 2))
        dc.b = run_context(exe, store, gen, Path(work) / "before", ways=list(last_way), rels=list(last_rel),
                           nodes=old_n, node_places=op, log=log)
        if over_road is not None:
            # the nodes that moved (alive at D, at another place than at D-1): the untouched ways they are a vertex of
            # move their quest points; and the roads the changed bridges crossed at D-1
            alive = np.array([bool(last_node[n][2]) for n in old_n.tolist()], bool) if len(old_n) else np.zeros(0, bool)
            newp = np.array([last_node[n][4] if last_node[n][2] else (np.nan, np.nan) for n in old_n.tolist()],
                            float).reshape(-1, 2)
            moved = alive & np.isfinite(op).all(axis=1) & (np.abs(newp - op) > 1e-9).any(axis=1)
            dc.moved = old_n[moved]
            dc.bxb = dc._crossings(exe, store, gen, work, "b", dc.b, log)
            dc.bx = run_context(exe, store, gen, Path(work) / "before-x", nodes=dc.moved, node_places=op[moved],
                                vertex_ways=True, crossing=_segments_e7(dc.bridges["b"]), log=log)
        # the nodes a container reads, by their new or their old tags; their old places: what held them
        dc.contained = [n for n, v in last_node.items()
                        if (v[2] and contained_kind(v[3])) or contained_kind(dc.b.nodes.get(n, {}).get("tags"))]
        if dc.contained:
            c = np.array(dc.contained, np.int64)
            dc.bp = run_context(exe, store, gen, Path(work) / "before-points", points=old_places.places(c), log=log)
            dc.bp_ids = c[np.isfinite(old_places.places(c)).all(axis=1)]
        return dc

    def after(self, exe, store, gen, new_places, work: Path, log=print) -> "DayContext":
        # the changed relations' member ways (at D), as their geometry for the cover
        members = [ref for rid, (vis, tags, mem) in self.last_rel.items() if vis and self.wanted_relation(tags)
                   for t, ref in mem if t == "w"]
        addr_nodes = [n for n, v in self.last_node.items() if v[2] and v[3] and any(k.startswith(ADDR_PREFIX) for k in v[3])]
        pts_ids = np.array(self.contained, np.int64)
        pts = new_places.places(pts_ids) if len(pts_ids) else np.zeros((0, 2))
        an = np.array(addr_nodes, np.int64)
        self.a = run_context(exe, store, gen, Path(work) / "after",
                             ways=list(self.last_way) + members, rels=list(self.last_rel),
                             nodes=an, node_places=new_places.places(an) if len(an) else np.zeros((0, 2)),
                             points=pts, log=log)
        self.a_pts_ids = pts_ids[np.isfinite(pts).all(axis=1)] if len(pts_ids) else pts_ids
        if self.over_road is not None:
            # the relations holding a changed way (at D-1 or D) with their member ways at D; the moved nodes' ways at
            # D; the roads the changed bridges cross at D
            self.held = self.held_by(self.b) | self.held_by(self.a)
            mp = new_places.places(self.moved) if len(self.moved) else np.zeros((0, 2))
            self.axb = self._crossings(exe, store, gen, work, "a", self.a, log)
            self.ax = run_context(exe, store, gen, Path(work) / "after-x", rels=sorted(self.held), rel_geometry=True,
                                  nodes=self.moved, node_places=mp, vertex_ways=True,
                                  crossing=_segments_e7(self.bridges["a"]), log=log)
        return self

    def extra_lines(self) -> list[tuple[str, np.ndarray]]:
        """lines the diff does not show whose quests move (world_tier2.cover's extra_lines)"""
        out = []
        if self.ax:
            for r, lines in self.ax.rel_lines.items():
                out += [("relation holding a changed way", g) for g in lines]
        for c in (self.bx, self.ax):
            if c:
                out += [("road crossing a changed bridge", v["line"]) for v in c.crossing.values()]
                out += [("way of a moved node", v["line"]) for w, v in c.vertex_ways.items() if w not in self.last_way]
        return out

    def crossing_candidates(self) -> list[tuple]:
        """a box from each road's quest point to where it crosses a bridge, when the road or the bridge changed, at
        D-1 and at D: one rectangle city then holds the road's quest and the bridge (its area pass's map data holds the
        ways with a node in its padded box, so a bridge crossing far from the road's centre is otherwise not seen)"""
        out = []
        for when, cx, cxb in (("b", self.bx, self.bxb), ("a", self.ax, self.axb)):
            if cx:  # roads crossing a changed bridge
                changed = self.bridges.get(when, [])
                cboxes = line_boxes(changed)
                for w, v in cx.crossing.items():
                    b = crossing_box(v["line"], changed, cboxes)
                    if b is not None:
                        out.append((b, "way", ROAD_UNDER, True, ("way", w)))
            if cxb:  # bridges crossing a changed road
                bridges = [v["line"] for v in cxb.crossing.values() if self.over_road(v["tags"])]
                if bridges:
                    bboxes = line_boxes(bridges)
                    for w, g in self.roads.get(when, {}).items():
                        b = crossing_box(g, bridges, bboxes)
                        if b is not None:
                            out.append((b, "way", ROAD_UNDER, True, ("way", w)))
        return out

    def held_candidates(self, container_kind) -> list[tuple]:
        """every relation holding a changed way as a box candidate, its tags at D: a container is boxed whole (as
        extra_candidates), any other by the box rule (small: whole; else its member lines, from extra_lines)"""
        out = []
        if self.ax:
            for r in sorted(self.held):
                info = self.ax.rels.get(r)
                if info and info["box"] is not None and container_kind(info["tags"], relation=True) is None:
                    out.append((info["box"], "relation", None, True, ("relation", r)))
        return out

    # --- hooks for world_tier2.cover ---

    def old_refs(self, wid):
        w = self.b.ways.get(wid) if self.b else None
        return w["refs"] if w else None

    def member_refs(self, wid):
        w = self.a.ways.get(wid) if self.a else None
        if w:
            return w["refs"]
        v = self.last_way.get(wid)
        return v[4] if v and v[2] else None

    def old_tags(self, kind, i):
        if self.b is None:
            return None
        if kind == "w":
            w = self.b.ways.get(i)
            return w["tags"] if w else None
        r = self.b.rels.get(i)
        return r["tags"] if r else None

    def old_node_tags(self, nid):
        if self.b is None or nid not in self.b.nodes:
            return None
        return self.b.nodes[nid]["tags"]

    def address_nodes(self) -> np.ndarray:
        s = set()
        for c in (self.b, self.a):
            if c:
                for w in c.ways.values():
                    s.update(w["addr"])
        s.update(n for n, v in self.last_node.items() if v[2] and v[3] and any(k.startswith(ADDR_PREFIX) for k in v[3]))
        return np.array(sorted(s), np.int64)

    def extra_candidates(self, container_kind) -> list[tuple]:
        """container boxes the diff alone does not show: (box, kind, reason, tags known, ident)"""
        out, seen = [], set()

        def add(box, kind, reason, ident):
            if box is not None and reason and (ident, reason) not in seen:
                seen.add((ident, reason))
                out.append((box, kind, reason, True, ident))

        # relations holding a changed way (D-1 and D): a container multipolygon's whole box
        for c in (self.b, self.a):
            if not c:
                continue
            for wid in self.last_way:
                w = c.ways.get(wid)
                for rid in (w or {}).get("held_by") or []:
                    r = c.rels.get(rid)
                    if r:
                        add(r["box"], "relation", container_kind(r["tags"], relation=True), ("relation", rid))
        # the containers holding a changed contained node, at its old and new place
        for c in (self.bp, self.a):
            if not c:
                continue
            for hits in c.points:
                for k, x in hits:
                    e = c.elements.get((k, x))
                    if e:
                        add(e["box"], "way" if k == 1 else "relation", container_kind(e["tags"], relation=(k == 2)),
                            ("way" if k == 1 else "relation", x))
        # the areas a changed address node is (or was) a vertex of
        for c in (self.b, self.a):
            if not c:
                continue
            for n, info in c.nodes.items():
                had = any(k.startswith(ADDR_PREFIX) for k in (info["tags"] or {}))
                v = self.last_node.get(n)
                has = bool(v and v[2] and v[3] and any(k.startswith(ADDR_PREFIX) for k in v[3]))
                if not (had or has):
                    continue
                for wid in info["vertex_of"]:
                    e = c.elements.get((1, wid))
                    if e:
                        add(e["box"], "way", "area with an address on its outline (AddHousenumber)", ("way", wid))
        return out

    @classmethod
    def load(cls, work: Path, last_node, last_way, last_rel, contained_kind, wanted_relation, over_road=None) -> "DayContext":
        """a day's answers already asked (`day` below): work/before, before-points, after (and P3's x and xb)"""
        work = Path(work)
        dc = cls(last_node, last_way, last_rel, contained_kind, wanted_relation)
        dc.over_road = over_road
        dc.b = Context(work / "before")
        dc.bp = Context(work / "before-points") if (work / "before-points").exists() else None
        dc.a = Context(work / "after") if (work / "after").exists() else None
        dc.bx = Context(work / "before-x") if (work / "before-x").exists() else None
        dc.ax = Context(work / "after-x") if (work / "after-x").exists() else None
        dc.bxb = Context(work / "before-xb") if (work / "before-xb").exists() else None
        dc.axb = Context(work / "after-xb") if (work / "after-xb").exists() else None
        if dc.ax is not None:
            dc.held = set(dc.ax.rels)
        if over_road is not None:
            for when, c in (("b", dc.b), ("a", dc.a)):
                dc.bridges[when], dc.roads[when] = dc._over_lines(c), dc._road_lines(c)
        dc.contained = [n for n, v in last_node.items()
                        if (v[2] and contained_kind(v[3])) or contained_kind(dc.b.nodes.get(n, {}).get("tags"))]
        return dc

    def hooks(self, container_kind) -> dict:
        return {"old_refs": self.old_refs, "member_refs": self.member_refs, "old_tags": self.old_tags,
                "address_nodes": self.address_nodes(), "old_node_tags": self.old_node_tags,
                "extra_candidates": (self.extra_candidates(container_kind) + self.held_candidates(container_kind)
                                     + self.crossing_candidates()),
                "extra_lines": self.extra_lines()}


def main():
    """store_context.py day: one day's three questions around the store's own update, for a test on a copy of a store
    (the planet store's run does the same inside planet_store_day.py once wired)"""
    import argparse
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import stream as S
    import world_tier2 as W
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["day"])
    ap.add_argument("--exe", type=Path, default=Path(__file__).resolve().parents[2] / "tilestore/target/release/tilestore.exe")
    ap.add_argument("--store", type=Path, required=True)
    ap.add_argument("--diff", type=Path, required=True)
    ap.add_argument("--day", required=True, help="the day the diff ends (the store's new generation)")
    ap.add_argument("--before-pbf", type=Path, required=True, help="the clip of D-1: node places before, and the update's --before")
    ap.add_argument("--polygon", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    o = ap.parse_args()
    import osmium
    last_node, last_way, last_rel, _ = S.read_diff(o.diff)
    want = set(last_node)
    old = {}
    for n in osmium.FileProcessor(str(o.before_pbf), osmium.osm.NODE):
        if n.id in want and n.location.valid():
            old[n.id] = (n.location.lat, n.location.lon)
    old_places = W.DictPlaces(old.get)
    new = dict(old)
    for n, v in last_node.items():
        new[n] = v[4] if v[2] else None
    new_places = W.DictPlaces(new.get)
    meta = json.loads((o.store / "store.json").read_text())
    g0 = meta["generations"][-1]["gen"]
    dc = DayContext.before(o.exe, o.store, g0, last_node, last_way, last_rel, old_places, o.work, W.contained_kind,
                           W.wanted_relation, over_road=W.over_road)
    r = subprocess.run([str(o.exe), "update", "--store", str(o.store), "--diff", str(o.diff), "--before", str(o.before_pbf),
                        "--day", o.day, "--polygon", str(o.polygon), "--prune-pairs"], capture_output=True, text=True)
    (o.work / "update.log").write_text(r.stderr or "", encoding="utf-8")
    if r.returncode:
        raise SystemExit(f"update failed: {o.work / 'update.log'}")
    dc.after(o.exe, o.store, g0 + 1, new_places, o.work)
    print(json.dumps({"before": dc.b.stats, "beforePoints": dc.bp.stats if dc.bp else None, "after": dc.a.stats,
                      "beforeX": dc.bx.stats if dc.bx else None, "afterX": dc.ax.stats if dc.ax else None,
                      "extraCandidates": len(dc.extra_candidates(W.container_kind)),
                      "heldCandidates": len(dc.held_candidates(W.container_kind)),
                      "extraLines": len(dc.extra_lines())}, indent=1))


if __name__ == "__main__":
    main()
