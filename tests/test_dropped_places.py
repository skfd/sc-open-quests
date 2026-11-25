"""config/dropped-places.json: the list and what reads it. Run: python -m unittest"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import places  # noqa: E402
import run  # noqa: E402


def row(gers, parent=None, anc=()):
    return {"gers": gers, "parent": parent, "anc": list(anc), "name": gers}


class DroppedPlacesTest(unittest.TestCase):
    def test_the_checked_in_list_is_clean(self):
        d = run.dropped_places()
        self.assertTrue(d)
        keeps = {p["keeps"]["id"] for p in d.values()}
        self.assertFalse(keeps & set(d))  # nothing is both kept and dropped
        for p in d.values():
            self.assertRegex(p["id"], r"^[0-9a-f]{12}$")
            self.assertEqual(p["id"], p["gers"].replace("-", "")[:12])
            self.assertTrue(re.match(r"^[rw][0-9]+$", p["osm"]))
            self.assertIn(p["why"], ("duplicate",))

    def test_the_registry_has_none_of_them(self):
        d = run.dropped_places()
        seen = {p["id"] for f in run.PARTS_CONFIG.glob("*.json") for p in run.read_json(f)["parts"]}
        self.assertFalse(seen & set(d))
        self.assertTrue({p["keeps"]["id"] for p in d.values()} <= seen)  # the kept twin is still a part

    def test_an_absent_list_drops_nothing_and_a_repeated_id_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run.dropped_places(Path(tmp) / "none.json"), {})
            twice = Path(tmp) / "twice.json"
            twice.write_text(json.dumps({"places": [{"id": "a"}, {"id": "a"}]}))
            with self.assertRaises(ValueError):
                run.dropped_places(twice)

    def test_the_name_layer_leaves_them_out_and_keeps_the_rest(self):
        dropped = {"places": [{"gers": "g2", "id": "x"}]}
        kept, n = places.leave_out([row("g1"), row("g2"), row("g3", "g1", ["g1"])], dropped)
        self.assertEqual([r["gers"] for r in kept], ["g1", "g3"])
        self.assertEqual(n, 1)

    def test_a_dropped_place_with_places_under_it_stops_the_build(self):
        dropped = {"places": [{"gers": "g1", "id": "x"}]}
        with self.assertRaises(SystemExit):
            places.leave_out([row("g1"), row("g3", "g1", ["g1"])], dropped)
        with self.assertRaises(SystemExit):
            places.leave_out([row("g1"), row("g4", "g3", ["g3", "g1"])], dropped)


if __name__ == "__main__":
    unittest.main()
