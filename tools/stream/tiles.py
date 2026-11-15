"""A z14 tile store of map data for tier 2 of the world (DESIGN.md, "Tier 2 for the world", measurement (c)).

Tier 2 recounts the ground a day touched; today it reads the whole day clip. A world needs a store answering "the
map data of these boxes at day D (and D-1)". The tile rule, what a tile holds:
  - every node located in the tile;
  - every way with a segment that crosses the tile (not only a node in it: a long segment can carry a way's quest
    point across a small rectangle), complete: all its nodes, wherever they lie;
  - every relation with a member node in the tile or a member way that crosses it (the store keeps only the kept
    ones, tagged and not ignored by the app, and stores their member nodes in the tile too: tilestore.tile_pairs);
  - the member ways of those relations, complete (the engine builds a relation's geometry from all its member ways,
    which a clip has whole): kept apart, as the relation store, to size it on its own.
The engine picks an area's ways by a node in its padded box and orders its map data by id hash (AreaPass.kt), so the
tiles under a box and its ring, joined with duplicates dropped, must give the same rows as the whole clip.

  tiles.py geom --clip X.osm.pbf --dir G
      the clip's node locations (G/nodes.idx), way refs (G/ways.npz) and relation members (G/rels.npz)
  tiles.py extract --geom G --clip X.osm.pbf --cities C.json --out Y.osm.pbf [--ring 300] [--no-rel-ways]
      what the tiles under the cities' boxes (each padded by the ring, as the engine pads) hold, as one PBF:
      the equality test of the rule, before any store is built
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

# the tiles' zoom; OPENQUESTS_TILE_Z sets another for a measurement (DESIGN.md, "Smaller tiles"); a store records its own
Z = int(os.environ.get("OPENQUESTS_TILE_Z", "14"))
NT = 1 << Z
KB = 2 * Z  # bits of a tile key
M_LAT = 111_320.0


def log(msg: str):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# --- tiles ---------------------------------------------------------------------------------------

def frac_xy(lat, lon):
    """web mercator tile coordinates at Z, fractional"""
    lat = np.clip(np.asarray(lat, np.float64), -85.0511, 85.0511)
    fx = (np.asarray(lon, np.float64) + 180.0) / 360.0 * NT
    r = np.radians(lat)
    fy = (1.0 - np.log(np.tan(r) + 1.0 / np.cos(r)) / math.pi) / 2.0 * NT
    return fx, fy


def key_of(x, y):
    return (np.clip(x, 0, NT - 1).astype(np.int64) << Z) | np.clip(y, 0, NT - 1).astype(np.int64)


def segment_tiles(fx0, fy0, fx1, fy1, eps=1e-9):
    """every tile each segment crosses (column by column, its rows between the segment's y where it enters and
    leaves the column): (segment index, tile key)"""
    n = len(fx0)
    if n == 0:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    xa, xb = np.minimum(fx0, fx1), np.maximum(fx0, fx1)
    c0, c1 = np.floor(xa).astype(np.int64), np.floor(xb).astype(np.int64)
    ncol = c1 - c0 + 1
    seg = np.repeat(np.arange(n), ncol)
    col = np.repeat(c0, ncol) + (np.arange(ncol.sum()) - np.repeat(np.cumsum(ncol) - ncol, ncol))
    lo, hi = np.maximum(col, xa[seg]), np.minimum(col + 1, xb[seg])
    dx, dy = (fx1 - fx0)[seg], (fy1 - fy0)[seg]
    with np.errstate(divide="ignore", invalid="ignore"):
        t_lo = np.where(dx != 0, (lo - fx0[seg]) / dx, 0.0)
        t_hi = np.where(dx != 0, (hi - fx0[seg]) / dx, 1.0)
    ya, yb = fy0[seg] + t_lo * dy, fy0[seg] + t_hi * dy
    r0, r1 = np.floor(np.minimum(ya, yb) - eps).astype(np.int64), np.floor(np.maximum(ya, yb) + eps).astype(np.int64)
    nrow = r1 - r0 + 1
    s2 = np.repeat(seg, nrow)
    c2 = np.repeat(col, nrow)
    row = np.repeat(r0, nrow) + (np.arange(nrow.sum()) - np.repeat(np.cumsum(nrow) - nrow, nrow))
    return s2, key_of(c2, row)


def box_tiles(s, w, n, e) -> np.ndarray:
    """the tile keys under a box in degrees"""
    x0, y1 = frac_xy(s, w)
    x1, y0 = frac_xy(n, e)
    xs = np.arange(int(np.floor(x0)), int(np.floor(x1)) + 1)
    ys = np.arange(int(np.floor(y0)), int(np.floor(y1)) + 1)
    gx, gy = np.meshgrid(xs, ys)
    return key_of(gx.ravel(), gy.ravel())


def padded(s, w, n, e, ring):
    """the engine's padding of a city box (AreaPass.kt): ring metres, the longitude's at the box's larger |lat|"""
    d_lat = ring / M_LAT
    d_lon = ring / (M_LAT * math.cos(math.radians(min(85.0, max(abs(s), abs(n))))))
    return s - d_lat, w - d_lon, n + d_lat, e + d_lon


