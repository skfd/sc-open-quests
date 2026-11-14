"""tier2.delta: the state changes only where the recount changed from yesterday's to today's."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "stream"))
import tier2  # noqa: E402
from stream import REC, MATCH, DUE, M_NOW  # noqa: E402


def rec(*rows):
    return np.array([(k, lat, 0, q, f, kind, due) for k, lat, q, f, kind, due in rows], REC)


def codes(a):
    return sorted(((int(r["key"]), int(r["quest"]), int(r["lat"]), int(r["kind"])) for r in a))


class DeltaTest(unittest.TestCase):
    def test_four_cases(self):
        # key 5: unchanged; 9: a disagreement on both days (the state lacks it); 13: opens; 17: closes;
        # 21: moves (the state holds it); 25: moves (the state lacks it); 29: a date that came
        state = rec((5, 1, 3, M_NOW, MATCH, 0), (17, 1, 3, M_NOW, MATCH, 0), (21, 1, 3, M_NOW, MATCH, 0),
                    (29, 1, 3, M_NOW, DUE, 100), (33, 1, 3, M_NOW, MATCH, 0))
        old = rec((5, 1, 3, M_NOW, MATCH, 0), (9, 1, 3, M_NOW, MATCH, 0), (17, 1, 3, M_NOW, MATCH, 0),
                  (21, 1, 3, M_NOW, MATCH, 0), (25, 1, 3, M_NOW, MATCH, 0), (29, 1, 3, M_NOW, DUE, 100))
        new = rec((5, 1, 3, M_NOW, MATCH, 0), (9, 1, 3, M_NOW, MATCH, 0), (13, 1, 3, M_NOW, MATCH, 0),
                  (21, 2, 3, M_NOW, MATCH, 0), (25, 2, 3, M_NOW, MATCH, 0), (29, 1, 3, M_NOW | 2, MATCH, 0))
        out, st = tier2.delta(state, old, new)
        self.assertEqual(codes(out), [(5, 3, 1, MATCH), (13, 3, 1, MATCH), (21, 3, 2, MATCH), (29, 3, 1, MATCH),
                                      (33, 3, 1, MATCH)])
        self.assertEqual(st["added"], 1)
        self.assertEqual(st["removed"], 1)
        self.assertEqual(st["changed"], 2)
        self.assertEqual(st["changed, the state lacked it (kept out)"], 1)

    def test_nothing_changed(self):
        state = rec((5, 1, 3, M_NOW, MATCH, 0))
        same = rec((5, 1, 3, M_NOW, MATCH, 0), (9, 1, 4, M_NOW, MATCH, 0))
        out, st = tier2.delta(state, same, same.copy())
        self.assertEqual(codes(out), codes(state))
        self.assertEqual(st["rows dropped"], 0)


if __name__ == "__main__":
    unittest.main()
