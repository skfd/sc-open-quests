"""The world loop's two ends that are not a STOP, and the gate's heap as a metric (tools/stream/planet_store_day.py,
tools/stream/world_gate.py; DESIGN.md "The world day on the planet", "Engine heap"): a gate region the machine has
no heap for ends the run and leaves the day resumable; a new day the disk has no room for is not taken; each gate
region's heap given and peak are read off its engine's log. Run: python -m unittest"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "stream"))
import planet_store_day as PSD  # noqa: E402
import run  # noqa: E402
import world_gate as WG  # noqa: E402

ENDED = ("193 quests in v64.1.json (193 counted), 20 cities; threads=24 maxHeap=27648 MB\n"
         "pass 140.2 s, total 148.0 s; peak heap (sum of pool peaks) 27189 MB\n")
DIED = ("193 quests in v64.1.json (193 counted), 20 cities; threads=24 maxHeap=14336 MB\n"
        "error: Java heap space\njava.lang.OutOfMemoryError: Java heap space\n")


class Tmp(unittest.TestCase):
    """the loop's paths in a folder of the test's own; its log lines kept in self.lines"""

    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.d = Path(self.t.name)
        self.lines = []
        for name, value in (("STOPPED", self.d / "STOPPED"), ("LOG", self.d / "log.txt"), ("log", self.lines.append)):
            p = mock.patch.object(PSD, name, value)
            p.start()
            self.addCleanup(p.stop)


class GateHeapLines(unittest.TestCase):
    def test_given_and_peak(self):
        self.assertEqual(WG.heap_line("europe-central", run.engine_heap_of(ENDED)),
                         "gate heap: europe-central given 27,648 MB, peak 27,189 MB (98% of it)")

    def test_an_engine_that_died_of_memory(self):
        self.assertEqual(WG.heap_line("europe-central", run.engine_heap_of(DIED)),
                         "gate heap: europe-central given 14,336 MB, died of OutOfMemoryError before it logged a peak")

    def test_no_log(self):
        self.assertEqual(WG.heap_line("europe-west", {}),
                         "gate heap: europe-west given: not in the engine's log, no peak logged (the engine did not end)")

    def test_the_line_is_not_one_the_days_steps_read_as_a_gate_region(self):
        import day_metrics as DM
        self.assertIsNone(DM.GATE.match(WG.heap_line("europe-central", run.engine_heap_of(ENDED))))
        self.assertIsNone(DM.EXIT.match(WG.heap_line("europe-central", run.engine_heap_of(ENDED))))


class ClipHeap(unittest.TestCase):
    def test_every_region_with_a_log_also_one_counted_by_an_earlier_run(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t)
            for region, text in (("europe-west", ENDED.replace("27189", "20000")), ("europe-central", ENDED)):
                (out / region).mkdir()
                (out / region / "log.txt").write_text(text, encoding="utf-8", newline="\n")
            (out / "europe-west" / "done").write_text("", encoding="utf-8")
            got = WG.clip_heap(out)
        self.assertEqual(sorted(got), ["europe-central", "europe-west"])   # east and msk have no log yet
        self.assertEqual((got["europe-central"]["given MB"], got["europe-central"]["peak MB"]), (27648, 27189))
        self.assertEqual(got["europe-west"]["peak MB"], 20000)
        json.dumps(got)   # it goes into gate.json


class ClipSide(unittest.TestCase):
    """world_gate.clip_side with the engine replaced: what it asks for, and what a region short of memory leaves"""

    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.out = Path(self.t.name) / "gate"
        self.lines = []
        self.calls = []
        regions = [r for r in run.regions() if r["id"] in WG.REGIONS]
        for target, name, value in (
                (WG, "gate_notes", lambda w, regs, log=None: {r["id"]: Path(self.t.name) / f"{r['id']}.jsonl" for r in regs}),
                (run, "newest_quests_file", lambda: ROOT / "data" / "quests" / "v64.1.json"),
                (run, "region_cities", lambda r: ROOT / "data" / "cities" / f"{r['id']}.json")):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.assertEqual(len(regions), 4)

    def engine(self, fail_at=None, error=None, log_text=ENDED):
        def fake(pbf, cities, d, notes, tz, quests, today, min_heap_gb=None, what=None, log=None):
            region = d.name
            self.calls.append((region, min_heap_gb, what, log))
            if region == fail_at:
                if isinstance(error, subprocess.CalledProcessError):
                    d.mkdir(parents=True, exist_ok=True)
                    (d / "log.txt").write_text(DIED, encoding="utf-8", newline="\n")
                raise error
            d.mkdir(parents=True, exist_ok=True)
            (d / "log.txt").write_text(log_text, encoding="utf-8", newline="\n")
            return 50.0
        return mock.patch.object(WG.SCC, "engine", fake)

    def side(self):
        return WG.clip_side(Path(self.t.name), Path("europe-2026-11-21.osm.pbf"), "2026-11-21", self.out,
                            log=self.lines.append)

    def test_each_region_is_asked_with_its_minimum_and_its_heap_is_logged(self):
        with self.engine():
            secs = self.side()
        self.assertEqual(sorted(secs), sorted(WG.REGIONS))
        by = {c[0]: c for c in self.calls}
        self.assertEqual(by["europe-central"][1], 27)
        self.assertEqual([by[r][1] for r in WG.REGIONS if r != "europe-central"], [None, None, None])
        self.assertEqual(by["europe-central"][2], "gate europe-central")
        self.assertEqual(by["europe-central"][3], self.lines.append)   # the wait's lines go to the loop's log
        self.assertIn("gate: europe-central counted on europe-2026-11-21.osm.pbf in 50 s", self.lines)
        self.assertIn("gate heap: europe-central given 27,648 MB, peak 27,189 MB (98% of it)", self.lines)
        self.assertEqual(sum(l.startswith("gate heap: ") for l in self.lines), 4)

    def test_a_region_short_of_memory_leaves_the_ones_before_done_and_itself_to_do(self):
        with self.engine(fail_at="europe-central", error=run.MemoryBusy("not enough memory for the engine")):
            with self.assertRaises(run.MemoryBusy):
                self.side()
        self.assertTrue((self.out / "europe-west" / "done").exists())
        self.assertFalse((self.out / "europe-central" / "done").exists())
        self.assertFalse((self.out / "gate.json").exists())
        self.assertEqual([c[0] for c in self.calls], ["europe-west", "europe-central"])
        # the next run of the gate: west is not counted again, central is the first engine
        self.calls.clear()
        with self.engine():
            secs = self.side()
        self.assertEqual([c[0] for c in self.calls], ["europe-central", "europe-east", "europe-msk"])
        self.assertNotIn("europe-west", secs)
        self.assertEqual(sorted(WG.clip_heap(self.out)), sorted(WG.REGIONS))   # west's heap is still in gate.json

    def test_an_engine_that_dies_has_its_heap_said_before_the_failure_goes_up(self):
        err = subprocess.CalledProcessError(1, ["engine"])
        with self.engine(fail_at="europe-central", error=err):
            with self.assertRaises(subprocess.CalledProcessError):
                self.side()
        self.assertEqual(self.lines[-1],
                         "gate heap: europe-central given 14,336 MB, died of OutOfMemoryError before it logged a peak")
        self.assertFalse((self.out / "europe-central" / "done").exists())


class GuardedAndDays(Tmp):
    def test_a_failure_is_still_a_stop(self):
        def fails():
            raise ValueError("a count differs")
        with self.assertRaises(SystemExit):
            PSD.guarded("world gate 2026-11-21", fails)
        self.assertTrue(PSD.STOPPED.exists())
        self.assertIn("world gate 2026-11-21 failed: ValueError: a count differs", PSD.STOPPED.read_text())

    def test_memory_busy_passes_through_and_writes_no_stopped(self):
        def waits():
            raise run.MemoryBusy("not enough memory for the engine for gate europe-central after waiting 60 min")
        with self.assertRaises(run.MemoryBusy):
            PSD.guarded("world gate 2026-11-21", waits)
        self.assertFalse(PSD.STOPPED.exists())
        self.assertEqual(self.lines, [])

    def test_the_run_ends_cleanly_when_the_gate_has_no_memory(self):
        steps = iter([True, run.MemoryBusy("not enough memory for the engine for gate europe-central after waiting "
                                           "60 min: the machine can spare 14 GB of heap and it needs 27 GB")])

        def day():
            s = next(steps)
            if isinstance(s, BaseException):
                raise s
            return s
        self.assertEqual(PSD.days(40, day), 1)   # returns: main goes on to "planet store run ended"
        self.assertFalse(PSD.STOPPED.exists())
        self.assertEqual(len(self.lines), 1)
        for part in ("not now: not enough memory", "can spare 14 GB of heap", "needs 27 GB", "No STOPPED",
                     "the next run resumes the day at its gate"):
            self.assertIn(part, self.lines[0])
        self.assertNotIn("STOPPED:", self.lines[0])   # store_lock.run_going reads "STOPPED:" in the log as a stop

    def test_days_until_one_says_no_more_and_never_over_the_most(self):
        steps = iter([True, True, False, True])
        self.assertEqual(PSD.days(40, lambda: next(steps)), 2)
        self.assertEqual(PSD.days(3, lambda: True), 3)
        self.assertEqual(self.lines, [])

    def test_a_stop_inside_a_day_still_leaves_the_run(self):
        def day():
            PSD.stop("compact failed (exit 101)")
        with self.assertRaises(SystemExit):
            PSD.days(40, day)
        self.assertTrue(PSD.STOPPED.exists())


class DayDisk(unittest.TestCase):
    def test_the_two_numbers(self):
        self.assertEqual((PSD.DAY_NEEDS_GB, PSD.DISK_FLOOR_GB), (75, 40))

    def test_room_for_a_day(self):
        self.assertIsNone(PSD.day_disk_short("2026-11-22", free=lambda: 124.3))
        self.assertIsNone(PSD.day_disk_short("2026-11-22", free=lambda: 115.0))

    def test_no_room_says_the_numbers_and_that_it_is_no_stop(self):
        line = PSD.day_disk_short("2026-11-22", free=lambda: 97.4)
        for part in ("day 2026-11-22 not taken", "97 GiB free", "a day needs 115", "about 75 at its low",
                     "the 40 GiB floor", "no STOPPED", "done for now", "free 18 GiB"):
            self.assertIn(part, line)
        self.assertNotIn("\n", line)

    def test_the_default_reader_reads_a_disk(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertGreater(PSD.free_gb(Path(t)), 0)


class NewDayAsksTheDisk(Tmp):
    """one_day at a state a new day starts from (the store, the node file and the world at 11-21, the diff to 11-22
    and its Europe clip on disk): with the disk short it takes no day and writes nothing of one"""

    def setUp(self):
        super().setUp()
        d = self.d
        store, world, europe, diffs = d / "store", d / "world", d / "europe", d / "diffs"
        for p in (store, world, europe, diffs):
            p.mkdir()
        (store / "store.json").write_text(json.dumps({"generations": [{"gen": 20, "day": "2026-11-21"}]}), encoding="utf-8")
        (d / "planet.loc.state").write_text("2026-11-21T00:00:00Z\n", encoding="utf-8")
        (world / PSD.WS.WORLD_META).write_text(json.dumps({"clock": "2026-11-21T00:00:00Z"}), encoding="utf-8")
        (diffs / "5200.state.txt").write_text("sequenceNumber=5200\ntimestamp=2026-11-22T00\\:00\\:00Z\n", encoding="utf-8")
        (diffs / "5200.osc.gz").write_bytes(b"")
        (europe / "europe-2026-11-22.meta.json").write_text(json.dumps({"replication_sequence": 5200}), encoding="utf-8")
        (europe / "europe-2026-11-22.osm.pbf").write_bytes(b"")
        self.notes = mock.Mock(side_effect=AssertionError("the day was taken: its notes were asked for"))
        for target, name, value in ((PSD, "STORE", store), (PSD, "LOC", d / "planet.loc"), (PSD, "WORLD", world),
                                    (PSD, "EUROPE", europe), (PSD, "DIFF_DIRS", [diffs]), (PSD, "KEEP", d / "keep"),
                                    (PSD, "PINS", europe / "pins.json"), (PSD, "HOLD", d / "HOLD"),
                                    (PSD, "WDAYS", d / "world-days"), (PSD.WD, "notes_until", self.notes)):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_under_what_a_day_needs_no_day_is_taken(self):
        with mock.patch.object(PSD, "day_disk_short", lambda day: PSD_day_disk_short(day, lambda: 97.4)):
            self.assertIs(PSD.one_day(), False)
        self.assertEqual(len([l for l in self.lines if "not taken" in l]), 1)
        self.assertIn("day 2026-11-22 not taken: 97 GiB free", self.lines[-1])
        self.assertFalse(PSD.STOPPED.exists())
        self.assertFalse((self.d / "world-days").exists())   # no before/, no work
        self.assertFalse((self.d / "keep").exists())
        self.notes.assert_not_called()

    def test_with_room_the_day_goes_on_past_the_disk(self):
        with mock.patch.object(PSD, "day_disk_short", lambda day: None):
            with self.assertRaises(AssertionError):   # the next thing a new day does: the world's notes
                PSD.one_day()
        self.notes.assert_called_once()
        self.assertFalse(any("not taken" in l for l in self.lines))


PSD_day_disk_short = PSD.day_disk_short   # the function itself, while a test replaces the module's name


if __name__ == "__main__":
    unittest.main()
