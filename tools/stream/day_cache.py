"""What a world day (world_day.finish) can keep across a stop, and the PAUSE that stops it on purpose.

A finish that did not end is put back to the world before the day (planet_store_day.restore) and run again: its
writes into the world (tier 1's rewrite, tier 2's delta, the hidden flags, the counts) are always replayed from that
copy, in the same order, so the place-set numbering and every byte come out as one uninterrupted run would make them.
What is kept is only what writes nothing into the world and costs the most: the cover and its rectangles, the tier 1
small PBF, and every engine's output (tier 1 per plan file, tier 2 per group and date, the note engines per plan
file). Each is reused only when its marker is there: a small JSON file written last, through a temporary name, after
the step ended well (an engine: exit 0, its dump and side file on disk). An output folder without a marker is
emptied before its step runs again. Ingested rows are never kept: ingesting numbers place sets, so the dumps are
read again in order on every run.

SCOQ_DAY_CACHE=0 in the environment ignores every marker (each step runs and writes its marker again): the way back,
and the uninterrupted run a resumed one is held against.

PAUSE beside the store (its text the reason): a running day stops at its next engine start or step and the run
ends with no STOPPED; engines already running end first and keep their output. While it exists a run takes no day
and resumes none. Delete it and start the task to go on. Unlike HOLD, which a reader of the store places expecting
the running day to finish, PAUSE stops the day itself."""
import json
import os
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAUSE = ROOT / ".scratch/planet-cut/PAUSE"
MARK = "done.json"   # inside the step's own output folder: emptying the folder takes it away


class Paused(Exception):
    """PAUSE was found: the day stops here (not a failure, not a STOP)"""


def ignored() -> bool:
    return os.environ.get("SCOQ_DAY_CACHE") == "0"


def check_pause(where: str) -> None:
    if PAUSE.exists():
        try:
            why = PAUSE.read_text(encoding="utf-8").strip()
        except OSError:
            why = ""
        raise Paused(f"{PAUSE} found before {where}" + (f" ({why})" if why else ""))


def done(out: Path, clock: str | None = None, needs: tuple[str, ...] = ()) -> dict | None:
    """the marker of a step that ended well in `out`, or None (no marker, ignored, another clock, or a file it names
    gone). `needs`: keys of the marker naming files in `out` that must still exist"""
    if ignored():
        return None
    m = Path(out) / MARK
    try:
        rec = json.loads(m.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if clock is not None and rec.get("clock") != clock:
        return None
    for k in needs:
        if not rec.get(k) or not (Path(out) / rec[k]).exists():
            return None
    return rec


def mark(out: Path, rec: dict) -> None:
    """the step in `out` ended well: its marker, written last and whole (a temporary name, then replaced)"""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / (MARK + ".writing")
    tmp.write_text(json.dumps(rec, indent=1), encoding="utf-8", newline="\n")
    os.replace(tmp, out / MARK)


def clear(out: Path) -> None:
    """an output folder without a marker emptied before its step runs again (a stopped engine's half output)"""
    out = Path(out)
    if not out.exists():
        return
    for _ in range(5):   # a file of an engine that just ended can stay locked a moment
        shutil.rmtree(out, ignore_errors=True)
        if not out.exists():
            return
        time.sleep(1)
    shutil.rmtree(out)
