"""Notes at the clock for the stream's state (DESIGN.md, "Release 1: the world day", step 4).

What the engine does with notes (engine/src/main/kotlin/openquests/Notes.kt), and so what this does:

- **Open at a clock** (`NotesClip.openAt`): a note created by then, with at least one comment by then, whose last
  status action by then (opened, closed, reopened, hidden) is opened or reopened, or which has none.
- **Hidden** (`OpenNotes.hides`, SC's OsmQuestController blacklist): a quest is hidden when its position, each
  coordinate truncated toward zero to 6 decimals (`(x * 10.0.pow(6)).toInt()`), equals that of any open note,
  question or not. The note's coordinate is the dump's string parsed as a double; Python's float() and Kotlin's
  toDouble() give the same double, and the product and truncation are the same IEEE arithmetic.
  A state row stores its position in 1e-7 degrees. Plain rounding loses SC's truncation where the exact value lies
  within 0.5e-7 below a 1e-6 step (and where the double product falls just short of a whole number), so the engine
  keeps the stored value inside the steps whose truncation is the exact value's (`StateDump.e7`); then
  `trunc(stored / 10)` toward zero is SC's truncated value, exactly. Rows from an engine before that change can be
  wrong on such positions.
- **The note quest** (OsmNoteQuestType): the open notes that pass the app's filter (a question, "#surveyme",
  ...; NoteQuest.kt, ported verbatim), counted where the engine counts them: in each city holding the position
  and enabled there, and in that city's parts. That filter and the places are the engine's, so the note quests are
  counted by the engine itself: `note_quests` runs it on a PBF with no elements, the notes, the cities and their
  parts, at the clock. No Python port of the filter, no point-in-polygon here.

Per day: `hidden_step(rows, clip, clock, prev_clock, fresh)` sets HIDDEN on the rows whose truncated position
gained or lost an open note between prev_clock and clock, and on every row in `fresh` (the day's recounts, which
ran without notes); `hidden_step(rows, clip, clock)` with no prev_clock recomputes every row (a seed counted without
notes, or a check). The rows are changed in place (REC or placesets.WREC: only `flags` is touched).

    python tools/stream/notes_day.py hidden STATE.bin CLIP.jsonl --clock ISO [--prev ISO] [--out OUT.bin]
    python tools/stream/notes_day.py quests CITIES.json CLIP.jsonl --clock ISO --out DIR [--parts DIR]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HIDDEN = 64
STATUS = {"opened", "closed", "reopened", "hidden"}


def ms(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def load_clip(path: Path) -> tuple[dict, list[tuple]]:
    """the clip's header and its notes as (lat string, lon string, created ms, [(timestamp ms, action), ...])"""
    notes = []
    with open(path, encoding="utf-8") as f:
        header = json.loads(f.readline())
        assert str(header.get("schema")) == "1", f"{path}: not a schema 1 notes clip"
        for line in f:
            if not line.strip():
                continue
            o = json.loads(line)
            notes.append((o["lat"], o["lon"], ms(o["created"]), [(ms(c["timestamp"]), c["action"]) for c in o["comments"]]))
    return header, notes


def open_at(notes: list[tuple], clock_ms: int) -> list[tuple]:
    """NotesClip.openAt: the notes open at the clock"""
    out = []
    for n in notes:
        lat, lon, created, comments = n
        if created > clock_ms:
            continue
        cs = [a for t, a in comments if t <= clock_ms]
        if not cs:
            continue
        last = next((a for a in reversed(cs) if a in STATUS), None)
        if last is not None and last not in ("opened", "reopened"):
            continue
        out.append(n)
    return out


def trunc6(s: str) -> int:
    """SC's truncateTo6Decimals of the dump's coordinate string, as an integer of 1e-6 degrees"""
    return int(float(s) * 10.0 ** 6)


def key(lat_t: np.ndarray, lon_t: np.ndarray) -> np.ndarray:
    """one int64 per truncated position (both parts fit 32 bits: |coordinate| <= 180e6)"""
    return (np.asarray(lat_t, np.int64) << 32) + (np.asarray(lon_t, np.int64) + (1 << 31))


def note_keys(notes: list[tuple]) -> np.ndarray:
    if not notes:
        return np.zeros(0, np.int64)
    return np.unique(key([trunc6(n[0]) for n in notes], [trunc6(n[1]) for n in notes]))


