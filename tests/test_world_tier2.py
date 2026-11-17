"""tools/stream/world_tier2.py: the world's tier-2 cover in one global grid, its rectangles split at the plan's cells,
and the engine's files (DESIGN.md, "Release 1: the world day", step 3).

The synthetic cases run always. `WORLD_TIER2_EUROPE=1` adds the comparison with tier2.cover on a real day (diff 5175
through europe-west's cities, the inputs of `.scratch/stream/europe-west/t2a/`): every cell tier2 marks must lie inside
one of the world's rectangles."""
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "stream"))
import world_tier2 as W  # noqa: E402
from tier2 import M_LAT  # noqa: E402

DATA = Path(os.environ.get("OPENQUESTS_DATA_ROOT", ROOT))


def node(lat, lon, alive=True):
    return (2, 0, alive, {}, (lat, lon) if alive else None)


def way(refs, alive=True, tags=None):
    return (2, 0, alive, tags or {}, refs)


PLACES = {1: (52.0, 9.9995), 2: (52.0, 10.0005), 3: (52.001, 10.0), 10: (52.01, 9.99), 11: (52.01, 9.995),
          12: (52.015, 9.995), 13: (52.015, 9.99)}


def plan(tmp: Path) -> dict:
    """two cells sharing the edge at longitude 10, each with a parts file"""
    p = {"files": [{"id": "f0", "cells": [{"id": "f0c0", "rect": [50.0, 5.0, 55.0, 10.0], "timeZone": "Europe/Berlin"},
                                          {"id": "f0c1", "rect": [50.0, 10.0, 55.0, 15.0], "timeZone": "Europe/Berlin"}]}],
         "cityParts": [{"id": "osm-x", "bbox": [9.99, 52.0, 10.01, 52.02]}]}
    for c in ("f0c0", "f0c1"):
        d = tmp / "files" / "f0" / "parts"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{c}.json").write_text(json.dumps({"schema": 1, "city": c, "parts": [
            {"id": "near", "geometry": "g/near.geojson"}, {"id": "far", "geometry": "g/far.geojson"},
            {"id": "osm-x", "geometry": "g/osm-x.geojson"}]}))
    (tmp / "plan.json").write_text(json.dumps(p))
    return p


def inside_any(rects: dict, lat: float, lon: float) -> bool:
    return any(((r[:, 0] <= lat) & (lat < r[:, 2]) & (r[:, 1] <= lon) & (lon < r[:, 3])).any() for r in rects.values())


class GridTest(unittest.TestCase):
    def test_cells_are_fifty_metres(self):
        a = W.cells_of([52.0], [10.0])[0]
        b = W.cells_of([52.0 + 50.5 / M_LAT], [10.0])[0]
        i0, j0 = W.decode(np.array([a]))
        i1, j1 = W.decode(np.array([b]))
        self.assertEqual(int(i1[0] - i0[0]), 1)
        self.assertAlmostEqual(float(W.dlon_of(i0)[0]) * M_LAT * math.cos(math.radians(52.0)), 50.0, delta=0.1)

    def test_segment_marks_every_cell_it_crosses(self):
        m = W.Marks()
        m.segments(np.array([[52.0, 10.0, 52.0, 10.01]]), "way")  # about 685 m east
        i, j = W.decode(m.codes())
        self.assertEqual(len(set(i.tolist())), 1)
        self.assertEqual(sorted(j.tolist()), list(range(j.min(), j.max() + 1)))
        self.assertGreaterEqual(len(j), 13)

    def test_box_marks_its_area(self):
        m = W.Marks()
        m.boxes(np.array([[52.0, 10.0, 52.0045, 10.0073]]), "box")  # about 500 x 500 m
        self.assertAlmostEqual(len(m.codes()), 121, delta=25)

    def test_blocks_split_runs_at_their_edges_and_keep_every_point(self):
        rs = np.array([[0.4999, -0.6, 0.5001, -0.4], [10.1, 10.1, 10.2, 10.2]])
        bl = W.blocks_of(rs, (-90.0, -180.0, 90.0, 180.0), block=0.5)
        self.assertEqual(len(bl), 5)  # the first run spans 2 x 2 blocks
        allr = np.vstack([b for _, b in bl])
        self.assertAlmostEqual(float(W.box_km2(allr).sum()), float(W.box_km2(rs).sum()), places=6)
        for brect, b in bl:
            self.assertTrue((b[:, 0] >= brect[0]).all() and (b[:, 2] <= brect[2]).all())

    def test_antimeridian_segment_marks_its_ends_only(self):
        m = W.Marks()
        m.segments(np.array([[0.0, 179.9999, 0.0, -179.9999]]), "way")
        self.assertEqual(len(m.codes()), 2)


class CoverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.plan = plan(self.tmp)
        self.cells = W.plan_cells(self.plan)
        self.places = W.DictPlaces(PLACES.get)
        self.logs = []

    def cover(self, last_node=None, last_way=None, last_rel=None, rows=None, **kw):
        codes, stats, _ = W.cover(last_node or {}, last_way or {}, last_rel or {}, self.places, self.places, rows,
                                  log=self.logs.append, **kw)
        return codes, stats, W.rectangles(codes, self.cells)

    def test_a_way_across_a_cell_edge_is_split_there(self):
        _, _, rects = self.cover(last_way={7: way([1, 2])})
        self.assertEqual(set(rects), {0, 1})
        self.assertTrue((rects[0][:, 3] <= 10.0).all() and (rects[1][:, 1] >= 10.0).all())
        for lon in (9.9995, 9.99999, 10.0, 10.0005):
            self.assertTrue(inside_any(rects, 52.0, lon), lon)

    def test_old_and_new_place_of_a_moved_node(self):
        old = W.DictPlaces({5: (52.002, 10.002)}.get)
        codes, _, _ = W.cover({5: node(52.003, 10.004)}, {}, {}, old, self.places, None, log=self.logs.append)
        rects = W.rectangles(codes, self.cells)
        self.assertTrue(inside_any(rects, 52.002, 10.002) and inside_any(rects, 52.003, 10.004))

    def test_a_deleted_way_is_found_by_its_old_rows(self):
        rows = np.zeros(1, dtype=W.ROWPOS)
        rows["key"], rows["lat"], rows["lon"] = 9 * 4 + 1, int(52.03 * 1e7), int(10.03 * 1e7)
        _, stats, rects = self.cover(last_way={9: way([], alive=False)}, rows=rows)
        self.assertEqual(stats["deleted ways"], 1)
        self.assertTrue(inside_any(rects, 52.03, 10.03))

    def test_old_refs_are_used_for_old_geometry(self):
        _, _, rects = self.cover(last_way={7: way([1, 3])}, old_refs=lambda w: [10, 11])
        self.assertTrue(inside_any(rects, 52.01, 9.9925))  # on the old segment 10-11
        self.assertTrue(inside_any(rects, 52.0005, 9.99975))  # on the new segment 1-3

    def test_closed_way_box_and_its_cap(self):
        ring = [10, 11, 12, 13, 10]
        whole, _, rects = self.cover(last_way={8: way(ring)})
        self.assertTrue(inside_any(rects, 52.0125, 9.9925))  # the middle of the box
        outline, stats, _ = self.cover(last_way={8: way(ring)}, cap_km2=0.1)
        self.assertEqual(stats["closed boxes over the cap (outline only)"], 1)
        # the box's inside is not marked (a small outline's rectangles may still merge over it: merge_rects' ring)
        self.assertLess(len(outline), len(whole) / 2)
        self.assertTrue(any("outline only" in x for x in self.logs))

    def test_a_multipolygon_marks_its_members_and_box(self):
        members = {20: [10, 11, 12], 21: [12, 13, 10]}
        rel = {30: (True, {"type": "multipolygon"}, [("w", 20), ("w", 21)]),
               31: (True, {"type": "route", "route": "bus"}, [("w", 20)])}
        _, stats, rects = self.cover(last_rel=rel, member_refs=members.get)
        self.assertEqual(stats["wanted relations"], 1)
        self.assertTrue(inside_any(rects, 52.0125, 9.9925))

    def test_engine_files(self):
        _, _, rects = self.cover(last_way={7: way([1, 2])})
        ids = np.array(["far", "near"])
        bbox = np.array([[20.0, 60.0, 20.1, 60.1], [9.9, 51.9, 10.1, 52.1]])
        cf, pdir, st = W.write_engine_files(rects, self.cells, self.tmp, self.tmp / "work", self.tmp,
                                            W.PartBoxes(ids, bbox, self.plan["cityParts"]))
        cities = json.loads(cf.read_text())["cities"]
        self.assertEqual(st["rectangles"], len(cities))
        c = cities[0]
        self.assertIsNone(c["countryCodes"])
        self.assertEqual(c["timeZone"], "Europe/Berlin")
        self.assertEqual(len(c["box"]), 4)
        b = json.loads((self.tmp / c["boundary"]).read_text())
        self.assertEqual([b["bounds"][k] for k in ("minlat", "minlon", "maxlat", "maxlon")], c["box"])
        parts = json.loads((pdir / f"{c['id']}.json").read_text())["parts"]
        self.assertEqual(sorted(p["id"] for p in parts), ["near", "osm-x"])


