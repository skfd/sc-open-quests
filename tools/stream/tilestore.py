"""The z14 tile store itself (DESIGN.md, "Tier 2 for the world", measurement (c)); the tile rule is in tiles.py.

Layout of a store directory:
  pack-GGGG.bin     tile payloads of generation G, one after another (zstd, byte-shuffled numpy columns)
  idx-GGGG.npy      the whole index at generation G: key, pack (the generation that wrote it), offset, length.
                    A day writes only the tiles it changed into a new pack; its index is the previous one with those
                    entries replaced. D is the newest index, D-1 the one before: no tile is copied to keep it.
  rel-GGGG.bin, relidx-GGGG.npy
                    the relation store: per kept relation (tagged, not one the app ignores), its member ways whole
                    with their nodes' places, for the engine's relation geometry
  store.json        generations and what each cost

A tile payload: its nodes (every node of its ways, and its tagged nodes; tagged ones with version, timestamp and
tags, the rest with a place only: the store gives them version 1 and no timestamp), its ways (all whose segments
cross the tile, complete) and its relations (kept ones with a member node in the tile or a member way crossing it).

  tilestore.py cut --geom G --out S --day 2026-11-12
  tilestore.py read --store S [--gen -1] --cities C.json --out Y.osm.pbf [--ring 300]
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from compression import zstd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tiles as T  # noqa: E402

log = T.log
LEVEL = 3
IDX = np.dtype([("key", "<i8"), ("pack", "<i4"), ("off", "<i8"), ("len", "<i4")])
IGNORED_TYPES = {"route_master", "superroute", "network", "disused:route", "boundary", "water", "waterway", "watershed",
                 "collection", "person", "power", "pipeline", "railway"}


def ignore_relation(tags: dict) -> bool:
    """engine/.../IgnoreRelation.kt (SC's ApplicationConstants.ignoreRelation)"""
    t = tags.get("type")
    if t is None:
        return False
    if t == "route":
        return tags.get("route") != "ferry"
    return t in IGNORED_TYPES


def parse_tags(b: bytes) -> dict:
    if not b:
        return {}
    p = b.decode().split("\0")
    return dict(zip(p[0:-1:2], p[1:-1:2]))


# --- columns -------------------------------------------------------------------------------------

def pack_cols(cols: list[np.ndarray]) -> bytes:
    """numpy columns, each byte-shuffled, behind a small header; zstd over the whole"""
    head = [len(cols)]
    body = []
    for a in cols:
        a = np.ascontiguousarray(a)
        code = {np.dtype(np.int64): 0, np.dtype(np.int32): 1, np.dtype(np.int8): 2, np.dtype(np.uint8): 3}[a.dtype]
        head += [code, len(a)]
        body.append(a.view(np.uint8).reshape(-1, a.dtype.itemsize).T.tobytes())
    return zstd.compress(np.array(head, np.int64).tobytes() + b"".join(body), LEVEL)


DT = [np.int64, np.int32, np.int8, np.uint8]


def unpack_cols(buf: bytes) -> list[np.ndarray]:
    raw = zstd.decompress(buf)
    k = int(np.frombuffer(raw, np.int64, 1)[0])
    head = np.frombuffer(raw, np.int64, 1 + 2 * k)
    pos = 8 * (1 + 2 * k)
    out = []
    for i in range(k):
        dt, n = np.dtype(DT[head[1 + 2 * i]]), int(head[2 + 2 * i])
        nb = n * dt.itemsize
        out.append(np.frombuffer(raw, np.uint8, nb, pos).reshape(dt.itemsize, n).T.copy().view(dt).ravel())
        pos += nb
    return out


def delta(a):
    a = np.asarray(a, np.int64)
    return np.diff(a, prepend=0) if len(a) else a


def undelta(a):
    return np.cumsum(a) if len(a) else a


def gather(offs, rows, data):
    """the variable-length pieces rows of data (offs: len+1 offsets): (lengths int32, bytes uint8)"""
    lens = (offs[rows + 1] - offs[rows]).astype(np.int64)
    idx = np.repeat(offs[rows], lens) + (np.arange(lens.sum()) - np.repeat(np.cumsum(lens) - lens, lens))
    return lens.astype(np.int32), data[idx]


def offsets(lens):
    o = np.zeros(len(lens) + 1, np.int64)
    o[1:] = np.cumsum(lens)
    return o


# --- the clip in memory --------------------------------------------------------------------------

class Clip:
    """Geom plus attrs: everything a tile needs, by row"""

    def __init__(self, gdir: Path):
        g = self.g = T.Geom(gdir)
        t = time.time()
        a = np.load(gdir / "attrs.npz")
        self.tn_row = np.searchsorted(g.nid, a["n_ids"])
        assert (g.nid[self.tn_row] == a["n_ids"]).all(), "a tagged node without a place"
        self.tagged_of = np.full(len(g.nid), -1, np.int32)
        self.tagged_of[self.tn_row] = np.arange(len(self.tn_row), dtype=np.int32)
        self.tn_ver, self.tn_ts = a["n_ver"], a["n_ts"]
        self.tn_toff, self.tn_tags = offsets(a["n_tlen"]), a["n_tags"]
        assert (a["w_ids"] == g.wid).all() and (a["r_ids"] == g.rid).all()
        self.w_ver, self.w_ts, self.w_toff, self.w_tags = a["w_ver"], a["w_ts"], offsets(a["w_tlen"]), a["w_tags"]
        self.r_ver, self.r_ts, self.r_toff, self.r_tags = a["r_ver"], a["r_ts"], offsets(a["r_tlen"]), a["r_tags"]
        self.r_roff, self.r_roles = offsets(a["r_rlen"]), a["r_roles"]
        # kept relations: tagged and not ignored by the app
        self.r_kept = np.zeros(len(g.rid), bool)
        for i in range(len(g.rid)):
            b = self.r_tags[self.r_toff[i]:self.r_toff[i + 1]].tobytes()
            self.r_kept[i] = bool(b) and not ignore_relation(parse_tags(b))
        log(f"attrs loaded: {len(self.tn_row):,} tagged nodes, {self.r_kept.sum():,} of {len(g.rid):,} relations kept, "
            f"{time.time() - t:.0f} s")

    # --- payloads ---

    def node_cols(self, rows):
        g = self.g
        rows = np.sort(rows)
        ti = self.tagged_of[rows]
        tagged = ti >= 0
        tl, tb = gather(self.tn_toff, ti[tagged], self.tn_tags)
        return [delta(g.nid[rows]), delta(g.lat7[rows]).astype(np.int32), delta(g.lon7[rows]).astype(np.int32),
                np.flatnonzero(tagged).astype(np.int32), self.tn_ver[ti[tagged]].astype(np.int32),
                self.tn_ts[ti[tagged]].astype(np.int64), tl, tb]

    def way_cols(self, rows):
        g = self.g
        rows = np.sort(rows)
        nref = (g.woffs[rows + 1] - g.woffs[rows]).astype(np.int64)
        idx = np.repeat(g.woffs[rows], nref) + (np.arange(nref.sum()) - np.repeat(np.cumsum(nref) - nref, nref))
        tl, tb = gather(self.w_toff, rows, self.w_tags)
        return [delta(g.wid[rows]), self.w_ver[rows].astype(np.int32), self.w_ts[rows].astype(np.int64),
                nref.astype(np.int32), delta(g.wref_ids[idx]), tl, tb]

    def rel_cols(self, rows):
        g = self.g
        rows = np.sort(rows)
        nmem = (g.roffs[rows + 1] - g.roffs[rows]).astype(np.int64)
        idx = np.repeat(g.roffs[rows], nmem) + (np.arange(nmem.sum()) - np.repeat(np.cumsum(nmem) - nmem, nmem))
        rl = (self.r_roff[idx + 1] - self.r_roff[idx]).astype(np.int64)
        ridx = np.repeat(self.r_roff[idx], rl) + (np.arange(rl.sum()) - np.repeat(np.cumsum(rl) - rl, rl))
        tl, tb = gather(self.r_toff, rows, self.r_tags)
        return [delta(g.rid[rows]), self.r_ver[rows].astype(np.int32), self.r_ts[rows].astype(np.int64),
                nmem.astype(np.int32), g.mtype[idx].astype(np.int8), delta(g.mref[idx]), rl.astype(np.int32),
                self.r_roles[ridx], tl, tb]


def tile_pairs(c: Clip):
    """(key, row) pairs, sorted by key, for the tiles' nodes, ways and relations"""
    g = c.g
    t = time.time()
    # ways: by segment (Geom)
    wk, wr = g.wt_key, g.wt_way
    # relations: a member node's tile, every tile a member way crosses; kept relations only
    nr = len(g.rid)
    rel_of = np.repeat(np.arange(nr), np.diff(g.roffs))
    sel = c.r_kept[rel_of]
    mn = sel & (g.mtype == 0)
    ni = np.minimum(np.searchsorted(g.nid, g.mref[mn]), len(g.nid) - 1)
    okn = g.nid[ni] == g.mref[mn]
    rk = [g.nkey[ni[okn]]]
    rr = [rel_of[mn][okn]]
    mw = sel & (g.mtype == 1)
    wi = np.minimum(np.searchsorted(g.wid, g.mref[mw]), len(g.wid) - 1)
    okw = g.wid[wi] == g.mref[mw]
    wi, wrel = wi[okw], rel_of[mw][okw]
    lo, hi = np.searchsorted(wr, wi, "left"), np.searchsorted(wr, wi, "right")  # wt is sorted by way
    cnt = hi - lo
    idx = np.repeat(lo, cnt) + (np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt))
    rk.append(wk[idx])
    rr.append(np.repeat(wrel, cnt))
    rel = np.unique(np.concatenate(rk) << 28 | np.concatenate(rr))
    # nodes: tagged nodes in the tile, and every node of every way in the tile
    nref = g.woffs[wr + 1] - g.woffs[wr]
    idx = np.repeat(g.woffs[wr], nref) + (np.arange(nref.sum()) - np.repeat(np.cumsum(nref) - nref, nref))
    nrow = g.wrefs[idx]
    nkey = np.repeat(wk, nref)
    ok = nrow >= 0
    node = np.unique(np.concatenate([nkey[ok] << 28 | nrow[ok], g.nkey[c.tn_row] << 28 | c.tn_row]))
    order = np.argsort(wk, kind="stable")
    way = (wk[order], wr[order])
    log(f"tile pairs: {len(node):,} node, {len(way[0]):,} way, {len(rel):,} relation copies in {time.time() - t:.0f} s")
    m = (1 << 28) - 1
    return (node >> 28, node & m), way, (rel >> 28, rel & m)


