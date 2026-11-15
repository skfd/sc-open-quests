"""A pair index (wtiles/rtiles) of an updated store against a fresh cut's: the objects that differ, and how many of them
lie wholly inside the clip polygon (tiles either side)."""
import sys, json, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, tilestore as S, tiles as T
from shapely.geometry import shape, box
from shapely.ops import unary_union
poly = unary_union([shape(f['geometry']) for f in json.loads(Path(sys.argv[3]).read_text())['features']])
def tb(k):
    x, y, n = k >> T.Z, k & (T.NT - 1), T.NT
    lat = lambda yy: math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n))))
    return box(x / n * 360 - 180, lat(y + 1), (x + 1) / n * 360 - 180, lat(y))
a, b = np.load(sys.argv[1]), np.load(sys.argv[2])
sa = set(zip(a['id'].tolist(), a['key'].tolist())); sb = set(zip(b['id'].tolist(), b['key'].tolist()))
ids = {i for i, _ in sa ^ sb}
pa, pb = S.pairs_of(a, list(ids)), S.pairs_of(b, list(ids))
inner = [i for i in ids if all(poly.contains(tb(k)) for k in (pa.get(i, set()) | pb.get(i, set())))]
print(Path(sys.argv[1]).name, 'objects differing', len(ids), 'wholly interior', len(inner), sorted(inner)[:5])
