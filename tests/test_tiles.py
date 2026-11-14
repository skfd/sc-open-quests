"""tiles.py and tilestore.py: the tiles a segment crosses, the tiles under a padded box, and a tile payload's columns
coming back as they went in."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "stream"))
import tiles as T  # noqa: E402
import tilestore as S  # noqa: E402


def xy(keys):
    return sorted((int(k) >> T.Z, int(k) & (T.NT - 1)) for k in keys)


class TilesTest(unittest.TestCase):
    def test_segment_tiles(self):
        s, k = T.segment_tiles(np.array([0.5]), np.array([0.5]), np.array([2.5]), np.array([1.5]))
        self.assertEqual(xy(k), [(0, 0), (1, 0), (1, 1), (2, 1)])
        s, k = T.segment_tiles(np.array([0.5]), np.array([0.5]), np.array([0.6]), np.array([3.5]))
        self.assertEqual(xy(k), [(0, 0), (0, 1), (0, 2), (0, 3)])
        # a diagonal through a corner region still takes both tiles beside it, never a tile it does not touch
        s, k = T.segment_tiles(np.array([0.9]), np.array([0.2]), np.array([1.2]), np.array([0.9]))
        self.assertEqual(xy(k), [(0, 0), (1, 0)])

    def test_box_tiles_and_padding(self):
        s, w, n, e = 51.50, -0.13, 51.51, -0.12
        keys = T.box_tiles(s, w, n, e)
        fx, fy = T.frac_xy(np.array([s, n]), np.array([w, e]))
        self.assertEqual(len(keys), (int(fx[1]) - int(fx[0]) + 1) * (int(fy[0]) - int(fy[1]) + 1))
        ps, pw, pn, pe = T.padded(s, w, n, e, 300)
        self.assertAlmostEqual((pn - n) * T.M_LAT, 300, places=6)
        self.assertTrue(set(keys.tolist()) <= set(T.box_tiles(ps, pw, pn, pe).tolist()))


class PayloadTest(unittest.TestCase):
    def test_round_trip(self):
        cols = [S.delta(np.array([5, 9, 12, 40], np.int64)), np.array([-3, 7], np.int32), np.array([1, 0, 2], np.int8),
                np.frombuffer(b"k\0v\0", np.uint8), np.zeros(0, np.int64)]
        back = S.unpack_cols(S.pack_cols(cols))
        self.assertEqual(len(back), len(cols))
        for a, b in zip(cols, back):
            self.assertEqual(a.dtype, b.dtype)
            self.assertTrue((a == b).all())
        self.assertEqual(S.undelta(back[0]).tolist(), [5, 9, 12, 40])

    def test_gather(self):
        data = np.frombuffer(b"aabbbc", np.uint8)
        offs = np.array([0, 2, 5, 6])
        lens, b = S.gather(offs, np.array([2, 0]), data)
        self.assertEqual(lens.tolist(), [1, 2])
        self.assertEqual(b.tobytes(), b"caa")

    def test_ignore_relation(self):
        self.assertTrue(S.ignore_relation({"type": "route", "route": "bus"}))
        self.assertFalse(S.ignore_relation({"type": "route", "route": "ferry"}))
        self.assertFalse(S.ignore_relation({"type": "multipolygon"}))
        self.assertTrue(S.ignore_relation({"type": "boundary"}))
        self.assertEqual(S.parse_tags(b"a\0b\0c\0\0"), {"a": "b", "c": ""})


if __name__ == "__main__":
    unittest.main()
