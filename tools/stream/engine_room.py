"""Room in the machine's commit charge for one more of the world day's engines (tier 1, tier 2, the notes).

Those engines started with a fixed -Xmx (Day.heap_gb, 8 g), WORLD_T2_WORKERS at a time, and never asked what the
machine could commit. On 2026-11-23 four of them died together at 14:57:11, "G1 virtual space", with 7 MB of
the commit limit left: at rest the machine had 37 GB of 108.6 uncommitted, and four heaps of 8 g with the JVMs'
own memory do not fit in that (HANDOFF, "STOPPED at 15:20:23 on 11-23"). The gate's engine asks
(run.engine_heap_gb); this is the same question for the engines that run several at a time.

    with ROOM.engine(heap_gb, "t2/groups/f8/old", day.log) as slot:
        ...  # start the engine (slot.started(process) once it runs) and wait for it

An engine enters when the commit left, less RESERVE_GB, holds what it can take and what every engine of this
process still alive can still take. With engines alive it waits for one to leave, however long. With none alive
there is nobody to wait for but the rest of the machine: a line every LOG_MINUTES, and after WAIT_MINUTES
SystemExit, which the world day turns into its STOP (a machine that cannot commit one heap for an hour wants a
person). Off Windows (no reading) every engine enters at once.

What an engine can take, sized (the default): its cap, -Xmx and JVM_OWN_GB for the JVM's own memory. What an
alive one can still take: its cap less what its process tree has committed now (the private bytes of the
launcher and everything under it, `tree_commit_gb`), because that part is out of the commit left already; an
engine with no reading (not started yet, gone, a failed call) is counted whole, the safe side. And each engine
gets a heap of its own, from what it used on the last kept days (`heaps`, `heap_for`), instead of the day's 8 g.

SCOQ_ROOM_SIZED=0 is the way back without a revert, the rule of 2026-11-24 to 11-25: every engine the day's
heap, an alive one counted by its whole heap (`left - 8 >= heap + sum(alive)`; a full-grown engine counted
twice), no reading by pid, no second run.
"""
from __future__ import annotations

import contextlib
import json
import math
import os
import shutil
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RESERVE_GB = 8      # left to Windows and everything else running (run.HEAP_RESERVE_GB)
WAIT_MINUTES = int(os.environ.get("SCOQ_HEAP_WAIT_MINUTES", "60"))  # with no engine of ours alive
LOG_MINUTES = 5     # while it waits with none alive, one line this often
POLL_SECONDS = 30
SIZED = os.environ.get("SCOQ_ROOM_SIZED", "1") != "0"   # 0: fixed heaps, alive engines counted whole
JVM_OWN_GB = 0.5    # a JVM's memory besides its heap (the crash logs of 11-23: about 0.3 GB over the heap)
HEAP_TIMES = 1.5    # an engine's heap: this many times its highest peak of the last HEAP_DAYS kept days
HEAP_DAYS = 3
HEAP_MIN_GB = 3
# a sized-down engine that runs out of heap ends at once, with a line in its log (a worker thread's
# OutOfMemoryError would otherwise leave the others running or waiting)
SIZED_OPTS = "-XX:+ExitOnOutOfMemoryError"
# an engine that failed for memory says one of these in its log (the JVM names its hs_err file there too)
MEMORY_SIGNS = ("OutOfMemoryError", "Java heap space", "G1 virtual space", "Native memory allocation",
                "insufficient memory for the Java Runtime Environment", "Could not reserve enough space", "hs_err_pid")


def _status():
    """run.memory_status: (free physical, free commit charge, total physical) in GB, or None off Windows"""
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    import run
    return run.memory_status()


