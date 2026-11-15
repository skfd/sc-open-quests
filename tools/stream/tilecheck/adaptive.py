"""Smaller tiles, estimated from whole stores: uniform z14, z15, z16, and an adaptive split (a z14 tile over a threshold
held as its 16 z16 children). Per layout: tiles, bytes, the day's write (generation 1's own entries), and the bytes read
for the day's rectangles and ring. Usage: adaptive.py ROOT (.scratch/tiles) CITIES"""
import json
import math
import sys
from pathlib import Path

import numpy as np

root, cities = Path(sys.argv[1]), Path(sys.argv[2])
base = Path(__file__).resolve().parents[3]
M_LAT = 111_320.0


def key_xy(keys, z):
    return keys >> z, keys & ((1 << z) - 1)


def tiles_under(z, ring=300.0):
    n = 1 << z
    out = set()
    for c in json.loads(cities.read_text(encoding="utf-8"))["cities"]:
        b = json.loads((base / c["boundary"]).read_text(encoding="utf-8"))["bounds"]
        s, w, nn, e = b["minlat"], b["minlon"], b["maxlat"], b["maxlon"]
        d_lat = ring / M_LAT
        d_lon = ring / (M_LAT * math.cos(math.radians(min(85.0, max(abs(s), abs(nn))))))
        s, w, nn, e = s - d_lat, w - d_lon, nn + d_lat, e + d_lon

        def fx(lon):
            return int((lon + 180) / 360 * n)

        def fy(lat):
            r = math.radians(lat)
            return int((1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n)
        for x in range(fx(w), fx(e) + 1):
            for y in range(fy(nn), fy(s) + 1):
                out.add((x << z) | y)
    return np.array(sorted(out), np.int64)


def load(d: Path, z: int):
    i0, i1 = np.load(d / "idx-0000.npy"), np.load(d / "idx-0001.npy")
    m = json.loads((d / "store.json").read_text())
    assert m["z"] == z
    w = i1[i1["pack"] == 1]
    return {"keys": i0["key"], "len": i0["len"].astype(np.int64), "wkeys": w["key"], "wlen": w["len"].astype(np.int64),
            "gen1": m["generations"][1]}


stores = {}
for z, d in ((14, root / "store"), (15, root / "store-z15"), (16, root / "store-z16")):
    if (d / "idx-0001.npy").exists():
        stores[z] = load(d, z)
rows = []
for z, s in stores.items():
    under = tiles_under(z)
    read = s["len"][np.isin(s["keys"], under)].sum()
    rows.append({"layout": f"z{z}", "tiles": len(s["keys"]), "bytes": int(s["len"].sum()), "written": len(s["wkeys"]),
                 "writtenBytes": int(s["wlen"].sum()), "readTiles": int(np.isin(s["keys"], under).sum()), "readBytes": int(read),
                 "updateSeconds": s["gen1"]["seconds"]})
if 14 in stores and 16 in stores:
    a, b = stores[14], stores[16]
    # each z16 tile's z14 parent
    x16, y16 = key_xy(b["keys"], 16)
    par = ((x16 >> 2) << 14) | (y16 >> 2)
    wx, wy = key_xy(b["wkeys"], 16)
    wpar = ((wx >> 2) << 14) | (wy >> 2)
    under14, under16 = tiles_under(14), tiles_under(16)
    rx, ry = key_xy(under16, 16)
    for thr in (64 << 10, 128 << 10, 256 << 10, 512 << 10):
        big = a["keys"][a["len"] > thr]
        small_m = ~np.isin(a["keys"], big)
        child_m = np.isin(par, big)
        wsmall = ~np.isin(a["wkeys"], big)
        wchild = np.isin(wpar, big)
        r14 = np.isin(a["keys"], under14) & small_m
        r16 = np.isin(b["keys"], under16) & child_m
        rows.append({"layout": f"z14, z16 over {thr >> 10} KB", "tiles": int(small_m.sum() + child_m.sum()),
                     "bytes": int(a["len"][small_m].sum() + b["len"][child_m].sum()),
                     "written": int(wsmall.sum() + wchild.sum()),
                     "writtenBytes": int(a["wlen"][wsmall].sum() + b["wlen"][wchild].sum()),
                     "readTiles": int(r14.sum() + r16.sum()), "readBytes": int(a["len"][r14].sum() + b["len"][r16].sum()),
                     "bigZ14Tiles": len(big)})
for r in rows:
    print(json.dumps(r))
print()
print(f"{'layout':24} {'tiles':>8} {'GB':>6} {'written':>8} {'written MB':>11} {'% bytes':>8} {'read tiles':>10} {'read MB':>8}")
for r in rows:
    print(f"{r['layout']:24} {r['tiles']:>8,} {r['bytes'] / 1e9:>6.2f} {r['written']:>8,} {r['writtenBytes'] / 1e6:>11.0f} "
          f"{100 * r['writtenBytes'] / r['bytes']:>7.1f}% {r['readTiles']:>10,} {r['readBytes'] / 1e6:>8.1f}")
