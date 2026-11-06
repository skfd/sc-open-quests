"""coverage.json: city boundaries for the site's map. Run: python -m unittest"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run  # noqa: E402


def way(role, *points):
    return {"type": "way", "ref": 1, "role": role, "geometry": [{"lat": y, "lon": x} for y, x in points]}


# A square in two ways, one with a point on its edge, around a hole, and an islet under the tolerance.
BOUNDARY = {"type": "relation", "id": 7, "members": [
    {"type": "node", "ref": 2, "role": "admin_centre", "lat": 0.5, "lon": 0.5},
    {"type": "relation", "ref": 3, "role": "subarea"},
    way("outer", (0, 0), (0, 0.5), (0, 1), (1, 1)),
    way("outer", (1, 1), (1, 0), (0, 0)),
    way("inner", (0.4, 0.4), (0.4, 0.6), (0.6, 0.6), (0.4, 0.4)),
    way("outer", (5, 5), (5, 5.00001), (5.00001, 5.00001), (5, 5)),
]}


class SimplifyTest(unittest.TestCase):
    def test_a_point_on_a_straight_edge_goes(self):
        ring = [(0, 0), (0, 0.5), (0, 1), (1, 1), (1, 0), (0, 0)]
        self.assertEqual([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)], run.simplify_ring(ring))

    def test_a_bump_over_the_tolerance_stays(self):
        ring = [(0, 0), (0.01, 0.5), (0, 1), (1, 1), (1, 0), (0, 0)]
        self.assertIn((0.01, 0.5), run.simplify_ring(ring))

    def test_a_ring_under_the_tolerance_collapses(self):
        self.assertLess(len(run.simplify_ring([(5, 5), (5, 5.00001), (5.00001, 5.00001), (5, 5)])), 4)


class GeometryTest(unittest.TestCase):
    def test_outer_with_its_hole_and_no_islet(self):
        geometry = run.coverage_geometry(BOUNDARY)
        self.assertEqual("MultiPolygon", geometry["type"])
        self.assertEqual(1, len(geometry["coordinates"]))
        outer, hole = geometry["coordinates"][0]
        self.assertCountEqual([[0, 0], [1, 0], [1, 1], [0, 1]], outer[:-1])
        self.assertEqual(outer[0], outer[-1])
        self.assertEqual([0.4, 0.4], hole[0])   # lon, lat
        self.assertEqual(hole[0], hole[-1])


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "b.json").write_text(json.dumps(BOUNDARY), encoding="utf-8")
        self.cities = [{"id": "zed", "boundary": "b.json"}, {"id": "alpha", "boundary": "b.json"}]

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_one_feature_per_city_by_id_and_a_rerun_changes_nothing(self):
        self.assertTrue(run.publish_coverage(self.tmp, self.cities, self.tmp))
        written = json.loads((self.tmp / "coverage.json").read_text(encoding="utf-8"))
        self.assertEqual(["alpha", "zed"], [f["id"] for f in written["features"]])
        self.assertEqual({}, written["features"][0]["properties"])
        self.assertFalse(run.publish_coverage(self.tmp, self.cities, self.tmp))


if __name__ == "__main__":
    unittest.main()