def cut(gdir: Path, out: Path, day: str):
    t0 = time.time()
    c = Clip(gdir)
    g = c.g
    (nk, nr), (wk, wr), (rk, rr) = tile_pairs(c)
    keys = np.unique(np.concatenate([nk, wk, rk]))
    out.mkdir(parents=True, exist_ok=True)
    t = time.time()
    idx = np.zeros(len(keys), IDX)
    idx["key"] = keys
    nb = [np.searchsorted(nk, keys, "left"), np.searchsorted(nk, keys, "right")]
    wb = [np.searchsorted(wk, keys, "left"), np.searchsorted(wk, keys, "right")]
    rb = [np.searchsorted(rk, keys, "left"), np.searchsorted(rk, keys, "right")]
    off = 0
    with open(out / "pack-0000.bin", "wb") as f:
        for i in range(len(keys)):
            cols = (c.node_cols(nr[nb[0][i]:nb[1][i]]) + c.way_cols(wr[wb[0][i]:wb[1][i]])
                    + c.rel_cols(rr[rb[0][i]:rb[1][i]]))
            buf = pack_cols(cols)
            f.write(buf)
            idx["off"][i], idx["len"][i] = off, len(buf)
            off += len(buf)
    np.save(out / "idx-0000.npy", idx)
    tt = time.time() - t
    # the relation store
    t = time.time()
    rel_rows = np.flatnonzero(c.r_kept)
    ridx = np.zeros(len(rel_rows), IDX)
    ridx["key"] = g.rid[rel_rows]
    roff = 0
    member_ways = 0
    with open(out / "rel-0000.bin", "wb") as f:
        for j, r in enumerate(rel_rows):
            ms = slice(g.roffs[r], g.roffs[r + 1])
            mw = g.mref[ms][g.mtype[ms] == 1]
            wi = np.minimum(np.searchsorted(g.wid, mw), len(g.wid) - 1)
            wi = np.unique(wi[g.wid[wi] == mw])
            member_ways += len(wi)
            u = np.unique(g.way_node_rows(wi))
            cols = c.way_cols(wi) + [delta(g.nid[u]), delta(g.lat7[u]).astype(np.int32), delta(g.lon7[u]).astype(np.int32)]
            buf = pack_cols(cols)
            f.write(buf)
            ridx["off"][j], ridx["len"][j] = roff, len(buf)
            roff += len(buf)
    np.save(out / "relidx-0000.npy", ridx)
    tr = time.time() - t
    meta = {"z": T.Z, "generations": [{"gen": 0, "day": day, "from": str(gdir), "tiles": len(keys),
                                       "bytes": off, "relations": len(rel_rows), "relationWays": member_ways,
                                       "relBytes": roff, "tileSeconds": round(tt, 1), "relSeconds": round(tr, 1),
                                       "seconds": round(time.time() - t0, 1),
                                       "copies": {"nodes": len(nk), "ways": len(wk), "relations": len(rk)}}]}
    (out / "store.json").write_text(json.dumps(meta, indent=1))
    log(f"cut {day}: {len(keys):,} tiles, {off / 2**30:.2f} GiB in {tt:.0f} s; relation store {len(rel_rows):,} relations, "
        f"{member_ways:,} member ways, {roff / 2**20:.0f} MiB in {tr:.0f} s; {time.time() - t0:.0f} s in all")


