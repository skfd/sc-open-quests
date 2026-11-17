"""placesets and place_counts: a run's place sets interned into the world table (the same set, the same number, across
runs), the counting rules at a clock (matches by their bits, dates coming due aged-only, hidden rows nowhere), and the
(set, quest) sums expanded to every part of the set; world_state.seed_w and counts_w end to end on two files."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "stream"))
import place_counts as C  # noqa: E402
import placesets as P  # noqa: E402
import world_state as W  # noqa: E402

M_NOW, M_AGED, M_05, M_AGED_05, M_2, M_AGED_2, HIDDEN = 1, 2, 4, 8, 16, 32, 64
DAY = 1440


def wrec(rows):
    """(key, quest, flags, kind, due, place)"""
    a = np.zeros(len(rows), P.WREC)
    for i, (k, q, fl, kind, due, place) in enumerate(rows):
        a[i]["key"], a[i]["quest"], a[i]["flags"], a[i]["kind"], a[i]["due"], a[i]["place"] = k, q, fl, kind, due, place
    return a


def dump(d: Path, rows, quests, run_sets, parts, asof="2026-11-01T00:00:00Z"):
    """an engine dump with places: rows (key, quest, flags, kind, due, run set)"""
    a = np.zeros(len(rows), P.REC)
    sets = np.zeros(len(rows), "<u4")
    for i, (k, q, fl, kind, due, s) in enumerate(rows):
        a[i]["key"], a[i]["quest"], a[i]["flags"], a[i]["kind"], a[i]["due"] = k, q, fl, kind, due
        sets[i] = s
    d.mkdir(parents=True, exist_ok=True)
    a.tofile(d / "state.bin")
    sets.tofile(d / "state.bin.places")
    (d / "state.bin.json").write_text(json.dumps({"asOf": asof, "quests": quests}))
    (d / "state.bin.places.json").write_text(json.dumps({"sets": run_sets, "parts": parts}))


class PlaceSetsTest(unittest.TestCase):
    def test_intern_across_runs(self):
        with tempfile.TemporaryDirectory() as t:
            ps = P.PlaceSets(Path(t) / "place-sets.json")
            a = ps.remap({"parts": ["x", "y", "city:c1"], "sets": [[], [0, 2], [0, 1, 2]]})
            b = ps.remap({"parts": ["city:c1", "x"], "sets": [[], [1, 0]]})  # the same set as a's 1, numbered its own way
            self.assertEqual(a[0], 0)
            self.assertEqual(b[1], a[1])
            self.assertNotEqual(a[1], a[2])
            ps.save()
            again = P.PlaceSets(Path(t) / "place-sets.json")
            self.assertEqual(sorted(again.ids_of(int(a[2]))), ["city:c1", "x", "y"])
            self.assertEqual(again.intern(["y", "city:c1", "x", "x"]), a[2])


class CountsTest(unittest.TestCase):
    def test_rules(self):
        clock = 1000 * DAY
        rows = wrec([
            (4 * 1, 0, M_NOW, 0, 0, 1),                                  # a node match: open
            (4 * 2 + 1, 0, M_NOW | M_AGED | M_05 | M_2, 0, 0, 1),        # a way match, aged at x1, open at all three
            (4 * 3, 0, M_NOW | HIDDEN, 0, 0, 1),                         # hidden: nowhere
            (4 * 4, 0, M_NOW, 1, clock - DAY, 1),                        # dated, come: open, aged
            (4 * 5, 0, M_NOW, 1, clock + DAY, 1),                        # dated, not yet
            (4 * 6, 0, M_05, 1, clock, 1),                               # dated for 0.5, come today
            (4 * 7, 0, 0, 1, clock - DAY, 1),                            # dated, no setting bit: the default
            (4 * 8 + 2, 1, M_2 | M_AGED_2, 0, 0, 2),                     # a relation, only at 2, another set
        ])
        codes, sums = C.by_set(rows, clock, 2)
        got = {int(c): dict(zip(C.MEASURES, s.tolist())) for c, s in zip(codes, sums)}
        q0 = got[1 * 2 + 0]
        self.assertEqual((q0["open"], q0["nodes"], q0["ways"], q0["relations"]), (4, 3, 1, 0))
        self.assertEqual(q0["agedOnly"], 3)  # the way, the come date, the date with no setting bit
        self.assertEqual((q0["open05"], q0["aged05"], q0["open2"], q0["aged2"]), (2, 1, 1, 0))
        q1 = got[2 * 2 + 1]
        self.assertEqual((q1["open"], q1["open2"], q1["aged2"]), (0, 1, 1))

    def test_expand(self):
        sets = [(), (0, 1), (1, 2)]
        codes = np.array([1 * 3 + 0, 2 * 3 + 0, 2 * 3 + 2], np.int64)
        sums = np.array([[5] + [0] * 8, [7] + [0] * 8, [1] + [0] * 8], np.int64)
        c, s = C.expand(codes, sums, sets, 3)
        got = {int(k): int(v[0]) for k, v in zip(c, s)}
        self.assertEqual(got, {0 * 3 + 0: 5, 1 * 3 + 0: 12, 2 * 3 + 0: 7, 1 * 3 + 2: 1, 2 * 3 + 2: 1})

    def test_seed_and_counts(self):
        with tempfile.TemporaryDirectory() as t:
            w = Path(t)
            plan = {"files": [{"id": "f0", "rect": [0, 0, 1, 1]}, {"id": "f1", "rect": [0, 1, 1, 2]}]}
            (w / "plan.json").write_text(json.dumps(plan))
            # two files, their quests listed in different orders, a place (p) in both
            dump(w / "files/f0", [(8, 0, M_NOW, 0, 0, 1), (4, 1, M_NOW, 0, 0, 1), (4, 1, M_NOW, 0, 0, 1)],
                 ["A", "B"], [[], [0, 1]], ["p", "city:c0"])
            dump(w / "files/f1", [(12, 1, M_NOW | M_AGED, 0, 0, 1)], ["B", "A"], [[], [1, 0]], ["city:c1", "p"])
            W.seed_w(w)
            meta = json.loads((w / "world.json").read_text())
            self.assertEqual(meta["quests"], ["A", "B"])
            r0 = np.fromfile(w / "files/f0/world.bin", P.WREC)
            self.assertEqual(len(r0), 2)  # the duplicate record dropped
            self.assertTrue(W.is_sorted(r0))
            W.counts_w(w)
            cm = json.loads((w / "counts/counts.json").read_text())
            with np.load(w / "counts/counts.npz") as z:  # closed, or Windows keeps the temporary folder
                d = C.as_dict(z["part"].astype(np.int64) * 2 + z["quest"], z["m"], 2, cm["parts"], cm["quests"])
            self.assertEqual(d["p"]["A"]["open"], 2)  # key 8 in f0 and key 12 in f1 (its own order said "A" second)
            self.assertEqual(d["p"]["B"]["open"], 1)
            self.assertEqual(d["p"]["A"]["agedOnly"], 1)
            self.assertEqual(d["city:c0"], {"A": {"open": 1, "nodes": 1}, "B": {"open": 1, "nodes": 1}})
            self.assertEqual(d["city:c1"], {"A": {"open": 1, "nodes": 1, "agedOnly": 1}})


if __name__ == "__main__":
    unittest.main()