# --- the clip's geometry -------------------------------------------------------------------------

def geom(clip: Path, d: Path):
    import osmium
    import stream
    from array import array
    d.mkdir(parents=True, exist_ok=True)
    t = time.time()
    stream.nodes(clip, d)  # nodes.idx, a sorted sparse file (and an empty overlay.pickle, unused here)
    tn = time.time() - t
    t = time.time()
    ids, lens, refs = array("q"), array("q"), array("q")
    for w in osmium.FileProcessor(str(clip), osmium.osm.WAY):
        r = [n.ref for n in w.nodes]
        ids.append(w.id)
        lens.append(len(r))
        refs.extend(r)
    ids, lens, refs = (np.frombuffer(a, np.int64) for a in (ids, lens, refs))
    offs = np.zeros(len(ids) + 1, np.int64)
    offs[1:] = np.cumsum(lens)
    np.savez(d / "ways.npz", ids=ids, offs=offs, refs=refs)
    tw = time.time() - t
    t = time.time()
    rids, rlens, mtype, mref = array("q"), array("q"), array("b"), array("q")
    tm = {"n": 0, "w": 1, "r": 2}
    for r in osmium.FileProcessor(str(clip), osmium.osm.RELATION):
        ms = [(tm[m.type], m.ref) for m in r.members]
        rids.append(r.id)
        rlens.append(len(ms))
        for a, b in ms:
            mtype.append(a)
            mref.append(b)
    rids, rlens, mref = (np.frombuffer(a, np.int64) for a in (rids, rlens, mref))
    roffs = np.zeros(len(rids) + 1, np.int64)
    roffs[1:] = np.cumsum(rlens)
    np.savez(d / "rels.npz", ids=rids, offs=roffs, mtype=np.frombuffer(mtype, np.int8), mref=mref)
    tr = time.time() - t
    (d / "geom.json").write_text(json.dumps({"clip": str(clip), "nodesSeconds": round(tn, 1), "waysSeconds": round(tw, 1),
                                             "relationsSeconds": round(tr, 1), "ways": len(ids), "refs": len(refs),
                                             "relations": len(rids), "members": len(mref)}, indent=1))
    log(f"geom of {clip.name}: nodes {tn:.0f} s, {len(ids):,} ways ({len(refs):,} refs) {tw:.0f} s, "
        f"{len(rids):,} relations {tr:.0f} s")