# --- reading -------------------------------------------------------------------------------------

def decode_tile(buf: bytes):
    c = unpack_cols(buf)
    nid, lat, lon, tpos, tver, tts, ntl, ntb = c[0:8]
    wid, wver, wts, wnref, wrefs, wtl, wtb = c[8:15]
    rid, rver, rts, rnmem, rmt, rmref, rrl, rroles, rtl, rtb = c[15:25]
    return {"n": (undelta(nid), undelta(lat), undelta(lon), tpos, tver, tts, ntl, ntb),
            "w": (undelta(wid), wver, wts, wnref, undelta(wrefs), wtl, wtb),
            "r": (undelta(rid), rver, rts, rnmem, rmt, undelta(rmref), rrl, rroles, rtl, rtb)}


class Store:
    def __init__(self, d: Path, gen: int = -1):
        self.d = d
        self.meta = json.loads((d / "store.json").read_text())
        g = self.meta["generations"][gen]["gen"]
        self.gen = g
        self.idx = np.load(d / f"idx-{g:04d}.npy")
        rg = max(x["gen"] for x in self.meta["generations"] if x["gen"] <= g and (d / f"relidx-{x['gen']:04d}.npy").exists())
        self.ridx = np.load(d / f"relidx-{rg:04d}.npy")
        self._files = {}

    def _read(self, prefix, pack, off, n):
        f = self._files.get((prefix, pack))
        if f is None:
            f = self._files[(prefix, pack)] = open(self.d / f"{prefix}-{pack:04d}.bin", "rb")
        f.seek(off)
        return f.read(n)

    def tile(self, key):
        i = np.searchsorted(self.idx["key"], key)
        if i >= len(self.idx) or self.idx["key"][i] != key:
            return None
        e = self.idx[i]
        return self._read("pack", int(e["pack"]), int(e["off"]), int(e["len"]))

    def relation(self, rid):
        i = np.searchsorted(self.ridx["key"], rid)
        if i >= len(self.ridx) or self.ridx["key"][i] != rid:
            return None
        e = self.ridx[i]
        return self._read("rel", int(e["pack"]), int(e["off"]), int(e["len"]))