def _print(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --- what a process and everything under it has committed (Windows) ------------------------------------------------

def _tree_commit_bytes(root_pid: int) -> int | None:
    import ctypes
    from ctypes import wintypes as wt

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                    ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", wt.LONG), ("dwFlags", wt.DWORD),
                    ("szExeFile", wt.WCHAR * 260)]

    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD)] + [(n, ctypes.c_size_t) for n in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
            "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage",
            "PrivateUsage")]

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateToolhelp32Snapshot.restype, k.CreateToolhelp32Snapshot.argtypes = wt.HANDLE, [wt.DWORD, wt.DWORD]
    k.Process32FirstW.restype, k.Process32FirstW.argtypes = wt.BOOL, [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k.Process32NextW.restype, k.Process32NextW.argtypes = wt.BOOL, [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k.OpenProcess.restype, k.OpenProcess.argtypes = wt.HANDLE, [wt.DWORD, wt.BOOL, wt.DWORD]
    k.CloseHandle.restype, k.CloseHandle.argtypes = wt.BOOL, [wt.HANDLE]
    k.GetProcessTimes.restype = wt.BOOL
    k.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
    k.K32GetProcessMemoryInfo.restype = wt.BOOL
    k.K32GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), wt.DWORD]

    snap = k.CreateToolhelp32Snapshot(0x2, 0)                 # TH32CS_SNAPPROCESS
    if snap is None or snap == wt.HANDLE(-1).value:
        return None
    children: dict[int, list[int]] = {}
    seen = set()
    try:
        e = PROCESSENTRY32W()
        e.dwSize = ctypes.sizeof(e)
        ok = k.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            seen.add(e.th32ProcessID)
            children.setdefault(e.th32ParentProcessID, []).append(e.th32ProcessID)
            ok = k.Process32NextW(snap, ctypes.byref(e))
    finally:
        k.CloseHandle(snap)
    if root_pid not in seen:
        return None

    def read(pid):
        """(creation time, private bytes) of one process, or None"""
        h = k.OpenProcess(0x1000, False, pid)                 # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return None
        try:
            c, x, kt, ut = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
            m = PROCESS_MEMORY_COUNTERS_EX()
            m.cb = ctypes.sizeof(m)
            if not k.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(x), ctypes.byref(kt), ctypes.byref(ut)):
                return None
            if not k.K32GetProcessMemoryInfo(h, ctypes.byref(m), m.cb):
                return None
            return (c.dwHighDateTime << 32) | c.dwLowDateTime, int(m.PrivateUsage)
        finally:
            k.CloseHandle(h)

    r = read(root_pid)
    if r is None:
        return None
    total, todo, done = r[1], [(root_pid, r[0])], {root_pid}
    while todo:
        pid, born = todo.pop()
        for c in children.get(pid, ()):
            if c in done:
                continue
            done.add(c)
            rc = read(c)
            # a parent pid is a number that can be used again: a child is one made no earlier than its parent.
            # One that cannot be read is left out (it ended, or is not ours): the engine then counts for more
            if rc is None or rc[0] < born:
                continue
            total += rc[1]
            todo.append((c, rc[0]))
    return total


def tree_commit_gb(pid: int) -> float | None:
    """the commit (private bytes) of the process `pid` and everything started under it, in GB: the launcher
    (cmd.exe running the gradle .bat) and its java.exe. None off Windows, when the process is gone, or on any
    failure: the caller then counts the engine whole"""
    if sys.platform != "win32" or not pid:
        return None
    try:
        b = _tree_commit_bytes(int(pid))
    except Exception:  # noqa: BLE001  a reading, never a stop
        return None
    return None if b is None else b / (1 << 30)


# --- the room ------------------------------------------------------------------------------------------------------

class Slot:
    """one engine in the room: its heap (GB) and, once it runs, its launcher's pid"""
    def __init__(self, heap_gb):
        self.heap_gb, self.pid = heap_gb, None

    def started(self, process) -> None:
        """the engine's process (anything with .pid), said by whoever starts it"""
        self.pid = getattr(process, "pid", None)


