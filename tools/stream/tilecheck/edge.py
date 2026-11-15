"""Which tiles differ between the updated store and the fresh cut, and does each touch the clip polygon's edge?"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from compression import zstd
from shapely.geometry import box, shape
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tilestore as S  # noqa: E402
import tiles as T  # noqa: E402

poly = unary_union([shape(f["geometry"]) for f in json.loads(Path(sys.argv[3]).read_text())["features"]])
edge = poly.boundary


def tile_box(k):
    x, y = k >> T.Z, k & (T.NT - 1)
    n = T.NT

    def lat(yy):
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n))))
    return box(x / n * 360 - 180, lat(y + 1), (x + 1) / n * 360 - 180, lat(y))


sa, sb = S.Store(Path(sys.argv[1])), S.Store(Path(sys.argv[2]))
keys = np.union1d(sa.idx["key"], sb.idx["key"])
kinds = {"differ": [0, 0], "onlyA": [0, 0], "onlyB": [0, 0]}  # [touching the edge or outside, wholly inside]
inside_examples = []
for k in keys.tolist():
    x, y = sa.tile(k), sb.tile(k)
    if x is not None and y is not None and zstd.decompress(x) == zstd.decompress(y):
        continue
    kind = "differ" if x is not None and y is not None else ("onlyA" if x is not None else "onlyB")
    b = tile_box(k)
    inner = poly.contains(b)
    kinds[kind][1 if inner else 0] += 1
    if inner and len(inside_examples) < 5:
        inside_examples.append((kind, k, k >> T.Z, k & (T.NT - 1)))
print({k: {"edgeOrOutside": v[0], "whollyInside": v[1]} for k, v in kinds.items()})
print("inside examples:", inside_examples)
