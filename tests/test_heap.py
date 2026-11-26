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

    def test_a_regions_minimum_and_name_go_to_the_wait_and_the_line(self):
        said = []
        with mock.patch.dict(run.os.environ, {"JAVA_OPTS": ""}), \
                mock.patch.object(run, "engine_heap_gb", return_value=30) as heap:
            env = run.engine_env("Europe/Berlin", heap=True, min_heap_gb=27, what="europe-central", say=said.append)
        heap.assert_called_once_with(min_gb=27, what="the engine for europe-central", say=said.append)
        self.assertEqual(env["JAVA_OPTS"], "-Xmx30g -Duser.timezone=Europe/Berlin")
        self.assertEqual(said, ["engine heap, europe-central: -Xmx30g (what the machine can spare now; at least 27g)"])

    def test_without_a_minimum_the_line_names_the_general_one(self):
        with mock.patch.dict(run.os.environ, {"JAVA_OPTS": ""}), \
                mock.patch.object(run, "engine_heap_gb", return_value=30), mock.patch.object(run, "log") as log:
            run.engine_env("Europe/Berlin", heap=True)
        log.assert_called_once_with(
            f"engine heap: -Xmx30g (what the machine can spare now; at least {run.HEAP_MIN_GB}g)")


class RegionMinimum(unittest.TestCase):
    """a region's least heap (config/regions.json minHeapGb): wait for it, then MemoryBusy with the numbers"""
    SHORT = (22.0, 40.0, 88.0)   # 14 GB to spare: over HEAP_MIN_GB, under europe-central's 27 (the 11-21 gate)
    STILL = (35.0, 60.0, 88.0)   # 27 GB to spare

    def setUp(self):
        self.slept, self.said = [], []

    def heap(self, readings, min_gb, wait_minutes=60):
        it = iter(readings)
        return run.engine_heap_gb(status=lambda: next(it), sleep=self.slept.append, wait_minutes=wait_minutes,
                                  min_gb=min_gb, what="the engine for europe-central", say=self.said.append)

    def test_what_the_config_says(self):
        regs = {r["id"]: r for r in run.regions()}
        self.assertEqual(run.region_min_heap_gb(regs["europe-central"]), 27)
        # no recorded peak, no minimum: every other region as before
        self.assertEqual([r for r in regs if r != "europe-central" and run.region_min_heap_gb(regs[r]) is not None], [])

    def test_a_minimum_is_a_whole_number_of_gb(self):
        self.assertIsNone(run.region_min_heap_gb({"id": "x"}))
        self.assertEqual(run.region_min_heap_gb({"id": "x", "minHeapGb": 27}), 27)
        for bad in (0, -1, 27.5, "27", True):
            with self.assertRaises(ValueError):
                run.region_min_heap_gb({"id": "x", "minHeapGb": bad})

    def test_without_a_minimum_14_gb_starts_as_before(self):
        self.assertEqual(self.heap([self.SHORT], None), 14)
        self.assertEqual(self.slept, [])

    def test_a_minimum_under_the_general_one_changes_nothing(self):
        self.assertEqual(self.heap([self.SHORT], 4), 14)
        with self.assertRaises(run.MemoryBusy):
            self.heap([(15.0, 40.0, 88.0)] * 3, 4, wait_minutes=1)   # 7 GB to spare: still under HEAP_MIN_GB

    def test_short_of_the_minimum_it_waits_and_starts_once_there_is_enough(self):
        self.assertEqual(self.heap([self.SHORT, self.SHORT, self.STILL], 27), 27)
        self.assertEqual(len(self.slept), 2)
        self.assertEqual(len(self.said), 2)   # the wait's first line, and "memory freed"
        self.assertIn("can spare 14 GB of heap", self.said[0])
        self.assertIn("the engine for europe-central needs 27 GB", self.said[0])
        self.assertIn("memory freed after 2 min", self.said[1])

    def test_one_line_every_few_minutes_while_it_waits(self):
        with self.assertRaises(run.MemoryBusy):
            self.heap([self.SHORT] * 20, 27, wait_minutes=12)
        self.assertEqual(len(self.slept), 12)
        self.assertEqual(len(self.said), 3)   # at 0, 5 and 10 minutes
        self.assertEqual([("waited 0 of" in s, "waited 5 of" in s, "waited 10 of" in s) for s in self.said],
                         [(True, False, False), (False, True, False), (False, False, True)])

    def test_after_the_bound_the_error_names_memory_and_the_numbers(self):
        with self.assertRaises(run.MemoryBusy) as e:
            self.heap([self.SHORT] * 5, 27, wait_minutes=2)
        msg = str(e.exception)
        self.assertIsInstance(e.exception, RuntimeError)   # run.main logs it as the run's ERROR line
        for part in ("not enough memory", "after waiting 2 min", "can spare 14 GB of heap", "22 GB free",
                     "40 GB commit left", "needs 27 GB", "no engine started"):
            self.assertIn(part, msg)

    def test_the_bound_is_sixty_minutes_unless_the_environment_says(self):
        self.assertEqual(run.HEAP_WAIT_MINUTES, int(run.os.environ.get("SCOQ_HEAP_WAIT_MINUTES", "60")))

    def test_the_city_run_asks_for_its_regions_minimum_before_the_engine(self):
        # count() is not run here (it takes the pipeline lock and reads the store); the line it calls is this one
        with mock.patch.dict(run.os.environ, {"JAVA_OPTS": ""}), \
                mock.patch.object(run, "engine_heap_gb", side_effect=run.MemoryBusy("not enough memory")), \
                mock.patch.object(run, "log"):
            region = {"id": "europe-central", "timeZone": "Europe/Berlin", "minHeapGb": 27}
            with self.assertRaises(run.MemoryBusy):
                run.engine_env(region["timeZone"], heap=True, min_heap_gb=run.region_min_heap_gb(region),
                               what=region["id"])


class EngineHeapOf(unittest.TestCase):
    """the heap an engine had and the peak it reached, read off its own log"""
    HEAD = ("startup: registry and cities 0.4 s, parts 0.0 s, engine and its indexes 0.1 s\n"
            "193 quests in v64.1.json (193 counted: 140 filter, 52 ported custom, the note quest), 20 cities; "
            "threads=24 maxHeap=27648 MB\n"
            "nodes                    19.3 s  128105644 nodes\n")

    def test_an_engine_that_ended(self):
        h = run.engine_heap_of(self.HEAD + "pass 140.2 s, total 148.0 s; peak heap (sum of pool peaks) 27189 MB\n")
        self.assertEqual(h, {"given MB": 27648, "pass s": 140.2, "total s": 148.0, "peak MB": 27189, "ended": True})

    def test_an_engine_that_died_of_memory_logs_no_peak(self):
        h = run.engine_heap_of(self.HEAD.replace("27648", "14336") + "error: Java heap space\n"
                               "java.lang.OutOfMemoryError: Java heap space\n\tat openquests.AreaPass.run(AreaPass.kt:292)\n")
        self.assertEqual(h, {"given MB": 14336, "ended": False, "out of memory": True})

    def test_no_log_lines_at_all(self):
        self.assertEqual(run.engine_heap_of(""), {"ended": False})


if __name__ == "__main__":
    unittest.main()