def attrs(clip: Path, d: Path):
    """what the geometry leaves out: tagged nodes (id, version, timestamp, tags), every way's and relation's version,
    timestamp and tags, and relation member roles; tags as b"k\\0v\\0..." per object, in the clip's (id) order.
    Untagged nodes keep only their place (geom): the store gives them version 1 and no timestamp."""
    import osmium
    import osmium.filter as F
    from array import array
    d.mkdir(parents=True, exist_ok=True)
    out = {}
    t0 = time.time()

    def run(kind, filt=None):
        ids, ver, ts, tlen = array("q"), array("i"), array("q"), array("i")
        tags = bytearray()
        rlen, roles = array("i"), bytearray()
        fp = osmium.FileProcessor(str(clip), kind)
        if filt is not None:
            fp = fp.with_filter(filt)
        for o in fp:
            ids.append(o.id)
            ver.append(o.version)
            ts.append(int(o.timestamp.timestamp()))
            b = "".join(f"{t.k}\0{t.v}\0" for t in o.tags).encode()
            tlen.append(len(b))
            tags += b
            if kind == osmium.osm.RELATION:
                for m in o.members:
                    rb = m.role.encode()
                    rlen.append(len(rb))
                    roles += rb
        p = {"ids": np.frombuffer(ids, np.int64), "ver": np.frombuffer(ver, np.int32), "ts": np.frombuffer(ts, np.int64),
             "tlen": np.frombuffer(tlen, np.int32), "tags": np.frombuffer(bytes(tags), np.uint8)}
        if kind == osmium.osm.RELATION:
            p["rlen"], p["roles"] = np.frombuffer(rlen, np.int32), np.frombuffer(bytes(roles), np.uint8)
        return p

    for name, kind, filt in (("n", osmium.osm.NODE, F.EmptyTagFilter()), ("w", osmium.osm.WAY, None),
                             ("r", osmium.osm.RELATION, None)):
        t = time.time()
        for k, v in run(kind, filt).items():
            out[f"{name}_{k}"] = v
        log(f"attrs {name}: {len(out[name + '_ids']):,} in {time.time() - t:.0f} s")
    np.savez(d / "attrs.npz", **out)
    log(f"attrs of {clip.name} in {time.time() - t0:.0f} s")


