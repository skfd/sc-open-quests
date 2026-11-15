"""For relation-store differences: does each relation touch the clip polygon's edge (its tiles, either store)?"""
import json, math, sys
from pathlib import Path
import numpy as np
from compression import zstd
from shapely.geometry import box, shape
from shapely.ops import unary_union
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tilestore as S, tiles as T
poly = unary_union([shape(f["geometry"]) for f in json.loads(Path(sys.argv[3]).read_text())["features"]])
def tile_box(k):
    x, y, n = k >> T.Z, k & (T.NT - 1), T.NT
    lat = lambda yy: math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n))))
    return box(x / n * 360 - 180, lat(y + 1), (x + 1) / n * 360 - 180, lat(y))
a, b = Path(sys.argv[1]), Path(sys.argv[2])
sa, sb = S.Store(a), S.Store(b)
ra = np.load(a / f"rtiles-{sa.gen:04d}.npy"); rb = np.load(b / f"rtiles-{sb.gen:04d}.npy")
ka, kb = sa.ridx["key"], sb.ridx["key"]
both = np.intersect1d(ka, kb)
bad = [int(r) for r in both.tolist() if zstd.decompress(sa.relation(r)) != zstd.decompress(sb.relation(r))]
bad += np.setxor1d(ka, kb).tolist()
pa, pb = S.pairs_of(ra, bad), S.pairs_of(rb, bad)
out = {"edge": 0, "inside": 0, "noTiles": 0}
for r in bad:
    ks = pa.get(r, set()) | pb.get(r, set())
    if not ks:
        out["noTiles"] += 1; continue
    inside = all(poly.contains(tile_box(k)) for k in ks)
    out["inside" if inside else "edge"] += 1
    if inside: print("inside:", r, sorted(ks)[:5])
print(out)
