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
from collections import Counter
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
          12: (52.015, 9.995), 13: (52.015, 9.99),
          # a big ring, about 7 x 7 km (49 km2), west of the cell edge, and a node far inside it
          40: (52.1, 9.8), 41: (52.1, 9.9), 42: (52.163, 9.9), 43: (52.163, 9.8), 44: (52.13, 9.85)}
BIG = [40, 41, 42, 43, 40]
INSIDE = (52.13, 9.85)  # the big ring's middle, about 3 km from its outline


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

    def test_a_small_closed_way_is_boxed_whatever_its_tags(self):
        _, stats, rects = self.cover(last_way={8: way([10, 11, 12, 13, 10])})
        self.assertTrue(inside_any(rects, 52.0125, 9.9925))  # the middle of the box (0.19 km2)
        self.assertEqual(stats["boxes marked whole: small"], 2)  # its new ring and its old one (NO_WAY_INDEX)

    def test_a_big_polygon_no_quest_reads_is_marked_by_outline_and_quest_points(self):
        _, stats, rects = self.cover(last_way={8: way(BIG, tags={"landuse": "forest"})})
        self.assertEqual(stats["boxes by outline"], 2)
        self.assertFalse(inside_any(rects, 52.12, 9.83))  # inside, away from the outline and the centroid
        self.assertTrue(inside_any(rects, 52.1, 9.85))  # on the outline
        self.assertTrue(inside_any(rects, 52.1315, 9.85))  # the centroid: the polygon's own quest point
        self.assertLess(W.rect_km2(rects), 15)

    def test_a_big_building_or_mall_or_addressed_area_is_boxed(self):
        for tags in ({"building": "yes"}, {"shop": "mall"}, {"railway": "station"},
                     {"amenity": "school", "addr:housenumber": "5"}):
            _, stats, rects = self.cover(last_way={8: way(BIG, tags=tags)})
            self.assertTrue(inside_any(rects, 52.12, 9.83), tags)
            self.assertEqual(stats["boxes marked whole: container"], 2, tags)
        _, stats, rects = self.cover(last_way={8: way(BIG, tags={"building": "roof"})})
        self.assertFalse(inside_any(rects, 52.12, 9.83))  # a roof holds nothing (buildingFilter: building != roof)

    def test_an_area_with_an_address_on_its_outline_is_boxed(self):
        addr = (2, 0, True, {"addr:housenumber": "1"}, PLACES[41])
        _, _, rects = self.cover(last_node={41: addr}, last_way={8: way(BIG, tags={"landuse": "residential"})})
        self.assertTrue(inside_any(rects, 52.12, 9.83))
        _, _, rects = self.cover(last_way={8: way(BIG, tags={"landuse": "residential"})},
                                 address_nodes=np.array([7, 42, 99], np.int64))
        self.assertTrue(inside_any(rects, 52.12, 9.83))

    def test_old_tags_decide_the_old_ring(self):
        _, stats, rects = self.cover(last_way={8: way(BIG, tags={"landuse": "grass"})},
                                     old_tags=lambda kind, i: {"building": "yes"})
        self.assertTrue(inside_any(rects, 52.12, 9.83))  # it was a building yesterday: its inside is recounted
        _, stats, _ = self.cover(last_way={8: way(BIG, tags={"landuse": "grass"})})
        self.assertEqual(stats["  of them, old tags unknown"], 1)  # the old ring, its tags not known

    def test_the_safety_cap_is_logged(self):
        _, stats, _ = self.cover(last_way={8: way(BIG, tags={"building": "yes"})}, cap_km2=10)
        self.assertEqual(stats["boxes over the safety cap"], 2)
        self.assertTrue(any("safety cap" in x for x in self.logs))

    def test_a_multipolygon_marks_its_members_and_is_boxed_only_as_a_container(self):
        members = {20: [40, 41, 42], 21: [42, 43, 40]}
        rel = {30: (True, {"type": "multipolygon", "natural": "wood"}, [("w", 20), ("w", 21)]),
               31: (True, {"type": "route", "route": "bus"}, [("w", 20)])}
        _, stats, rects = self.cover(last_rel=rel, member_refs=members.get)
        self.assertEqual(stats["wanted relations: multipolygon"], 1)
        self.assertTrue(inside_any(rects, 52.1, 9.85))  # a member way
        self.assertFalse(inside_any(rects, 52.12, 9.83))
        rel[30] = (True, {"type": "multipolygon", "building": "yes"}, [("w", 20), ("w", 21)])
        _, _, rects = self.cover(last_rel=rel, member_refs=members.get)
        self.assertTrue(inside_any(rects, 52.12, 9.83))

    def test_hiking_routes_and_addressed_relations_mark_their_member_ways(self):
        members = {20: [10, 11]}
        for tags in ({"type": "route", "route": "hiking"}, {"type": "site", "addr:housenumber": "3"}):
            _, _, rects = self.cover(last_rel={30: (True, tags, [("w", 20)])}, member_refs=members.get)
            self.assertTrue(inside_any(rects, 52.01, 9.9925), tags)

    def test_a_street_relation_marks_its_member_nodes(self):
        rel = {30: (True, {"type": "associatedStreet"}, [("n", 13), ("w", 20)])}
        _, _, rects = self.cover(last_rel=rel, member_refs={20: [1, 2]}.get)
        self.assertTrue(inside_any(rects, *PLACES[13]))

    def test_a_contained_node_marks_its_surroundings(self):
        n = (2, 0, True, {"addr:housenumber": "9"}, INSIDE)
        _, stats, rects = self.cover(last_node={44: n})
        self.assertTrue(inside_any(rects, INSIDE[0] + 0.0008, INSIDE[1]))  # about 90 m north
        self.assertEqual(stats["contained nodes: address"], 1)
        _, _, rects = self.cover(last_node={44: (2, 0, True, {"amenity": "bench"}, INSIDE)})
        self.assertFalse(inside_any(rects, INSIDE[0] + 0.0008, INSIDE[1]))

    def test_a_deleted_node_no_way_held_marks_its_surroundings(self):
        _, stats, rects = self.cover(last_node={44: node(0, 0, alive=False)})
        self.assertTrue(inside_any(rects, INSIDE[0] + 0.0008, INSIDE[1]))  # its old place, from the old places
        self.assertEqual(stats["contained nodes: deleted, tags unknown"], 1)
        _, stats, _ = self.cover(last_node={44: node(0, 0, alive=False)}, last_way={8: way([44, 1])})
        self.assertEqual(stats["contained nodes: deleted, tags unknown"], 0)

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
        # every mark tier2 makes, by where it came from: a box (the element) or anything else ("line")
        src: dict = {}
        orig_bbox, orig_mark = T.Cover.bbox, T.Cover.mark

        def bbox(cov, pts, kind, element):
            cov._box = element
            try:
                orig_bbox(cov, pts, kind, element)
            finally:
                cov._box = None

        def mark(cov, i, j, kind, element):
            if 0 <= i <= cov.max_i and 0 <= j <= cov.max_j:
                src.setdefault((id(cov), i, j), set()).add(getattr(cov, "_box", None) or "line")
            orig_mark(cov, i, j, kind, element)

        T.NO_WAY_INDEX, was = True, T.NO_WAY_INDEX
        T.Cover.bbox, T.Cover.mark = bbox, mark
        try:
            t = time.time()
            covers, _ = T.cover(infos, rows, last_node, last_way, last_rel, old_pos, locs, ways, print)
            t_old = time.time() - t
        finally:
            T.NO_WAY_INDEX = was
            T.Cover.bbox, T.Cover.mark = orig_bbox, orig_mark
        cells, sources = [], []
        for cov in covers:
            c = cov.c
            for (i, j) in cov.cells:
                cells.append((c["lat0"] + (i + 0.5) * cov.cell / M_LAT, c["lon0"] + (j + 0.5) * cov.cell / c["mlon"]))
                sources.append(src[(id(cov), i, j)])
        pts = np.array(cells, float)
        keys = W.changed_keys(last_node, last_way, last_rel)
        sel = rows[np.isin(rows["key"], keys)]
        plan_cells = W.plan_cells(json.loads(plan_path.read_text()))
        # tier2 fills a box only inside each city's grid (its box and one cell)
        clip = [(s - 0.01, w - 0.01, n + 0.01, e + 0.01) for s, w, n, e in (c["box"] for c in infos)]

        def outside(rects):
            allr = np.vstack(list(rects.values()))
            out = np.zeros(len(pts), bool)
            for k in range(0, len(pts), 2000):
                p = pts[k:k + 2000]
                out[k:k + 2000] = ~((allr[None, :, 0] <= p[:, None, 0]) & (p[:, None, 0] < allr[None, :, 2])
                                    & (allr[None, :, 1] <= p[:, None, 1]) & (p[:, None, 1] < allr[None, :, 3])).any(axis=1)
            return out

        for label, rule in (("every box (tier2's way)", False), ("the rule", True)):
            t = time.time()
            boxed: set = set()
            codes, stats, _ = W.cover(last_node, last_way, last_rel, places, places, sel, member_refs=ways.refs_of,
                                      box_clip=clip, rule=rule, boxed_out=boxed)
            rects = W.rectangles(codes, plan_cells)
            out = outside(rects)
            justified = np.array([("line" in s) or bool(s & boxed) for s in sources], bool)
            print(f"{label}: world {sum(len(v) for v in rects.values()):,} rectangles, {W.rect_km2(rects):.0f} km2 "
                  f"({time.time() - t:.0f} s); tier2's {len(pts):,} cells ({t_old:.0f} s): {int(justified.sum()):,} "
                  f"justified by the rule, {int((justified & out).sum())} of them outside; "
                  f"{int((~justified).sum()):,} only in boxes the rule leaves to their outline, "
                  f"{int((~justified & out).sum()):,} of those outside")
            if rule:
                why = Counter()
                for s in (sources[k] for k in np.flatnonzero(~justified & out)):
                    for el in s:
                        if el == "line":
                            continue
                        typ, i = el
                        tags = (last_way[i][3] if last_way[i][2] else None) if typ == "way" else last_rel[i][1]
                        cls = ("deleted, tags unknown" if tags is None else
                               next((f"{k}={tags[k]}" for k in ("landuse", "natural", "leisure", "amenity", "boundary",
                                                                "place", "waterway", "highway", "barrier") if k in tags),
                                    "other: " + ",".join(sorted(tags)[:3])))
                        why[(typ, cls)] += 1
                print("dropped cells' boxes, by element class:", why.most_common(25))
                print("rule stats:", {k: v for k, v in stats.items() if "box" in k or "contain" in k or "km2" in k})
            self.assertEqual(int((justified & out).sum()), 0, label)
        self.assertGreater(len(pts), 0)


if __name__ == "__main__":
    unittest.main()
