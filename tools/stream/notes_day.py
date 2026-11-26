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


# --- planet-sized: the clip as a table, the files in parallel, flags written in place -----------------
#
# A world day's hidden step (world_day.py) at Europe size took 165-185 s for 50M rows, nearly none of it work (about
# 40,000 rows looked at, 70-85 flags changed): 46 s parsing the 1.4 GB clip's JSON, 8 s of open_at in Python, and
# five passes over every row in numpy (one of them a sort of every row's code against the day's new rows). Here the
# clip is parsed once into a table (cached beside it, in parallel), notes open at a clock are worked out on arrays,
# a file is opened only if a position that gained or lost an open note lies in its box or it got new rows, its rows
# are looked up in the small sorted sets of those positions and codes (no sort of the rows), the files run in
# parallel, and only changed flags are written back, in place. Same rule as hidden_step, row for row.

ACTION_CODE = {"opened": 0, "closed": 1, "reopened": 2, "hidden": 3}  # anything else (commented, ...): 4
TABLE_VERSION = 1


def _parse_range(args) -> tuple:
    """the notes of one byte range of the clip (lines that start in it): their keys, created ms, and comments"""
    path, start, end = args
    keys, created, ev_note, ev_ts, ev_act = [], [], [], [], []
    with open(path, "rb") as f:
        if start:
            f.seek(start - 1)
            f.readline()  # to the end of the line holding byte start-1: a line that starts before start is not ours
        else:
            f.seek(0)
        pos = f.tell()
        while pos < end:
            line = f.readline()
            if not line:
                break
            pos += len(line)
            if not line.strip():
                continue
            o = json.loads(line)
            if "schema" in o:  # the header
                continue
            i = len(keys)
            keys.append((trunc6(o["lat"]), trunc6(o["lon"])))
            created.append(ms(o["created"]))
            for c in o["comments"]:
                ev_note.append(i)
                ev_ts.append(ms(c["timestamp"]))
                ev_act.append(ACTION_CODE.get(c["action"], 4))
    k = np.array(keys, np.int64).reshape(-1, 2)
    return (key(k[:, 0], k[:, 1]) if len(k) else np.zeros(0, np.int64), np.array(created, np.int64),
            np.array(ev_note, np.int64), np.array(ev_ts, np.int64), np.array(ev_act, np.int8))