class Geom:
    """a clip's geometry in memory: nodes (ids sorted, lat7, lon7, tile key), ways (ids, offs, refs as node rows,
    each way's tile keys by segment), relations (ids, offs, member type and ref)"""

    def __init__(self, d: Path):
        t = time.time()
        a = np.memmap(d / "nodes.idx", dtype=[("id", "<u8"), ("x", "<i4"), ("y", "<i4")], mode="r")
        n = len(a)
        ids = a["id"]
        # trailing unused slots are zero
        lo, hi = 0, n
        while lo < hi:
            mid = (lo + hi) // 2
            if ids[mid] == 0:
                hi = mid
            else:
                lo = mid + 1
        self.nid = np.array(ids[:lo], np.int64)
        self.lon7 = np.array(a["x"][:lo])
        self.lat7 = np.array(a["y"][:lo])
        del a
        fx, fy = frac_xy(self.lat7 / 1e7, self.lon7 / 1e7)
        self.nfx, self.nfy = fx, fy
        self.nkey = key_of(np.floor(fx), np.floor(fy))
        z = np.load(d / "ways.npz")
        self.wid, self.woffs = z["ids"], z["offs"]
        refs = z["refs"]
        ri = np.searchsorted(self.nid, refs)
        ri = np.minimum(ri, len(self.nid) - 1)
        ok = self.nid[ri] == refs
        self.wrefs = np.where(ok, ri, -1).astype(np.int64)  # node rows; -1: not in the clip
        self.wref_ids = refs
        z = np.load(d / "rels.npz")
        self.rid, self.roffs, self.mtype, self.mref = z["ids"], z["offs"], z["mtype"], z["mref"]
        log(f"geom loaded: {len(self.nid):,} nodes, {len(self.wid):,} ways, {len(self.rid):,} relations in {time.time() - t:.0f} s")
        self._way_tiles()

    def _way_tiles(self):
        """(way row, tile key) for every tile a way's segments cross, unique"""
        t = time.time()
        nw = len(self.wid)
        lens = np.diff(self.woffs)
        way_of_ref = np.repeat(np.arange(nw, dtype=np.int64), lens)
        ok = self.wrefs >= 0
        keys = np.where(ok, self.nkey[np.maximum(self.wrefs, 0)], -1)
        pairs = [way_of_ref[ok] << KB | keys[ok]]
        # segments: consecutive refs of one way, both placed, in different tiles
        a, b = np.arange(len(self.wrefs) - 1), np.arange(1, len(self.wrefs))
        same_way = way_of_ref[a] == way_of_ref[b]
        both = ok[a] & ok[b]
        cross = same_way & both & (keys[a] != keys[b])
        a, b = a[cross], b[cross]
        ra, rb = self.wrefs[a], self.wrefs[b]
        s, k = segment_tiles(self.nfx[ra], self.nfy[ra], self.nfx[rb], self.nfy[rb])
        pairs.append(way_of_ref[a][s] << KB | k)
        wt = np.unique(np.concatenate(pairs))
        self.wt_way, self.wt_key = wt >> KB, wt & ((1 << KB) - 1)
        log(f"way tiles: {len(wt):,} (way, tile) pairs from {len(self.wrefs):,} refs, {cross.sum():,} segments "
            f"crossing tiles, in {time.time() - t:.0f} s")

    def way_node_rows(self, way_rows: np.ndarray) -> np.ndarray:
        lens = self.woffs[way_rows + 1] - self.woffs[way_rows]
        idx = np.repeat(self.woffs[way_rows], lens) + (np.arange(lens.sum()) - np.repeat(np.cumsum(lens) - lens, lens))
        r = self.wrefs[idx]
        return r[r >= 0]

    def select(self, tiles: np.ndarray, rel_ways=True):
        """the tile rule for a set of tiles: (node rows, way rows, relation rows), and the relation store's share"""
        tiles = np.unique(tiles)
        n_in = np.isin(self.nkey, tiles)
        w_rows = np.unique(self.wt_way[np.isin(self.wt_key, tiles)])
        w_mask = np.zeros(len(self.wid), bool)
        w_mask[w_rows] = True
        # relations: a member node in the tiles, or a member way that crosses them
        nr = len(self.rid)
        rel_of = np.repeat(np.arange(nr), np.diff(self.roffs))
        hit = np.zeros(len(self.mref), bool)
        mn = self.mtype == 0
        ni = np.minimum(np.searchsorted(self.nid, self.mref[mn]), len(self.nid) - 1)
        hit[mn] = (self.nid[ni] == self.mref[mn]) & n_in[ni]
        mw = self.mtype == 1
        wi = np.minimum(np.searchsorted(self.wid, self.mref[mw]), len(self.wid) - 1)
        hit[mw] = (self.wid[wi] == self.mref[mw]) & w_mask[wi]
        r_rows = np.unique(rel_of[hit])
        # the relation store's share: every member way of those relations
        r_mask = np.zeros(nr, bool)
        r_mask[r_rows] = True
        mw_sel = mw & r_mask[rel_of]
        wi = np.minimum(np.searchsorted(self.wid, self.mref[mw_sel]), len(self.wid) - 1)
        rw_rows = np.unique(wi[self.wid[wi] == self.mref[mw_sel]])
        rw_rows = np.setdiff1d(rw_rows, w_rows)
        all_ways = np.union1d(w_rows, rw_rows) if rel_ways else w_rows
        n_rows = np.union1d(np.flatnonzero(n_in), self.way_node_rows(all_ways))
        return n_rows, all_ways, r_rows, {"tiles": len(tiles), "nodesInTiles": int(n_in.sum()), "ways": len(w_rows),
                                          "relationWays": len(rw_rows), "relations": len(r_rows), "nodes": len(n_rows)}


def write_subset(clip: Path, out: Path, nodes, ways, rels):
    """the clip's objects with these ids, in the clip's order, its header's replication timestamp kept"""
    import osmium
    import osmium.filter as F
    t = time.time()
    hdr_in = osmium.io.Reader(str(clip), osmium.osm.NOTHING).header()
    header = osmium.io.Header()
    stamp = hdr_in.get("osmosis_replication_timestamp")
    if stamp:
        header.set("osmosis_replication_timestamp", stamp)
    header.set("sorting", "Type_then_ID")
    out.parent.mkdir(parents=True, exist_ok=True)
    w = osmium.SimpleWriter(str(out), header=header, overwrite=True)
    fp = (osmium.FileProcessor(str(clip))
          .with_filter(F.IdFilter(nodes.tolist()).enable_for(osmium.osm.NODE))
          .with_filter(F.IdFilter(ways.tolist()).enable_for(osmium.osm.WAY))
          .with_filter(F.IdFilter(rels.tolist()).enable_for(osmium.osm.RELATION)))
    n = 0
    for o in fp:
        w.add(o)
        n += 1
    w.close()
    log(f"wrote {out.name}: {n:,} objects, {out.stat().st_size / 2**20:.1f} MiB in {time.time() - t:.0f} s")


