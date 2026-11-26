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


if __name__ == "__main__":
    unittest.main()
