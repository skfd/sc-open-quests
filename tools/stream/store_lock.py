"""A reader's hold on the planet tile store (tools/stream/planet_store_day.py): while a reader holds it, the daily
store run takes no day, and a reader waits while a run is moving the store.

  with store_lock.reading("world read for the seed"):
      ...  # tilestore read on .scratch/planet-cut/store

`compact` leaves only the newest generation readable and `punch` zeroes pack 0 in place, so nothing may read the
store while a run works on it. The hold is the file HOLD beside the store, its text the reason; a hold left by a
reader that died is removed by hand (its text says who and when). A hold someone else set (a seed-day hold) is left
in place: the reader only adds and removes its own."""
from __future__ import annotations

import contextlib
import datetime as dt
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / ".scratch/planet-cut/store"
HOLD = STORE.parent / "HOLD"
RUNNING = STORE.parent / "RUNNING"
STOPPED = STORE.parent / "STOPPED"
LOG = ROOT / "logs/planet-store.log"


def run_going() -> bool:
    """A store run at work: its RUNNING marker, or (runs started before the marker existed) a log whose last
    "started" line has no "ended" line after it."""
    if RUNNING.exists():
        return True
    if not LOG.exists():
        return False
    started = ended = -1
    for i, line in enumerate(LOG.read_text(encoding="utf-8", errors="replace").splitlines()):
        if "planet store run started" in line:
            started = i
        elif "planet store run ended" in line or "STOPPED:" in line:
            ended = i
    return started > ended


@contextlib.contextmanager
def reading(reason: str, wait_s: float = 6 * 3600):
    if STOPPED.exists():
        raise SystemExit(f"the store is STOPPED: {STOPPED.read_text().strip()}")
    # the hold first, then the wait: a run checks HOLD before each day, so once HOLD exists a run either has not
    # begun a day (and will not) or is inside one, which RUNNING shows
    mine = not HOLD.exists()
    if mine:
        HOLD.write_text(f"{dt.datetime.now().isoformat(timespec='seconds')} pid {os.getpid()}: {reason}\n",
                        encoding="utf-8")
    try:
        t = time.time()
        while run_going():
            if time.time() - t > wait_s:
                raise SystemExit(f"a store run is still going after {wait_s / 3600:.0f} h")
            time.sleep(30)
        yield
    finally:
        if mine:
            HOLD.unlink(missing_ok=True)