@unittest.skipUnless(os.environ.get("WORLD_TIER2_EUROPE") == "1", "set WORLD_TIER2_EUROPE=1 (minutes, real data)")
class EuropeDayTest(unittest.TestCase):
    """tier2.cover and world_tier2.cover on the same inputs: diff 5175, europe-west's node places and way store at
    11-13, its state rows; tier2 without its way index (as the world runs). Every cell tier2 marks in a city must lie
    inside one of the world's rectangles."""

    def test_world_rectangles_hold_every_tier2_cell(self):
        import time
        import stream as S
        import tier2 as T
        d = DATA / ".scratch/stream/europe-west/t2a"
        diff = DATA / ".scratch/planet/diffs-keep/5175.osc.gz"
        plan_path = DATA / ".scratch/planet/world-places/plan.json"
        if not (d / "ways.npz").exists() or not diff.exists() or not plan_path.exists():
            self.skipTest("the europe-west t2a inputs are gone")
        last_node, last_way, last_rel, _ = S.read_diff(diff)
        locs = S.Locations(d)
        places = W.SparsePlaces(d)
        ways = T.WayStore(d)
        rows = np.load(d / "rows.npy")
        meta = json.loads((d / "state.json").read_text())
        infos = T.city_infos(Path(meta["cities"]))
        nid = np.fromiter(last_node, np.int64, len(last_node))
        old_pos = {n: (None if np.isnan(p[0]) else (p[0], p[1])) for n, p in zip(nid.tolist(), places.places(nid).tolist())}
        T.NO_WAY_INDEX, was = True, T.NO_WAY_INDEX
        try:
            t = time.time()
            covers, _ = T.cover(infos, rows, last_node, last_way, last_rel, old_pos, locs, ways, print)
            t_old = time.time() - t
        finally:
            T.NO_WAY_INDEX = was
        cells = [(c["lat0"] + (i + 0.5) * cov.cell / M_LAT, c["lon0"] + (j + 0.5) * cov.cell / c["mlon"])
                 for cov in covers for c in (cov.c,) for (i, j) in cov.cells]
        pts = np.array(cells, float)
        keys = W.changed_keys(last_node, last_way, last_rel)
        sel = rows[np.isin(rows["key"], keys)]
        plan_cells = W.plan_cells(json.loads(plan_path.read_text()))
        result = {}
        # tier2 fills a box only inside each city's grid (its box and one cell)
        clip = [(s - 0.01, w - 0.01, n + 0.01, e + 0.01) for s, w, n, e in (c["box"] for c in infos)]
        for label, cap, bc in (("no cap, boxes cut to the cities", 1e12, clip), ("cap 25 km2", W.CAP_KM2, None)):
            t = time.time()
            codes, _, _ = W.cover(last_node, last_way, last_rel, places, places, sel, member_refs=ways.refs_of,
                                  cap_km2=cap, box_clip=bc)
            rects = W.rectangles(codes, plan_cells)
            allr = np.vstack(list(rects.values()))
            missing = 0
            for k in range(0, len(pts), 2000):
                p = pts[k:k + 2000]
                inside = ((allr[None, :, 0] <= p[:, None, 0]) & (p[:, None, 0] < allr[None, :, 2])
                          & (allr[None, :, 1] <= p[:, None, 1]) & (p[:, None, 1] < allr[None, :, 3])).any(axis=1)
                missing += int((~inside).sum())
            result[label] = missing
            print(f"{label}: world {len(allr):,} rectangles, {W.rect_km2(rects):.0f} km2 ({time.time() - t:.0f} s); "
                  f"tier2's {len(pts):,} marked cells ({t_old:.0f} s) outside them: {missing}")
        self.assertGreater(len(pts), 0)
        self.assertEqual(result["no cap, boxes cut to the cities"], 0)


if __name__ == "__main__":
    unittest.main()
