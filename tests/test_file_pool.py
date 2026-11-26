"""tools/stream/file_pool.py and the world day's passes that go through it: each pooled pass against its serial
form on a fixture of several files, every file byte for byte and every returned value exactly."""
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "stream"))
import file_pool as FP  # noqa: E402
import placesets as P  # noqa: E402
import world_day as WD  # noqa: E402
import world_state as WS  # noqa: E402
import world_tier2 as T2  # noqa: E402


def same_array(a: np.ndarray, b: np.ndarray) -> bool:
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


def tree(d: Path) -> dict[str, bytes]:
    """every file under d by its relative name: the bytes"""
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


def world(d: Path, n_files: int = 7, rows: int = 400, seed: int = 5) -> list[dict]:
    """a world of n_files files in a row of 10-degree boxes, WREC rows sorted, keys shared between neighbours (an
    element on an edge has rows in two files); file 3 is empty"""
    rng = np.random.default_rng(seed)
    files = []
    for k in range(n_files):
        n = 0 if k == 3 else rows + 37 * k
        r = np.zeros(n, P.WREC)
        r["key"] = rng.integers(1, 3000, n) * 4 + rng.integers(0, 3, n)
        r["quest"] = rng.integers(0, 6, n)
        r["lat"] = rng.integers(0, int(10e7), n)
        r["lon"] = rng.integers(int(k * 10e7), int((k + 1) * 10e7), n)
        r["flags"] = rng.choice(np.array([1, 3, 5, 21, 65], np.uint8), n)
        r["kind"] = rng.integers(0, 2, n)
        r["due"] = rng.integers(0, 2000, n)
        r["place"] = rng.integers(0, 9, n)
        r = np.unique(r)
        r = r[np.argsort(WS.order_code(r), kind="stable")]
        fid = f"f{k}"
        (d / "files" / fid).mkdir(parents=True)
        WS.write_rows(d / "files" / fid / WS.WORLD_BIN, r)
        files.append({"id": fid, "rect": [0.0, k * 10.0, 10.0, (k + 1) * 10.0]})
    (d / "plan.json").write_text(json.dumps({"files": files}), encoding="utf-8")
    return files


class OrderedTest(unittest.TestCase):
    def test_in_order_and_never_more_than_the_width_at_once(self):
        live, most, lock = [0], [0], threading.Lock()

        def work(i):
            with lock:
                live[0] += 1
                most[0] = max(most[0], live[0])
            time.sleep(0.03 * (8 - i) if i < 8 else 0.0)   # the earlier, the slower: they end out of order
            return i

        def done(i):
            with lock:
                live[0] -= 1

        started = []

        def items():
            for i in range(20):
                started.append(i)
                yield i

        got = []
        for i in FP.ordered(work, items(), 3):
            got.append(i)
            self.assertLessEqual(len(started) - len(got), 2)   # beside the one held here, two more at most
            time.sleep(0.005)                                  # the caller's own work on the result
            done(i)
        self.assertEqual(got, list(range(20)))
        self.assertLessEqual(most[0], 3)   # in work or waiting to be taken, the caller's one among them
        self.assertEqual(most[0], 3)

    def test_width_one_is_the_plain_loop_on_this_thread(self):
        me = threading.get_ident()
        seen = []
        out = list(FP.ordered(lambda i: seen.append(threading.get_ident()) or i * 2, range(5), 1))
        self.assertEqual(out, [0, 2, 4, 6, 8])
        self.assertEqual(set(seen), {me})

    def test_a_failure_comes_at_its_place_and_nothing_new_starts(self):
        started = []

        def work(i):
            started.append(i)
            if i == 2:
                raise ValueError("file 2")
            return i

        got = []
        with self.assertRaises(ValueError):
            for i in FP.ordered(work, range(50), 2):
                got.append(i)
        self.assertEqual(got, [0, 1])
        self.assertLess(max(started), 5)


