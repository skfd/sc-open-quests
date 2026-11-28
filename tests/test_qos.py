"""tools/stream/qos.py: the switch, the watcher on real processes (Windows), and that nothing of it can stop a day."""
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools" / "stream"))
import day_metrics as dm  # noqa: E402
import engine_room as ER  # noqa: E402
import qos  # noqa: E402


# --- the switch ------------------------------------------------------------------------------------------------------

def test_the_environment_wins(tmp_path):
    f = tmp_path / "qos.txt"
    f.write_text("high\n", encoding="utf-8")
    assert qos.mode({"SCOQ_QOS": "default"}, f)[0] == "default"
    assert qos.mode({"SCOQ_QOS": "OFF"}, f)[0] == "off"


def test_no_switch_is_the_old_way(tmp_path):
    assert qos.mode({}, tmp_path / "none.txt") == ("default", "no switch")


def test_a_dated_line_beats_the_bare_one(tmp_path):
    f = tmp_path / "qos.txt"
    f.write_text("# the trial\ndefault\n2026-11-28 high   # first day\n2026-11-30 default\n", encoding="utf-8")
    assert qos.mode({}, f, "2026-11-28")[0] == "high"
    assert qos.mode({}, f, "2026-11-30")[0] == "default"
    assert qos.mode({}, f, "2026-12-05")[0] == "default"


def test_a_word_that_is_no_mode_is_the_old_way(tmp_path):
    f = tmp_path / "qos.txt"
    f.write_text("2026-11-28 turbo\n", encoding="utf-8")
    m, why = qos.mode({}, f, "2026-11-28")
    assert m == "default" and "turbo" in why
    assert qos.mode({"SCOQ_QOS": "fast"}, f)[0] == "default"


# --- nothing of it can stop a day ------------------------------------------------------------------------------------

class Broken:
    """a Windows whose every call fails"""
    def __getattr__(self, name):
        def fail(*a, **k):
            raise OSError(5, f"{name} failed")
        return fail


def test_a_watcher_whose_calls_fail_only_logs(tmp_path):
    said = []
    w = qos.Watcher("high", "test", out_dir=tmp_path, log=said.append, win=Broken(), root_pid=1)
    w.start()
    time.sleep(0.3)
    w.stop()
    assert said and all(s.startswith("qos: ") for s in said) and len(said) <= 5
    assert w.tree_cpu(1) is None
    assert w.day_done(tmp_path / "day", said.append)["samples"] == 0   # what it has, with no samples


def test_the_module_calls_do_nothing_without_a_watcher(tmp_path, monkeypatch):
    monkeypatch.setattr(qos, "WATCHER", None)
    qos.engine_started(123)
    qos.note_engine_cpu(tmp_path, 123)
    qos.day_done(tmp_path / "d")
    assert not any(tmp_path.iterdir())


def test_start_off_starts_nothing(monkeypatch):
    monkeypatch.setenv("SCOQ_QOS", "off")
    monkeypatch.setattr(qos, "WATCHER", None)
    said = []
    assert qos.start(said.append) is None and qos.WATCHER is None
    assert "off" in said[0]


class FakeWin:
    """processes as a table: pid -> (parent, name, creation time, cpu s); what was set, and what was closed"""
    def __init__(self, procs):
        self.procs, self.set, self.closed = procs, [], []

    def processes(self):
        return [(pid, par, name) for pid, (par, name, _, _) in self.procs.items()]

    def open(self, pid):
        return (pid, True) if pid in self.procs else (None, False)

    def times(self, h):
        return self.procs[h][2], self.procs[h][3]

    def set_high(self, h):
        self.set.append(h)
        return ""

    def state(self, h):
        return 1, 0, 0x4000

    def ended(self, h):
        return False

    def close(self, h):
        self.closed.append(h)

    def cores(self):
        return [(0, 0)] * 24


def test_a_pid_used_again_is_not_ours(tmp_path):
    """process 30 names 20 as its parent but was made before 20: 20's pid is a number used again, and 30 is
    somebody else's (the owner's app): never set, its children not walked, its handle closed"""
    win = FakeWin({10: (1, "python.exe", 100, 1.0), 20: (10, "cmd.exe", 200, 0.5), 30: (20, "app.exe", 150, 9.0),
                   40: (30, "child.exe", 160, 9.0), 21: (20, "java.exe", 210, 20.0)})
    w = qos.Watcher("high", "test", out_dir=tmp_path, log=print, win=win, root_pid=10)
    w.poll()
    w.poll()
    assert sorted(win.set) == [10, 20, 21] and 30 in win.closed and 40 not in win.set
    assert w.tree_cpu(20)["cpu s"] == 20.5 and w.tree_cpu(20)["processes"] == 2