def notes_table(clip: Path, workers: int = 16) -> dict:
    """the clip as arrays: per note `key` (its truncated position) and `created` (ms); per comment, in the clip's
    order, `ev_note`, `ev_ts` (ms) and `ev_act` (ACTION_CODE). Cached as <clip>.table.npz, rebuilt when the clip's
    size or modification time changes."""
    clip = Path(clip)
    cache = clip.with_name(clip.name + ".table.npz")
    st = clip.stat()
    stamp = np.array([TABLE_VERSION, st.st_size, st.st_mtime_ns], np.int64)
    if cache.exists():
        with np.load(cache) as z:  # closed before the cache is replaced below: Windows refuses to replace an open file
            if (z["stamp"] == stamp).all():
                return {k: z[k] for k in ("key", "created", "ev_note", "ev_ts", "ev_act")}
    size = st.st_size
    n = max(1, min(workers, size // (8 << 20) + 1))
    bounds = [size * i // n for i in range(n + 1)]
    if n == 1:
        parts = [_parse_range((str(clip), 0, size))]
    else:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(n) as ex:
            parts = list(ex.map(_parse_range, [(str(clip), bounds[i], bounds[i + 1]) for i in range(n)]))
    off = np.cumsum([0] + [len(p[0]) for p in parts])[:-1]
    t = {"key": np.concatenate([p[0] for p in parts]), "created": np.concatenate([p[1] for p in parts]),
         "ev_note": np.concatenate([p[2] + o for p, o in zip(parts, off)]),
         "ev_ts": np.concatenate([p[3] for p in parts]), "ev_act": np.concatenate([p[4] for p in parts])}
    tmp = cache.with_name(cache.name + ".writing.npz")
    np.savez(tmp, stamp=stamp, **t)
    import os
    os.replace(tmp, cache)
    return t


def open_keys(t: dict, clock_ms: int) -> np.ndarray:
    """open_at and note_keys on the table: the sorted, distinct truncated positions of the notes open at the clock"""
    n = len(t["key"])
    by = t["ev_ts"] <= clock_ms
    has_comment = np.zeros(n, bool)
    has_comment[t["ev_note"][by]] = True
    status = by & (t["ev_act"] < 4)
    sn, sa = t["ev_note"][status], t["ev_act"][status]
    last = np.full(n, -1, np.int8)  # the last status action by the clock, in the clip's order (events are in it)
    if len(sn):
        u, first_from_end = np.unique(sn[::-1], return_index=True)
        last[u] = sa[::-1][first_from_end]
    ok = (t["created"] <= clock_ms) & has_comment & ((last == -1) | (last == 0) | (last == 2))
    return np.unique(t["key"][ok])


def in_sorted(x: np.ndarray, s: np.ndarray) -> np.ndarray:
    """x in s, s sorted and distinct: searchsorted, no sort of x"""
    if not len(s) or not len(x):
        return np.zeros(len(x), bool)
    i = np.searchsorted(s, x)
    i[i == len(s)] = 0
    return s[i] == x


def key_degrees(keys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """a key's truncated latitude and longitude in degrees (the inverse of key())"""
    keys = np.asarray(keys, np.int64)
    return (keys >> 32) / 1e6, ((keys & 0xFFFFFFFF) - (1 << 31)) / 1e6


def _hidden_file(args) -> dict:
    """one file's part of hidden_files (a worker)"""
    import os
    path, dtype, moved, now, fresh, chunk = args
    out = {"rowsTouched": 0, "flagsChanged": 0, "opened": 0}
    if not len(moved) and not len(fresh) or not os.path.getsize(path):
        return out
    out["opened"] = 1
    rows = np.memmap(path, dtype=dtype, mode="r")
    hit = []
    for s in range(0, len(rows), chunk):
        r = rows[s:s + chunk]
        m = in_sorted(row_keys(r), moved) if len(moved) else np.zeros(len(r), bool)
        if len(fresh):
            m |= in_sorted(r["key"] * 1024 + r["quest"].astype(np.int64), fresh)
        idx = np.flatnonzero(m)
        if len(idx):
            sub = r[idx]
            hid = in_sorted(row_keys(sub), now)
            old = sub["flags"]
            new = np.where(hid, old | HIDDEN, old & ~np.uint8(HIDDEN)).astype(np.uint8)
            out["rowsTouched"] += len(idx)
            ch = new != old
            if ch.any():
                hit.append((idx[ch] + s, new[ch]))
    rows = r = sub = None  # noqa: F841 (no view of the map left: Windows will not replace a mapped file)
    if hit and os.stat(path).st_nlink > 1:
        # another name holds this file (a world day's hard-link copy of the state before the day): write a new file
        # and put it in place, so that copy keeps its bytes
        import shutil
        tmp = path + ".flags"
        shutil.copyfile(path, tmp)
        os.replace(tmp, path)
    if hit:
        w = np.memmap(path, dtype=dtype, mode="r+")
        for idx, new in hit:
            w["flags"][idx] = new
            out["flagsChanged"] += len(idx)
        w.flush()
        del w
    return out


def hidden_files(paths: list[Path], rects: list, dtype, table: dict, clock: str, prev_clock: str,
                 fresh: list | None = None, workers: int = 8, chunk: int = 8 << 20, prev_table: dict | None = None) -> dict:
    """hidden_step's day path over a world's files: HIDDEN set at the clock on every row whose truncated position
    gained or lost an open note since prev_clock, and on the rows whose (key * 1024 + quest) is in that file's
    `fresh` (sorted, distinct; the day's recounted rows). `rects` are the files' [s, w, n, e] boxes: a file is opened
    only if such a position lies in its box (padded 0.01 degree: rows sit in their file's rect, a few on its edge by
    rounding) or it has fresh rows. Flags change in place; no other byte of a file is written."""
    now = open_keys(table, ms(clock))
    # prev_table: the clip the flags at prev_clock came from, when the clip was cut again from a newer dump since
    # (a note the newer dump lacks was open at prev_clock: its positions are among the moved)
    moved = np.setxor1d(open_keys(table if prev_table is None else prev_table, ms(prev_clock)), now)
    mlat, mlon = key_degrees(moved)
    jobs = []
    for i, (p, (s, w, n, e)) in enumerate(zip(paths, rects)):
        pad = 0.01
        sel = (mlat >= s - pad) & (mlat <= n + pad) & (mlon >= w - pad) & (mlon <= e + pad)
        fr = fresh[i] if fresh is not None and fresh[i] is not None else np.zeros(0, np.int64)
        jobs.append((str(p), dtype, moved[sel], now, fr, chunk))
    work = [j for j in jobs if len(j[2]) or len(j[4])]
    tot = {"openNotePositions": int(len(now)), "positionsChanged": int(len(moved)), "files": len(paths),
           "filesOpened": 0, "rowsTouched": 0, "flagsChanged": 0}
    if workers > 1 and len(work) > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(min(workers, len(work))) as ex:
            res = list(ex.map(_hidden_file, work))
    else:
        res = [_hidden_file(j) for j in work]
    for r in res:
        tot["filesOpened"] += r["opened"]
        tot["rowsTouched"] += r["rowsTouched"]
        tot["flagsChanged"] += r["flagsChanged"]
    return tot


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
                engine: Path | None = None, heap_gb: int = 4, zone: str = "UTC", base: Path = ROOT,
                parts_cache: Path | None = None, on_start=None, extra_opts: str = "") -> dict:
    """the note quests at the clock, counted by the engine over no elements: per city the note quests at the app's
    default ("showAllNotes": false) and with "show all notes", and per part. Returns
    {"cities": {id: {"quests": n, "allNotes": n}}, "parts": {part id: n}} from the run's snapshot.
    on_start(process) is called once the launcher runs (engine_room reads what its process tree commits, by pid)."""
    engine = engine or ROOT / "engine/build/install/sc-open-quests-engine/bin/sc-open-quests-engine.bat"
    out.mkdir(parents=True, exist_ok=True)
    pbf = empty_pbf(out / "empty.osm.pbf", clock)
    args = [str(engine), "count", "--pbf", str(pbf.resolve()), "--quests",
            str(sorted((base / "data/quests").glob("v*.json"))[-1].resolve()), "--cities", str(Path(cities).resolve()),
            "--out", str((out / "out").resolve()), "--notes", str(Path(clip).resolve()), "--today", clock]
    if parts:
        args += ["--parts", str(Path(parts).resolve())]
        if parts_cache and Path(parts_cache).exists():  # the outlines read from one file (engine PartsCache.kt)
            args += ["--parts-cache", str(Path(parts_cache).resolve())]
    import os
    env = dict(os.environ, JAVA_HOME=os.environ.get("JAVA_HOME", r"C:\Program Files\Android\Android Studio\jbr"),
               JAVA_OPTS=f"-Duser.timezone={zone} -Duser.language=en -Duser.country=CA -Xmx{heap_gb}g"
                         # no elements, so no area pass (it refuses to start without the main pass's nodes)
                         " -Dopenquests.areaPass=false" + (" " + extra_opts if extra_opts else ""))
    with open(out / "engine.log", "w", encoding="utf-8") as f:
        # subprocess.run with the process shown to on_start (stream.run_started; this module does not import stream)
        with subprocess.Popen(args, cwd=base, env=env, stdout=f, stderr=subprocess.STDOUT) as p:
            try:
                if on_start:
                    try:
                        on_start(p)
                    except Exception:  # noqa: BLE001  whoever watches is never the engine's failure
                        pass
                returncode = p.wait()
            except:  # noqa: E722
                p.kill()
                raise
    if returncode:
        raise SystemExit(f"engine failed ({returncode}), see {out / 'engine.log'}")
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