def city_boxes(cities: Path, base: Path):
    out = []
    for c in json.loads(cities.read_text(encoding="utf-8"))["cities"]:
        b = json.loads((base / c["boundary"]).read_text(encoding="utf-8"))["bounds"]
        out.append((c["id"], b["minlat"], b["minlon"], b["maxlat"], b["maxlon"]))
    return out


def tiles_of(boxes, ring):
    return np.unique(np.concatenate([box_tiles(*padded(s, w, n, e, ring)) for _, s, w, n, e in boxes]))


def recount(pbf: Path, cities: Path, today: str, out: Path, base: Path, ring: float) -> Path:
    """the tier-2 recount as stream.tier2_step runs it: the rectangles as cities, area pass, the ring as padding"""
    import stream
    return stream.engine(pbf, out, today, cities, "Europe/London", None, area_pass=True, heap_gb=30, base=base,
                         extra_opts=f"-Dopenquests.areaPaddingM={ring:.0f}")


def compare(a: Path, b: Path, cities: Path | None = None, base: Path | None = None) -> dict:
    """two --dump-state files row for row; with the cities, also only the rows inside their boxes"""
    import stream
    names: list[str] = []
    ra, rb = stream.read_dump(a, names), stream.read_dump(b, names)
    out = {"rowsA": len(ra), "rowsB": len(rb)}

    def diff(x, y, tag):
        only_x, only_y = np.setdiff1d(x, y), np.setdiff1d(y, x)
        out[f"{tag}onlyA"], out[f"{tag}onlyB"] = len(only_x), len(only_y)
        for nm, arr in (("A", only_x), ("B", only_y)):
            if len(arr):
                out[f"{tag}examples{nm}"] = [f"{int(k)} {names[int(q)]} kind{int(kd)} flags{int(f)}"
                                            for k, q, kd, f in zip(arr["key"][:8], arr["quest"][:8], arr["kind"][:8], arr["flags"][:8])]

    diff(ra, rb, "")
    if cities is not None:
        boxes = city_boxes(cities, base)

        def inside(r):
            lat, lon = r["lat"] / 1e7, r["lon"] / 1e7
            m = np.zeros(len(r), bool)
            for _, s, w, n, e in boxes:
                m |= (lat >= s) & (lat <= n) & (lon >= w) & (lon <= e)
            return r[m]
        diff(inside(ra), inside(rb), "inside ")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["geom", "attrs", "extract", "recount", "compare"])
    ap.add_argument("--pbf", type=Path)
    ap.add_argument("--today")
    ap.add_argument("--a", type=Path)
    ap.add_argument("--b", type=Path)
    ap.add_argument("--clip", type=Path)
    ap.add_argument("--dir", type=Path)
    ap.add_argument("--geom", type=Path)
    ap.add_argument("--cities", type=Path)
    ap.add_argument("--base", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--ring", type=float, default=300.0)
    ap.add_argument("--no-rel-ways", action="store_true", help="leave the relation store's member ways out")
    o = ap.parse_args()
    if o.cmd == "geom":
        geom(o.clip, o.dir)
    elif o.cmd == "attrs":
        attrs(o.clip, o.dir)
    elif o.cmd == "extract":
        g = Geom(o.geom)
        tiles = tiles_of(city_boxes(o.cities, o.base), o.ring)
        n, w, r, st = g.select(tiles, rel_ways=not o.no_rel_ways)
        log(f"tile rule: {st}")
        write_subset(o.clip, o.out, g.nid[n], g.wid[w], g.rid[r])
        Path(str(o.out) + ".json").write_text(json.dumps(st, indent=1))
    elif o.cmd == "recount":
        recount(o.pbf, o.cities, o.today, o.out, o.base, o.ring)
    elif o.cmd == "compare":
        print(json.dumps(compare(o.a, o.b, o.cities, o.base), indent=1))


if __name__ == "__main__":
    main()