def join(store: Store, keys: np.ndarray, out: Path, stamp: str | None) -> dict:
    """the tiles' map data as one PBF, duplicates dropped, every kept relation's member ways from the relation store"""
    import osmium
    t = time.time()
    keys = keys[np.isin(keys, store.idx["key"])]
    nbytes = 0
    nodes, tnodes, ways, rels = [], [], [], []
    for k in keys.tolist():
        buf = store.tile(k)
        nbytes += len(buf)
        p = decode_tile(buf)
        nid, lat, lon, tpos, tver, tts, ntl, ntb = p["n"]
        nodes.append((nid, lat, lon))
        to = offsets(ntl)
        for j, pos in enumerate(tpos.tolist()):
            tnodes.append((int(nid[pos]), int(tver[j]), int(tts[j]), ntb[to[j]:to[j + 1]].tobytes()))
        wid, wver, wts, wnref, wrefs, wtl, wtb = p["w"]
        ro, to = offsets(wnref), offsets(wtl)
        for j in range(len(wid)):
            ways.append((int(wid[j]), int(wver[j]), int(wts[j]), wrefs[ro[j]:ro[j + 1]], wtb[to[j]:to[j + 1]].tobytes()))
        rid, rver, rts, rnmem, rmt, rmref, rrl, rroles, rtl, rtb = p["r"]
        mo, to = offsets(rnmem), offsets(rtl)
        rlo = offsets(rrl)
        for j in range(len(rid)):
            ms = slice(mo[j], mo[j + 1])
            roles = [rroles[rlo[m]:rlo[m + 1]].tobytes().decode() for m in range(mo[j], mo[j + 1])]
            rels.append((int(rid[j]), int(rver[j]), int(rts[j]), rmt[ms], rmref[ms], roles, rtb[to[j]:to[j + 1]].tobytes()))
    t_tiles = time.time() - t
    rel_ids = sorted({r[0] for r in rels})
    rbytes = 0
    for rid_ in rel_ids:
        buf = store.relation(rid_)
        if buf is None:
            continue
        rbytes += len(buf)
        c = unpack_cols(buf)
        wid, wver, wts, wnref, wrefs, wtl, wtb = c[0], c[1], c[2], c[3], undelta(c[4]), c[5], c[6]
        wid = undelta(wid)
        ro, to = offsets(wnref), offsets(wtl)
        for j in range(len(wid)):
            ways.append((int(wid[j]), int(wver[j]), int(wts[j]), wrefs[ro[j]:ro[j + 1]], wtb[to[j]:to[j + 1]].tobytes()))
        nodes.append((undelta(c[7]), undelta(c[8]), undelta(c[9])))
    # nodes: the first copy of each id; a tagged one carries its attributes
    nid = np.concatenate([n[0] for n in nodes]) if nodes else np.zeros(0, np.int64)
    lat = np.concatenate([n[1] for n in nodes]) if nodes else np.zeros(0, np.int64)
    lon = np.concatenate([n[2] for n in nodes]) if nodes else np.zeros(0, np.int64)
    u, first = np.unique(nid, return_index=True)
    lat, lon = lat[first], lon[first]
    tagged = {}
    for n in tnodes:
        tagged.setdefault(n[0], n)
    way_by = {}
    for w in ways:
        way_by.setdefault(w[0], w)
    rel_by = {}
    for r in rels:
        rel_by.setdefault(r[0], r)
    t_merge = time.time() - t - t_tiles
    header = osmium.io.Header()
    if stamp:
        header.set("osmosis_replication_timestamp", stamp)
    header.set("sorting", "Type_then_ID")
    out.parent.mkdir(parents=True, exist_ok=True)
    w = osmium.SimpleWriter(str(out), header=header, overwrite=True)
    N, W, R = osmium.osm.mutable.Node, osmium.osm.mutable.Way, osmium.osm.mutable.Relation

    def ts(s):
        return datetime.fromtimestamp(s, timezone.utc)

    for i, (n_, la, lo) in enumerate(zip(u.tolist(), lat.tolist(), lon.tolist())):
        loc = (lo / 1e7, la / 1e7)
        tn = tagged.get(n_)
        if tn is None:
            w.add_node(N(id=n_, version=1, location=loc))
        else:
            w.add_node(N(id=n_, version=tn[1], timestamp=ts(tn[2]), location=loc, tags=parse_tags(tn[3])))
    for wid_ in sorted(way_by):
        _, v, s, refs, tb = way_by[wid_]
        w.add_way(W(id=wid_, version=v, timestamp=ts(s), nodes=refs.tolist(), tags=parse_tags(tb)))
    tn_ = {0: "n", 1: "w", 2: "r"}
    for rid_ in sorted(rel_by):
        _, v, s, mt, mr, roles, tb = rel_by[rid_]
        members = [(tn_[int(a)], int(b), rl) for a, b, rl in zip(mt.tolist(), mr.tolist(), roles)]
        w.add_relation(R(id=rid_, version=v, timestamp=ts(s), members=members, tags=parse_tags(tb)))
    w.close()
    st = {"tiles": len(keys), "tileBytes": nbytes, "relBytes": rbytes, "nodes": len(u), "ways": len(way_by),
          "relations": len(rel_by), "secondsTiles": round(t_tiles, 1), "secondsMerge": round(t_merge, 1),
          "secondsWrite": round(time.time() - t - t_tiles - t_merge, 1), "seconds": round(time.time() - t, 1)}
    log(f"join: {st}")
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cut", "read"])
    ap.add_argument("--geom", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--day")
    ap.add_argument("--store", type=Path)
    ap.add_argument("--gen", type=int, default=-1)
    ap.add_argument("--cities", type=Path)
    ap.add_argument("--base", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--ring", type=float, default=300.0)
    ap.add_argument("--stamp")
    o = ap.parse_args()
    if o.cmd == "cut":
        cut(o.geom, o.out, o.day)
    else:
        s = Store(o.store, o.gen)
        keys = T.tiles_of(T.city_boxes(o.cities, o.base), o.ring)
        st = join(s, keys, o.out, o.stamp)
        Path(str(o.out) + ".json").write_text(json.dumps(st, indent=1))


if __name__ == "__main__":
    main()
