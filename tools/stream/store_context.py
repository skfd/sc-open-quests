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


def run_context(exe: Path, store: Path, gen: int, out: Path, ways=None, rels=None, nodes=None, node_places=None,
                points=None, around: int = 1, log=print) -> Context:
    """`tilestore context` with these inputs (id lists; node_places and points as (lat, lon) degree arrays)"""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    args = [str(exe), "context", "--store", str(store), "--gen", str(gen), "--out", str(out), "--around", str(around)]

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

    @classmethod
    def before(cls, exe, store, gen, last_node, last_way, last_rel, old_places, work: Path, contained_kind,
               wanted_relation, log=print) -> "DayContext":
        dc = cls(last_node, last_way, last_rel, contained_kind, wanted_relation)
        # nodes that existed the day before: every changed node but a new one (version 1)
        old_n = np.array([n for n, v in last_node.items() if v[0] > 1], np.int64)
        op = old_places.places(old_n) if len(old_n) else np.zeros((0, 2))
        dc.b = run_context(exe, store, gen, Path(work) / "before", ways=list(last_way), rels=list(last_rel),
                           nodes=old_n, node_places=op, log=log)
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
        return self

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
    def load(cls, work: Path, last_node, last_way, last_rel, contained_kind, wanted_relation) -> "DayContext":
        """a day's answers already asked (`day` below): work/before, before-points, after"""
        work = Path(work)
        dc = cls(last_node, last_way, last_rel, contained_kind, wanted_relation)
        dc.b = Context(work / "before")
        dc.bp = Context(work / "before-points") if (work / "before-points").exists() else None
        dc.a = Context(work / "after") if (work / "after").exists() else None
        dc.contained = [n for n, v in last_node.items()
                        if (v[2] and contained_kind(v[3])) or contained_kind(dc.b.nodes.get(n, {}).get("tags"))]
        return dc

    def hooks(self, container_kind) -> dict:
        return {"old_refs": self.old_refs, "member_refs": self.member_refs, "old_tags": self.old_tags,
                "address_nodes": self.address_nodes(), "old_node_tags": self.old_node_tags,
                "extra_candidates": self.extra_candidates(container_kind)}


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
                           W.wanted_relation)
    r = subprocess.run([str(o.exe), "update", "--store", str(o.store), "--diff", str(o.diff), "--before", str(o.before_pbf),
                        "--day", o.day, "--polygon", str(o.polygon), "--prune-pairs"], capture_output=True, text=True)
    (o.work / "update.log").write_text(r.stderr or "", encoding="utf-8")
    if r.returncode:
        raise SystemExit(f"update failed: {o.work / 'update.log'}")
    dc.after(o.exe, o.store, g0 + 1, new_places, o.work)
    print(json.dumps({"before": dc.b.stats, "beforePoints": dc.bp.stats if dc.bp else None, "after": dc.a.stats,
                      "extraCandidates": len(dc.extra_candidates(W.container_kind))}, indent=1))


if __name__ == "__main__":
    main()