class Room:
    def __init__(self, status=_status, clock=time.monotonic, poll_seconds: float = POLL_SECONDS,
                 wait_minutes: float = WAIT_MINUTES, commit=tree_commit_gb, sized: bool | None = None):
        self.status, self.clock, self.poll, self.wait_minutes = status, clock, poll_seconds, wait_minutes
        self.commit = commit         # (pid) -> the GB its process tree has committed, or None
        self.sized = SIZED if sized is None else sized
        self.cond = threading.Condition()
        self.slots: list[Slot] = []  # this process's engines that have entered and not left
        self.most = 0                # the most alive at once (a metric)
        self.waited_s = 0.0          # seconds engines stood waiting for room, summed (a metric)
        self._phase = [0, 0.0, 0]    # most, waited, entered since the last phase()
        self.stop_check = None       # (what) -> None, raising to end a wait (world_day sets day_cache.check_pause)

    @property
    def alive(self) -> list:
        """the heaps (GB) of the engines in the room"""
        return [s.heap_gb for s in self.slots]

    @alive.setter
    def alive(self, heaps) -> None:
        self.slots = [Slot(h) for h in heaps]

    def cap(self, heap_gb) -> float:
        """what an engine of this heap can commit"""
        return heap_gb + JVM_OWN_GB if self.sized else heap_gb

    def owed(self, slot: Slot) -> float:
        """what an alive engine can still take of the commit left"""
        cap = self.cap(slot.heap_gb)
        if not self.sized or slot.pid is None:
            return cap
        try:
            c = self.commit(slot.pid)
        except Exception:  # noqa: BLE001
            c = None
        return cap if c is None or c < 0 else max(0.0, cap - c)

    def fits(self, heap_gb: int) -> tuple[bool, float | None]:
        """(room for one more engine of heap_gb, the commit left in GB or None with no reading)"""
        st = self.status()
        if st is None:
            return True, None
        self._owed = sum(self.owed(s) for s in self.slots)
        return st[1] - RESERVE_GB >= self.cap(heap_gb) + self._owed, st[1]

    def enter(self, heap_gb: int, what: str = "an engine", say=_print) -> Slot:
        t0 = self.clock()
        said = None
        with self.cond:
            while True:
                ok, left = self.fits(heap_gb)
                if ok:
                    slot = Slot(heap_gb)
                    self.slots.append(slot)
                    self.most = max(self.most, len(self.slots))
                    waited = self.clock() - t0
                    self.waited_s += waited
                    self._phase = [max(self._phase[0], len(self.slots)), self._phase[1] + waited, self._phase[2] + 1]
                    if said is not None:
                        say(f"engine room: {what} starts after {waited:.0f} s; {left:.0f} GB commit left, "
                            f"{len(self.slots)} alive")
                    return slot
                waited = self.clock() - t0
                if self.sized:
                    now = (f"{left:.0f} GB commit left, {RESERVE_GB} kept back, {len(self.slots)} of our engines "
                           f"alive (they can take {self._owed:.1f} g more), {what} needs {self.cap(heap_gb):g} g")
                else:
                    now = (f"{left:.0f} GB commit left, {RESERVE_GB} kept back, {len(self.slots)} of our engines "
                           f"alive ({sum(self.alive)} g), {what} needs {heap_gb} g")
                if not self.slots and waited >= self.wait_minutes * 60:
                    raise SystemExit(f"no room in the commit charge for {what} after {waited / 60:.0f} min with no "
                                     f"engine of ours alive: {now}; not started (it would die as on 2026-11-23)")
                if said is None or (not self.slots and waited - said >= LOG_MINUTES * 60):
                    say(f"engine room: {what} waits: {now}")
                    said = waited
                if self.stop_check is not None:   # day_cache.check_pause: a PAUSE ends the wait (it raises)
                    self.stop_check(what)
                self.cond.wait(self.poll)

    def leave(self, slot) -> None:
        """a slot `enter` gave, or a heap (the first engine of that heap leaves)"""
        with self.cond:
            if not isinstance(slot, Slot):
                slot = next(s for s in self.slots if s.heap_gb == slot)
            self.slots.remove(slot)
            self.cond.notify_all()

    @contextlib.contextmanager
    def engine(self, heap_gb: int, what: str = "an engine", say=_print):
        slot = self.enter(heap_gb, what, say)
        try:
            yield slot
        finally:
            self.leave(slot)

    def phase(self) -> dict:
        """the most engines alive at once, the seconds they waited summed and how many entered since the last
        call (a phase of the day: tier 1, tier 2's two dates, the notes); the count starts again"""
        with self.cond:
            most, waited, entered = self._phase
            self._phase = [len(self.slots), 0.0, 0]
        return {"most": most, "waited s": round(waited, 1), "engines": entered}

    def phase_line(self, name: str) -> str:
        p = self.phase()
        return f"engine room: {name}: most {p['most']} at once, waited {p['waited s']:,.0f} s summed ({p['engines']} engines)"


ROOM = Room()  # one for the process: the world day's engines of every phase share the machine


# --- a heap per engine, from what it used on the last kept days -----------------------------------------------------

GIVEN = "given.json"   # beside an engine's log: the heap it was given (day_metrics keeps it beside the peak)
FAILED_LOG = "engine-failed.log"   # the log of a run that failed for memory, kept beside its second run's
_heaps: dict = {}
_heaps_lock = threading.Lock()


def peaks(world: Path, today: str, days: int = HEAP_DAYS) -> dict[str, int]:
    """per engine (day_metrics.harvest's names: `t1/f12`, `t2/groups/f12/old`, `notes/f12`) its highest peak
    heap in MB over the newest `days` kept days before `today` (W/days/<D>/engines.json). A day that cannot be
    read is no day; nothing here raises"""
    out: dict[str, int] = {}
    try:
        kept = sorted(d for d in (Path(world) / "days").iterdir()
                      if d.name < today[:10] and (d / "engines.json").is_file())
    except OSError:
        return out
    n = 0
    for d in reversed(kept):
        try:
            engines = json.loads((d / "engines.json").read_text(encoding="utf-8"))["engines"]
            got = {k: int(e["heap MB"]) for k, e in engines.items() if isinstance(e, dict) and "heap MB" in e}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        for k, mb in got.items():
            out[k] = max(out.get(k, 0), mb)
        n += 1
        if n >= days:
            break
    return out


def heap_of(peak_mb: int | None, day_heap_gb: int) -> int:
    """the heap (GB) for an engine whose highest peak was peak_mb: HEAP_TIMES the peak, at least HEAP_MIN_GB, at
    most the day's; the day's with no history"""
    if not peak_mb or peak_mb <= 0:
        return day_heap_gb
    return max(min(HEAP_MIN_GB, day_heap_gb), min(day_heap_gb, math.ceil(HEAP_TIMES * peak_mb / 1024)))


