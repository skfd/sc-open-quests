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

    def test_in_keys(self):
        rows = np.array([1, 1, 2, 5, 5, 5, 9], np.int64)
        self.assertEqual([True, True, False, True, True, True, False], W.in_keys(rows, np.array([0, 1, 5, 7])).tolist())
        self.assertFalse(W.in_keys(rows, np.zeros(0, np.int64)).any())

    def test_route_and_replace(self):
        files = [{"id": "a", "rect": [0, 0, 1, 1]}, {"id": "b", "rect": [1, 0, 2, 1]}]
        rows = np.array([(4, 5_000_000, 5_000_000, 1, 1, 0, 0), (8, 10_000_000, 5_000_000, 1, 1, 0, 0),
                         (12, 15_000_000, 5_000_000, 2, 1, 0, 0), (16, 30_000_000, 0, 1, 1, 0, 0)], W.REC)
        parts, unrouted = W.route(rows, files)
        self.assertEqual([[0, 1], [2]], [p.tolist() for p in parts])  # on the shared edge: the first file
        self.assertEqual(1, unrouted)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.bin"
            np.sort(rec([(4, 1, 0), (4, 2, 0), (8, 1, 1), (20, 1, 0)]), order=W.ORDER).tofile(p)
            mask = np.array([False, True, False] + [False] * 8)  # quest 1 only
            d, a = W.replace_in_file(p, np.array([4, 8]), mask, rec([(8, 1, 0), (6, 1, 0)]))
            got = [(int(x["key"]), int(x["quest"]), int(x["kind"])) for x in np.fromfile(p, W.REC)]
            self.assertEqual((2, 2), (d, a))
            self.assertEqual([(4, 2, 0), (6, 1, 0), (8, 1, 0), (20, 1, 0)], got)
            self.assertEqual([4, 6, 8, 20], np.load(Path(td) / "state-keys.npy").tolist())
            self.assertEqual((0, 0), W.replace_in_file(p, np.array([99]), mask, rec([])))

    def test_dense_locations(self):
        import stream as S
        # the index maps the file until it is collected, which Windows will not let a temp folder delete under
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            p = Path(td) / "t.loc"
            locs = S.DenseLocations(p)
            locs.overlay[5], locs.overlay[9] = (52.5, 13.25), (1.0, 2.0)
            self.assertEqual((52.5, 13.25), locs.get(5))  # from the overlay, before save
            locs.save()
            self.assertEqual({}, locs.overlay)
            locs.overlay[9] = None  # deleted
            locs.save()
            del locs
            again = S.DenseLocations(p)
            self.assertEqual({5: (52.5, 13.25), 9: None, 7: None}, again.get_many([5, 9, 7]))
            del again

    def test_is_sorted(self):
        self.assertTrue(W.is_sorted(rec([(1, 2, 0), (1, 2, 1), (2, 0, 0)])))
        self.assertFalse(W.is_sorted(rec([(1, 2, 1), (1, 2, 0)])))
        self.assertFalse(W.is_sorted(rec([(2, 0, 0), (1, 0, 0)])))


if __name__ == "__main__":
    unittest.main()
