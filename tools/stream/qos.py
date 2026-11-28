"""The world day's processes kept off Windows' power throttling, and what it takes to judge whether that helps.

Why (measured in ~/Code/osmium-windows-fast, README "Cause 3", 2026-11-28): this CPU has four fast cores (logical
CPUs 0-7) and eight slow ones (8-23). Windows power-throttles (EcoQoS) a process it thinks unimportant, a process
with no window above all, and that in practice puts its threads on the slow cores; every task here starts under
`conhost.exe --headless`. One-thread osmium took 14.2-17.0 s throttled against 11.8-12.4 s opted out. The opt-out is
not inherited, so every process of the day has to be set: the world day, its Python children, tilestore.exe, and
each engine's cmd.exe and java.exe.

    SCOQ_QOS=high      every process of the day: never throttled, and BELOW_NORMAL priority (the fast cores when
                       they are free, the owner's work first when they are not)
    SCOQ_QOS=default   as before 11-28: nothing set; the processes and the cores are still recorded
    SCOQ_QOS=off       no watcher at all

The environment wins; with no SCOQ_QOS the mode comes from data/qos.txt (gitignored): a line `<YYYY-MM-DD> <mode>`
for the run started on that local date, or a bare `<mode>` for any other; no file, `default`.

One thread (Watcher) walks this process's descendants every POLL_S seconds, every EAGER_POLL_S for a while after
an engine starts (an engine runs 3-25 s; its java.exe appears a moment after its launcher), sets each process the
first time it sees it, reads back what the process now has (the API says what was asked for, not whether Windows
throttles it now), and keeps a handle on it, so its CPU seconds can still be read once it has ended. Every
CORES_S seconds it samples each core's load: the only direct view of where threads run.

What it leaves:
  logs/qos/<run>-procs.csv   a row per process: when, pid, parent, name, mode, ControlMask, StateMask, priority,
                             error, and how many ms after its start it was set
  logs/qos/<run>-cores.csv   a row per sample: when, the fast cores' mean busy %, the slow cores', then every core
  <engine out>/cpu.json      the engine's process tree's CPU seconds (user + kernel), beside its engine.log;
                             day_metrics reads it into engines.json ("cpu s")
  W/days/<D>/qos.json        the day's mode, processes seen, set and failed since the day before (or the run's
                             start), the cores' mean load (+ cores.csv)

Nothing here can stop a day: every call is caught and logged, the thread is a daemon, and a failure turns into a
line, never into an exception for the caller.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SWITCH_FILE = ROOT / "data" / "qos.txt"
OUT_DIR = ROOT / "logs" / "qos"
MODES = ("high", "default", "off")
FAST_CPUS = 8          # logical CPUs 0-7: the four Zen 5 cores; 8-23 the Zen 5c
POLL_S = 3.0
EAGER_POLL_S = 0.1    # java.exe was set 260 ms after it started at 0.25 (11-28 probe)
EAGER_FOR_S = 6.0      # after an engine starts
CORES_S = 15.0

PROCESS_POWER_THROTTLING = 4               # ProcessPowerThrottling (PROCESS_INFORMATION_CLASS)
THROTTLE_EXECUTION_SPEED = 0x1
BELOW_NORMAL = 0x4000                      # BELOW_NORMAL_PRIORITY_CLASS
PRIORITY_NAMES = {0x40: "idle", 0x4000: "below normal", 0x20: "normal", 0x8000: "above normal", 0x80: "high",
                  0x100: "realtime"}


def mode(env=None, switch_file: Path | None = None, today: str | None = None) -> tuple[str, str]:
    """(the mode, where it came from)"""
    env = os.environ if env is None else env
    v = (env.get("SCOQ_QOS") or "").strip().lower()
    if v:
        return (v, "SCOQ_QOS") if v in MODES else ("default", f"SCOQ_QOS={v!r} is no mode")
    f = SWITCH_FILE if switch_file is None else switch_file
    today = today or dt.date.today().isoformat()
    try:
        lines = f.read_text(encoding="utf-8").splitlines()
    except OSError:
        return "default", "no switch"
    bare = None
    for line in lines:
        w = line.split("#", 1)[0].split()
        if len(w) == 2 and w[0] == today:
            m = w[1].lower()
            return (m, f"{f.name}, {today}") if m in MODES else ("default", f"{f.name}: {m!r} is no mode")
        if len(w) == 1 and bare is None:
            bare = w[0].lower()
    if bare is not None:
        return (bare, f.name) if bare in MODES else ("default", f"{f.name}: {bare!r} is no mode")
    return "default", f"{f.name}: nothing for {today}"


# --- Windows -------------------------------------------------------------------------------------------------------

class _Win:
    """the calls, bound once; None off Windows"""
    def __init__(self):
        import ctypes
        from ctypes import wintypes as wt
        self.ct, self.wt = ctypes, wt

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                        ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                        ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", wt.LONG), ("dwFlags", wt.DWORD),
                        ("szExeFile", wt.WCHAR * 260)]

        class THROTTLING(ctypes.Structure):
            _fields_ = [("Version", wt.ULONG), ("ControlMask", wt.ULONG), ("StateMask", wt.ULONG)]

        class PERF(ctypes.Structure):   # SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION
            _fields_ = [("IdleTime", ctypes.c_longlong), ("KernelTime", ctypes.c_longlong),
                        ("UserTime", ctypes.c_longlong), ("DpcTime", ctypes.c_longlong),
                        ("InterruptTime", ctypes.c_longlong), ("InterruptCount", wt.ULONG)]

        self.PE, self.THR, self.PERF = PROCESSENTRY32W, THROTTLING, PERF
        k = self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateToolhelp32Snapshot.restype, k.CreateToolhelp32Snapshot.argtypes = wt.HANDLE, [wt.DWORD, wt.DWORD]
        k.Process32FirstW.restype, k.Process32FirstW.argtypes = wt.BOOL, [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k.Process32NextW.restype, k.Process32NextW.argtypes = wt.BOOL, [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k.OpenProcess.restype, k.OpenProcess.argtypes = wt.HANDLE, [wt.DWORD, wt.BOOL, wt.DWORD]
        k.CloseHandle.restype, k.CloseHandle.argtypes = wt.BOOL, [wt.HANDLE]
        k.GetProcessTimes.restype = wt.BOOL
        k.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
        k.SetProcessInformation.restype = wt.BOOL
        k.SetProcessInformation.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
        k.GetProcessInformation.restype = wt.BOOL
        k.GetProcessInformation.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
        k.SetPriorityClass.restype, k.SetPriorityClass.argtypes = wt.BOOL, [wt.HANDLE, wt.DWORD]
        k.GetPriorityClass.restype, k.GetPriorityClass.argtypes = wt.DWORD, [wt.HANDLE]
        k.WaitForSingleObject.restype, k.WaitForSingleObject.argtypes = wt.DWORD, [wt.HANDLE, wt.DWORD]
        nt = self.nt = ctypes.WinDLL("ntdll")
        nt.NtQuerySystemInformation.restype = ctypes.c_long
        nt.NtQuerySystemInformation.argtypes = [ctypes.c_int, ctypes.c_void_p, wt.ULONG, ctypes.POINTER(wt.ULONG)]
        self.ncpu = os.cpu_count() or 1

    def processes(self) -> list[tuple[int, int, str]]:
        """(pid, parent pid, exe name) of every process"""
        snap = self.k.CreateToolhelp32Snapshot(0x2, 0)
        if snap is None or snap == self.wt.HANDLE(-1).value:
            raise OSError(self.ct.get_last_error(), "CreateToolhelp32Snapshot")
        out = []
        try:
            e = self.PE()
            e.dwSize = self.ct.sizeof(e)
            ok = self.k.Process32FirstW(snap, self.ct.byref(e))
            while ok:
                out.append((int(e.th32ProcessID), int(e.th32ParentProcessID), e.szExeFile))
                ok = self.k.Process32NextW(snap, self.ct.byref(e))
        finally:
            self.k.CloseHandle(snap)
        return out

    def open(self, pid: int) -> tuple[int | None, bool]:
        """(a handle, whether it can set) or (None, False)"""
        h = self.k.OpenProcess(0x0200 | 0x1000 | 0x00100000, False, pid)   # SET_INFORMATION | QUERY_LIMITED | SYNCHRONIZE
        if h:
            return h, True
        h = self.k.OpenProcess(0x1000 | 0x00100000, False, pid)
        return (h, False) if h else (None, False)

    def times(self, h) -> tuple[int, float] | None:
        """(creation time, user + kernel seconds)"""
        c, x, kt, ut = (self.wt.FILETIME() for _ in range(4))
        if not self.k.GetProcessTimes(h, self.ct.byref(c), self.ct.byref(x), self.ct.byref(kt), self.ct.byref(ut)):
            return None
        q = lambda f: (f.dwHighDateTime << 32) | f.dwLowDateTime   # noqa: E731
        return q(c), (q(kt) + q(ut)) / 1e7

    def close(self, h) -> None:
        self.k.CloseHandle(h)

    def ended(self, h) -> bool:
        return self.k.WaitForSingleObject(h, 0) == 0

    def set_high(self, h) -> str:
        """never throttled + BELOW_NORMAL; '' or what failed"""
        errs = []
        s = self.THR(1, THROTTLE_EXECUTION_SPEED, 0)
        if not self.k.SetProcessInformation(h, PROCESS_POWER_THROTTLING, self.ct.byref(s), self.ct.sizeof(s)):
            errs.append(f"throttling: error {self.ct.get_last_error()}")
        if not self.k.SetPriorityClass(h, BELOW_NORMAL):
            errs.append(f"priority: error {self.ct.get_last_error()}")
        return "; ".join(errs)

    def state(self, h) -> tuple[int | None, int | None, int | None]:
        """(ControlMask, StateMask, priority class) as the process has them now; None for what cannot be read"""
        s = self.THR(1, 0, 0)
        ok = self.k.GetProcessInformation(h, PROCESS_POWER_THROTTLING, self.ct.byref(s), self.ct.sizeof(s))
        pc = self.k.GetPriorityClass(h)
        return (int(s.ControlMask) if ok else None, int(s.StateMask) if ok else None, int(pc) if pc else None)

    def cores(self) -> list[tuple[int, int]]:
        """per logical CPU (busy, total) in 100 ns since boot"""
        arr = (self.PERF * self.ncpu)()
        got = self.wt.ULONG(0)
        st = self.nt.NtQuerySystemInformation(8, arr, self.ct.sizeof(arr), self.ct.byref(got))
        if st != 0:
            raise OSError(st, "NtQuerySystemInformation")
        n = got.value // self.ct.sizeof(self.PERF)
        return [(a.KernelTime + a.UserTime - a.IdleTime, a.KernelTime + a.UserTime) for a in arr[:n]]


# --- the watcher ---------------------------------------------------------------------------------------------------

class Proc:
    __slots__ = ("pid", "born", "parent", "name", "handle", "cpu_s", "ended")

    def __init__(self, pid, born, parent, name, handle):
        self.pid, self.born, self.parent, self.name, self.handle = pid, born, parent, name, handle
        self.cpu_s, self.ended = 0.0, False


class Watcher:
    def __init__(self, mode_: str = "default", source: str = "", out_dir: Path = OUT_DIR, log=print, win=None,
                 root_pid: int | None = None, stamp: str | None = None):
        self.mode, self.source, self.log = mode_, source, log
        self.root = root_pid or os.getpid()
        self.win = win
        stamp = stamp or f"{dt.datetime.now():%Y%m%d-%H%M%S}-{self.root}"
        self.procs_csv = Path(out_dir) / f"{stamp}-procs.csv"
        self.cores_csv = Path(out_dir) / f"{stamp}-cores.csv"
        self.lock = threading.RLock()
        self.procs: dict[tuple[int, int], Proc] = {}    # (pid, creation time) -> Proc
        self.by_pid: dict[int, Proc] = {}                # the live process of each pid we know
        self.set_ok = self.set_failed = self.seen = 0
        self.cores_rows: list[list] = []                 # [iso time, fast %, slow %, *per cpu %] since the last day
        self._last_cores = None
        self._eager_until = 0.0
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None
        self.errors = 0

    # the parts that touch Windows, each one caught by the caller

    def _record(self, p: Proc, err: str) -> None:
        cm = sm = pc = None
        try:
            cm, sm, pc = self.win.state(p.handle)
        except Exception as e:  # noqa: BLE001
            err = (err + "; " if err else "") + f"state: {type(e).__name__}"
        try:
            self.procs_csv.parent.mkdir(parents=True, exist_ok=True)
            new = not self.procs_csv.exists()
            with open(self.procs_csv, "a", encoding="utf-8", newline="") as f:
                w = csv.writer(f, lineterminator="\n")
                if new:
                    w.writerow(["time", "pid", "parent", "name", "mode", "control", "state", "priority", "error",
                                "after ms"])
                # how long the process ran before it was set (an engine's java.exe: the part of it run throttled)
                after = round(((time.time() + 11644473600) * 1e7 - p.born) / 1e4) if p.born > 1e15 else ""
                w.writerow([dt.datetime.now().isoformat(timespec="seconds"), p.pid, p.parent, p.name, self.mode,
                            cm, sm, PRIORITY_NAMES.get(pc, pc), err, after])
        except OSError:
            pass

    def _adopt(self, pid: int, parent: int, name: str, parent_born: int | None = None) -> Proc | None:
        """a new process set (when `high`), recorded and kept; None when it cannot be opened, or when it was made
        before its parent: then its parent pid is a number used again, and it is not ours (never set, not walked)"""
        h, can_set = self.win.open(pid)
        if not h:
            return None
        t = self.win.times(h)
        if t is None or (parent_born is not None and t[0] < parent_born):
            self.win.close(h)
            return None
        p = Proc(pid, t[0], parent, name, h)
        err = ""
        if self.mode == "high":
            err = self.win.set_high(h) if can_set else "no right to set"
            if err:
                self.set_failed += 1
            else:
                self.set_ok += 1
        self.seen += 1
        self.procs[(pid, p.born)] = p
        self.by_pid[pid] = p
        self._record(p, err)
        return p

    def poll(self) -> None:
        """every descendant of the root not seen yet is set; ended ones have their last CPU seconds read"""
        with self.lock:
            procs = self.win.processes()
            kids: dict[int, list[tuple[int, str]]] = {}
            names = {}
            for pid, ppid, name in procs:
                kids.setdefault(ppid, []).append((pid, name))
                names[pid] = name
            if self.root not in self.by_pid and self.root in names:
                self._adopt(self.root, 0, names[self.root])
            todo = [self.root]
            while todo:
                parent = todo.pop()
                pp = self.by_pid.get(parent)
                for pid, name in kids.get(parent, ()):
                    known = self.by_pid.get(pid)
                    if known is not None and not known.ended and known.parent == parent:
                        todo.append(pid)
                        continue
                    if self._adopt(pid, parent, name, pp.born if pp is not None else None) is not None:
                        todo.append(pid)
            for p in self.procs.values():
                if p.ended or p.handle is None:
                    continue
                gone = self.win.ended(p.handle)   # asked first: the times read after it are then the last
                t = self.win.times(p.handle)
                if t is not None:
                    p.cpu_s = t[1]
                if gone:
                    p.ended = True
                    self.win.close(p.handle)
                    p.handle = None
                    if self.by_pid.get(p.pid) is p:
                        del self.by_pid[p.pid]

    def sample_cores(self) -> None:
        now = self.win.cores()
        last, self._last_cores = self._last_cores, now
        if last is None or len(last) != len(now):
            return
        pct = []
        for (b0, t0), (b1, t1) in zip(last, now):
            pct.append(round(100.0 * (b1 - b0) / (t1 - t0), 1) if t1 > t0 else 0.0)
        fast, slow = pct[:FAST_CPUS], pct[FAST_CPUS:]
        row = [dt.datetime.now().isoformat(timespec="seconds"),
               round(sum(fast) / len(fast), 1) if fast else "", round(sum(slow) / len(slow), 1) if slow else "", *pct]
        with self.lock:
            self.cores_rows.append(row)
        try:
            self.cores_csv.parent.mkdir(parents=True, exist_ok=True)
            new = not self.cores_csv.exists()
            with open(self.cores_csv, "a", encoding="utf-8", newline="") as f:
                w = csv.writer(f, lineterminator="\n")
                if new:
                    w.writerow(["time", "fast %", "slow %", *(f"cpu{i}" for i in range(len(pct)))])
                w.writerow(row)
        except OSError:
            pass

    # what the day asks

    def engine_started(self, pid: int) -> None:
        """an engine's launcher runs: the next poll now (it sets the launcher), and polls often a while for its java.exe"""
        try:
            with self.lock:
                self._eager_until = time.monotonic() + EAGER_FOR_S
            self._wake.set()
        except Exception:  # noqa: BLE001
            pass

    def tree_cpu(self, pid: int) -> dict | None:
        """the CPU seconds of the process `pid` (a launcher this watcher has seen) and everything under it, read
        once more now; None when it was never seen"""
        try:
            self.poll()
            with self.lock:
                roots = [p for p in self.procs.values() if p.pid == pid]
                if not roots:
                    return None
                root = max(roots, key=lambda p: p.born)
                tree, todo = [root], [root]
                while todo:
                    q = todo.pop()
                    for p in self.procs.values():
                        if p.parent == q.pid and p.born >= q.born and p is not root and p not in tree:
                            tree.append(p)
                            todo.append(p)
                return {"cpu s": round(sum(p.cpu_s for p in tree), 2), "processes": len(tree), "qos": self.mode,
                        "names": sorted({p.name for p in tree})}
        except Exception:  # noqa: BLE001
            return None

    def day_done(self, keep: Path, log=None) -> dict | None:
        """W/days/<D>/qos.json and cores.csv: the samples since the last day_done (or the run's start)"""
        try:
            with self.lock:
                rows, self.cores_rows = self.cores_rows, []
                rec = {"mode": self.mode, "source": self.source, "processes": self.seen, "set": self.set_ok,
                       "failed": self.set_failed, "errors": self.errors, "samples": len(rows), "fast cpus": FAST_CPUS}
                self.seen = self.set_ok = self.set_failed = self.errors = 0   # each day its own
            if rows:
                rec["fast % mean"] = round(sum(r[1] for r in rows) / len(rows), 1)
                rec["slow % mean"] = round(sum(r[2] for r in rows) / len(rows), 1)
                rec["from"], rec["to"] = rows[0][0], rows[-1][0]
                keep.mkdir(parents=True, exist_ok=True)
                with open(keep / "cores.csv", "w", encoding="utf-8", newline="") as f:
                    w = csv.writer(f, lineterminator="\n")
                    w.writerow(["time", "fast %", "slow %", *(f"cpu{i}" for i in range(len(rows[0]) - 3))])
                    w.writerows(rows)
            keep.mkdir(parents=True, exist_ok=True)
            (keep / "qos.json").write_text(json.dumps(rec), encoding="utf-8", newline="\n")
            if log:
                log(f"qos: {self.mode}; {rec['processes']} processes seen, {rec['set']} set, {rec['failed']} failed; "
                    f"cores busy fast {rec.get('fast % mean', '-')}%, slow {rec.get('slow % mean', '-')}% "
                    f"({rec['samples']} samples)")
            return rec
        except Exception as e:  # noqa: BLE001
            if log:
                log(f"qos: day not recorded ({type(e).__name__}: {e})")
            return None

    # the thread

    def _run(self) -> None:
        next_cores = 0.0
        while not self._stop.is_set():
            for what, fn in (("processes", self.poll), ("cores", None)):
                try:
                    if fn is not None:
                        fn()
                    elif time.monotonic() >= next_cores:
                        next_cores = time.monotonic() + CORES_S
                        self.sample_cores()
                except Exception as e:  # noqa: BLE001
                    self.errors += 1
                    if self.errors <= 5:
                        self.log(f"qos: {what} not read ({type(e).__name__}: {e})")
            wait = EAGER_POLL_S if time.monotonic() < self._eager_until else POLL_S
            self._wake.wait(wait)
            self._wake.clear()

    def start(self) -> "Watcher":
        self._thread = threading.Thread(target=self._run, name="qos-watcher", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()


WATCHER: Watcher | None = None   # the process's one, once start() ran


def start(log=print) -> Watcher | None:
    """the watcher for this process, by the switch; None off Windows, with `off`, or on any failure"""
    global WATCHER
    try:
        m, src = mode()
        if m == "off" or sys.platform != "win32":
            log(f"qos: {m} ({src}); no watcher" if m == "off" else "qos: not Windows; no watcher")
            return None
        w = Watcher(m, src, log=log, win=_Win())
        w.poll()                      # this process itself before anything starts under it
        WATCHER = w.start()
        log(f"qos: {m} ({src}); processes to {w.procs_csv.relative_to(ROOT).as_posix()}, cores every "
            f"{CORES_S:g} s to {w.cores_csv.name}")
        return w
    except Exception as e:  # noqa: BLE001
        log(f"qos: no watcher ({type(e).__name__}: {e})")
        return None


def engine_started(pid) -> None:
    if WATCHER is not None and pid:
        WATCHER.engine_started(int(pid))


def note_engine_cpu(out: Path, pid) -> None:
    """the engine's tree's CPU seconds beside its engine.log (cpu.json); nothing when there is no watcher"""
    if WATCHER is None or not pid:
        return
    try:
        r = WATCHER.tree_cpu(int(pid))
        if r is not None:
            Path(out).mkdir(parents=True, exist_ok=True)
            (Path(out) / "cpu.json").write_text(json.dumps(r), encoding="utf-8", newline="\n")
    except Exception:  # noqa: BLE001
        pass


def day_done(keep: Path, log=None) -> None:
    if WATCHER is not None:
        WATCHER.day_done(keep, log)