class OldRowsTest(unittest.TestCase):
    def test_the_threaded_old_rows_are_rows_of_keys(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            files = world(d)
            every = np.concatenate([np.fromfile(d / "files" / f["id"] / WS.WORLD_BIN, P.WREC)["key"] for f in files])
            rng = np.random.default_rng(1)
            for keys in (rng.choice(every, 150), np.array([4 * 5000 + 1], np.int64), np.zeros(0, np.int64),
                         np.fromfile(d / "files" / "f5" / WS.WORLD_BIN, P.WREC)["key"][:40]):   # one file's only
                want = WD.rows_of_keys(d, keys)
                for workers in (1, 4):
                    got = T2.old_rows(d, keys, dtype=P.WREC, name=WS.WORLD_BIN, keys_name=WS.WORLD_KEYS, workers=workers)
                    self.assertTrue(same_array(want, got))
                self.assertTrue(same_array(want, WD.old_rows_of(d, keys, 4)))
                self.assertTrue(same_array(want, WD.old_rows_of(d, keys, 1)))
            self.assertGreater(len(WD.rows_of_keys(d, every[:300])), 0)


def added_of(added) -> str:
    return json.dumps([[k, sorted(v)] for k, v in added.items()])   # the keys in the order they were made


def new_rows(d: Path, files: list[dict], n: int, seed: int) -> np.ndarray:
    """rows of a recount: some at keys the files hold, some new, at positions in every file but the last two"""
    rng = np.random.default_rng(seed)
    r = np.zeros(n, P.WREC)
    r["key"] = rng.integers(1, 3300, n) * 4 + rng.integers(0, 3, n)
    r["quest"] = rng.integers(0, 6, n)
    r["lat"] = rng.integers(0, int(10e7), n)
    r["lon"] = rng.integers(0, int((len(files) - 2) * 10e7), n)
    r["flags"], r["place"] = 1, rng.integers(0, 9, n)
    return np.unique(r)


class PooledPassesTest(unittest.TestCase):
    """each pass with a pool of 1 (the serial loop it was) and of 4, on copies of one world: the same files, byte
    for byte, and the same values back"""

    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.d = Path(self.t.name)
        self.files = world(self.d / "w1")
        world(self.d / "w4")
        self.assertEqual(tree(self.d / "w1"), tree(self.d / "w4"))

    def test_tier_1s_rewrite(self):
        new1 = new_rows(self.d, self.files, 300, 11)
        every = np.concatenate([np.fromfile(self.d / "w1" / "files" / f["id"] / WS.WORLD_BIN, P.WREC)["key"]
                                for f in self.files])
        touched = np.unique(np.concatenate([every[::7], new1["key"]]))
        tier1 = np.array([True, True, False, True, True, False])
        new1 = new1[tier1[new1["quest"]]]
        parts, _ = WS.route(new1, self.files)
        got = {}
        for pool in (1, 4):
            w = self.d / f"w{pool}"
            from collections import defaultdict
            added = defaultdict(set, {"f6": {1}})
            got[pool] = (WD.tier1_rewrite(w, self.files, parts, touched, tier1, new1, added, pool), added_of(added), tree(w))
        self.assertEqual(got[1][:2], got[4][:2])
        self.assertEqual(got[1][2], got[4][2])
        self.assertGreater(got[1][0][0], 100)
        self.assertGreater(got[1][0][1], 100)

    def test_tier_1s_rewrite_is_the_loop_it_was(self):
        from collections import defaultdict
        new1 = new_rows(self.d, self.files, 200, 12)
        touched = np.unique(new1["key"])
        tier1 = np.ones(6, bool)
        parts, _ = WS.route(new1, self.files)
        w, added = self.d / "w1", defaultdict(set)
        d1 = a1 = 0
        for f, idx in zip(self.files, parts):     # finish's loop before the pool, word for word
            d_, a_ = WS.replace_in_file(w / "files" / f["id"] / WS.WORLD_BIN, touched, tier1, new1[idx], dtype=P.WREC,
                                        keys_name=WS.WORLD_KEYS)
            d1, a1 = d1 + d_, a1 + a_
            if len(idx):
                added[f["id"]] |= set(WD.codes_of(new1[idx]).tolist())
        added4 = defaultdict(set)
        self.assertEqual(WD.tier1_rewrite(self.d / "w4", self.files, parts, touched, tier1, new1, added4, 4), (d1, a1))
        self.assertEqual(added_of(added4), added_of(added))
        self.assertEqual(tree(self.d / "w4"), tree(w))

    def test_the_tier_2_delta(self):
        from collections import defaultdict
        state = np.concatenate([np.fromfile(self.d / "w1" / "files" / f["id"] / WS.WORLD_BIN, P.WREC) for f in self.files])
        rng = np.random.default_rng(3)
        old = np.unique(state[rng.choice(len(state), 600, replace=False)])
        new = old.copy()
        new["lat"][200:350] += 5                             # changed, held
        new = np.unique(np.concatenate([new[200:], new_rows(self.d, self.files, 150, 13)]))   # removed; added
        got = {}
        for pool in (1, 4):
            w = self.d / f"w{pool}"
            added, T = defaultdict(set), {}
            st = WD.delta_w(w, old, new, self.files, added, T, pool)
            got[pool] = (json.dumps(st), added_of(added), list(T), tree(w))
        self.assertEqual(got[1][:3], got[4][:3])
        self.assertEqual(got[1][3], got[4][3])
        st = json.loads(got[1][0])
        self.assertGreater(st["rows dropped"], 100)
        self.assertGreater(st["rows added"], 100)
        self.assertGreater(st["changed"], 50)
        self.assertEqual(list(st)[-3:], ["rows added", "unrouted", "rows dropped"])

    def test_the_delta_with_nothing_changed_and_with_nothing_dropped(self):
        from collections import defaultdict
        state = np.fromfile(self.d / "w1" / "files" / "f0" / WS.WORLD_BIN, P.WREC)
        for old, new in ((state[:50], state[:50]),                                  # nothing: no file read twice
                         (np.zeros(0, P.WREC), new_rows(self.d, self.files, 40, 14))):    # only added rows
            got = {}
            for pool in (1, 4):
                added, T = defaultdict(set), {}
                st = WD.delta_w(self.d / f"w{pool}", old, new, self.files, added, T, pool)
                got[pool] = (json.dumps(st), added_of(added), list(T), tree(self.d / f"w{pool}"))
            self.assertEqual(got[1], got[4])
        # rows of elements no file holds, all in f1's box: f1 is rewritten, every other file is left as it was
        far = np.zeros(30, P.WREC)
        far["key"], far["quest"], far["flags"] = np.arange(30) * 4 + 4 * 9000, 2, 1
        far["lat"], far["lon"] = int(5e7), int(15e7)
        before = tree(self.d / "w1")
        got = {}
        for pool in (1, 4):
            added, T = defaultdict(set), {}
            st = WD.delta_w(self.d / f"w{pool}", np.zeros(0, P.WREC), far, self.files, added, T, pool)
            got[pool] = (json.dumps(st), added_of(added), list(T), tree(self.d / f"w{pool}"))
        self.assertEqual(got[1], got[4])
        self.assertEqual(json.loads(got[1][0]), {"added": 30, "rows added": 30, "unrouted": 0, "rows dropped": 0})
        self.assertEqual(sorted(n for n, b_ in got[1][3].items() if before[n] != b_),
                         ["files/f1/world-keys.npy", "files/f1/world.bin"])

    def test_the_counts(self):
        import place_counts as C
        paths = [self.d / "w1" / "files" / f["id"] / WS.WORLD_BIN for f in self.files]
        sets = [(), (0,), (1,), (0, 2), (3,), (1, 3, 4), (2,), (4,), (0, 1, 2, 3, 4)]
        extra = [(2, 5, np.array([3] + [0] * (len(C.MEASURES) - 1), np.int64))]
        a = C.count_files(paths, P.WREC, 1000, sets, 6, extra=extra, pool=1)
        b = C.count_files(paths, P.WREC, 1000, sets, 6, extra=extra, pool=4)
        self.assertTrue(same_array(a[0], b[0]) and same_array(a[1], b[1]))
        self.assertGreater(len(a[0]), 20)
        # the loop it was, word for word
        per = []
        for p in paths:
            rows = np.fromfile(p, P.WREC)
            per.append(C.by_set(rows, 1000, 6))
        c = C.add_up([C.expand(*C.add_up(per), sets, 6),
                      (np.array([2 * 6 + 5], np.int64), np.array([extra[0][2]], np.int64))])
        self.assertTrue(same_array(a[0], c[0]) and same_array(a[1], c[1]))
        out = {}
        for pool, (codes, sums) in ((1, a), (4, b)):
            C.write(self.d / f"counts{pool}", codes, sums, 6, "2026-11-02T00:00:00Z", list("abcdef"), list("vwxyz"))
            out[pool] = tree(self.d / f"counts{pool}")
        self.assertEqual(out[1], out[4])

    def test_the_engines_small_files(self):
        from unittest import mock
        cells, wd = [], self.d / "world"
        for k in range(5):
            cid = f"f{k // 2}c{k}"
            cells.append({"id": cid, "file": f"f{k // 2}", "rect": [50.0, k * 1.0, 51.0, k + 1.0], "timeZone": "UTC"})
            if k != 3:   # a cell without a parts file
                pd = wd / "files" / f"f{k // 2}" / "parts"
                pd.mkdir(parents=True, exist_ok=True)
                (pd / f"{cid}.json").write_text(json.dumps({"schema": 1, "city": cid, "parts": [
                    {"id": "near", "geometry": "g/near.geojson"}, {"id": "far", "geometry": "g/far.geojson"},
                    {"id": f"nobox{k}", "geometry": "g/é.geojson"}]}), encoding="utf-8")
        rng = np.random.default_rng(9)
        rects = {}
        for k in (4, 0, 3, 1):   # not in the cells' order: the files' numbers follow the dict's
            s, w_ = 50.0 + rng.random(40) * 0.9, k + rng.random(40) * 0.9
            rects[k] = np.column_stack([s, w_, s + 0.01, w_ + 0.01])
        boxes = T2.PartBoxes(np.array(["far", "near"]), np.array([[20.0, 60.0, 20.1, 60.1], [0.0, 50.0, 2.5, 50.5]]), [])
        got = {}
        for name, pool, batch in (("p1", 1, 256), ("p4", 4, 256), ("p4small", 4, 3), ("p2", 2, 1)):
            work = self.d / name / "work"
            (work / "cells").mkdir(parents=True)
            (work / "cells" / "left-from-a-run-before.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(FP, "SMALL_BATCH", batch):
                cf, pdir, st = T2.write_engine_files(rects, cells, wd, work, self.d / name, boxes, pool=pool)
            got[name] = (cf.relative_to(self.d / name).as_posix(), pdir.relative_to(self.d / name).as_posix(),
                         json.dumps(st), tree(self.d / name))
        for name in ("p4", "p4small", "p2"):
            self.assertEqual(got["p1"][:3], got[name][:3])
            self.assertEqual(got["p1"][3], got[name][3], name)
        files = got["p1"][3]
        self.assertEqual(sum(n.startswith("work/cells/") for n in files), 160)
        self.assertNotIn("work/cells/left-from-a-run-before.json", files)
        self.assertGreater(sum(n.startswith("work/parts/") for n in files), 100)
        self.assertLess(sum(n.startswith("work/parts/") for n in files), 160)   # cell 3 has no parts
        self.assertEqual(json.loads(got["p1"][2])["rectangles"], 160)

    def test_a_small_file_that_cannot_be_written_is_an_error(self):
        with self.assertRaises(OSError):
            with FP.SmallFiles(4) as out:
                for i in range(600):
                    out.put(self.d / "no-such-folder" / f"{i}.json", "{}")
        with self.assertRaises(OSError):
            with FP.SmallFiles(4) as out:
                out.put(self.d / "no-such-folder" / "one.json", "{}")   # in the last, part-filled batch


if __name__ == "__main__":
    unittest.main()
