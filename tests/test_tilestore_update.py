"""tilestore.update: a small clip cut into a store, a day's diff applied, and the result held tile for tile (and blob
for blob in the relation store) against a fresh cut of the clip after the diff."""
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "stream"))
import tiles as T  # noqa: E402
import tilestore as S  # noqa: E402

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)

BASE_NODES = {1: (51.500, -0.120, {}), 2: (51.500, -0.090, {}), 3: (51.510, -0.120, {}),
              4: (51.505, -0.105, {"amenity": "bench"}), 5: (51.520, -0.100, {}), 6: (51.520, -0.095, {}),
              7: (51.525, -0.095, {}), 8: (51.525, -0.100, {}), 9: (51.505, -0.075, {})}
BASE_WAYS = {1: ([1, 2], {"highway": "residential"}), 2: ([1, 3], {"highway": "footway"}),
             3: ([5, 6, 7, 8, 5], {"building": "yes"}), 4: ([3, 5], {})}
BASE_RELS = {1: ([("w", 4, "outer"), ("w", 3, "inner")], {"type": "multipolygon", "landuse": "grass"}),
             2: ([("w", 1, "")], {"type": "route", "route": "bus"})}


def write_pbf(path, nodes, ways, rels, versions):
    import osmium
    w = osmium.SimpleWriter(str(path), overwrite=True)
    for i in sorted(nodes):
        lat, lon, tags = nodes[i]
        v, ts = versions.get(("n", i), (1, T0))
        w.add_node(osmium.osm.mutable.Node(id=i, version=v, timestamp=ts, location=(lon, lat), tags=tags))
    for i in sorted(ways):
        refs, tags = ways[i]
        v, ts = versions.get(("w", i), (1, T0))
        w.add_way(osmium.osm.mutable.Way(id=i, version=v, timestamp=ts, nodes=refs, tags=tags))
    for i in sorted(rels):
        ms, tags = rels[i]
        v, ts = versions.get(("r", i), (1, T0))
        w.add_relation(osmium.osm.mutable.Relation(id=i, version=v, timestamp=ts, members=ms, tags=tags))
    w.close()


OSC = """<?xml version='1.0' encoding='UTF-8'?>
<osmChange version="0.6">
<modify>
 <node id="2" version="2" timestamp="2026-11-13T10:00:00Z" lat="51.54" lon="-0.09"/>
 <way id="2" version="2" timestamp="2026-11-13T10:00:00Z"><nd ref="1"/><nd ref="3"/>
  <tag k="highway" v="footway"/><tag k="surface" v="paved"/></way>
 <relation id="1" version="2" timestamp="2026-11-13T10:00:00Z">
  <member type="way" ref="4" role="outer"/><member type="way" ref="3" role="inner"/>
  <tag k="type" v="multipolygon"/><tag k="landuse" v="grass"/><tag k="name" v="Park"/></relation>
</modify>
<delete>
 <node id="4" version="2" timestamp="2026-11-13T10:00:00Z" lat="51.505" lon="-0.105"/>
</delete>
<create>
 <node id="10" version="1" timestamp="2026-11-13T10:00:00Z" lat="51.505" lon="-0.07"><tag k="shop" v="bakery"/></node>
 <way id="5" version="1" timestamp="2026-11-13T10:00:00Z"><nd ref="9"/><nd ref="10"/><tag k="highway" v="service"/></way>
</create>
</osmChange>
"""


class UpdateTest(unittest.TestCase):
    def test_update_equals_fresh_cut(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            d = Path(tmp)
            write_pbf(d / "before.osm.pbf", BASE_NODES, BASE_WAYS, BASE_RELS, {})
            nodes = dict(BASE_NODES)
            nodes[2] = (51.540, -0.090, {})
            del nodes[4]
            nodes[10] = (51.505, -0.070, {"shop": "bakery"})
            ways = dict(BASE_WAYS)
            ways[2] = ([1, 3], {"highway": "footway", "surface": "paved"})
            ways[5] = ([9, 10], {"highway": "service"})
            rels = dict(BASE_RELS)
            rels[1] = (BASE_RELS[1][0], {"type": "multipolygon", "landuse": "grass", "name": "Park"})
            versions = {("n", 2): (2, T1), ("n", 10): (1, T1), ("w", 2): (2, T1), ("w", 5): (1, T1), ("r", 1): (2, T1)}
            write_pbf(d / "after.osm.pbf", nodes, ways, rels, versions)
            (d / "day.osc").write_text(OSC, encoding="utf-8")
            for name in ("before", "after"):
                T.geom(d / f"{name}.osm.pbf", d / f"g-{name}")
                T.attrs(d / f"{name}.osm.pbf", d / f"g-{name}")
                S.cut(d / f"g-{name}", d / f"s-{name}", name)
            S.update(d / "s-before", d / "day.osc", d / "g-before", "after")
            r = S.compare_stores(d / "s-before", d / "s-after")
            self.assertEqual((r["differ"], r["onlyA"], r["onlyB"]), (0, 0, 0), r)
            self.assertGreater(r["same"], 0)
            # the way and relation tile indexes, and the relation store
            for f in ("wtiles", "rtiles"):
                a, b = np.load(d / "s-before" / f"{f}-0001.npy"), np.load(d / "s-after" / f"{f}-0000.npy")
                self.assertTrue(np.array_equal(a, b), f)
            sa, sb = S.Store(d / "s-before"), S.Store(d / "s-after")
            self.assertEqual(sa.ridx["key"].tolist(), sb.ridx["key"].tolist())
            from compression import zstd
            for rid in sb.ridx["key"].tolist():
                self.assertEqual(zstd.decompress(sa.relation(rid)), zstd.decompress(sb.relation(rid)), rid)
            # D-1 is the generation before
            old = S.Store(d / "s-before", 0)
            r0 = S.compare_stores(d / "s-before", d / "s-before", ga=0, gb=0)
            self.assertEqual(r0["differ"], 0)
            self.assertEqual(old.gen, 0)


if __name__ == "__main__":
    unittest.main()
