"""world_day: the delta form on the world's WREC files, and a rectangle city's pseudo part mapped to its cell."""
import json
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "stream"))
import placesets as P  # noqa: E402
import world_day as WD  # noqa: E402
import world_state as WS  # noqa: E402


def rec(key, quest, lat=10.0, lon=10.0, flags=1, kind=0, due=0, place=0):
    r = np.zeros(1, P.WREC)
    r["key"], r["quest"], r["lat"], r["lon"] = key, quest, int(lat * 1e7), int(lon * 1e7)
    r["flags"], r["kind"], r["due"], r["place"] = flags, kind, due, place
    return r


class DeltaTest(unittest.TestCase):
    def world(self, d: Path, rows_by_file):
        files = []
        for k, (fid, rows) in enumerate(rows_by_file.items()):
            (d / "files" / fid).mkdir(parents=True)
            r = np.sort(np.concatenate(rows) if rows else np.zeros(0, P.WREC), order=WS.ORDER)
            WS.write_rows(d / "files" / fid / WS.WORLD_BIN, r)
            files.append({"id": fid, "rect": [k * 20.0, 0.0, k * 20.0 + 20.0, 20.0]})
        (d / "plan.json").write_text(json.dumps({"files": files}))
        return files

    def rows(self, d, fid):
        return np.fromfile(d / "files" / fid / WS.WORLD_BIN, P.WREC)

    def test_delta_forms(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            files = self.world(d, {"a": [rec(4, 1), rec(8, 1), rec(12, 1)], "b": [rec(16, 1, lat=25)]})
            # 4: unchanged by the recount; 8: removed; 12: changed (moved), held; 20: added; 24: changed, not held
            old = np.concatenate([rec(4, 1), rec(8, 1), rec(12, 1), rec(24, 1)])
            new = np.concatenate([rec(4, 1), rec(12, 1, lat=11), rec(20, 1, lat=26), rec(24, 1, lat=12)])
            added = defaultdict(set)
            st = WD.delta_w(d, old, new, files, added)
            a, b = self.rows(d, "a"), self.rows(d, "b")
            self.assertEqual(sorted(a["key"].tolist()), [4, 12])
            self.assertEqual(int(a[a["key"] == 12]["lat"][0]), int(11e7))
            self.assertEqual(sorted(b["key"].tolist()), [16, 20])  # 20 routed by its position to file b
            self.assertEqual(st["changed, the state lacked it (kept out)"], 1)
            self.assertEqual(st["removed"], 1)
            self.assertIn(20 * 1024 + 1, added["b"])

    def test_place_change_alone_is_applied(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            files = self.world(d, {"a": [rec(4, 1, place=1)]})
            st = WD.delta_w(d, rec(4, 1, place=1), rec(4, 1, place=2), files, defaultdict(set))
            self.assertEqual(int(self.rows(d, "a")["place"][0]), 2)
            self.assertEqual(st["changed"], 1)


class RectToCellTest(unittest.TestCase):
    def test_pseudo_part(self):
        with tempfile.TemporaryDirectory() as t:
            sets = P.PlaceSets(Path(t) / "place-sets.json")
            s1 = sets.intern(["city:f0c1-3", "abc"])
            s2 = sets.intern(["abc"])
            want = sets.intern(["city:f0c1", "abc"])
            rows = np.concatenate([rec(4, 1, place=s1), rec(8, 1, place=s2), rec(12, 1, place=0)])
            out = WD.rect_to_cell(rows, sets)
            self.assertEqual(out["place"].tolist(), [want, s2, 0])

    def test_rect_groups(self):
        def city(cid, s, w, n, e):
            return {"id": cid, "box": [s, w, n, e]}
        with tempfile.TemporaryDirectory() as t:
            cs = [city("f10c0-0", 50, 10, 50.01, 10.01), city("f2c3-0", 50, 10, 50.01, 10.01),
                  city("f2c3-1", 50, 11, 50.01, 11.01), city("f2c4-0", 50, 12, 50.01, 12.01)]
            src = Path(t) / "cities.json"
            src.write_text(json.dumps({"cities": cs}))
            # per plan file, in plan-file order (f2 before f10), each file's cities in their order
            gs = WD.rect_groups(src, Path(t) / "g")
            self.assertEqual([g for g, _ in gs], ["f2", "f10"])
            got = [[c["id"] for c in json.loads(p.read_text())["cities"]] for _, p in gs]
            self.assertEqual(got, [["f2c3-0", "f2c3-1", "f2c4-0"], ["f10c0-0"]])
            # a rectangle of about 1.1 x 0.7 km padded by 300 m is about 1.7 x 1.3 km: two fit under 5 km2, not three
            a = WD.padded_km2([50, 10, 50.01, 10.01])
            self.assertAlmostEqual(a, (1.1132 + 0.6) * (0.7155 + 0.6), delta=0.01)
            gs = WD.rect_groups(src, Path(t) / "h", cap_km2=5)
            self.assertEqual([g for g, _ in gs], ["f2-0", "f2-1", "f10"])
            got = [[c["id"] for c in json.loads(p.read_text())["cities"]] for _, p in gs]
            self.assertEqual(got, [["f2c3-0", "f2c3-1"], ["f2c4-0"], ["f10c0-0"]])


if __name__ == "__main__":
    unittest.main()
