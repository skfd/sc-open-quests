"""The world day on the planet store (tools/stream/planet_store_day.py, DESIGN.md "The world day on the planet"): the
tier-2 delta's group fingerprints against the per-row form, a prepared day saved and read back without the node
file's memmap, the world's D-1 kept by hard links and put back, and the hidden flags written around such a link."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "stream"))
import notes_day as N  # noqa: E402
import placesets as P  # noqa: E402
import planet_store_day as PSD  # noqa: E402
import world_day as WD  # noqa: E402
import world_state as WS  # noqa: E402


def rows(rng, n):
    a = np.zeros(n, P.WREC)
    a["key"] = rng.integers(0, max(1, n // 3), n) * 4 + rng.integers(0, 3, n)
    a["quest"] = rng.integers(0, 8, n)
    a["lat"], a["lon"] = rng.integers(0, 5, n), rng.integers(0, 5, n)
    a["place"] = rng.integers(0, 3, n)
    return np.unique(a)


class ChangedGroupsTest(unittest.TestCase):
    def test_same_as_per_row_groups(self):
        rng = np.random.default_rng(7)
        for _ in range(3):
            old = rows(rng, 50_000)
            new = old.copy()
            i = rng.choice(len(new), 900, replace=False)
            new["flags"][i[:300]] ^= 64
            new["lat"][i[300:600]] += 1
            new = np.unique(np.concatenate([np.delete(new, i[600:]), rows(rng, 200)]))
            go, gn = WD.groups(old), WD.groups(new)
            want = sorted(c for c in go.keys() | gn.keys() if go.get(c) != gn.get(c))
            cand, ho, hn = WD.changed_groups(old, new)
            self.assertEqual(cand.tolist(), want)
            self.assertEqual(ho.tolist(), [c in go for c in want])
            self.assertEqual(hn.tolist(), [c in gn for c in want])

    def test_empty_sides(self):
        a = rows(np.random.default_rng(1), 100)
        cand, ho, hn = WD.changed_groups(np.zeros(0, P.WREC), a)
        self.assertEqual(len(cand), len(np.unique(WD.codes_of(a))))
        self.assertFalse(ho.any())
        self.assertTrue(hn.all())


class SaveDayTest(unittest.TestCase):
    def test_round_trip_without_the_memmap(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            nodes = t / "planet.loc"
            m = np.zeros((10, 2), "<i4")
            m[3] = (100_000_000, 450_000_000)  # lon, lat in 1e-7
            m.tofile(nodes)
            last_node = {3: (2, 0, True, {}, (46.0, 11.0)), 5: (2, 0, False, {}, None)}
            from world_tier2 import NodeFile
            day = WD.Day(t, t, t / "5164.osc.gz", "2026-11-02T00:00:00Z", "2026-11-01T00:00:00Z", t, nodes, last_node,
                         {}, {}, {7: [3, 5]}, NodeFile(nodes), NodeFile(nodes, overlay={3: (46.0, 11.0)}),
                         np.zeros(4, WD.T2.ROWPOS),
                         14, None, 8, None, print, {"read diff": 1.0}, {"oldRows": 4})
            WD.save_day(day, t / "day.pkl")
            self.assertLess((t / "day.pkl").stat().st_size, 10_000)  # no node file inside
            back = WD.load_day(t / "day.pkl")
            self.assertEqual((back.today, back.prev, back.gen_before, back.old_refs), (day.today, day.prev, 14, {7: [3, 5]}))
            self.assertAlmostEqual(back.old_places.places([3])[0][0], 45.0)
            self.assertAlmostEqual(back.new_places.places([3])[0][0], 46.0)
            self.assertTrue(np.isnan(back.new_places.places([5])[0][0]))
            del day, back  # their memmaps, before the directory goes
            import gc
            gc.collect()


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        w = Path(self.t.name) / "world"
        self.w = w
        rng = np.random.default_rng(3)
        files = []
        for k in range(3):
            d = w / "files" / f"f{k}"
            d.mkdir(parents=True)
            WS.write_rows(d / WS.WORLD_BIN, np.sort(rows(rng, 1000), order=["key"]))
            files.append({"id": f"f{k}", "rect": [-90, -180, 90, 180]})
        (w / "plan.json").write_text(json.dumps({"files": files}), encoding="utf-8")
        (w / "world.json").write_text(json.dumps({"clock": "2026-11-01T00:00:00Z"}), encoding="utf-8")
        (w / "place-sets.json").write_text("{}", encoding="utf-8")
        self.old = (PSD.WORLD, PSD.LOG)
        PSD.WORLD, PSD.LOG = w, Path(self.t.name) / "log.txt"

    def tearDown(self):
        PSD.WORLD, PSD.LOG = self.old
        self.t.cleanup()

    def bins(self):
        return {f: (self.w / "files" / f / WS.WORLD_BIN).read_bytes() for f in ("f0", "f1", "f2")}

    def test_put_back_after_every_kind_of_write(self):
        before = self.w.parent / "before"
        want = self.bins()
        keys0 = np.load(self.w / "files" / "f1" / WS.WORLD_KEYS)
        PSD.snapshot(before)
        # a finish's writes: replace_in_file / write_rows (a new file), flags in place, keys saved, small files
        p0 = self.w / "files" / "f0" / WS.WORLD_BIN
        r = np.fromfile(p0, P.WREC)
        WS.write_rows(p0, r[: len(r) // 2])
        p1 = self.w / "files" / "f1" / WS.WORLD_BIN
        r1 = np.fromfile(p1, P.WREC)
        moved = np.unique(N.row_keys(r1[:50]))
        N._hidden_file((str(p1), P.WREC, moved, moved, np.zeros(0, np.int64), 1 << 20))
        self.assertNotEqual(p1.read_bytes(), want["f1"])
        self.assertEqual((before / "files" / "f1" / WS.WORLD_BIN).read_bytes(), want["f1"])  # the link kept its bytes
        np.save(self.w / "files" / "f1" / WS.WORLD_KEYS, np.zeros(3, np.int64))
        (self.w / "world.json").write_text(json.dumps({"clock": "2026-11-02T00:00:00Z"}), encoding="utf-8")
        np.save(self.w / "touched.npy", np.arange(5))
        (self.w / "counts" / "2026-11-02").mkdir(parents=True)
        PSD.restore(before, "2026-11-02")
        self.assertEqual(self.bins(), want)
        self.assertEqual(np.load(self.w / "files" / "f1" / WS.WORLD_KEYS).tolist(), keys0.tolist())
        self.assertEqual(PSD.world_clock(), "2026-11-01T00:00:00Z")
        self.assertFalse((self.w / "touched.npy").exists())
        self.assertFalse((self.w / "counts" / "2026-11-02").exists())
        # and again: a second failed finish is put back from the same copy
        WS.write_rows(p0, r[:10])
        PSD.restore(before, "2026-11-02")
        self.assertEqual(self.bins(), want)

    def test_flags_in_place_without_a_link(self):
        p = self.w / "files" / "f2" / WS.WORLD_BIN
        ino = os.stat(p).st_ino
        r = np.fromfile(p, P.WREC)
        moved = np.unique(N.row_keys(r[:50]))
        res = N._hidden_file((str(p), P.WREC, moved, moved, np.zeros(0, np.int64), 1 << 20))
        self.assertGreater(res["flagsChanged"], 0)
        self.assertEqual(os.stat(p).st_ino, ino)  # no copy when nothing else holds the file


if __name__ == "__main__":
    unittest.main()
