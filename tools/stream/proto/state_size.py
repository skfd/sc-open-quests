"""Step 5: how large is the state? The 11-09 dump of europe-west packed three ways."""
import struct, sys, zlib, lzma, time
from array import array
from pathlib import Path
S = Path(__file__).parent
DUMP = S.parent / "diff-flips" / "matches-2026-11-09.tsv"
rows = []
quests = {}
T = {"node": 0, "way": 1, "relation": 2}
with open(DUMP, encoding="utf-8") as f:
    next(f)
    for line in f:
        p = line.rstrip("\n").split("\t")
        q = quests.setdefault(p[0], len(quests))
        rows.append((T[p[1]], int(p[2]), q, round(float(p[6]) * 1e7), round(float(p[7]) * 1e7), p[8] == "true"))
n = len(rows)
elements = len({(r[0], r[1]) for r in rows})
print(f"{n:,} matches on {elements:,} elements, {len(quests)} quests; the text dump {DUMP.stat().st_size / n:.1f} bytes a match")

def varint(v, out):
    while v >= 0x80:
        out.append((v & 0x7F) | 0x80); v >>= 7
    out.append(v)

def zz(v):
    return (v << 1) ^ (v >> 63)

def report(name, blobs):
    raw = sum(len(b) for b in blobs)
    z = sum(len(zlib.compress(bytes(b), 6)) for b in blobs)
    x = sum(len(lzma.compress(bytes(b), preset=6)) for b in blobs)
    print(f"{name:<58} {raw / n:5.2f} bytes a match raw, {z / n:5.2f} zlib, {x / n:5.2f} xz")

# 1. fixed records: type+quest 2, id 8, lat 4, lon 4, flags folded into type
fixed = bytearray()
for t, i, q, la, lo, aged in sorted(rows):
    fixed += struct.pack("<BBqii", t | (aged << 7), q, i, la, lo)
report("fixed 18-byte records, by element", [fixed])

# 2. by element: one entry per element (id delta, place), then its quests
ids, place, qs = bytearray(), bytearray(), bytearray()
prev = (0, 0); cur = None
for t, i, q, la, lo, aged in sorted(rows):
    if (t, i) != cur:
        if cur is not None:
            qs.append(255)
        varint(i - prev[1] if t == prev[0] else i, ids)
        place += struct.pack("<ii", la, lo)
        prev = (t, i); cur = (t, i)
    qs.append(q | (0x80 if aged else 0))
report("by element: id deltas, a place per element, quest lists", [ids, place, qs])
report("  the same without places (a node's place is in the store)", [ids, qs])

# 3. by place: z14 tile, then deltas within it
import math
def tile(la, lo, z=14):
    lat, lon = la / 1e7, lo / 1e7
    x = int((lon + 180) / 360 * (1 << z))
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * (1 << z))
    return x, y
bt = sorted((tile(r[3], r[4]), r[3], r[4], r[0], r[1], r[2], r[5]) for r in rows)
a, b = bytearray(), bytearray()
pl = (0, 0)
for tl, la, lo, t, i, q, aged in bt:
    varint(zz(la - pl[0]), a); varint(zz(lo - pl[1]), a); pl = (la, lo)
    b += struct.pack("<Bq", q | (0x80 if aged else 0), (i << 2) | t)
report("by z14 tile: place deltas, quest, full id", [a, b])
print(f"\nGermany as cells: 76,065,341 open quests on 442,630,768 nodes = {76065341 / 442630768:.3f} a node")
for nodes in (10e9, 11e9):
    w = nodes * 76065341 / 442630768
    print(f"  the world at {nodes / 1e9:.0f} billion nodes and Germany's density: {w / 1e9:.2f} billion open quests")