# --- the engine's CPU seconds, through the room and into engines.json ------------------------------------------------

class FakeWatcher:
    def __init__(self):
        self.started, self.asked = [], []

    def engine_started(self, pid):
        self.started.append(pid)

    def tree_cpu(self, pid):
        self.asked.append(pid)
        return {"cpu s": 42.5, "processes": 2, "qos": "high", "names": ["cmd.exe", "java.exe"]}


class P:
    pid = 4711


def test_in_room_shows_the_launcher_and_keeps_its_cpu(tmp_path, monkeypatch):
    fw = FakeWatcher()
    monkeypatch.setattr(qos, "WATCHER", fw)
    out = tmp_path / "t2" / "groups" / "f1" / "old"

    def run(heap, on_start, more):
        on_start(P())
        return "dump"

    room = ER.Room(status=lambda: None, sized=True)
    assert ER.in_room(run, out, "t2/groups/f1/old", 4, 8, say=None, room=room) == "dump"
    assert fw.started == [4711] and fw.asked == [4711]
    assert json.loads((out / "cpu.json").read_text(encoding="utf-8"))["cpu s"] == 42.5


def test_a_failed_engine_still_has_its_cpu_kept(tmp_path, monkeypatch):
    fw = FakeWatcher()
    monkeypatch.setattr(qos, "WATCHER", fw)
    out = tmp_path / "t1" / "f0"

    def run(heap, on_start, more):
        on_start(P())
        raise SystemExit("engine failed (1), see engine.log")

    with pytest.raises(SystemExit):
        ER.in_room(run, out, "t1/f0", 8, 8, say=None, room=ER.Room(status=lambda: None))
    assert (out / "cpu.json").is_file()


def test_harvest_reads_cpu_beside_the_log(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_day_metrics import log_of
    work = tmp_path / "work"
    log_of(work / "t1" / "f0", [], 8.0)
    log_of(work / "t1" / "f1", [], 9.0)
    (work / "t1" / "f0" / "cpu.json").write_text(json.dumps({"cpu s": 30.25, "qos": "high"}), encoding="utf-8")
    rec = dm.harvest(work)
    assert rec["engines"]["t1/f0"]["cpu s"] == 30.25 and rec["engines"]["t1/f0"]["qos"] == "high"
    assert "cpu s" not in rec["engines"]["t1/f1"]
    assert rec["phases"]["t1"]["cpu s"] == 30.2 and rec["phases"]["t1"]["with cpu"] == 1


# --- on real processes -----------------------------------------------------------------------------------------------

BUSY = "import time\nt=time.time()\nwhile time.time()-t<1.5: pass\n"
LAUNCHER = ("import subprocess,sys,time\ntime.sleep(0.4)\n"
            f"subprocess.run([sys.executable,'-c',{BUSY!r}])\n")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
@pytest.mark.parametrize("mode", ["high", "default"])
def test_a_launcher_and_its_child_are_set_and_counted(tmp_path, mode):
    """a launcher (as cmd.exe for the engine) that starts a busy child (as java.exe) after a moment: both are
    seen, set when `high`, and the child's CPU second and a half is in the launcher's tree"""
    p = subprocess.Popen([sys.executable, "-c", LAUNCHER])
    said = []
    w = qos.Watcher(mode, "test", out_dir=tmp_path, log=said.append, win=qos._Win(), root_pid=p.pid)
    w.poll()
    w.start()
    w.engine_started(p.pid)
    p.wait(timeout=30)
    r = w.tree_cpu(p.pid)
    w.sample_cores()
    time.sleep(0.2)
    w.sample_cores()
    w.stop()
    assert not said, said
    assert r is not None and r["processes"] >= 2, r
    assert r["cpu s"] >= 1.2, r
    rows = (tmp_path / w.procs_csv.name).read_text(encoding="utf-8").splitlines()
    assert rows[0] == "time,pid,parent,name,mode,control,state,priority,error,after ms"
    body = [r_.split(",") for r_ in rows[1:]]
    assert len(body) >= 2
    if mode == "high":
        assert all(b[5] == "1" and b[6] == "0" and b[7] == "below normal" and b[8] == "" for b in body), rows
        assert w.set_ok >= 2 and w.set_failed == 0
    else:
        assert w.set_ok == 0   # the priority is whatever it inherited (the task's default is below normal)
    rec = w.day_done(tmp_path / "day")
    assert rec["mode"] == mode and rec["samples"] >= 1 and "fast % mean" in rec
    head = (tmp_path / "day" / "cores.csv").read_text(encoding="utf-8").splitlines()[0]
    assert head.startswith("time,fast %,slow %,cpu0")
