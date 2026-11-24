"""tools/stream/engine_room.py: the world day's engines enter only when the commit charge holds them."""
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "stream"))

import engine_room as ER  # noqa: E402


class Clock:
    """a clock the test moves: every poll of the room adds 30 s to it"""
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def room(commit, clock=None, wait_minutes=60):
    """a Room whose commit left is read from the list `commit` (its last value stays)"""
    clock = clock or Clock()
    seen = []

    def status():
        v = commit.pop(0) if len(commit) > 1 else commit[0]
        seen.append(v)
        return (50.0, v, 88.0)

    r = ER.Room(status=status, clock=clock, poll_seconds=0, wait_minutes=wait_minutes)
    wait = r.cond.wait

    def waiting(timeout=None):   # a poll: 30 s pass on the test's clock, no real sleep
        clock.t += 30
        wait(0)
    r.cond.wait = waiting
    return r, seen


class Fits(unittest.TestCase):
    def test_the_first_engine_needs_its_heap_over_the_reserve(self):
        r, _ = room([16.0])
        self.assertEqual(r.fits(8), (True, 16.0))
        r, _ = room([15.9])
        self.assertEqual(r.fits(8), (False, 15.9))

    def test_the_day_of_the_stop_runs_three_at_a_time_not_four(self):
        """2026-11-23 at rest: 37 GB commit left. 37 - 8 = 29 holds three heaps of 8 g, not four."""
        r, _ = room([37.0])
        self.assertTrue(r.fits(8)[0])
        r.alive = [8]
        self.assertTrue(r.fits(8)[0])
        r.alive = [8, 8]
        self.assertTrue(r.fits(8)[0])
        r.alive = [8, 8, 8]
        self.assertFalse(r.fits(8)[0])

    def test_no_reading_lets_every_engine_in(self):
        r = ER.Room(status=lambda: None)
        r.alive = [8] * 20
        self.assertEqual(r.fits(8), (True, None))


class Enter(unittest.TestCase):
    def test_room_at_once_says_nothing(self):
        r, _ = room([40.0])
        said = []
        r.enter(8, "f1/old", said.append)
        self.assertEqual((r.alive, said, r.most, r.waited_s), ([8], [], 1, 0.0))

    def test_waits_for_the_machine_then_enters_and_says_both(self):
        r, seen = room([10.0, 10.0, 10.0, 20.0])
        said = []
        r.enter(8, "f1/old", said.append)
        self.assertEqual(r.alive, [8])
        self.assertEqual(len(said), 2)
        self.assertIn("f1/old waits: 10 GB commit left, 8 kept back, 0 of our engines alive (0 g), f1/old needs 8 g",
                      said[0])
        self.assertIn("f1/old starts after 90 s; 20 GB commit left, 1 alive", said[1])
        self.assertEqual(r.waited_s, 90.0)

    def test_one_line_every_five_minutes_while_none_is_alive(self):
        r, _ = room([10.0] * 25 + [20.0])     # 25 polls of 30 s short: 12.5 min
        said = []
        r.enter(8, "f1/old", said.append)
        self.assertEqual(len([s for s in said if "waits" in s]), 3)   # at 0, 5 and 10 min

    def test_after_the_bound_with_none_alive_it_is_a_stop(self):
        r, _ = room([10.0], wait_minutes=60)
        with self.assertRaises(SystemExit) as e:
            r.enter(8, "f1/old", lambda m: None)
        self.assertIn("no room in the commit charge for f1/old after 60 min with no engine of ours alive", str(e.exception))
        self.assertIn("10 GB commit left", str(e.exception))
        self.assertEqual(r.alive, [])

    def test_with_engines_alive_it_waits_past_the_bound_and_says_so_once(self):
        r, _ = room([20.0] * 200 + [40.0], wait_minutes=60)   # 100 min short, then room
        r.alive = [8]
        said = []
        r.enter(8, "f2/old", said.append)
        self.assertEqual(r.alive, [8, 8])
        self.assertEqual(len([s for s in said if "waits" in s]), 1)
        self.assertIn("1 of our engines alive (8 g)", said[0])

    def test_leaving_wakes_the_one_that_waits(self):
        r = ER.Room(status=lambda: (50.0, 24.0, 88.0), poll_seconds=5)   # 24 - 8 = 16: one engine, not two
        r.enter(8)
        entered = threading.Event()
        t = threading.Thread(target=lambda: (r.enter(8, "second", lambda m: None), entered.set()))
        t.start()
        self.assertFalse(entered.wait(0.2))
        r.leave(8)                      # the status still says 24, and now nobody is alive
        self.assertTrue(entered.wait(2))
        t.join()
        self.assertEqual(r.alive, [8])

    def test_the_context_leaves_when_the_engine_fails(self):
        r, _ = room([40.0])
        with self.assertRaises(RuntimeError):
            with r.engine(8, "f1/old"):
                self.assertEqual(r.alive, [8])
                raise RuntimeError("the engine died")
        self.assertEqual(r.alive, [])


if __name__ == "__main__":
    unittest.main()
