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

A tile payload: its nodes (every node of its ways, its tagged nodes, and its relations' member nodes located in it;
tagged ones with version, timestamp and tags, the rest with a place only: the store gives them version 1 and no
timestamp), its ways (all whose segments cross the tile, complete) and its relations (kept ones with a member node in
the tile or a member way crossing it).

  tilestore.py update --store S --diff N.osc.gz --before G
      a day's diff into a new generation: the reached tiles rebuilt from their old payloads and the diff (see update);
      G is the node store before the day (a clip's nodes.idx here)
  tilestore.py compare --a S1 --b S2 [--cities C.json --under]
      two stores tile by tile

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
    # nodes: tagged nodes in the tile, every node of every way in the tile, and the kept relations' member nodes
    # there (an untagged one no way holds, a site's label say, is how its relation is in the tile: a rebuilt tile must
    # find it again)
    nref = g.woffs[wr + 1] - g.woffs[wr]
    idx = np.repeat(g.woffs[wr], nref) + (np.arange(nref.sum()) - np.repeat(np.cumsum(nref) - nref, nref))
    nrow = g.wrefs[idx]
    nkey = np.repeat(wk, nref)
    ok = nrow >= 0
    mrow = ni[okn]
    node = np.unique(np.concatenate([nkey[ok] << 28 | nrow[ok], g.nkey[c.tn_row] << 28 | c.tn_row,
                                     g.nkey[mrow] << 28 | mrow]))
    order = np.argsort(wk, kind="stable")
    way = (wk[order], wr[order])
    log(f"tile pairs: {len(node):,} node, {len(way[0]):,} way, {len(rel):,} relation copies in {time.time() - t:.0f} s")
    m = (1 << 28) - 1
    return (node >> 28, node & m), way, (rel >> 28, rel & m)


PAIR = np.dtype([("id", "<i8"), ("key", "<i8")])


def save_pairs(path: Path, ids, keys):
    p = np.zeros(len(ids), PAIR)
    p["id"], p["key"] = ids, keys
    np.save(path, np.sort(p, order=["id", "key"]))


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
    # the tiles of every way and relation, by id: a day's update finds a changed object's old tiles here
    save_pairs(out / "wtiles-0000.npy", g.wid[wr], wk)
    save_pairs(out / "rtiles-0000.npy", g.rid[rr], rk)
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
        assert self.meta["z"] == T.Z, f"{d} holds z{self.meta['z']} tiles; set OPENQUESTS_TILE_Z={self.meta['z']}"
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


# --- the day's update ----------------------------------------------------------------------------
#
# The tiles a day changes are rebuilt from a working set: the old payloads of every tile the day reaches (they hold
# every object that stays), the relation store's old blobs of the relations it reaches, and the diff over them; the
# tile rule (tile_pairs) is run again on that set and only the reached tiles are written, into a new generation.
# A tile is reached through the old and new tiles of: each changed node (its own place), each changed way and each
# way holding a changed node (found in that node's old home tile, which holds every way with a node there: no way
# index), and each relation that changed or has such a way or node as member.

class Objs:
    """objects of one type as columns: `fix` (name -> one value per object, "id" among them) and `var` (name ->
    (lengths, data): a variable-length piece per object)"""

    def __init__(self, fix: dict, var: dict):
        self.fix, self.var = fix, var

    def __len__(self):
        return len(self.fix["id"])

    def select(self, rows):
        rows = np.asarray(rows, np.int64)
        var = {}
        for k, (lens, data) in self.var.items():
            o = offsets(lens)
            ln, d = gather(o, rows, data)
            var[k] = (ln.astype(np.int64), d)
        return Objs({k: v[rows] for k, v in self.fix.items()}, var)

    @staticmethod
    def concat(parts: list["Objs"]) -> "Objs":
        parts = [p for p in parts if p is not None]
        fix = {k: np.concatenate([p.fix[k] for p in parts]) for k in parts[0].fix}
        var = {k: (np.concatenate([p.var[k][0] for p in parts]), np.concatenate([p.var[k][1] for p in parts]))
               for k in parts[0].var}
        return Objs(fix, var)

    def first_of_each(self, prefer=None) -> "Objs":
        """one object per id, sorted by id; with `prefer` (bool per object) a preferred copy wins"""
        ids = self.fix["id"]
        order = np.lexsort((~prefer, ids)) if prefer is not None else np.argsort(ids, kind="stable")
        _, first = np.unique(ids[order], return_index=True)
        return self.select(order[first])

    def without(self, ids) -> "Objs":
        return self.select(np.flatnonzero(~np.isin(self.fix["id"], np.asarray(ids, np.int64))))


def tile_objs(p) -> tuple[Objs, Objs, Objs]:
    """a decoded tile's nodes, ways and relations as Objs"""
    nid, lat, lon, tpos, tver, tts, ntl, ntb = p["n"]
    n = len(nid)
    tagged = np.zeros(n, bool)
    tagged[tpos] = True
    ver, ts, tl = np.ones(n, np.int32), np.zeros(n, np.int64), np.zeros(n, np.int64)
    ver[tpos], ts[tpos], tl[tpos] = tver, tts, ntl
    nodes = Objs({"id": nid, "lat7": lat.astype(np.int32), "lon7": lon.astype(np.int32), "tagged": tagged, "ver": ver,
                  "ts": ts}, {"tags": (tl, ntb)})
    wid, wver, wts, wnref, wrefs, wtl, wtb = p["w"]
    ways = Objs({"id": wid, "ver": wver, "ts": wts}, {"refs": (wnref.astype(np.int64), wrefs),
                                                      "tags": (wtl.astype(np.int64), wtb)})
    rid, rver, rts, rnmem, rmt, rmref, rrl, rroles, rtl, rtb = p["r"]
    cs, mo = offsets(rrl), offsets(rnmem)
    rbytes = cs[mo[1:]] - cs[mo[:-1]]
    rels = Objs({"id": rid, "ver": rver, "ts": rts}, {"mtype": (rnmem.astype(np.int64), rmt),
                                                      "mref": (rnmem.astype(np.int64), rmref),
                                                      "rlen": (rnmem.astype(np.int64), rrl),
                                                      "roles": (rbytes, rroles), "tags": (rtl.astype(np.int64), rtb)})
    return nodes, ways, rels


def empty_nodes():
    z = np.zeros(0, np.int64)
    return Objs({"id": z, "lat7": z.astype(np.int32), "lon7": z.astype(np.int32), "tagged": z.astype(bool),
                 "ver": z.astype(np.int32), "ts": z}, {"tags": (z, z.astype(np.uint8))})


def plain_nodes(ids, lat7, lon7):
    n = len(ids)
    return Objs({"id": np.asarray(ids, np.int64), "lat7": np.asarray(lat7, np.int32), "lon7": np.asarray(lon7, np.int32),
                 "tagged": np.zeros(n, bool), "ver": np.ones(n, np.int32), "ts": np.zeros(n, np.int64)},
                {"tags": (np.zeros(n, np.int64), np.zeros(0, np.uint8))})


class MiniGeom(T.Geom):
    """Geom over a working set, not a clip"""

    def __init__(self, nodes: Objs, ways: Objs, rels: Objs):
        self.nid, self.lat7, self.lon7 = nodes.fix["id"], nodes.fix["lat7"], nodes.fix["lon7"]
        self.nfx, self.nfy = T.frac_xy(self.lat7 / 1e7, self.lon7 / 1e7)
        self.nkey = T.key_of(np.floor(self.nfx), np.floor(self.nfy))
        self.wid = ways.fix["id"]
        self.woffs = offsets(ways.var["refs"][0])
        refs = ways.var["refs"][1]
        if len(self.nid):
            ri = np.minimum(np.searchsorted(self.nid, refs), len(self.nid) - 1)
            self.wrefs = np.where(self.nid[ri] == refs, ri, -1).astype(np.int64)
        else:
            self.wrefs = np.full(len(refs), -1, np.int64)
        self.wref_ids = refs
        self.rid = rels.fix["id"]
        self.roffs = offsets(rels.var["mtype"][0])
        self.mtype, self.mref = rels.var["mtype"][1], rels.var["mref"][1]
        self._way_tiles()


class MiniClip(Clip):
    def __init__(self, nodes: Objs, ways: Objs, rels: Objs):
        g = self.g = MiniGeom(nodes, ways, rels)
        self.tn_row = np.flatnonzero(nodes.fix["tagged"])
        self.tagged_of = np.full(len(g.nid), -1, np.int32)
        self.tagged_of[self.tn_row] = np.arange(len(self.tn_row), dtype=np.int32)
        self.tn_ver, self.tn_ts = nodes.fix["ver"][self.tn_row], nodes.fix["ts"][self.tn_row]
        tl, tb = nodes.var["tags"]
        self.tn_toff, self.tn_tags = offsets(tl[self.tn_row]), tb  # untagged nodes have no tag bytes
        self.w_ver, self.w_ts = ways.fix["ver"], ways.fix["ts"]
        self.w_toff, self.w_tags = offsets(ways.var["tags"][0]), ways.var["tags"][1]
        self.r_ver, self.r_ts = rels.fix["ver"], rels.fix["ts"]
        self.r_toff, self.r_tags = offsets(rels.var["tags"][0]), rels.var["tags"][1]
        self.r_roff, self.r_roles = offsets(rels.var["rlen"][1]), rels.var["roles"][1]
        self.r_kept = np.zeros(len(g.rid), bool)
        for i in range(len(g.rid)):
            b = self.r_tags[self.r_toff[i]:self.r_toff[i + 1]].tobytes()
            self.r_kept[i] = bool(b) and not ignore_relation(parse_tags(b))


def read_osc(path: Path):
    """the last version of every object in a day diff: Objs of the visible ones, and the ids of all (deleted too)"""
    import osmium
    from array import array
    t = time.time()
    nodes, ways, rels = {}, {}, {}
    tm = {"n": 0, "w": 1, "r": 2}
    for o in osmium.FileProcessor(str(path)):
        tags = "".join(f"{x.k}\0{x.v}\0" for x in o.tags).encode()
        ts = int(o.timestamp.timestamp())
        if o.is_node():
            ok = o.visible and o.location.valid()
            nodes[o.id] = (o.version, ts, tags, int(round(o.location.lat * 1e7)), int(round(o.location.lon * 1e7))) if ok else None
        elif o.is_way():
            ways[o.id] = (o.version, ts, tags, [n.ref for n in o.nodes]) if o.visible else None
        else:
            rels[o.id] = (o.version, ts, tags, [(tm[m.type], m.ref, m.role.encode()) for m in o.members]) if o.visible else None
    log(f"diff {path.name}: {len(nodes):,} nodes, {len(ways):,} ways, {len(rels):,} relations in {time.time() - t:.0f} s")

    def node_objs(d):
        ids = np.array(sorted(d), np.int64)
        tl = np.array([len(d[i][2]) for i in ids.tolist()], np.int64)
        return Objs({"id": ids, "lat7": np.array([d[i][3] for i in ids.tolist()], np.int32),
                     "lon7": np.array([d[i][4] for i in ids.tolist()], np.int32), "tagged": tl > 0,
                     "ver": np.array([d[i][0] for i in ids.tolist()], np.int32),
                     "ts": np.array([d[i][1] for i in ids.tolist()], np.int64)},
                    {"tags": (tl, np.frombuffer(b"".join(d[i][2] for i in ids.tolist()), np.uint8))})

    def way_objs(d):
        ids = np.array(sorted(d), np.int64)
        lst = [d[i] for i in ids.tolist()]
        refs = array("q")
        for x in lst:
            refs.extend(x[3])
        return Objs({"id": ids, "ver": np.array([x[0] for x in lst], np.int32), "ts": np.array([x[1] for x in lst], np.int64)},
                    {"refs": (np.array([len(x[3]) for x in lst], np.int64), np.frombuffer(refs, np.int64)),
                     "tags": (np.array([len(x[2]) for x in lst], np.int64), np.frombuffer(b"".join(x[2] for x in lst), np.uint8))})

    def rel_objs(d):
        ids = np.array(sorted(d), np.int64)
        lst = [d[i] for i in ids.tolist()]
        ms = [m for x in lst for m in x[3]]
        nmem = np.array([len(x[3]) for x in lst], np.int64)
        return Objs({"id": ids, "ver": np.array([x[0] for x in lst], np.int32), "ts": np.array([x[1] for x in lst], np.int64)},
                    {"mtype": (nmem, np.array([m[0] for m in ms], np.int8)), "mref": (nmem, np.array([m[1] for m in ms], np.int64)),
                     "rlen": (nmem, np.array([len(m[2]) for m in ms], np.int32)),
                     "roles": (np.array([sum(len(m[2]) for m in x[3]) for x in lst], np.int64),
                               np.frombuffer(b"".join(m[2] for m in ms), np.uint8)),
                     "tags": (np.array([len(x[2]) for x in lst], np.int64), np.frombuffer(b"".join(x[2] for x in lst), np.uint8))})

    vis = lambda d: {k: v for k, v in d.items() if v is not None}  # noqa: E731
    return ((np.array(sorted(nodes), np.int64), node_objs(vis(nodes))), (np.array(sorted(ways), np.int64), way_objs(vis(ways))),
            (np.array(sorted(rels), np.int64), rel_objs(vis(rels))))


class NodeTable:
    """the node store before the day (here a clip's nodes.idx; the world's is planet.loc, read before save())"""

    def __init__(self, d: Path):
        a = np.memmap(d / "nodes.idx", dtype=[("id", "<u8"), ("x", "<i4"), ("y", "<i4")], mode="r")
        ids = a["id"]
        lo, hi = 0, len(a)
        while lo < hi:
            mid = (lo + hi) // 2
            if ids[mid] == 0:
                hi = mid
            else:
                lo = mid + 1
        self.a, self.n = a, lo

    def get(self, ids):
        ids = np.asarray(ids, np.int64)
        if not len(ids) or not self.n:
            return np.zeros(len(ids), np.int32), np.zeros(len(ids), np.int32), np.zeros(len(ids), bool)
        keys = self.a["id"][:self.n]
        i = np.minimum(np.searchsorted(keys, ids.astype(np.uint64)), self.n - 1)
        found = keys[i].astype(np.int64) == ids
        return np.where(found, self.a["y"][i], 0), np.where(found, self.a["x"][i], 0), found


def pairs_of(p: np.ndarray, ids) -> dict:
    """id -> set of tile keys, from a sorted PAIR array"""
    ids = np.unique(np.asarray(ids, np.int64))
    lo, hi = np.searchsorted(p["id"], ids, "left"), np.searchsorted(p["id"], ids, "right")
    return {int(i): set(p["key"][a:b].tolist()) for i, a, b in zip(ids, lo, hi)}


def dilate(keys: np.ndarray, r: int = 1) -> np.ndarray:
    x, y = keys >> T.Z, keys & (T.NT - 1)
    out = [T.key_of(x + dx, y + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1)]
    return np.unique(np.concatenate(out))


def region_of(st, polygon: Path | None) -> np.ndarray:
    """The tiles a clip's store answers for, so the planet diff's changes elsewhere stay out (a world store has no
    such edge): the tiles it holds (a way reaching out of the polygon is held whole, and its far nodes move too) and
    the tiles under each part of the clip's polygon (new ground inside); without the polygon, those near its tiles."""
    if polygon is None:
        return dilate(st.idx["key"], 1 << max(0, T.Z - 14))
    out = []
    for f in json.loads(polygon.read_text(encoding="utf-8"))["features"]:
        geo = f["geometry"]
        parts = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
        for part in parts:
            ring = np.array(part[0])
            out.append(T.box_tiles(ring[:, 1].min(), ring[:, 0].min(), ring[:, 1].max(), ring[:, 0].max()))
    return np.unique(np.concatenate(out + [st.idx["key"]]))


def update(sd: Path, diff: Path, before: Path, day: str, polygon: Path | None = None):
    t0 = time.time()
    st = Store(sd)
    G = st.gen
    NG = G + 1
    wt, rt = np.load(sd / f"wtiles-{G:04d}.npy"), np.load(sd / f"rtiles-{G:04d}.npy")
    region = region_of(st, polygon)
    (cn_all, dn), (cw_all, dw), (cr_all, dr) = read_osc(diff)
    t_diff = time.time() - t0
    bt = NodeTable(before)
    stats = {}
    t1 = time.time()

    def key_of7(lat7, lon7):
        fx, fy = T.frac_xy(np.asarray(lat7) / 1e7, np.asarray(lon7) / 1e7)
        return T.key_of(np.floor(fx), np.floor(fy))

    dn_ids = dn.fix["id"]

    def after_pos(ids):
        """node places after the day: the diff's (none for a deleted node), else the store before"""
        ids = np.asarray(ids, np.int64)
        lat, lon, found = bt.get(ids)
        in_cn = np.isin(ids, cn_all)
        if in_cn.any():
            sub = ids[in_cn]
            if len(dn_ids):
                j = np.minimum(np.searchsorted(dn_ids, sub), len(dn_ids) - 1)
                vis = dn_ids[j] == sub
                lat[in_cn] = np.where(vis, dn.fix["lat7"][j], 0)
                lon[in_cn] = np.where(vis, dn.fix["lon7"][j], 0)
                found[in_cn] = vis
            else:
                found[in_cn] = False
        return lat, lon, found

    decoded: dict[int, tuple] = {}

    def dec(keys):
        for k in keys:
            k = int(k)
            if k in decoded:
                continue
            buf = st.tile(k)
            decoded[k] = tile_objs(decode_tile(buf)) if buf is not None else None

    # changed nodes: old and new home tiles, inside the store's region
    olat, olon, ofound = bt.get(cn_all)
    okey = np.where(ofound, key_of7(olat, olon), -1)
    nlat, nlon, nfound = after_pos(cn_all)
    nkey = np.where(nfound, key_of7(nlat, nlon), -1)
    keep = np.isin(okey, region) | np.isin(nkey, region)
    cn, okey, nkey = cn_all[keep], okey[keep], nkey[keep]
    stats["changedNodes"] = len(cn)
    # ways holding a changed node: in the node's old home tile
    homes = np.unique(okey[okey >= 0])
    dec(homes)
    parents = set()
    for k in homes.tolist():
        if decoded[k] is None:
            continue
        w = decoded[k][1]
        lens, refs = w.var["refs"]
        hit = np.isin(refs, cn)
        if hit.any():
            way_of = np.repeat(np.arange(len(w)), lens)
            parents |= set(w.fix["id"][np.unique(way_of[hit])].tolist())
    # changed ways reaching the region: old tiles from the index, new ones from their refs' places after the day
    had_tiles = cw_all[np.isin(cw_all, wt["id"])]
    dw_ids = dw.fix["id"]
    ro = offsets(dw.var["refs"][0])
    lat, lon, f = after_pos(dw.var["refs"][1])
    inreg = np.zeros(len(f), bool)
    inreg[f] = np.isin(key_of7(lat[f], lon[f]), region)
    cs = offsets(inreg.astype(np.int64))
    reaches = (cs[ro[1:]] - cs[ro[:-1]]) > 0
    cw = np.union1d(had_tiles, dw_ids[reaches])
    parents = np.array(sorted(parents - set(cw.tolist())), np.int64)
    stats["changedWays"], stats["parentWays"] = len(cw), len(parents)
    moved = np.concatenate([cw, parents])
    old_w = pairs_of(wt, moved)
    # one old tile of each (it holds the old version, its nodes, and every relation it is a member of), and the old
    # home tiles of the nodes of the new versions (their tagged attributes)
    dec([min(s) for s in old_w.values() if s])
    jv = np.flatnonzero(np.isin(dw_ids, cw))
    new_refs = np.unique(np.concatenate([dw.var["refs"][1][ro[j]:ro[j + 1]] for j in jv])) if len(jv) else np.zeros(0, np.int64)
    blat, blon, bfound = bt.get(new_refs)
    # the changed relations' member nodes too: an untagged one no tile held must still place its relation
    rel_nodes = np.unique(dr.var["mref"][1][dr.var["mtype"][1] == 0]) if len(dr) else np.zeros(0, np.int64)
    rlat, rlon, rfound = after_pos(rel_nodes)
    rel_nodes = rel_nodes[rfound][np.isin(key_of7(rlat[rfound], rlon[rfound]), region)]
    needed = np.union1d(new_refs, rel_nodes)
    dec(np.unique(key_of7(blat[bfound], blon[bfound])))
    t_find = time.time() - t1

    # the working set so far, to find the new tiles of the moved ways and the relations they reach
    def working(extra_rel_blobs=()):
        parts = [d for d in decoded.values() if d is not None]
        nodes = Objs.concat([p[0] for p in parts] + [b[0] for b in extra_rel_blobs] + [empty_nodes()])
        ways = Objs.concat([p[1] for p in parts] + [b[1] for b in extra_rel_blobs] + [dw.select(np.zeros(0, np.int64))])
        rels = Objs.concat([p[2] for p in parts] + [dr.select(np.zeros(0, np.int64))])
        nodes = nodes.first_of_each(prefer=nodes.fix["tagged"])
        # the new versions' nodes not in any tile (an untagged node no way held): a place from the store
        have = np.isin(needed, nodes.fix["id"])
        orphan = needed[~have]
        lat, lon, f = bt.get(orphan)
        nodes = Objs.concat([nodes, plain_nodes(orphan[f], lat[f], lon[f])])
        # the diff over them: its objects that reach the store's region
        dn_sub = dn.select(np.flatnonzero(np.isin(dn_ids, np.union1d(cn, needed))))
        dw_sub = dw.select(np.flatnonzero(np.isin(dw_ids, cw)))
        nodes = Objs.concat([nodes.without(cn_all), dn_sub]).first_of_each()
        ways = Objs.concat([ways.first_of_each().without(cw_all), dw_sub]).first_of_each()
        rels = Objs.concat([rels.first_of_each().without(cr_all), dr]).first_of_each()
        return MiniClip(nodes, ways, rels)

    t2 = time.time()
    m = working()
    g = m.g
    new_w = {}
    rows = np.searchsorted(g.wid, moved)
    rows = np.minimum(rows, max(len(g.wid) - 1, 0))
    for wid, r in zip(moved.tolist(), rows.tolist()):
        new_w[wid] = set()
    order = np.argsort(g.wt_way, kind="stable")
    wtw, wtk = g.wt_way[order], g.wt_key[order]
    present = (len(g.wid) > 0) & (g.wid[rows] == moved) if len(g.wid) else np.zeros(len(moved), bool)
    lo, hi = np.searchsorted(wtw, rows, "left"), np.searchsorted(wtw, rows, "right")
    for wid, ok, a, b in zip(moved.tolist(), present.tolist(), lo.tolist(), hi.tolist()):
        if ok:
            new_w[wid] = set(wtk[a:b].tolist())
    # relations reached: changed ones, and those with a moved way or a changed node as member
    nr = len(g.rid)
    rel_of = np.repeat(np.arange(nr), np.diff(g.roffs))
    hit = ((g.mtype == 1) & np.isin(g.mref, moved)) | ((g.mtype == 0) & np.isin(g.mref, cn))
    ar = set(g.rid[np.unique(rel_of[hit])].tolist()) if nr else set()
    old_r_all = pairs_of(rt, cr_all)
    for rid in cr_all.tolist():
        if old_r_all.get(rid):
            ar.add(rid)
    if len(dr):  # a changed relation reaching the region: a member way with tiles, or a member node placed there
        dmo = offsets(dr.var["mtype"][0])
        mt_all, mr_all = dr.var["mtype"][1], dr.var["mref"][1]
        hit_m = (mt_all == 1) & (np.isin(mr_all, moved) | np.isin(mr_all, wt["id"]))
        isn = mt_all == 0
        la, lo_, fd = after_pos(mr_all[isn])
        nreg = np.zeros(int(isn.sum()), bool)
        nreg[fd] = np.isin(key_of7(la[fd], lo_[fd]), region)
        hit_m[isn] = nreg
        cs = offsets(hit_m.astype(np.int64))
        ar |= set(dr.fix["id"][(cs[dmo[1:]] - cs[dmo[:-1]]) > 0].tolist())
    ar = np.array(sorted(ar), np.int64)
    stats["relations"] = len(ar)
    # the tiles reached, and why: a changed node's home, old and new; a moved way's tiles, old and new; a changed
    # relation's tiles, old and new (its record is in all of them). An unchanged relation's tiles change only where a
    # moved member way came or went, which are reached already.
    changed_r = np.intersect1d(ar, cr_all)
    old_r = pairs_of(rt, changed_r)
    why = {"node": set(okey[okey >= 0].tolist()) | set(nkey[nkey >= 0].tolist()), "way": set(), "relation": set()}
    for s in list(old_w.values()) + list(new_w.values()):
        why["way"] |= s
    for s in old_r.values():
        why["relation"] |= s
    for rid in np.intersect1d(ar, dr.fix["id"]).tolist():
        j = np.searchsorted(g.rid, rid)
        if j < nr and g.rid[j] == rid and m.r_kept[j]:  # a relation the app ignores is in no tile
            ms = slice(g.roffs[j], g.roffs[j + 1])
            mw = g.mref[ms][g.mtype[ms] == 1]
            for w_ in mw.tolist():
                why["relation"] |= new_w.get(w_, set())
            for s in pairs_of(wt, mw[~np.isin(mw, moved)]).values():
                why["relation"] |= s
            mn = g.mref[ms][g.mtype[ms] == 0]
            la, lo_, fd = after_pos(mn)
            why["relation"] |= set(key_of7(la[fd], lo_[fd]).tolist())
    reach = np.array(sorted(why["node"] | why["way"] | why["relation"]), np.int64)
    reach = reach[np.isin(reach, region)]
    dec(reach)
    # the relation store's old blobs of the relations reached: their far member ways
    blobs = []
    for rid in ar.tolist():
        buf = st.relation(rid)
        if buf is None:
            continue
        c = unpack_cols(buf)
        wid, wver, wts, wnref, wrefs, wtl, wtb = undelta(c[0]), c[1], c[2], c[3], undelta(c[4]), c[5], c[6]
        ways_b = Objs({"id": wid, "ver": wver, "ts": wts}, {"refs": (wnref.astype(np.int64), wrefs),
                                                            "tags": (wtl.astype(np.int64), wtb)})
        blobs.append((plain_nodes(undelta(c[7]), undelta(c[8]), undelta(c[9])), ways_b))
    t_reach = time.time() - t2
    t3 = time.time()
    m = working(blobs)
    g = m.g
    (nk, nrw), (wk, wr), (rk, rr) = tile_pairs(m)
    t_rule = time.time() - t3
    # write the reached tiles into the new generation
    t4 = time.time()
    nb = [np.searchsorted(nk, reach, "left"), np.searchsorted(nk, reach, "right")]
    wb = [np.searchsorted(wk, reach, "left"), np.searchsorted(wk, reach, "right")]
    rb = [np.searchsorted(rk, reach, "left"), np.searchsorted(rk, reach, "right")]
    new_entries = []
    unchanged, changed = [], set()
    off = 0
    with open(sd / f"pack-{NG:04d}.bin", "wb") as f:
        for i, k in enumerate(reach.tolist()):
            if nb[0][i] == nb[1][i] and wb[0][i] == wb[1][i] and rb[0][i] == rb[1][i]:
                changed.add(k)
                continue  # the tile is empty now
            buf = pack_cols(m.node_cols(nrw[nb[0][i]:nb[1][i]]) + m.way_cols(wr[wb[0][i]:wb[1][i]])
                            + m.rel_cols(rr[rb[0][i]:rb[1][i]]))
            old = st.tile(k)
            if old is not None and zstd.decompress(old) == zstd.decompress(buf):
                unchanged.append(k)  # reached, but the same: the old entry stays
                continue
            changed.add(k)
            f.write(buf)
            new_entries.append((k, NG, off, len(buf)))
            off += len(buf)
    keep_idx = st.idx[~np.isin(st.idx["key"], np.setdiff1d(reach, np.array(unchanged, np.int64)))]
    ne = np.array(new_entries, IDX) if new_entries else np.zeros(0, IDX)
    idx = np.sort(np.concatenate([keep_idx, ne]), order="key")
    np.save(sd / f"idx-{NG:04d}.npy", idx)
    # the way and relation tile indexes
    moved_rows = np.searchsorted(g.wid, moved)
    moved_rows = np.minimum(moved_rows, max(len(g.wid) - 1, 0))
    mrows = moved_rows[(g.wid[moved_rows] == moved)] if len(g.wid) else moved_rows[:0]
    sel = np.isin(wr, mrows)
    wt2 = wt[~np.isin(wt["id"], np.concatenate([moved, cw_all]))]
    add = np.zeros(int(sel.sum()), PAIR)
    add["id"], add["key"] = g.wid[wr[sel]], wk[sel]
    np.save(sd / f"wtiles-{NG:04d}.npy", np.sort(np.concatenate([wt2, add]), order=["id", "key"]))
    # a reached relation's tiles: the working set's inside the day's reach, the old ones outside it (a far member node
    # or way is not in the working set, and a tile not reached did not change)
    ar_rows = np.flatnonzero(np.isin(g.rid, ar))
    sel = np.isin(rr, ar_rows) & np.isin(rk, reach)
    gone = np.isin(rt["id"], np.concatenate([ar, cr_all]))
    keep_far = gone & np.isin(rt["id"], g.rid[ar_rows[m.r_kept[ar_rows]]]) & ~np.isin(rt["key"], reach)
    add = np.zeros(int(sel.sum()), PAIR)
    add["id"], add["key"] = g.rid[rr[sel]], rk[sel]
    np.save(sd / f"rtiles-{NG:04d}.npy", np.sort(np.concatenate([rt[~gone | keep_far], add]), order=["id", "key"]))
    # the relation store: the reached relations' blobs again, from the working set
    rentries = []
    roff = 0
    with open(sd / f"rel-{NG:04d}.bin", "wb") as f:
        for j in ar_rows.tolist():
            if not m.r_kept[j]:
                continue
            ms = slice(g.roffs[j], g.roffs[j + 1])
            mw = g.mref[ms][g.mtype[ms] == 1]
            wi = np.minimum(np.searchsorted(g.wid, mw), max(len(g.wid) - 1, 0))
            wi = np.unique(wi[g.wid[wi] == mw])
            u = np.unique(g.way_node_rows(wi))
            buf = pack_cols(m.way_cols(wi) + [delta(g.nid[u]), delta(g.lat7[u]).astype(np.int32), delta(g.lon7[u]).astype(np.int32)])
            f.write(buf)
            rentries.append((int(g.rid[j]), NG, roff, len(buf)))
            roff += len(buf)
    rkeep = st.ridx[~np.isin(st.ridx["key"], np.concatenate([ar, cr_all]))]
    re_ = np.array(rentries, IDX) if rentries else np.zeros(0, IDX)
    np.save(sd / f"relidx-{NG:04d}.npy", np.sort(np.concatenate([rkeep, re_]), order="key"))
    t_write = time.time() - t4
    in_store = set(st.idx["key"].tolist())
    stats["reachedBy"] = {c: {"tiles": len(s & set(reach.tolist())), "changed": len(s & changed),
                              "changedBytes": int(sum(int(st.idx["len"][np.searchsorted(st.idx["key"], k)]) for k in s & changed
                                                      if k in in_store))} for c, s in why.items()}
    stats["tilesUnchanged"] = len(unchanged)
    stats.update({"gen": NG, "day": day, "diff": str(diff), "tilesReached": len(reach), "tilesWritten": len(new_entries),
                  "tilesNew": int((~np.isin(ne["key"], st.idx["key"])).sum()),
                  "tilesDropped": int((np.isin(reach, st.idx["key"]) & ~np.isin(reach, ne["key"])
                                       & ~np.isin(reach, np.array(unchanged, np.int64))).sum()),
                  "bytes": off, "relBytes": roff, "relBlobs": len(rentries), "tilesDecoded": len(decoded),
                  "secondsDiff": round(t_diff, 1), "secondsFind": round(t_find, 1), "secondsReach": round(t_reach, 1),
                  "secondsRule": round(t_rule, 1), "secondsWrite": round(t_write, 1),
                  "seconds": round(time.time() - t0, 1)})
    st.meta["generations"].append(stats)
    (sd / "store.json").write_text(json.dumps(st.meta, indent=1))
    log(f"update to {day}: {stats}")


def compare_stores(a: Path, b: Path, keys=None, ga: int = -1, gb: int = -1) -> dict:
    """two stores tile by tile (the decompressed payloads, byte for byte); keys: only these tiles"""
    sa, sb = Store(a, ga), Store(b, gb)
    ka, kb = sa.idx["key"], sb.idx["key"]
    allk = np.union1d(ka, kb) if keys is None else np.unique(keys)
    same = differ = only_a = only_b = 0
    examples = []
    for k in allk.tolist():
        x, y = sa.tile(k), sb.tile(k)
        if x is None and y is None:
            continue
        if x is None:
            only_b += 1
            continue
        if y is None:
            only_a += 1
            continue
        if zstd.decompress(x) == zstd.decompress(y):
            same += 1
        else:
            differ += 1
            if len(examples) < 5:
                pa, pb = decode_tile(x), decode_tile(y)
                d = {}
                for t, i in (("n", 0), ("w", 0), ("r", 0)):
                    ia, ib = set(pa[t][i].tolist()), set(pb[t][i].tolist())
                    d[t] = {"onlyA": sorted(ia - ib)[:5], "onlyB": sorted(ib - ia)[:5], "both": len(ia & ib)}
                examples.append({"key": k, "xy": [k >> T.Z, k & (T.NT - 1)], **d})
    return {"tiles": len(allk), "same": same, "differ": differ, "onlyA": only_a, "onlyB": only_b, "examples": examples}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cut", "read", "update", "compare"])
    ap.add_argument("--diff", type=Path)
    ap.add_argument("--before", type=Path)
    ap.add_argument("--a", type=Path)
    ap.add_argument("--b", type=Path)
    ap.add_argument("--polygon", type=Path, help="update: the clip's polygon, the store's region")
    ap.add_argument("--under", action="store_true", help="compare: only the tiles under the cities' boxes and ring")
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
    elif o.cmd == "update":
        update(o.store, o.diff, o.before, o.day, o.polygon)
    elif o.cmd == "compare":
        keys = T.tiles_of(T.city_boxes(o.cities, o.base), o.ring) if o.under else None
        print(json.dumps(compare_stores(o.a, o.b, keys), indent=1))
    else:
        s = Store(o.store, o.gen)
        keys = T.tiles_of(T.city_boxes(o.cities, o.base), o.ring)
        st = join(s, keys, o.out, o.stamp)
        Path(str(o.out) + ".json").write_text(json.dumps(st, indent=1))


if __name__ == "__main__":
    main()
