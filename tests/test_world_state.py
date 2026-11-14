"""world_state.sort_all: every file sorted in place by (key, quest, kind), the same rows kept, the manifest and the
keys shared between files written, and a second run changes nothing."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "stream"))
import world_state as W  # noqa: E402


def rec(rows):
    return np.array([(k, 0, 0, q, 0, kind, 0) for k, q, kind in rows], W.REC)


class WorldStateTest(unittest.TestCase):
    def test_sort(self):
        with tempfile.TemporaryDirectory() as td:
            w = Path(td)
            files = {"f0": [(9, 3, 0), (5, 2, 1), (5, 2, 0), (5, 1, 0), (13, 1, 0)],
                     "f1": [(21, 1, 0), (13, 4, 0), (17, 1, 1)]}
            plan = {"files": [{"id": i, "rect": [0, n, 1, n + 1]} for n, i in enumerate(files)]}
            (w / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            for i, rows in files.items():
                (w / "files" / i).mkdir(parents=True)
                rec(rows).tofile(w / "files" / i / "state.bin")
            W.sort_all(w, workers=1)
            for i, rows in files.items():
                r = np.fromfile(w / "files" / i / "state.bin", W.REC)
                self.assertTrue(W.is_sorted(r))
                self.assertEqual(sorted(rows), [(int(x["key"]), int(x["quest"]), int(x["kind"])) for x in r])
            self.assertEqual([(5, 1, 0), (5, 2, 0), (5, 2, 1), (9, 3, 0), (13, 1, 0)],
                             [(int(x["key"]), int(x["quest"]), int(x["kind"])) for x in np.fromfile(w / "files" / "f0" / "state.bin", W.REC)])
            m = json.loads((w / "world-state.json").read_text(encoding="utf-8"))
            self.assertEqual(8, m["rows"])
            self.assertEqual([(3, 5, 13), (3, 13, 21)], [(f["keys"], f["minKey"], f["maxKey"]) for f in m["files"]])
            self.assertEqual([13], np.load(w / "world-state-shared.npy").tolist())
            before = {i: (w / "files" / i / "state.bin").read_bytes() for i in files}
            W.sort_all(w, workers=1)
            self.assertEqual(before, {i: (w / "files" / i / "state.bin").read_bytes() for i in files})

    def test_is_sorted(self):
        self.assertTrue(W.is_sorted(rec([(1, 2, 0), (1, 2, 1), (2, 0, 0)])))
        self.assertFalse(W.is_sorted(rec([(1, 2, 1), (1, 2, 0)])))
        self.assertFalse(W.is_sorted(rec([(2, 0, 0), (1, 0, 0)])))


if __name__ == "__main__":
    unittest.main()
