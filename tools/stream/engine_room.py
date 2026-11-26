"""Room in the machine's commit charge for one more of the world day's engines (tier 1, tier 2, the notes).

Those engines start with a fixed -Xmx (Day.heap_gb, 8 g), WORLD_T2_WORKERS at a time, and never asked what the
machine could commit. On 2026-11-23 four of them died together at 14:57:11, "G1 virtual space", with 7 MB of
the commit limit left: at rest the machine had 37 GB of 108.6 uncommitted, and four heaps of 8 g with the JVMs'
own memory do not fit in that (HANDOFF, "STOPPED at 15:20:23 on 11-23"). The gate's engine asks
(run.engine_heap_gb); this is the same question for the engines that run several at a time.

    with ROOM.engine(day.heap_gb, "f8/old", day.log):
        ...  # start the engine and wait for it

An engine enters when the commit left, less RESERVE_GB, holds its heap and that of every engine of this process
still alive: a JVM commits its heap as it grows, so one that started a minute ago has not taken its share yet
and is counted whole. That counts a full-grown engine twice, which is the safe side: fewer run at a time, none
dies. With engines alive it waits for one to leave, however long. With none alive there is nobody to wait for
but the rest of the machine: a line every LOG_MINUTES, and after WAIT_MINUTES SystemExit, which the world day
turns into its STOP (a machine that cannot commit one 8 g heap for an hour wants a person).
Off Windows (no reading) every engine enters at once.
"""
from __future__ import annotations

import contextlib
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RESERVE_GB = 8      # left to Windows and everything else running (run.HEAP_RESERVE_GB)
WAIT_MINUTES = int(os.environ.get("SCOQ_HEAP_WAIT_MINUTES", "60"))  # with no engine of ours alive
LOG_MINUTES = 5     # while it waits with none alive, one line this often
POLL_SECONDS = 30


def _status():
    """run.memory_status: (free physical, free commit charge, total physical) in GB, or None off Windows"""
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    import run
    return run.memory_status()


def _print(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Room:
    def __init__(self, status=_status, clock=time.monotonic, poll_seconds: float = POLL_SECONDS,
                 wait_minutes: float = WAIT_MINUTES):
        self.status, self.clock, self.poll, self.wait_minutes = status, clock, poll_seconds, wait_minutes
        self.cond = threading.Condition()
        self.alive: list[int] = []   # the heaps (GB) of this process's engines that have entered and not left
        self.most = 0                # the most alive at once (a metric)
        self.waited_s = 0.0          # seconds engines stood waiting for room, summed (a metric)

    def fits(self, heap_gb: int) -> tuple[bool, float | None]:
        """(room for one more engine of heap_gb, the commit left in GB or None with no reading)"""
        st = self.status()
        if st is None:
            return True, None
        return st[1] - RESERVE_GB >= heap_gb + sum(self.alive), st[1]

    def enter(self, heap_gb: int, what: str = "an engine", say=_print) -> None:
        t0 = self.clock()
        said = None
        with self.cond:
            while True:
                ok, left = self.fits(heap_gb)
                if ok:
                    self.alive.append(heap_gb)
                    self.most = max(self.most, len(self.alive))
                    waited = self.clock() - t0
                    self.waited_s += waited
                    if said is not None:
                        say(f"engine room: {what} starts after {waited:.0f} s; {left:.0f} GB commit left, "
                            f"{len(self.alive)} alive")
                    return
                waited = self.clock() - t0
                now = (f"{left:.0f} GB commit left, {RESERVE_GB} kept back, {len(self.alive)} of our engines alive "
                       f"({sum(self.alive)} g), {what} needs {heap_gb} g")
                if not self.alive and waited >= self.wait_minutes * 60:
                    raise SystemExit(f"no room in the commit charge for {what} after {waited / 60:.0f} min with no "
                                     f"engine of ours alive: {now}; not started (it would die as on 2026-11-23)")
                if said is None or (not self.alive and waited - said >= LOG_MINUTES * 60):
                    say(f"engine room: {what} waits: {now}")
                    said = waited
                self.cond.wait(self.poll)

    def leave(self, heap_gb: int) -> None:
        with self.cond:
            self.alive.remove(heap_gb)
            self.cond.notify_all()

    @contextlib.contextmanager
    def engine(self, heap_gb: int, what: str = "an engine", say=_print):
        self.enter(heap_gb, what, say)
        try:
            yield
        finally:
            self.leave(heap_gb)


ROOM = Room()  # one for the process: the world day's engines of every phase share the machine
