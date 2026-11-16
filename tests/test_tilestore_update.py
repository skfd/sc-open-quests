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
              7: (51.525, -0.095, {}), 8: (51.525, -0.100, {}), 9: (51.505, -0.075, {}),
              11: (51.506, -0.121, {}), 12: (51.560, -0.150, {}), 13: (51.580, -0.180, {}), 14: (51.561, -0.149, {}),
              15: (51.470, -0.170, {})}
BASE_WAYS = {1: ([1, 2], {"highway": "residential"}), 2: ([1, 3], {"highway": "footway"}),
             3: ([5, 6, 7, 8, 5], {"building": "yes"}), 4: ([3, 5], {}), 6: ([12, 14], {"barrier": "fence"})}
BASE_RELS = {1: ([("w", 4, "outer"), ("w", 3, "inner")], {"type": "multipolygon", "landuse": "grass"}),
             2: ([("w", 1, "")], {"type": "route", "route": "bus"}),
             # in the tile of nodes 1 and 3 only through an untagged node no way holds (a rebuilt tile must keep it)
             3: ([("n", 11, "label"), ("w", 3, "")], {"type": "site", "name": "Yard"}),
             # a member way moves (1, by its node 2), other members lie where the day reaches nothing (way 6, node 13):
             # the relation's tile index must keep their tiles
             4: ([("w", 1, ""), ("w", 6, ""), ("n", 13, "entrance")], {"type": "site", "name": "Depot"})}


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
  <member type="way" ref="4" role="outer"/><member type="way" ref="3" role="inner"/><member type="node" ref="15" role=""/>
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
            # the relation gains a member node where nothing else reaches (its tile must take the relation)
            rels[1] = (BASE_RELS[1][0] + [("n", 15, "")], {"type": "multipolygon", "landuse": "grass", "name": "Park"})
            versions = {("n", 2): (2, T1), ("n", 10): (1, T1), ("w", 2): (2, T1), ("w", 5): (1, T1), ("r", 1): (2, T1)}
            write_pbf(d / "after.osm.pbf", nodes, ways, rels, versions)
            (d / "day.osc").write_text(OSC, encoding="utf-8")
            for name in ("before", "after"):
                T.geom(d / f"{name}.osm.pbf", d / f"g-{name}")
                T.attrs(d / f"{name}.osm.pbf", d / f"g-{name}")
                S.cut(d / f"g-{name}", d / f"s-{name}", name)
            # the clip's polygon is the store's region (the planet diff's changes elsewhere stay out)
            poly = d / "polygon.geojson"
            poly.write_text('{"features": [{"geometry": {"type": "Polygon", "coordinates": '
                            '[[[-0.2, 51.45], [0.0, 51.45], [0.0, 51.6], [-0.2, 51.6], [-0.2, 51.45]]]}}]}')
            S.update(d / "s-before", d / "day.osc", d / "g-before", "after", poly)
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

    def test_rust_update_equals_fresh_cut(self):
        """the same day through the Rust store (tilestore/): its cut of the clip before, its update by the diff, held
        against its cut of the clip after and against the Python update of the Python cut"""
        exe = Path(__file__).resolve().parents[1] / "tilestore" / "target" / "release" / "tilestore.exe"
        if not exe.exists():
            self.skipTest("the Rust tilestore is not built (cargo build --release in tilestore/)")
        import subprocess
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
            rels[1] = (BASE_RELS[1][0] + [("n", 15, "")], {"type": "multipolygon", "landuse": "grass", "name": "Park"})
            versions = {("n", 2): (2, T1), ("n", 10): (1, T1), ("w", 2): (2, T1), ("w", 5): (1, T1), ("r", 1): (2, T1)}
            write_pbf(d / "after.osm.pbf", nodes, ways, rels, versions)
            (d / "day.osc").write_text(OSC, encoding="utf-8")
            poly = d / "polygon.geojson"
            poly.write_text('{"features": [{"geometry": {"type": "Polygon", "coordinates": '
                            '[[[-0.2, 51.45], [0.0, 51.45], [0.0, 51.6], [-0.2, 51.6], [-0.2, 51.45]]]}}]}')

            from compression import zstd as _z
            zstd_d = _z.decompress

            def run(*a):
                subprocess.run([str(exe), *map(str, a)], check=True, capture_output=True)

            for name in ("before", "after"):
                run("cut", "--pbf", d / f"{name}.osm.pbf", "--out", d / f"r-{name}", "--day", name)
            run("update", "--store", d / "r-before", "--diff", d / "day.osc", "--before", d / "before.osm.pbf",
                "--day", "after", "--polygon", poly)
            # the world's way: no region, the node places from a node file by id as the world stream keeps it
            # (osmium dense_file_array); nothing in this day lies outside the polygon, so the result is the same
            import osmium
            import osmium.index
            loc = osmium.index.create_map(f"dense_file_array,{d / 'before.loc'}")
            for n in osmium.FileProcessor(str(d / "before.osm.pbf"), osmium.osm.NODE):
                loc.set(n.id, n.location)
            del loc
            run("cut", "--pbf", d / "before.osm.pbf", "--out", d / "w-before", "--day", "before")
            run("update", "--store", d / "w-before", "--diff", d / "day.osc", "--before-loc", d / "before.loc",
                "--day", "after", "--world")
            r = S.compare_stores(d / "w-before", d / "r-after", ga=1, gb=0)
            self.assertEqual((r["differ"], r["onlyA"], r["onlyB"]), (0, 0, 0), ("world", r))
            # in groups, one tile each: every tile's working set is its own old payload and the carried copies
            run("cut", "--pbf", d / "before.osm.pbf", "--out", d / "g-before", "--day", "before")
            run("update", "--store", d / "g-before", "--diff", d / "day.osc", "--before", d / "before.osm.pbf",
                "--day", "after", "--polygon", poly, "--group-z", "14")
            r = S.compare_stores(d / "g-before", d / "r-after", ga=1, gb=0)
            self.assertEqual((r["differ"], r["onlyA"], r["onlyB"]), (0, 0, 0), ("grouped", r))
            sg, sr = S.Store(d / "g-before", 1), S.Store(d / "r-before", 1)
            self.assertEqual(sg.ridx["key"].tolist(), sr.ridx["key"].tolist())
            for rid in sr.ridx["key"].tolist():
                self.assertEqual(zstd_d(sg.relation(rid)), zstd_d(sr.relation(rid)), ("grouped", rid))
            for f in ("wtiles", "rtiles"):
                self.assertTrue(np.array_equal(np.load(d / "g-before" / f"{f}-0001.npy"),
                                               np.load(d / "r-before" / f"{f}-0001.npy")), ("grouped", f))
            for f in ("wtiles", "rtiles", "relidx"):
                a, b = np.load(d / "w-before" / f"{f}-0001.npy"), np.load(d / "r-before" / f"{f}-0001.npy")
                self.assertTrue(np.array_equal(a if f != "relidx" else a["key"], b if f != "relidx" else b["key"]), f)
            # the Python update of the Python cut, the oracle the Rust update is a port of
            T.geom(d / "before.osm.pbf", d / "g-before")
            T.attrs(d / "before.osm.pbf", d / "g-before")
            S.cut(d / "g-before", d / "p-before", "before")
            S.update(d / "p-before", d / "day.osc", d / "g-before", "after", poly)
            from compression import zstd
            for other, g in (("r-after", 0), ("p-before", 1)):
                r = S.compare_stores(d / "r-before", d / other, ga=1, gb=g)
                self.assertEqual((r["differ"], r["onlyA"], r["onlyB"]), (0, 0, 0), (other, r))
                self.assertGreater(r["same"], 0)
                for f in ("wtiles", "rtiles"):
                    a, b = np.load(d / "r-before" / f"{f}-0001.npy"), np.load(d / other / f"{f}-{g:04d}.npy")
                    self.assertTrue(np.array_equal(a, b), (other, f))
                sa, sb = S.Store(d / "r-before", 1), S.Store(d / other, g)
                self.assertEqual(sa.ridx["key"].tolist(), sb.ridx["key"].tolist(), other)
                for rid in sb.ridx["key"].tolist():
                    self.assertEqual(zstd.decompress(sa.relation(rid)), zstd.decompress(sb.relation(rid)), (other, rid))


if __name__ == "__main__":
    unittest.main()
