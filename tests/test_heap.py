"""run.py engine heap: what the machine can spare when the engine starts. Run: python -m unittest"""
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run  # noqa: E402


class SpareHeap(unittest.TestCase):
    def test_the_smaller_of_free_memory_and_commit_less_the_reserve(self):
        self.assertEqual(run.spare_heap_gb((60.0, 30.5, 92.0)), 30 - run.HEAP_RESERVE_GB)
        self.assertEqual(run.spare_heap_gb((20.9, 50.0, 92.0)), 20 - run.HEAP_RESERVE_GB)

    def test_never_more_than_a_share_of_physical_memory(self):
        self.assertEqual(run.spare_heap_gb((90.0, 200.0, 92.0)), int(92 * run.HEAP_MAX_FRACTION) - run.HEAP_RESERVE_GB)


class EngineHeap(unittest.TestCase):
    def setUp(self):
        self.slept = []
        self.log = mock.patch.object(run, "log").start()
        self.addCleanup(mock.patch.stopall)

    def heap(self, readings, wait_minutes=60):
        it = iter(readings)
        return run.engine_heap_gb(status=lambda: next(it), sleep=self.slept.append, wait_minutes=wait_minutes)

    def test_idle_machine_starts_at_once_with_what_it_can_spare(self):
        self.assertEqual(self.heap([(70.0, 70.0, 92.0)]), int(92 * run.HEAP_MAX_FRACTION) - run.HEAP_RESERVE_GB)
        self.assertEqual(self.slept, [])

    def test_busy_machine_waits_until_memory_frees(self):
        busy, free = (15.0, 40.0, 92.0), (50.0, 50.0, 92.0)
        self.assertEqual(self.heap([busy, busy, free]), 42)
        self.assertEqual(len(self.slept), 2)

    def test_memory_that_stays_busy_skips_the_count(self):
        busy = (15.0, 40.0, 92.0)
        with self.assertRaises(RuntimeError):
            self.heap([busy] * 10, wait_minutes=3)
        self.assertEqual(len(self.slept), 3)

    def test_off_windows_the_start_script_default_stands(self):
        self.assertIsNone(self.heap([None]))


class EngineEnv(unittest.TestCase):
    def test_heap_goes_into_java_opts_before_the_zone(self):
        with mock.patch.dict(run.os.environ, {"JAVA_OPTS": ""}), \
                mock.patch.object(run, "engine_heap_gb", return_value=30), mock.patch.object(run, "log"):
            env = run.engine_env("Europe/Berlin", heap=True)
        self.assertEqual(env["JAVA_OPTS"], "-Xmx30g -Duser.timezone=Europe/Berlin")

    def test_an_explicit_xmx_wins(self):
        with mock.patch.dict(run.os.environ, {"JAVA_OPTS": "-Xmx16g"}), \
                mock.patch.object(run, "engine_heap_gb") as heap:
            env = run.engine_env("America/Toronto", heap=True)
        heap.assert_not_called()
        self.assertEqual(env["JAVA_OPTS"], "-Xmx16g -Duser.timezone=America/Toronto")

    def test_the_build_gets_no_heap(self):
        with mock.patch.object(run, "engine_heap_gb") as heap:
            run.engine_env()
        heap.assert_not_called()


if __name__ == "__main__":
    unittest.main()
