"""tools/stream/engine_room.py, sized: an alive engine counted by what it can still take, a heap per engine from the
kept days, one more run at the day's heap after a failure for memory, the room's numbers per phase."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "stream"))

import day_metrics as DM  # noqa: E402
import engine_room as ER  # noqa: E402
import stream as S  # noqa: E402


class P:
    """a process as the room sees it"""
    def __init__(self, pid):
        self.pid = pid


def room(left, commits=None, sized=True):
    """a sized Room with `left` GB of commit and the engines' commit read from the dict `commits` (by pid)"""
    commits = commits if commits is not None else {}
    return ER.Room(status=lambda: (50.0, left, 88.0), poll_seconds=0, commit=commits.get, sized=sized), commits


class Sized(unittest.TestCase):
    def test_the_first_engine_needs_its_heap_and_the_jvms_own_over_the_reserve(self):
        self.assertTrue(room(16.5)[0].fits(8)[0])
        self.assertFalse(room(16.4)[0].fits(8)[0])

    def test_an_engine_not_started_is_counted_whole(self):
        r, _ = room(25.0)            # 25 - 8 = 17: two caps of 8.5 and not a gram more
        r.enter(8)
        self.assertTrue(r.fits(8)[0])
        r, _ = room(24.9)
        r.enter(8)
        self.assertFalse(r.fits(8)[0])

    def test_an_alive_engine_counts_for_what_it_can_still_take(self):
        """11-25 at rest: 24 GB left. Whole counting holds one engine alive and no second (16 < 8.5 + 8.5); an
        engine that has committed 5 GB of its 8.5 can take 3.5 more, and 16 holds 8.5 + 3.5"""
        r, commits = room(24.0)
        a = r.enter(8)
        self.assertFalse(r.fits(8)[0])
        a.started(P(11))
        self.assertFalse(r.fits(8)[0])          # started, no reading yet: whole
        commits[11] = 0.02                      # the launcher alone
        self.assertFalse(r.fits(8)[0])
        commits[11] = 5.0
        self.assertTrue(r.fits(8)[0])
        commits[11] = 0.9                       # 16 >= 8.5 + 7.6 is false by a hair
        self.assertFalse(r.fits(8)[0])

    def test_an_engine_over_its_cap_owes_nothing_and_never_gives_room_back(self):
        r, commits = room(16.5)
        r.enter(8).started(P(11))
        commits[11] = 9.4                       # past -Xmx and the allowance
        self.assertEqual(r.owed(r.slots[0]), 0.0)
        self.assertTrue(r.fits(8)[0])
        self.assertFalse(room(16.4, {11: 9.4})[0].fits(8)[0])

    def test_a_reader_that_fails_counts_the_engine_whole(self):
        def boom(pid):
            raise OSError("no such process")
        r = ER.Room(status=lambda: (50.0, 24.0, 88.0), commit=boom, sized=True)
        r.enter(8).started(P(11))
        self.assertEqual(r.owed(r.slots[0]), 8.5)
        r.commit = lambda pid: -1.0             # nonsense is no reading
        self.assertEqual(r.owed(r.slots[0]), 8.5)

    def test_small_heaps_run_side_by_side(self):
        """24 GB left: 16 for engines. Four of 3 g (3.5 each) fit whole; of 8 g, one"""
        r, _ = room(24.0)
        for _ in range(4):
            self.assertTrue(r.fits(3)[0])
            r.enter(3)
        self.assertFalse(r.fits(3)[0])

    def test_the_switch_off_is_the_old_rule_and_reads_no_pid(self):
        asked = []
        r = ER.Room(status=lambda: (50.0, 37.0, 88.0), commit=lambda pid: asked.append(pid) or 7.9, sized=False)
        for _ in range(3):
            self.assertTrue(r.fits(8)[0])
            r.enter(8).started(P(11))
        self.assertFalse(r.fits(8)[0])          # 29 >= 8 + 24 is false: three, as on the day of the stop
        self.assertEqual(asked, [])
        self.assertEqual(r.alive, [8, 8, 8])

    def test_the_waiting_line_says_what_the_alive_can_still_take(self):
        left = [19.0]
        r = ER.Room(status=lambda: (50.0, left[0], 88.0), poll_seconds=0, commit={11: 2.5}.get, sized=True)
        r.enter(8).started(P(11))
        said = []
        wait = r.cond.wait

        def waiting(timeout=None):
            left[0] = 30.0
            wait(0)
        r.cond.wait = waiting
        r.enter(5, "t1/f2", said.append)
        self.assertIn("t1/f2 waits: 19 GB commit left, 8 kept back, 1 of our engines alive (they can take 6.0 g more), "
                      "t1/f2 needs 5.5 g", said[0])
        self.assertIn("t1/f2 starts after", said[1])

    def test_leaving_by_slot_takes_that_engine_out(self):
        r, _ = room(60.0)
        a, b = r.enter(5), r.enter(5)
        r.leave(b)
        self.assertEqual(r.slots, [a])
        with r.engine(3) as s:
            self.assertEqual(r.alive, [5, 3])
            self.assertIsNone(s.pid)
        self.assertEqual(r.alive, [5])

    def test_the_phases_numbers_start_again(self):
        r, _ = room(60.0)
        a, b = r.enter(5), r.enter(5)
        r.leave(a)
        r.leave(b)
        r.waited_s, r._phase[1] = 1234.4, 1234.4
        self.assertEqual(r.phase_line("tier 2 old"),
                         "engine room: tier 2 old: most 2 at once, waited 1,234 s summed (2 engines)")
        self.assertEqual(r.phase(), {"most": 0, "waited s": 0.0, "engines": 0})
        r.enter(3)
        self.assertEqual(r.phase()["most"], 1)
        self.assertEqual((r.most, round(r.waited_s, 1)), (2, 1234.4))   # the process's own stay


