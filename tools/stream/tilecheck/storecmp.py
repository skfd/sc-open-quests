"""Two tile stores, one generation of each, held against each other in stages: the counts store.json records, the
index keys, every tile's decompressed payload, every relation blob, and the way and relation pair indexes.
Written for the Rust cut (tilestore/) against the Python store; exits 1 if anything differs.

  storecmp.py --a S1 --b S2 [--ga 0] [--gb 0]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from compression import zstd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tilestore as TS  # noqa: E402


def gen_meta(d: Path, g: int) -> dict:
    return next(x for x in json.loads((d / "store.json").read_text())["generations"] if x["gen"] == g)


def blobs(sa, sb, ia, ib, prefix):
    ka, kb = ia["key"], ib["key"]
    both = np.intersect1d(ka, kb)
    out = {"a": len(ka), "b": len(kb), "onlyA": int(len(ka) - len(both)), "onlyB": int(len(kb) - len(both)),
           "same": 0, "differ": 0, "examples": []}
    pa, pb = np.searchsorted(ka, both), np.searchsorted(kb, both)
    for k, i, j in zip(both.tolist(), pa.tolist(), pb.tolist()):
        ea, eb = ia[i], ib[j]
        x = sa._read(prefix, int(ea["pack"]), int(ea["off"]), int(ea["len"]))
        y = sb._read(prefix, int(eb["pack"]), int(eb["off"]), int(eb["len"]))
        if zstd.decompress(x) == zstd.decompress(y):
            out["same"] += 1
        else:
            out["differ"] += 1
            if len(out["examples"]) < 5:
                ca, cb = TS.unpack_cols(x), TS.unpack_cols(y)
                cols = [n for n, (p, q) in enumerate(zip(ca, cb)) if len(p) != len(q) or (p != q).any()]
                out["examples"].append({"key": k, "columnsA": len(ca), "columnsB": len(cb), "differingColumns": cols})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=Path, required=True)
    ap.add_argument("--b", type=Path, required=True)
    ap.add_argument("--ga", type=int, default=0)
    ap.add_argument("--gb", type=int, default=0)
    o = ap.parse_args()
    ma, mb = gen_meta(o.a, o.ga), gen_meta(o.b, o.gb)
    res = {"counts": {}}
    bad = False
    for k in ("tiles", "bytes", "relations", "relationWays", "relBytes", "copies"):
        res["counts"][k] = {"a": ma.get(k), "b": mb.get(k)}
    for k in ("tiles", "relations", "relationWays", "copies"):
        bad |= ma.get(k) != mb.get(k)
    sa, sb = TS.Store(o.a, o.ga), TS.Store(o.b, o.gb)
    ia, ib = np.load(o.a / f"idx-{o.ga:04d}.npy"), np.load(o.b / f"idx-{o.gb:04d}.npy")
    res["tiles"] = blobs(sa, sb, ia, ib, "pack")
    ra, rb = np.load(o.a / f"relidx-{o.ga:04d}.npy"), np.load(o.b / f"relidx-{o.gb:04d}.npy")
    res["relationStore"] = blobs(sa, sb, ra, rb, "rel")
    for name in ("wtiles", "rtiles"):
        x, y = np.load(o.a / f"{name}-{o.ga:04d}.npy"), np.load(o.b / f"{name}-{o.gb:04d}.npy")
        same = x.dtype == y.dtype and len(x) == len(y) and bool((x == y).all())
        res[name] = {"a": len(x), "b": len(y), "same": same}
        bad |= not same
    for k in ("tiles", "relationStore"):
        bad |= bool(res[k]["differ"] or res[k]["onlyA"] or res[k]["onlyB"])
    res["equal"] = not bad
    print(json.dumps(res, indent=1))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
