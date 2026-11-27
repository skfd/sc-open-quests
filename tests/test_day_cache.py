"""A world day that stops keeps what writes nothing into the world (tools/stream/day_cache.py): an engine's output is
reused only behind its marker, emptied without one, run again with SCOQ_DAY_CACHE=0; tier 2's kept groups are not
read again; PAUSE stops the day at the next engine (also one waiting for room) and the loop ends with no STOPPED,
taking no day while it is there. Run: python -m unittest"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "stream"))
import day_cache as DC  # noqa: E402
import engine_room  # noqa: E402
import planet_store_day as PSD  # noqa: E402
import world_day as WD  # noqa: E402

CLOCK = "2026-11-26T00:00:00Z"


class Base(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.d = Path(self.t.name)
        for target, name, value in ((DC, "PAUSE", self.d / "PAUSE"), (WD, "quiet", lambda *a, **k: None)):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.dict(os.environ, {"SCOQ_DAY_CACHE": ""})
        p.start()
        self.addCleanup(p.stop)
        self.day = SimpleNamespace(work=self.d / "work", w=self.d / "w", today=CLOCK, heap_gb=8, log=None,
                                   engine=None)
        self.runs = []

        def fake(day, pbf, out, clock, cities, parts, area_pass, extra_opts, key):
            self.runs.append(key)
            out.mkdir(parents=True, exist_ok=True)
            (out / "state.bin").write_bytes(b"rows")
            (out / "state.bin.json").write_text("{}")
            return out / "state.bin"

        p = mock.patch.object(WD, "_engine_dump", side_effect=fake)
        p.start()
        self.addCleanup(p.stop)

    def dump(self, name="f1"):
        return WD.engine_dump(self.day, self.d / "x.pbf", self.day.work / "t1" / name, CLOCK, self.d / "c.json",
                              self.d / "parts", False)


class Markers(Base):
    def test_written_last_and_whole(self):
        DC.mark(self.d / "o", {"clock": CLOCK, "dump": "a"})
        self.assertEqual(sorted(p.name for p in (self.d / "o").iterdir()), [DC.MARK])
        (self.d / "o" / "a").write_text("x")
        self.assertEqual(DC.done(self.d / "o", CLOCK, needs=("dump",))["dump"], "a")

    def test_not_for_another_clock_or_a_missing_file_or_when_ignored(self):
        DC.mark(self.d / "o", {"clock": CLOCK, "dump": "a"})
        self.assertIsNone(DC.done(self.d / "o", "2026-11-25T00:00:00Z"))
        self.assertIsNone(DC.done(self.d / "o", CLOCK, needs=("dump",)))
        (self.d / "o" / "a").write_text("x")
        with mock.patch.dict(os.environ, {"SCOQ_DAY_CACHE": "0"}):
            self.assertIsNone(DC.done(self.d / "o", CLOCK))

    def test_a_half_written_marker_is_no_marker(self):
        (self.d / "o").mkdir()
        (self.d / "o" / DC.MARK).write_text('{"clock": "2026-11-')
        self.assertIsNone(DC.done(self.d / "o", CLOCK))


class Engines(Base):
    def test_run_once_then_kept(self):
        a = self.dump()
        b = self.dump()
        self.assertEqual(a, b)
        self.assertEqual(self.runs, ["t1/f1"])
        rec = json.loads((a.parent / DC.MARK).read_text())
        self.assertEqual((rec["clock"], rec["dump"], rec["side"]), (CLOCK, "state.bin", "state.bin.json"))

    def test_a_stopped_engines_half_output_is_emptied_first(self):
        out = self.day.work / "t1" / "f1"
        out.mkdir(parents=True)
        (out / "half.txt").write_text("a killed engine's")
        self.dump()
        self.assertFalse((out / "half.txt").exists())
        self.assertEqual(self.runs, ["t1/f1"])

    def test_the_switch_runs_it_again(self):
        self.dump()
        with mock.patch.dict(os.environ, {"SCOQ_DAY_CACHE": "0"}):
            self.dump()
        self.assertEqual(self.runs, ["t1/f1", "t1/f1"])

    def test_a_failed_engine_leaves_no_marker(self):
        WD._engine_dump.side_effect = SystemExit("engine failed (1), see engine.log")
        with self.assertRaises(SystemExit):
            self.dump()
        self.assertFalse((self.day.work / "t1" / "f1" / DC.MARK).exists())

    def test_pause_stops_before_a_new_engine_not_before_a_kept_one(self):
        self.dump("f1")
        DC.PAUSE.write_text("owner: laptop busy")
        self.dump("f1")   # kept: nothing to start
        with self.assertRaises(DC.Paused) as e:
            self.dump("f2")
        self.assertIn("laptop busy", str(e.exception))
        self.assertEqual(self.runs, ["t1/f1"])


class Tier2Groups(Base):
    def test_a_kept_group_is_neither_read_nor_run(self):
        cities = self.d / "t2" / "cities.json"
        cities.parent.mkdir(parents=True)
        cities.write_text(json.dumps({"cities": [{"id": "f1c1-0", "box": [0, 0, 0.1, 0.1]},
                                                 {"id": "f2c1-0", "box": [0, 0, 0.1, 0.1]}]}))
        out = self.d / "t2" / "groups"
        reads = []

        def read(*args, **kw):
            pbf = Path(args[args.index("--out") + 1])
            reads.append(pbf.parent.name)
            pbf.write_bytes(b"x" * 1000)

        self.day.store = self.d / "store"
        with mock.patch.object(WD, "tilestore", side_effect=read), \
                mock.patch.object(WD, "dump_rows", return_value=WD.np.zeros(0, WD.P.WREC)):
            DC.mark(out / "f1" / "new", {"clock": CLOCK, "dump": "state.bin", "side": "state.bin.json",
                                         "pbf MB": 2.5})
            (out / "f1" / "new" / "state.bin").write_bytes(b"rows")
            (out / "f1" / "new" / "state.bin.json").write_text("{}")
            _, st = WD.rect_rows(self.day, cities, self.d / "parts", 7, CLOCK, CLOCK, "new", out, None, [], "",
                                 workers=1)
        self.assertEqual(reads, ["f2"])
        self.assertEqual(self.runs, ["f2/new"])   # the key outside a day's work: parent/name
        self.assertEqual((st["kept"], st["groups"], st["pbf MB"]), (1, 2, 2.5))


class RoomWait(unittest.TestCase):
    def test_pause_ends_an_engines_wait_for_room(self):
        room = engine_room.Room(status=lambda: (100.0, 0.0), poll_seconds=0.01, wait_minutes=60, sized=False)
        room.alive = [8]
        calls = []

        def check(what):
            calls.append(what)
            if len(calls) == 3:
                raise DC.Paused("PAUSE found")

        room.stop_check = check
        with self.assertRaises(DC.Paused):
            room.enter(8, "t2/groups/f3/new", say=lambda m: None)
        self.assertEqual(room.alive, [8])   # it never entered


class Loop(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.d = Path(self.t.name)
        self.lines = []
        for target, name, value in ((PSD, "STOPPED", self.d / "STOPPED"), (PSD, "LOG", self.d / "log.txt"),
                                    (PSD, "log", self.lines.append), (DC, "PAUSE", self.d / "PAUSE")):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_a_pause_passes_through_guarded_and_ends_the_run_with_no_stopped(self):
        steps = iter([True, "pause"])

        def day():
            if next(steps) == "pause":
                PSD.guarded("world finish 2026-11-26", DC.check_pause, "tier 2")
            return True

        DC.PAUSE.write_text("owner")
        self.assertEqual(PSD.days(5, day), 1)
        self.assertFalse(PSD.STOPPED.exists())
        self.assertTrue(self.lines[-1].startswith("paused: "))
        self.assertNotIn("STOPPED:", self.lines[-1])

    def test_no_day_taken_or_resumed_while_paused(self):
        DC.PAUSE.write_text("owner, 18:00")
        self.assertFalse(PSD.one_day())
        self.assertIn("owner, 18:00", self.lines[-1])


class Orphans(unittest.TestCase):
    """end_orphans picks what to end from the process list: the dead run's descendants (through a shell) and engines
    naming the days' work, only python/java/tilestore/osmium, never this run or its parents"""

    def test_what_is_ended(self):
        me = os.getpid()
        work = str(PSD.WDAYS / "2026-11-26" / "work" / "t2" / "groups" / "f3" / "new")
        procs = [
            {"ProcessId": 1, "ParentProcessId": 0, "Name": "explorer.exe", "CommandLine": ""},
            {"ProcessId": 2, "ParentProcessId": 1, "Name": "python.exe", "CommandLine": "python tests"},
            {"ProcessId": me, "ParentProcessId": 2, "Name": "python.exe", "CommandLine": f"python {work}"},
            {"ProcessId": 101, "ParentProcessId": 100, "Name": "python.exe", "CommandLine": "multiprocessing spawn"},
            {"ProcessId": 102, "ParentProcessId": 101, "Name": "cmd.exe", "CommandLine": "cmd /c engine.bat"},
            {"ProcessId": 103, "ParentProcessId": 102, "Name": "java.exe", "CommandLine": "java -Xmx8g"},
            {"ProcessId": 104, "ParentProcessId": 100, "Name": "notepad.exe", "CommandLine": "notepad"},
            {"ProcessId": 200, "ParentProcessId": 1, "Name": "tilestore.exe", "CommandLine": f"tilestore read --out {work}"},
            {"ProcessId": 300, "ParentProcessId": 1, "Name": "java.exe", "CommandLine": "java -jar other.jar"},
        ]
        calls = []

        def fake_run(args, **kw):
            calls.append(args)
            if args[0] == "powershell":
                return SimpleNamespace(stdout=json.dumps(procs), returncode=0)
            return SimpleNamespace(stdout="", returncode=0)

        lines = []
        with mock.patch.object(PSD.subprocess, "run", side_effect=fake_run), mock.patch.object(PSD, "log", lines.append):
            PSD.end_orphans(100)
        ended = sorted(int(a[3]) for a in calls if a[0] == "taskkill")
        self.assertEqual(ended, [101, 103, 200])   # not the shell, not notepad, not this run, not an unrelated java
        self.assertEqual(len(lines), 3)


if __name__ == "__main__":
    unittest.main()