@unittest.skipUnless(sys.platform == "win32", "the reading is Windows's")
class TreeCommit(unittest.TestCase):
    def test_a_launchers_grandchild_is_read_with_it(self):
        """a .bat (cmd.exe, as the engine's gradle launcher) starting a Python that holds 300 MB: the tree's commit
        is read from the launcher's pid, and the launcher alone is small"""
        with tempfile.TemporaryDirectory() as tmp:
            bat = Path(tmp) / "launcher.bat"
            flag = Path(tmp) / "holding"
            code = ("import sys,time,pathlib; b = bytearray(300 << 20); pathlib.Path(sys.argv[1]).write_text('y'); "
                    "time.sleep(60)")
            bat.write_text(f'@echo off\r\n"{sys.executable}" -c "{code}" "{flag}"\r\n', encoding="utf-8", newline="")
            seen = []
            p = subprocess.Popen([str(bat)], cwd=tmp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                t0 = time.time()
                while not flag.exists() and time.time() - t0 < 30:
                    time.sleep(0.1)
                self.assertTrue(flag.exists(), "the child did not start")
                gb = ER.tree_commit_gb(p.pid)
                self.assertIsNotNone(gb)
                self.assertGreater(gb, 0.29)
                self.assertLess(gb, 1.0)
                seen.append(gb)
            finally:
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
                p.wait()
            for _ in range(50):                 # gone: no reading (the room then counts it whole)
                if ER.tree_commit_gb(p.pid) is None:
                    break
                time.sleep(0.1)
            self.assertIsNone(ER.tree_commit_gb(p.pid))

    def test_this_process_reads_and_nothing_reads_as_none(self):
        self.assertGreater(ER.tree_commit_gb(os.getpid()), 0.001)
        self.assertIsNone(ER.tree_commit_gb(0))
        self.assertIsNone(ER.tree_commit_gb(None))


class RunStarted(unittest.TestCase):
    def test_the_exit_code_and_the_process_shown_once(self):
        seen = []
        rc = S.run_started([sys.executable, "-c", "import sys; sys.exit(3)"], seen.append)
        self.assertEqual(rc, 3)
        self.assertEqual(len(seen), 1)
        self.assertIsInstance(seen[0].pid, int)

    def test_a_watcher_that_fails_is_not_the_engines_failure(self):
        def boom(p):
            raise RuntimeError("the watcher")
        self.assertEqual(S.run_started([sys.executable, "-c", "pass"], boom), 0)
        self.assertEqual(S.run_started([sys.executable, "-c", "pass"]), 0)


def kept(world: Path, day: str, engines: dict) -> None:
    d = world / "days" / day
    d.mkdir(parents=True)
    (d / "engines.json").write_text(json.dumps({"schema": 1, "engines": {k: {"heap MB": v} for k, v in engines.items()}}),
                                    encoding="utf-8", newline="\n")


class Heaps(unittest.TestCase):
    def test_the_heap_of_a_peak(self):
        self.assertEqual(ER.heap_of(None, 8), 8)            # no history: the day's
        self.assertEqual(ER.heap_of(0, 8), 8)
        self.assertEqual(ER.heap_of(900, 8), 3)             # the notes: the least
        self.assertEqual(ER.heap_of(2048, 8), 3)            # 1.5 x 2 g = 3
        self.assertEqual(ER.heap_of(2049, 8), 4)            # a megabyte over: the next gigabyte
        self.assertEqual(ER.heap_of(2867, 8), 5)            # tier 2's median, 2.8 GB
        self.assertEqual(ER.heap_of(5120, 8), 8)            # p90: 7.5 -> 8
        self.assertEqual(ER.heap_of(6500, 8), 8)            # never over the day's
        self.assertEqual(ER.heap_of(900, 2), 2)             # a day's heap under the least stays the day's

    def test_the_highest_peak_of_the_newest_three_days_before_today(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Path(tmp)
            kept(w, "2026-11-21", {"t1/f1": 7000})                              # the fourth back: not read
            kept(w, "2026-11-22", {"t1/f1": 2000, "t2/groups/f1/old": 1000})
            kept(w, "2026-11-23", {"t1/f1": 3000})
            (w / "days" / "2026-11-24").mkdir()                                 # a day with no engines.json: no day
            kept(w, "2026-11-25", {"t1/f1": 2500, "notes/f1": 900})
            kept(w, "2026-11-26", {"t1/f1": 7500})                              # today's own, of a run before: not read
            kept(w, "2026-11-27", {"t1/f1": 7500})
            self.assertEqual(ER.peaks(w, "2026-11-26T00:00:00Z"),
                             {"t1/f1": 3000, "t2/groups/f1/old": 1000, "notes/f1": 900})
            ER._heaps.clear()
            self.assertEqual(ER.heap_for(w, "2026-11-26", "t1/f1", 8, sized=True), 5)       # ceil(1.5 x 3000 / 1024)
            self.assertEqual(ER.heap_for(w, "2026-11-26", "notes/f1", 8, sized=True), 3)
            self.assertEqual(ER.heap_for(w, "2026-11-26", "t1/f9", 8, sized=True), 8)       # no history
            self.assertEqual(ER.heap_for(w, "2026-11-26", "t1/f1", 8, sized=False), 8)      # the switch off

    def test_a_day_that_cannot_be_read_is_no_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Path(tmp)
            self.assertEqual(ER.peaks(w, "2026-11-26"), {})                     # no days folder
            kept(w, "2026-11-22", {"t1/f1": 2000})
            kept(w, "2026-11-23", {"t1/f1": 4000})
            for day, text in (("2026-11-24", "{not json"), ("2026-11-25", '{"engines": [1, 2]}')):
                (w / "days" / day).mkdir()
                (w / "days" / day / "engines.json").write_text(text, encoding="utf-8")
            self.assertEqual(ER.peaks(w, "2026-11-26"), {"t1/f1": 4000})

    def test_what_the_day_keeps_is_what_the_next_day_reads(self):
        """day_metrics.harvest's names are the keys, and the given heap is kept beside the peak"""
        log = ("area: f1c2-0   2.0 s  (map data 1.0 s: 10 nodes, 2 ways, 0 relations)\n"
               "pass 3.0 s, total 4.0 s; peak heap (sum of pool peaks) 2900 MB\n")
        with tempfile.TemporaryDirectory() as tmp:
            w, work = Path(tmp) / "w", Path(tmp) / "work"
            for rel in ("t1/f1", "t2/groups/f1/old", "t2/groups/f1/new", "notes/f1"):
                (work / rel).mkdir(parents=True)
                (work / rel / "engine.log").write_text(log, encoding="utf-8", newline="\n")
            ER.note_given(work / "t1/f1", 5)
            ER.note_given(work / "notes/f1", 8, 3)
            (work / "t2/groups/f1/old" / ER.FAILED_LOG).write_text(log, encoding="utf-8")   # not an engine of the day
            DM.write(w, "2026-11-25", work)
            rec = json.loads((w / "days/2026-11-25/engines.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(rec["engines"]), ["notes/f1", "t1/f1", "t2/groups/f1/new", "t2/groups/f1/old"])
            self.assertEqual(rec["engines"]["t1/f1"]["given MB"], 5120)
            self.assertEqual((rec["engines"]["notes/f1"]["given MB"], rec["engines"]["notes/f1"]["first given MB"]),
                             (8192, 3072))
            self.assertNotIn("given MB", rec["engines"]["t2/groups/f1/old"])
            ER._heaps.clear()
            for rel in rec["engines"]:
                self.assertEqual(ER.heap_for(w, "2026-11-26", rel, 8, sized=True), 5)       # ceil(1.5 x 2900 / 1024)


class InRoom(unittest.TestCase):
    """engine_room.in_room with an engine that is a function"""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "t2" / "groups" / "f1" / "old"
        self.room = ER.Room(status=lambda: (50.0, 60.0, 88.0), sized=True, commit=lambda pid: None)
        self.runs, self.said = [], []

    def tearDown(self):
        self.tmp.cleanup()

    def engine(self, fail_with=None, fail_under=8, code=1):
        def run(heap_gb, on_start, more):
            self.runs.append((heap_gb, more, list(self.room.alive)))
            on_start(P(4242))
            self.out.mkdir(parents=True, exist_ok=True)
            (self.out / "out").mkdir(exist_ok=True)
            (self.out / "out" / f"partial-{heap_gb}").write_text("x", encoding="utf-8")
            if fail_with is not None and heap_gb < fail_under:
                (self.out / "engine.log").write_text(fail_with, encoding="utf-8")
                raise SystemExit(f"engine failed ({code}), see {self.out / 'engine.log'}")
            (self.out / "engine.log").write_text("pass 1.0 s, total 2.0 s; peak heap (sum of pool peaks) 100 MB\n",
                                                 encoding="utf-8")
            return "the dump"
        return run

    def go(self, run, heap=5, day=8):
        return ER.in_room(run, self.out, "t2/groups/f1/old", heap, day, self.said.append, room=self.room,
                          cwd=Path(self.tmp.name))

    def given(self):
        return json.loads((self.out / ER.GIVEN).read_text(encoding="utf-8"))

    def test_an_engine_that_ends_well_runs_once_on_its_heap(self):
        self.assertEqual(self.go(self.engine()), "the dump")
        self.assertEqual(self.runs, [(5, ER.SIZED_OPTS, [5])])
        self.assertEqual((self.said, self.room.alive, self.given()), ([], [], {"given MB": 5120}))

    def test_out_of_heap_runs_once_more_on_the_days_heap_with_its_output_cleared(self):
        oom = "nodes 3.0 s\nTerminating due to java.lang.OutOfMemoryError: Java heap space\n"
        self.assertEqual(self.go(self.engine(oom, code=3)), "the dump")
        self.assertEqual(self.runs, [(5, ER.SIZED_OPTS, [5]), (8, "", [8])])    # the first had left the room
        self.assertEqual(self.said, ["engine room: t2/groups/f1/old failed for memory at 5 g (OutOfMemoryError); "
                                     "once more at 8 g"])
        self.assertFalse((self.out / "out" / "partial-5").exists())
        self.assertTrue((self.out / "out" / "partial-8").exists())
        self.assertEqual((self.out / ER.FAILED_LOG).read_text(encoding="utf-8"), oom)
        self.assertEqual(self.given(), {"given MB": 8192, "first given MB": 5120})
        self.assertEqual(self.room.alive, [])

    def test_the_commit_running_out_is_a_failure_for_memory_too(self):
        for text in ("# Native memory allocation (mmap) failed to map 2097152 bytes. Error detail: G1 virtual space\n",
                     "# An error report file with more information is saved as:\n# C:\\x\\hs_err_pid11428.log\n",
                     "Error occurred during initialization of VM\nCould not reserve enough space for 5242880KB object heap\n"):
            self.runs.clear()
            self.assertEqual(self.go(self.engine(text)), "the dump")
            self.assertEqual([r[0] for r in self.runs], [5, 8])

    def test_an_hs_err_file_written_since_the_start_is_a_failure_for_memory(self):
        old = Path(self.tmp.name) / "hs_err_pid1.log"
        old.write_text("an older crash", encoding="utf-8")
        os.utime(old, (time.time() - 3600, time.time() - 3600))
        with self.assertRaises(SystemExit):
            self.go(self.engine("it just stopped\n"))
        (Path(self.tmp.name) / "hs_err_pid2.log").write_text("this one", encoding="utf-8")
        self.runs.clear()
        self.assertEqual(self.go(self.engine("it just stopped\n")), "the dump")
        self.assertEqual([r[0] for r in self.runs], [5, 8])

    def test_any_other_failure_stays_the_failure_it_is(self):
        with self.assertRaises(SystemExit) as e:
            self.go(self.engine("Exception in thread main: no such file cities.json\n"))
        self.assertIn("engine failed (1)", str(e.exception))
        self.assertEqual([r[0] for r in self.runs], [5])
        self.assertTrue((self.out / "out" / "partial-5").exists())              # as it was left
        self.assertEqual((self.said, self.room.alive), ([], []))

    def test_a_second_failure_is_the_days_failure(self):
        with self.assertRaises(SystemExit):
            self.go(self.engine("java.lang.OutOfMemoryError: Java heap space\n", fail_under=99))
        self.assertEqual([r[0] for r in self.runs], [5, 8])
        self.assertEqual(self.room.alive, [])

    def test_out_of_heap_on_the_days_heap_is_not_run_again(self):
        with self.assertRaises(SystemExit):
            self.go(self.engine("java.lang.OutOfMemoryError: Java heap space\n", fail_under=99), heap=8)
        self.assertEqual(self.runs, [(8, "", [8])])                             # and no extra JVM option: as before

    def test_a_stop_of_the_room_is_not_an_engines_failure(self):
        self.room = ER.Room(status=lambda: (50.0, 9.0, 88.0), sized=True, poll_seconds=0, wait_minutes=0)
        with self.assertRaises(SystemExit) as e:
            self.go(self.engine())
        self.assertIn("no room in the commit charge", str(e.exception))
        self.assertEqual(self.runs, [])


class Launch(unittest.TestCase):
    """stream.engine and notes_day.note_quests as they start a launcher: a .bat that says a line and ends with 3"""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.bat = self.d / "engine.bat"
        self.bat.write_text("@echo off\r\necho opts %JAVA_OPTS%\r\nexit /b 3\r\n", encoding="utf-8", newline="")
        (self.d / "x").write_text("{}", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    @unittest.skipUnless(sys.platform == "win32", "a .bat")
    def test_stream_engine_fails_as_before_and_shows_its_process(self):
        seen = []
        with self.assertRaises(SystemExit) as e:
            S.engine(self.d / "x", self.d / "out", "2026-11-26T00:00:00Z", self.d / "x", "UTC", None, area_pass=False,
                     heap_gb=5, quests=self.d / "x", base=self.d, extra_opts="-Dx=1", exe=self.bat, on_start=seen.append)
        self.assertEqual(str(e.exception), f"engine failed (3), see {(self.d / 'out').resolve() / 'engine.log'}")
        self.assertEqual((self.d / "out" / "engine.log").read_text(encoding="utf-8").strip(),
                         "opts -Duser.timezone=UTC -Duser.language=en -Duser.country=CA -Xmx5g "
                         "-Dopenquests.areaPass=false -Dx=1")
        self.assertEqual(len(seen), 1)
        self.assertIsInstance(seen[0].pid, int)

    @unittest.skipUnless(sys.platform == "win32", "a .bat")
    def test_note_quests_fails_as_before_and_shows_its_process(self):
        import notes_day as N
        seen = []
        (self.d / "data" / "quests").mkdir(parents=True)
        (self.d / "data" / "quests" / "v1.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(SystemExit) as e:
            N.note_quests(self.d / "x", self.d / "x", "2026-11-26T00:00:00Z", self.d / "out", engine=self.bat,
                          heap_gb=3, base=self.d, on_start=seen.append, extra_opts=ER.SIZED_OPTS)
        self.assertEqual(str(e.exception), f"engine failed (3), see {self.d / 'out' / 'engine.log'}")
        self.assertEqual((self.d / "out" / "engine.log").read_text(encoding="utf-8").strip(),
                         "opts -Duser.timezone=UTC -Duser.language=en -Duser.country=CA -Xmx3g "
                         "-Dopenquests.areaPass=false -XX:+ExitOnOutOfMemoryError")
        self.assertEqual(len(seen), 1)


class WorldDay(unittest.TestCase):
    """world_day.engine_dump and counts_at's engines: the key, the heap and the process reach the room"""
    def setUp(self):
        import world_day as WD
        self.WD = WD
        self.tmp = tempfile.TemporaryDirectory()
        self.w, self.work = Path(self.tmp.name) / "w", Path(self.tmp.name) / "work"
        kept(self.w, "2026-11-25", {"t2/groups/f1/old": 2900, "t1/f1": 1000})
        self.saved = (WD.S.engine, WD.quiet, ER.ROOM, ER.SIZED)
        self.calls = []

        def engine(pbf, out, clock, cities, zone, notes, **kw):
            self.calls.append((out, kw["heap_gb"], kw["extra_opts"], list(ER.ROOM.alive)))
            kw["on_start"](P(77))
            self.pids = [s.pid for s in ER.ROOM.slots]
            return out / "state.bin"
        WD.S.engine, WD.quiet = engine, lambda s: None
        ER.ROOM = ER.Room(status=lambda: (50.0, 60.0, 88.0), sized=True, commit=lambda pid: None)
        ER._heaps.clear()
        self.said = []
        import types
        self.day = types.SimpleNamespace(w=self.w, work=self.work, today="2026-11-26T00:00:00Z", heap_gb=8,
                                         log=self.said.append, engine=None)

    def tearDown(self):
        self.WD.S.engine, self.WD.quiet, ER.ROOM, ER.SIZED = self.saved
        ER._heaps.clear()
        self.tmp.cleanup()

    def dump(self, rel, opts=""):
        out = self.work / rel
        return self.WD.engine_dump(self.day, self.work / "x.osm.pbf", out, "2026-11-25T00:00:00Z",
                                   self.work / "cities.json", self.work / "parts", True, opts)

    def test_each_engine_gets_its_own_heap_and_shows_its_process(self):
        ER.SIZED = True
        self.assertEqual(self.dump("t2/groups/f1/old", "-Dx=1"), self.work / "t2/groups/f1/old" / "state.bin")
        self.dump("t1/f1")
        self.dump("t2/groups/f2/old", "-Dx=1")          # no history: the day's heap, and the options as they were
        self.assertEqual([c[1:] for c in self.calls],
                         [(5, "-Dx=1 " + ER.SIZED_OPTS, [5]), (3, ER.SIZED_OPTS, [3]), (8, "-Dx=1", [8])])
        self.assertEqual(self.pids, [77])
        self.assertEqual(json.loads((self.work / "t1/f1" / ER.GIVEN).read_text(encoding="utf-8")), {"given MB": 3072})
        self.assertEqual(ER.ROOM.phase_line("tier 1"), "engine room: tier 1: most 1 at once, waited 0 s summed (3 engines)")

    def test_the_notes_engines_go_through_the_room_with_their_own_heap(self):
        WD = self.WD
        kept(self.w, "2026-11-24", {"notes/f1": 900})
        ER._heaps.clear()
        ER.SIZED = True
        got = []

        class Seen(Exception):
            pass

        def note_quests(cities, clip, clock, out, **kw):
            kw["on_start"](P(78))
            got.append((out, kw["heap_gb"], kw["extra_opts"], list(ER.ROOM.alive), [s.pid for s in ER.ROOM.slots]))
            raise Seen()
        saved = (WD.N.note_quests, WD.files_of)
        WD.N.note_quests, WD.files_of = note_quests, lambda w: [{"id": "f1"}]
        try:
            with self.assertRaises(Seen):
                WD.counts_at(self.w, "2026-11-26T00:00:00Z", None, [], self.work / "notes", None, 8)
        finally:
            WD.N.note_quests, WD.files_of = saved
        self.assertEqual(got, [(self.work / "notes" / "f1", 3, ER.SIZED_OPTS, [3], [78])])
        self.assertEqual(ER.ROOM.alive, [])
        self.assertEqual(ER.ROOM.phase_line("notes"), "engine room: notes: most 1 at once, waited 0 s summed (1 engines)")

    def test_the_switch_off_gives_every_engine_the_days_heap(self):
        ER.SIZED = False
        ER.ROOM = ER.Room(status=lambda: (50.0, 60.0, 88.0), sized=False)
        self.dump("t2/groups/f1/old", "-Dx=1")
        self.dump("t1/f1")
        self.assertEqual([c[1:] for c in self.calls], [(8, "-Dx=1", [8]), (8, "", [8])])


if __name__ == "__main__":
    unittest.main()