def row_keys(rows: np.ndarray) -> np.ndarray:
    """the rows' truncated positions: trunc(stored / 10) toward zero (StateDump.e7)"""
    def t(v):
        v = v.astype(np.int64)
        return np.sign(v) * (np.abs(v) // 10)
    return key(t(rows["lat"]), t(rows["lon"]))


def set_hidden(rows: np.ndarray, open_keys: np.ndarray, mask: np.ndarray | None = None) -> int:
    """HIDDEN on the rows (those in mask, or all) whose truncated position an open note holds; returns how many
    flags changed"""
    idx = np.arange(len(rows)) if mask is None else np.flatnonzero(mask)
    if not len(idx):
        return 0
    hid = np.isin(row_keys(rows[idx]), open_keys)
    old = rows["flags"][idx]
    new = np.where(hid, old | HIDDEN, old & ~np.uint8(HIDDEN)).astype(np.uint8)
    rows["flags"][idx] = new
    return int((new != old).sum())


def hidden_step(rows: np.ndarray, clip: Path | tuple, clock: str, prev_clock: str | None = None,
                fresh: np.ndarray | None = None) -> dict:
    """the rows' HIDDEN at the clock. With prev_clock: only the rows at positions whose open-note membership changed
    between the two clocks, plus the rows in `fresh` (a mask); without: every row."""
    _, notes = load_clip(clip) if isinstance(clip, (str, Path)) else clip
    now = note_keys(open_at(notes, ms(clock)))
    if prev_clock is None:
        changed = set_hidden(rows, now)
        return {"openNotePositions": len(now), "rowsTouched": len(rows), "flagsChanged": changed}
    before = note_keys(open_at(notes, ms(prev_clock)))
    moved = np.setxor1d(before, now)  # positions that gained or lost an open note
    mask = np.isin(row_keys(rows), moved) if len(moved) else np.zeros(len(rows), bool)
    if fresh is not None:
        mask |= fresh
    changed = set_hidden(rows, now, mask)
    return {"openNotePositions": len(now), "positionsChanged": len(moved), "rowsTouched": int(mask.sum()),
            "flagsChanged": changed}


# --- the note quests, by the engine ---------------------------------------------------------------

def empty_pbf(path: Path, clock: str) -> Path:
    """a PBF with a header and no elements, stamped with the clock (the engine takes asOf from it)"""
    import osmium
    h = osmium.io.Header()
    h.set("osmosis_replication_timestamp", clock)
    h.set("sorting", "Type_then_ID")
    path.unlink(missing_ok=True)
    with osmium.SimpleWriter(str(path), header=h):
        pass
    return path


def note_quests(cities: Path, clip: Path, clock: str, out: Path, parts: Path | None = None,
                engine: Path | None = None, heap_gb: int = 4, zone: str = "UTC", base: Path = ROOT) -> dict:
    """the note quests at the clock, counted by the engine over no elements: per city the note quests at the app's
    default ("showAllNotes": false) and with "show all notes", and per part. Returns
    {"cities": {id: {"quests": n, "allNotes": n}}, "parts": {part id: n}} from the run's snapshot."""
    engine = engine or ROOT / "engine/build/install/sc-open-quests-engine/bin/sc-open-quests-engine.bat"
    out.mkdir(parents=True, exist_ok=True)
    pbf = empty_pbf(out / "empty.osm.pbf", clock)
    args = [str(engine), "count", "--pbf", str(pbf.resolve()), "--quests",
            str(sorted((base / "data/quests").glob("v*.json"))[-1].resolve()), "--cities", str(Path(cities).resolve()),
            "--out", str((out / "out").resolve()), "--notes", str(Path(clip).resolve()), "--today", clock]
    if parts:
        args += ["--parts", str(Path(parts).resolve())]
    import os
    env = dict(os.environ, JAVA_HOME=os.environ.get("JAVA_HOME", r"C:\Program Files\Android\Android Studio\jbr"),
               JAVA_OPTS=f"-Duser.timezone={zone} -Duser.language=en -Duser.country=CA -Xmx{heap_gb}g"
                         # no elements, so no area pass (it refuses to start without the main pass's nodes)
                         " -Dopenquests.areaPass=false")
    with open(out / "engine.log", "w", encoding="utf-8") as f:
        r = subprocess.run(args, cwd=base, env=env, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        raise SystemExit(f"engine failed ({r.returncode}), see {out / 'engine.log'}")
    return snapshot_notes(next(iter(sorted((out / "out" / "snapshots").glob("*.json")))))


def snapshot_notes(snap_path: Path) -> dict:
    """a snapshot's note-quest counts: per city (default setting and "show all notes") and per part"""
    s = json.loads(Path(snap_path).read_text(encoding="utf-8"))
    cities, parts = {}, {}
    for cid, c in s["cities"].items():
        q = (c.get("quests") or {}).get("OsmNoteQuestType") or {}
        cities[cid] = {"quests": q.get("open", 0), "allNotes": q.get("openAllNotes", 0)}
        for pid, qs in (c.get("parts") or {}).items():
            if qs.get("OsmNoteQuestType"):
                parts[pid] = parts.get(pid, 0) + qs["OsmNoteQuestType"]
    return {"cities": cities, "parts": parts}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("hidden")
    a.add_argument("state", type=Path)
    a.add_argument("clip", type=Path)
    a.add_argument("--clock", required=True)
    a.add_argument("--prev")
    a.add_argument("--out", type=Path)
    a = sub.add_parser("quests")
    a.add_argument("cities", type=Path)
    a.add_argument("clip", type=Path)
    a.add_argument("--clock", required=True)
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--parts", type=Path)
    o = ap.parse_args()
    if o.cmd == "hidden":
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from placesets import REC
        rows = np.fromfile(o.state, dtype=REC)
        print(json.dumps(hidden_step(rows, o.clip, o.clock, o.prev)))
        rows.tofile(o.out or o.state)
    else:
        print(json.dumps(note_quests(o.cities, o.clip, o.clock, o.out, o.parts)))


if __name__ == "__main__":
    main()
