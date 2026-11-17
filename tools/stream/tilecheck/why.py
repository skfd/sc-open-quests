"""Every differing or planet-only tile of a subcmp run: the planet's tile with the ways the clip lacks (and the
nodes only those ways bring) taken out must equal the clip's tile object for object.
  why.py subcmp.json clipStore planetStore [planetGen]"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tilestore as TS  # noqa: E402


def ragged(lengths, data):
    ends = np.cumsum(np.asarray(lengths, np.int64))
    starts = ends - np.asarray(lengths, np.int64)
    return [data[a:b] for a, b in zip(starts.tolist(), ends.tolist())]


def objects(buf):
    if buf is None:
        return {}, {}, {}
    t = TS.decode_tile(buf)
    nid, lat, lon, tpos, tver, tts, ntl, ntb = t["n"]
    assert int(np.sum(ntl)) == len(ntb), "node tag bytes"
    nodes = {i: (a, b, None) for i, a, b in zip(nid.tolist(), lat.tolist(), lon.tolist())}
    for p, v, s, tg in zip(tpos.tolist(), tver.tolist(), tts.tolist(), ragged(ntl, ntb)):
        i = int(nid[p])
        nodes[i] = nodes[i][:2] + ((v, s, bytes(tg)),)
    wid, wver, wts, wnref, wrefs, wtl, wtb = t["w"]
    assert int(np.sum(wtl)) == len(wtb) and int(np.sum(wnref)) == len(wrefs), "way columns"
    ways = {i: (v, s, tuple(r.tolist()), bytes(tg)) for i, v, s, r, tg in
            zip(wid.tolist(), wver.tolist(), wts.tolist(), ragged(wnref, wrefs), ragged(wtl, wtb))}
    rid, rver, rts, rnmem, rmt, rmref, rrl, rroles, rtl, rtb = t["r"]
    assert int(np.sum(rnmem)) == len(rmt) == len(rmref) == len(rrl), "relation members"
    roles = ragged(rrl, rroles)
    rels = {}
    for j, (i, v, s, m, tg) in enumerate(zip(rid.tolist(), rver.tolist(), rts.tolist(), ragged(rnmem, np.arange(len(rmt))),
                                              ragged(rtl, rtb))):
        rels[i] = (v, s, tuple((int(rmt[k]), int(rmref[k]), bytes(roles[k])) for k in m.tolist()), bytes(tg))
    return nodes, ways, rels


def main():
    d = json.load(open(sys.argv[1]))
    c, p = TS.Store(Path(sys.argv[2]), 0), TS.Store(Path(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 0)
    keys = d["differKeys"] + d["onlyKeys"]
    extra_ways, bad = set(), []
    for k in keys:
        cn, cw, cr = objects(c.tile(k))
        pn, pw, pr = objects(p.tile(k))
        xw = set(pw) - set(cw)
        extra_ways |= xw
        brought = {r for w in xw for r in pw[w][2]}
        xn = set(pn) - set(cn)
        ok = (not (set(cw) - set(pw)) and not (set(cn) - set(pn)) and xn <= brought
              and all(pw[w] == cw[w] for w in cw) and all(pn[n] == cn[n] for n in cn) and pr == cr)
        if not ok:
            bad.append(k)
    print(json.dumps({"tiles": len(keys), "differ": len(d["differKeys"]), "onlyPlanet": len(d["onlyKeys"]),
                      "explained": len(keys) - len(bad), "notExplained": bad[:20],
                      "extraWays": sorted(extra_ways)}, indent=1))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