def heap_for(world: Path, today: str, key: str, day_heap_gb: int, sized: bool | None = None) -> int:
    """the heap (GB) the engine `key` gets on `today`; the kept days are read once per world and day"""
    if not (SIZED if sized is None else sized):
        return day_heap_gb
    k = (str(world), today[:10])
    with _heaps_lock:
        if k not in _heaps:
            _heaps.clear()
            _heaps[k] = peaks(Path(world), today)
        return heap_of(_heaps[k].get(key), day_heap_gb)


def memory_failure(out: Path, since: float | None = None, cwd: Path | None = None) -> str | None:
    """why an engine that ended with a non-zero exit code failed, when it failed for memory: the sign in its
    engine.log (the heap ran out, or the machine's commit did and the JVM wrote an hs_err file), or an
    hs_err_pid*.log written in the engine's working folder since it started. None for any other failure"""
    try:
        text = (Path(out) / "engine.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for sign in MEMORY_SIGNS:
        if sign in text:
            return sign
    if since is not None and cwd is not None:
        try:
            for f in Path(cwd).glob("hs_err_pid*.log"):   # the folder's own files, not its tree
                if f.stat().st_mtime >= since - 1:
                    return f.name
        except OSError:
            pass
    return None


def clear_failed(out: Path) -> None:
    """a failed run's output folder emptied for its second run; its log kept as FAILED_LOG (not a name
    day_metrics reads)"""
    out = Path(out)
    try:
        text = (out / "engine.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = None
    for _ in range(5):   # a file of the engine that just ended can stay locked a moment
        shutil.rmtree(out, ignore_errors=True)
        if not out.exists():
            break
        time.sleep(1)
    if out.exists():
        raise SystemExit(f"{out}: the failed engine's output could not be cleared for its second run")
    out.mkdir(parents=True)
    if text is not None:
        (out / FAILED_LOG).write_text(text, encoding="utf-8", newline="\n")


def note_given(out: Path, heap_gb: int, first_gb: int | None = None) -> None:
    """the heap an engine was given, beside its log (and the heap of the run that failed before it)"""
    rec = {"given MB": heap_gb * 1024}
    if first_gb is not None:
        rec["first given MB"] = first_gb * 1024
    try:
        Path(out).mkdir(parents=True, exist_ok=True)
        (Path(out) / GIVEN).write_text(json.dumps(rec), encoding="utf-8", newline="\n")
    except OSError:
        pass


def in_room(run, out: Path, key: str, heap_gb: int, day_heap_gb: int, say=_print, room: Room | None = None,
            cwd: Path | None = None):
    """one engine through the room: `run(heap_gb, slot.started, extra JVM options)` starts it into `out` and
    waits, raising SystemExit("engine failed (...") on a non-zero exit code. An engine given less than the day's
    heap that fails for memory is run once more at the day's heap, its output cleared; any other failure, and a
    failure at the day's heap, stays the failure it is"""
    room = room or ROOM
    t0 = None
    note_given(out, heap_gb)
    try:
        with room.engine(heap_gb, key, say) as slot:
            t0 = time.time()   # an hs_err file from here on can be this engine's (not one of its wait's)
            try:
                return run(heap_gb, _started(slot), SIZED_OPTS if heap_gb < day_heap_gb else "")
            finally:
                _cpu(out, slot)
    except SystemExit as e:
        if heap_gb >= day_heap_gb or not str(e).startswith("engine failed ("):
            raise
        why = memory_failure(out, t0, cwd)
        if why is None:
            raise
        if say:
            say(f"engine room: {key} failed for memory at {heap_gb} g ({why}); once more at {day_heap_gb} g")
    clear_failed(out)
    note_given(out, day_heap_gb, heap_gb)
    with room.engine(day_heap_gb, key, say) as slot:
        try:
            return run(day_heap_gb, _started(slot), "")
        finally:
            _cpu(out, slot)


def _started(slot: Slot):
    """slot.started, and the engine's launcher shown to the qos watcher (qos.py: its process tree is set when the
    switch says so, and its CPU seconds kept)"""
    def started(process):
        slot.started(process)
        try:
            import qos
            qos.engine_started(getattr(process, "pid", None))
        except Exception:  # noqa: BLE001  a reading, never the engine's failure
            pass
    return started


def _cpu(out: Path, slot: Slot) -> None:
    """the engine's tree's CPU seconds beside its log (cpu.json), when a qos watcher runs"""
    try:
        import qos
        qos.note_engine_cpu(out, slot.pid)
    except Exception:  # noqa: BLE001
        pass
