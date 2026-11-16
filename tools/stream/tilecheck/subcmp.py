"""A clip's tile store held against the planet's, inside the clip only: every tile whose square lies at least
--inset-km inside the clip's polygon, by decompressed payload. The planet store of a day is exact where the clip's
extract is whole, which is away from its polygon's edge; there the two must agree tile for tile.

  subcmp.py --clip S1 --planet S2 --poly polygon.geojson [--inset-km 2] [--gc 0] [--gp 0]

Exits 1 if any interior tile differs or is in only one store. Prints JSON (counts, examples with the columns that
differ: 0-7 nodes, 8-14 ways, 15-24 relations, as tilestore.unpack_cols lays them out).
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from compression import zstd
from shapely import contains_xy, from_geojson
from shapely.ops import transform, unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tilestore as TS  # noqa: E402
import tiles as T  # noqa: E402

R = 20037508.342789244  # half the web mercator world, metres


def merc(lon, lat):
    lat = max(min(lat, 85.0511), -85.0511)
    return lon * R / 180.0, math.log(math.tan(math.radians(45 + lat / 2))) * R / math.pi


def interior_keys(keys: np.ndarray, poly, inset_m: float) -> np.ndarray:
    """the keys whose z-tile square lies inside poly shrunk by inset_m (mercator metres, scaled for latitude)"""
    pm = transform(lambda x, y, z=None: tuple(zip(*[merc(a, b) for a, b in zip(x, y)])), poly)
    lat_max = max(abs(poly.bounds[1]), abs(poly.bounds[3]))
    nt, side = 1 << T.Z, 2 * R / (1 << T.Z)
    # a square lies inside the shrunk polygon when its centre lies inside it shrunk by half the square's diagonal
    # more (a little conservative near corners); vectorised over the centres
    inner = pm.buffer(-inset_m / math.cos(math.radians(lat_max)) - side * 0.7072)
    x, y = keys >> T.Z, keys & (nt - 1)
    cx, cy = -R + (x + 0.5) * side, R - (y + 0.5) * side
    return keys[contains_xy(inner, cx, cy)]


def payload(store: TS.Store, idx: np.ndarray, key: int) -> bytes:
    e = idx[np.searchsorted(idx["key"], key)]
    return store._read("pack", int(e["pack"]), int(e["off"]), int(e["len"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", type=Path, required=True)
    ap.add_argument("--planet", type=Path, required=True)
    ap.add_argument("--poly", type=Path, required=True)
    ap.add_argument("--inset-km", type=float, default=2.0)
    ap.add_argument("--gc", type=int, default=0)
    ap.add_argument("--gp", type=int, default=0)
    o = ap.parse_args()
    poly = from_geojson(o.poly.read_text())
    if poly.geom_type == "GeometryCollection":  # a FeatureCollection reads as one
        poly = unary_union(list(poly.geoms))
    if poly.geom_type not in ("Polygon", "MultiPolygon"):
        raise SystemExit(f"{o.poly}: expected a Polygon or MultiPolygon, got {poly.geom_type}")
    sc, sp = TS.Store(o.clip, o.gc), TS.Store(o.planet, o.gp)
    ic, ip = sc.idx, sp.idx
    # candidates: the clip's keys and the planet's keys inside the polygon's box, then the inset test on each
    b = poly.bounds
    fx, fy = T.frac_xy(np.array([b[1], b[3]]), np.array([b[0], b[2]]))
    x0, x1, y0, y1 = int(fx.min()), int(fx.max()), int(fy.min()), int(fy.max())
    kp = ip["key"]
    px, py = kp >> T.Z, kp & ((1 << T.Z) - 1)
    near = kp[(px >= x0) & (px <= x1) & (py >= y0) & (py <= y1)]
    cand = np.union1d(ic["key"], near)
    inner = interior_keys(cand, poly, o.inset_km * 1000)
    in_c, in_p = np.isin(inner, ic["key"]), np.isin(inner, kp)
    res = {"insetKm": o.inset_km, "clipTiles": int(len(ic)), "planetTiles": int(len(ip)),
           "interior": int(len(inner)), "onlyClip": int((in_c & ~in_p).sum()), "onlyPlanet": int((in_p & ~in_c).sum()),
           "same": 0, "differ": 0, "examples": [], "onlyExamples": []}
    for k in inner[in_c != in_p][:10].tolist():
        res["onlyExamples"].append({"key": k, "x": k >> T.Z, "y": k & ((1 << T.Z) - 1),
                                    "in": "clip" if np.isin(k, ic["key"]) else "planet"})
    for k in inner[in_c & in_p].tolist():
        a, p = payload(sc, ic, k), payload(sp, ip, k)
        if zstd.decompress(a) == zstd.decompress(p):
            res["same"] += 1
            continue
        res["differ"] += 1
        if len(res["examples"]) < 10:
            ca, cp = TS.unpack_cols(a), TS.unpack_cols(p)
            cols = [n for n, (u, v) in enumerate(zip(ca, cp)) if len(u) != len(v) or (u != v).any()]
            res["examples"].append({"key": k, "x": k >> T.Z, "y": k & ((1 << T.Z) - 1), "differingColumns": cols})
    res["equal"] = not (res["differ"] or res["onlyClip"] or res["onlyPlanet"])
    print(json.dumps(res, indent=1))
    sys.exit(0 if res["equal"] else 1)


if __name__ == "__main__":
    main()
