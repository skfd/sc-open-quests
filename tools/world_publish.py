"""World places published: the world's daily counts per place, as files for the place-data bucket.

DESIGN.md, "World places published: the files". Reads the world (`W`, `.scratch/planet/world-1101`): its gated days
(`days/<D>/gate.json` ok; the first day by the seed's gate, `counts/<first>/gate1101.json`) and each day's
`counts/<D>/counts.{json,npz}` (tools/stream/place_counts.py). Writes, under `--out`, the bucket's layout:

    latest.json
    place/<base>/<id[:2]>/<id>.json          when base moves, or when it is missing
    latest/<date>/<parent[:2]>/<parent>.json every build (a country's parent: latest/<date>/world.json)

Only the 12-hex Overture places the name layer (docs/places) has; only `open` and `agedOnly`. A quest's series is a
list of change points `[i, open, aged]`, i an index into the file's `dates`.

The day's changes are cached under `--work` (`events/<D>.npz`: every (place, quest) whose values differ from the
day before; the first day against nothing), so a new day reads one counts file, not all of them.

    python tools/world_publish.py build  [--world W] [--out O] [--work K]
    python tools/world_publish.py verify [--world W] [--out O] [--sample N]
    python tools/world_publish.py crosscheck [--world W] [--report R] [--day 2026-11-08]
    python tools/world_publish.py upload [--out O] [--print]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / ".scratch" / "planet" / "world-1101"
OUT = ROOT / ".scratch" / "world-publish" / "site"
WORK = ROOT / ".scratch" / "world-publish" / "work"
PLACES = ROOT / "docs" / "places"
FIRST = "2026-11-01"
SCHEMA = 1
WINDOW_DAYS = 28
BUCKET = "sc-open-quests-data"
KEEP_LATEST = 3  # the newest latest/<date>/ folders kept (local and in the bucket)
KEEP_PLACE = 2   # place/<base>/ folders kept
CACHE_IMMUTABLE = "public, max-age=31536000, immutable"
CACHE_LATEST_JSON = "public, max-age=300"
JSON_TYPE = ["--header-upload", "Content-Type: application/json"]  # not left to rclone's guess (Windows' registry)
SUBTYPES = ["country", "dependency", "region", "county", "localadmin", "locality",
            "borough", "macrohood", "neighborhood", "microhood"]  # tools/places.py SUBTYPES
QBITS = 8  # a key is (place id as a 48-bit int) << QBITS | quest index


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


# --- the name layer ----------------------------------------------------------------------------------------------

class NameLayer:
    """every place of docs/places: name, subtype, country code, and its parents (a place in more than one region
    file has one per file). A row's parent is its parentIdx row, else the region; a region's is its country; a
    country's is "world"."""

    def __init__(self, places: Path = PLACES):
        idx = json.loads((places / "index.json").read_text(encoding="utf-8"))
        self.overture = idx.get("overture")
        self.meta: dict[str, tuple[str, str, str]] = {}  # id -> (name, subtype, cc)
        self.parents: dict[str, list[str]] = {}

        def add(pid: str, parent: str, name: str, subtype: str, cc: str) -> None:
            if pid == parent:
                return
            self.meta.setdefault(pid, (name, subtype, cc))
            ps = self.parents.setdefault(pid, [])
            if parent not in ps:
                ps.append(parent)

        for c in idx["countries"]:
            cc = c["cc"]
            # a country no Overture division heads (PS, EH, ...) is addressed by its code in lower case, as the
            # page's countryId does; it has no place file of its own, only a latest file for its children
            cid = c["id"] or cc.lower()
            if c["id"]:
                add(cid, "world", c.get("en") or cc, "country", cc)
            for r in c["regions"]:
                rid = r["id"] if r["id"] and r["id"] != "_" else cid  # "_": rows straight under the country
                if rid != cid:
                    add(rid, cid, r["name"], "region", cc)
                rows = json.loads((places / r["file"]).read_text(encoding="utf-8"))["places"]
                for row in rows:
                    pid, name, st, pi = row[0], row[1], row[2], row[3]
                    parent = rows[pi][0] if pi >= 0 else rid
                    if parent == pid:
                        parent = cid
                    add(pid, parent, name, SUBTYPES[st] if 0 <= st < len(SUBTYPES) else str(st), cc)


# --- days and counts ---------------------------------------------------------------------------------------------

def gated_days(world: Path, first: str = FIRST) -> list[str]:
    """first, then each following day whose gate passed, stopping at the first day that has none (no gaps)"""
    if not (world / "counts" / first / "gate1101.json").exists() and not _gate_ok(world, first):
        raise SystemExit(f"the first day {first} has no gate in {world}")
    days = [first]
    d = date.fromisoformat(first)
    while True:
        d += timedelta(days=1)
        if not _gate_ok(world, d.isoformat()):
            return days
        days.append(d.isoformat())


def _gate_ok(world: Path, day: str) -> bool:
    g = world / "days" / day / "gate.json"
    if not g.exists() or not (world / "counts" / day / "counts.npz").exists():
        return False
    return bool(json.loads(g.read_text(encoding="utf-8")).get("ok"))


def _columns(npz: Path, measures: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """part, quest, open, agedOnly out of counts.npz, without holding all nine measures twice: a stored (not
    deflated) `m` is memory-mapped and only its two columns read"""
    io, ia = measures.index("open"), measures.index("agedOnly")
    with zipfile.ZipFile(npz) as z:
        info = z.getinfo("m.npy")
        stored = info.compress_type == zipfile.ZIP_STORED
    with np.load(npz) as f:
        part, quest = f["part"], f["quest"]
        if not stored:
            m = f["m"]
            return part, quest, m[:, io].astype(np.int64), m[:, ia].astype(np.int64)
    with open(npz, "rb") as fh:
        fh.seek(info.header_offset)
        local = fh.read(30)
        n_name, n_extra = int.from_bytes(local[26:28], "little"), int.from_bytes(local[28:30], "little")
        start = info.header_offset + 30 + n_name + n_extra
        fh.seek(start)
        version = np.lib.format.read_magic(fh)
        read = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
        shape, fortran, dtype = read(fh)
        offset = fh.tell()
    m = np.memmap(npz, dtype=dtype, mode="r", offset=offset, shape=shape, order="F" if fortran else "C")
    return part, quest, np.array(m[:, io], dtype=np.int64), np.array(m[:, ia], dtype=np.int64)


def hexkey(ids: list[str]) -> np.ndarray:
    return np.array([int(p, 16) for p in ids], dtype=np.int64)


def day_state(world: Path, day: str, quests: list[str], names: NameLayer) -> tuple[np.ndarray, ...]:
    """the day's published (place, quest) values: sorted keys, open, aged (rows 0 in both dropped), and the
    published places the world counted that day (sorted keys)"""
    meta = json.loads((world / "counts" / day / "counts.json").read_text(encoding="utf-8"))
    qmap = np.full(len(meta["quests"]), -1, dtype=np.int64)
    for i, q in enumerate(meta["quests"]):
        if q in quests:
            qmap[i] = quests.index(q)
    pub = [len(p) == 12 and p in names.meta for p in meta["parts"]]
    pkey = np.array([int(p, 16) if ok else -1 for p, ok in zip(meta["parts"], pub)], dtype=np.int64)
    part, quest, o, a = _columns(world / "counts" / day / "counts.npz", meta["measures"])
    pk, qi = pkey[part], qmap[quest]
    keep = (pk >= 0) & (qi >= 0) & ((o != 0) | (a != 0))
    keys = (pk[keep] << QBITS) | qi[keep]
    order = np.argsort(keys, kind="stable")
    keys, o, a = keys[order], o[keep][order], a[keep][order]
    if len(keys) > 1 and (keys[1:] == keys[:-1]).any():
        raise SystemExit(f"{day}: a (place, quest) pair twice in counts.npz")
    counted = np.unique(pkey[pkey >= 0])
    return keys, o.astype(np.int32), a.astype(np.int32), counted


def changes(prev: tuple, cur: tuple) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """the pairs whose (open, aged) differ between two states (a pair missing is 0, 0), with the new values"""
    pk, po, pa = prev
    ck, co, ca = cur
    allk = np.union1d(pk, ck)
    o0 = np.zeros(len(allk), np.int32); a0 = np.zeros(len(allk), np.int32)
    o1 = np.zeros(len(allk), np.int32); a1 = np.zeros(len(allk), np.int32)
    i = np.searchsorted(allk, pk); o0[i] = po; a0[i] = pa
    j = np.searchsorted(allk, ck); o1[j] = co; a1[j] = ca
    d = (o0 != o1) | (a0 != a1)
    return allk[d], o1[d], a1[d]


# --- build -------------------------------------------------------------------------------------------------------

def base_of(day: str, first: str) -> str:
    b = day[:8] + "01"
    return b if b >= first else first


def start_of(day: str, base: str, first: str) -> str:
    s = min(base, (date.fromisoformat(day) - timedelta(days=WINDOW_DAYS)).isoformat())
    return max(s, first)


def load_events(world: Path, work: Path, days: list[str], quests: list[str], names: NameLayer):
    """every day's changes, cached: (keys, day index, open, aged) sorted by key then day, and the published places
    counted on any of the days"""
    ev = work / "events"
    ev.mkdir(parents=True, exist_ok=True)
    stamp = dumps({"quests": quests, "first": days[0], "overture": names.overture})
    sfile = work / "events.key"
    if not sfile.exists() or sfile.read_text(encoding="utf-8") != stamp:
        shutil.rmtree(ev, ignore_errors=True)
        ev.mkdir(parents=True)
        write_text(sfile, stamp)
    prev = None
    parts: list[np.ndarray] = []
    out_k, out_d, out_o, out_a = [], [], [], []
    for di, day in enumerate(days):
        f = ev / f"{day}.npz"
        if not f.exists():
            if prev is None:
                prev = (day_state(world, days[di - 1], quests, names)[:3]
                        if di > 0 else (np.zeros(0, np.int64), np.zeros(0, np.int32), np.zeros(0, np.int32)))
            t = time.time()
            k, o, a, counted = day_state(world, day, quests, names)
            dk, do, da = changes(prev, (k, o, a))
            tmp = f.with_suffix(".tmp.npz")
            np.savez_compressed(tmp, keys=dk, open=do, aged=da, counted=counted)
            os.replace(tmp, f)
            prev = (k, o, a)
            log(f"{day}: {len(k):,} pairs, {len(dk):,} changed, {len(counted):,} places ({time.time() - t:.0f} s)")
        else:
            prev = None
        with np.load(f) as z:
            out_k.append(z["keys"]); out_o.append(z["open"]); out_a.append(z["aged"])
            out_d.append(np.full(len(z["keys"]), di, np.int32)); parts.append(z["counted"])
    k = np.concatenate(out_k); d = np.concatenate(out_d)
    o = np.concatenate(out_o); a = np.concatenate(out_a)
    order = np.lexsort((d, k))
    return k[order], d[order], o[order], a[order], np.unique(np.concatenate(parts))


def series_json(k: np.ndarray, d: np.ndarray, o: np.ndarray, a: np.ndarray, quests: list[str],
                shift: int = 0) -> dict[int, str]:
    """place key -> the JSON object of its quests' change points (rows sorted by key then day; i = day - shift)"""
    out: dict[int, str] = {}
    if not len(k):
        return out
    place = k >> QBITS
    qi = (k & ((1 << QBITS) - 1)).tolist()
    pl = place.tolist(); dl = (d - shift).tolist(); ol = o.tolist(); al = a.tolist()
    n = len(pl)
    i = 0
    while i < n:
        p = pl[i]
        parts = []
        while i < n and pl[i] == p:
            q = qi[i]
            pts = []
            while i < n and pl[i] == p and qi[i] == q:
                pts.append(f"[{dl[i]},{ol[i]},{al[i]}]")
                i += 1
            parts.append(f"{dumps(quests[q])}:[{','.join(pts)}]")
        out[p] = "{" + ",".join(parts) + "}"
    return out


def idstr(key: int) -> str:
    return f"{key:012x}"


def shard(pid: str) -> str:
    return "world.json" if pid == "world" else f"{pid[:2]}/{pid}.json"


def write_places(out: Path, base: str, days: list[str], ev, quests: list[str], names: NameLayer,
                 counted: np.ndarray) -> int:
    k, d, o, a = ev
    bi = days.index(base)
    m = d <= bi
    ser = series_json(k[m], d[m], o[m], a[m], quests)
    dest = out / "place" / base
    tmp = out / "place" / f".{base}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    dates = dumps(days[:bi + 1])
    n = 0
    for key in counted.tolist():
        pid = idstr(key)
        name, subtype, cc = names.meta[pid]
        text = (f'{{"schema":{SCHEMA},"id":"{pid}","name":{dumps(name)},"subtype":"{subtype}","cc":"{cc}",'
                f'"dates":{dates},"quests":{ser.get(key, "{}")}}}\n')
        write_text(tmp / shard(pid), text)
        n += 1
    shutil.rmtree(dest, ignore_errors=True)
    os.replace(tmp, dest)
    return n


def write_latest(out: Path, day: str, start: str, days: list[str], ev, quests: list[str], names: NameLayer,
                 counted: np.ndarray) -> int:
    k, d, o, a = ev
    si, di = days.index(start), days.index(day)
    m = d <= di
    k, d, o, a = k[m], d[m], o[m], a[m]
    # each pair's value at start (its last change on or before it) as index 0, then its changes after start
    le = d <= si
    nxt_same = np.zeros(len(k), bool)
    nxt_same[:-1] = (k[1:] == k[:-1]) & le[1:]
    at_start = le & ~nxt_same & ((o != 0) | (a != 0))
    keep = at_start | (d > si)
    dd = np.where(at_start, si, d)
    ser = series_json(k[keep], dd[keep], o[keep], a[keep], quests, shift=si)
    children: dict[str, list[str]] = {}
    for key in counted.tolist():
        pid = idstr(key)
        for p in names.parents.get(pid, []):
            children.setdefault(p, []).append(pid)
    dest = out / "latest" / day
    tmp = out / "latest" / f".{day}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    dates = dumps(days[si:di + 1])
    for parent, kids in children.items():
        body = ",".join(f'"{c}":{ser.get(int(c, 16), "{}")}' for c in sorted(kids))
        text = (f'{{"schema":{SCHEMA},"parent":"{parent}","date":"{day}","dates":{dates},'
                f'"places":{{{body}}}}}\n')
        write_text(tmp / shard(parent), text)
    shutil.rmtree(dest, ignore_errors=True)
    os.replace(tmp, dest)
    return len(children)


def prune(folder: Path, keep: int) -> None:
    if not folder.exists():
        return
    dirs = sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith("."))
    for p in dirs[:-keep]:
        shutil.rmtree(p, ignore_errors=True)


def build(world: Path, out: Path, work: Path, places: Path, first: str, through: str | None) -> dict:
    t0 = time.time()
    days = gated_days(world, first)
    if through:
        days = [d for d in days if d <= through]
    day = days[-1]
    base = base_of(day, first)
    start = start_of(day, base, first)
    quests = json.loads((world / "counts" / day / "counts.json").read_text(encoding="utf-8"))["quests"]
    names = NameLayer(places)
    log(f"{len(days)} gated days {days[0]}..{day}; base {base}, window from {start}; {len(names.meta):,} named places")
    k, d, o, a, counted = load_events(world, work, days, quests, names)
    log(f"{len(k):,} change points, {len(counted):,} published places")
    ev = (k, d, o, a)
    # place/<base>/ is rebuilt when it is missing, or when what it was built from changed (the quests, the name
    # layer, the days up to base): the stamp sits in the work folder, since the output is uploaded. Not the places:
    # the counted set grows by a few on later days (11-01 1,018,465, 11-02 1,018,472), and such a place has no
    # place file until base moves; the page then shows its days after base from the parent's file only
    pstamp = work / f"place-{base}.key"
    want = dumps({"quests": quests, "overture": names.overture, "names": len(names.meta),
                  "days": days[:days.index(base) + 1]})
    if (out / "place" / base).exists() and pstamp.exists() and pstamp.read_text(encoding="utf-8") != want:
        log(f"place/{base}/ was built from other inputs: rebuilt")
        shutil.rmtree(out / "place" / base)
    if not (out / "place" / base).exists():
        t = time.time()
        n = write_places(out, base, days, ev, quests, names, counted)
        log(f"place/{base}/: {n:,} files ({time.time() - t:.0f} s)")
    write_text(pstamp, want)
    t = time.time()
    n = write_latest(out, day, start, days, ev, quests, names, counted)
    log(f"latest/{day}/: {n:,} parent files ({time.time() - t:.0f} s)")
    sc = json.loads((world / "world.json").read_text(encoding="utf-8")) if (world / "world.json").exists() else {}
    latest = {"schema": SCHEMA, "date": day, "first": days[0], "base": base, "dates": days,
              "scVersion": sc.get("scVersion") or _sc_version(), "resurveyMultiplier": 1,
              "overture": names.overture, "quests": quests,
              "place": f"place/{base}/", "latest": f"latest/{day}/"}
    write_text(out / "latest.json", json.dumps(latest, ensure_ascii=False, indent=1) + "\n")
    prune(out / "latest", KEEP_LATEST)
    prune(out / "place", KEEP_PLACE)
    log(f"built {out} for {day} in {time.time() - t0:.0f} s")
    return latest


def _sc_version() -> str | None:
    q = ROOT / "docs" / "data" / "quests.json"
    return json.loads(q.read_text(encoding="utf-8")).get("scVersion") if q.exists() else None


# --- verify: the published files read back, against counts.npz ---------------------------------------------------

def decode(points: list, n: int) -> tuple[list[int], list[int]]:
    """change points to columns of length n (the reader's rule, written apart from the writer)"""
    o, a = [0] * n, [0] * n
    pts = sorted(points)
    for j, (i, vo, va) in enumerate(pts):
        end = pts[j + 1][0] if j + 1 < len(pts) else n
        for t in range(i, end):
            o[t], a[t] = vo, va
    return o, a


def read_place(out: Path, latest: dict, pid: str, names: NameLayer) -> dict[str, dict[str, tuple[int, int]]]:
    """what the page sees for one place: date -> quest -> (open, aged), joined from its place file (to base) and
    its parent's latest file (after base)"""
    pf = json.loads((out / latest["place"] / shard(pid)).read_text(encoding="utf-8"))
    parent = names.parents[pid][0]
    lf = json.loads((out / latest["latest"] / shard(parent)).read_text(encoding="utf-8"))
    seen: dict[str, dict[str, tuple[int, int]]] = {}
    for q, pts in pf["quests"].items():
        o, a = decode(pts, len(pf["dates"]))
        for t, dt in enumerate(pf["dates"]):
            seen.setdefault(dt, {})[q] = (o[t], a[t])
    for q, pts in lf["places"].get(pid, {}).items():
        o, a = decode(pts, len(lf["dates"]))
        for t, dt in enumerate(lf["dates"]):
            if dt > latest["base"]:
                seen.setdefault(dt, {})[q] = (o[t], a[t])
    return seen


def read_window(out: Path, latest: dict, pid: str, parent: str) -> dict[str, dict[str, tuple[int, int]]]:
    """the place as its parent's latest file gives it, over the file's whole window (the children table's view)"""
    lf = json.loads((out / latest["latest"] / shard(parent)).read_text(encoding="utf-8"))
    if pid not in lf["places"]:
        raise SystemExit(f"{pid} missing from its parent's latest file {parent}")
    seen: dict[str, dict[str, tuple[int, int]]] = {dt: {} for dt in lf["dates"]}
    for q, pts in lf["places"][pid].items():
        o, a = decode(pts, len(lf["dates"]))
        for t, dt in enumerate(lf["dates"]):
            seen[dt][q] = (o[t], a[t])
    return seen


def verify(world: Path, out: Path, places: Path, sample: int, seed: int = 1) -> int:
    latest = json.loads((out / "latest.json").read_text(encoding="utf-8"))
    names = NameLayer(places)
    quests = latest["quests"]
    files = sorted((out / latest["place"]).glob("*/*.json"))
    rng = np.random.default_rng(seed)
    pick = [files[i].stem for i in rng.choice(len(files), size=min(sample, len(files)), replace=False)]
    seen = {pid: read_place(out, latest, pid, names) for pid in pick}
    # every parent's file too, over its whole window (a place in two region files is under both)
    views = [(f"{pid} in {par}", pid, read_window(out, latest, pid, par))
             for pid in pick for par in names.parents[pid]]
    want = set(hexkey(pick).tolist())
    bad = 0
    shown = [d for d in latest["dates"] if d <= latest["base"]] + \
            [d for d in latest["dates"] if d > latest["base"]]
    for day in shown:
        k, o, a, _ = day_state(world, day, quests, names)
        place = k >> QBITS
        m = np.isin(place, list(want))
        truth: dict[str, dict[str, tuple[int, int]]] = {}
        for kk, vo, va in zip(k[m].tolist(), o[m].tolist(), a[m].tolist()):
            truth.setdefault(idstr(kk >> QBITS), {})[quests[kk & 255]] = (vo, va)
        for pid in pick:
            got = {q: v for q, v in seen[pid].get(day, {}).items() if v != (0, 0)}
            exp = truth.get(pid, {})
            if got != exp:
                bad += 1
                if bad <= 5:
                    diff = {q: (exp.get(q), got.get(q)) for q in set(exp) | set(got) if exp.get(q) != got.get(q)}
                    log(f"MISMATCH {day} {pid}: {list(diff.items())[:5]}")
        for label, pid, view in views:
            if day not in view:
                continue
            got = {q: v for q, v in view[day].items() if v != (0, 0)}
            exp = truth.get(pid, {})
            if got != exp:
                bad += 1
                if bad <= 5:
                    log(f"MISMATCH {day} {label} (latest window): {exp} != {got}")
        log(f"verify {day}: {len(pick)} places checked, and {len(views)} parent views")
    log(f"verify: {bad} mismatches over {len(pick)} places and {len(shown)} days")
    return 1 if bad else 0


# --- crosscheck: the streamed world against a whole planet count of the same instant -----------------------------

def crosscheck(world: Path, places: Path, report: Path, day: str, out_json: Path | None) -> int:
    """the world's day `day` (streamed from the seed) against an independent whole count at that instant: the
    11-08 planet count with places (`.scratch/planet/world-places/report.json`, its `places`: id -> quest -> open,
    the default setting). Every published place both have, per quest `open`. Reports, does not gate: the notes
    layers differ (the whole count's notes dump against the world's), as the daily gate's 11 cities show."""
    names = NameLayer(places)
    log(f"reading {report} ...")
    rep = json.loads(report.read_text(encoding="utf-8"))["places"]
    quests = json.loads((world / "counts" / day / "counts.json").read_text(encoding="utf-8"))["quests"]
    k, o, _, counted = day_state(world, day, quests, names)
    ours: dict[str, dict[str, int]] = {}
    for kk, vo in zip(k.tolist(), o.tolist()):
        if vo:
            ours.setdefault(idstr(kk >> QBITS), {})[quests[kk & 255]] = vo
    both = sorted(set(idstr(x) for x in counted.tolist()) & set(rep))
    exact, tot_w, tot_r, rows = 0, 0, 0, []
    qdiff: dict[str, int] = {}
    for pid in both:
        a = ours.get(pid, {})
        b = {q: n for q, n in rep[pid].items() if n and q in quests}
        sa, sb = sum(a.values()), sum(b.values())
        tot_w += sa; tot_r += sb
        if a == b:
            exact += 1
            continue
        for q in set(a) | set(b):
            dq = a.get(q, 0) - b.get(q, 0)
            if dq:
                qdiff[q] = qdiff.get(q, 0) + dq
        rows.append((abs(sa - sb), pid, sa, sb))
    rows.sort(reverse=True)
    rel = (tot_w - tot_r) / tot_r if tot_r else 0.0
    log(f"crosscheck {day}: {len(both):,} places in both ({len(counted):,} published, {len(rep):,} in the report)")
    log(f"  equal in every quest: {exact:,} ({exact / max(1, len(both)):.4%}); open world {tot_w:,}, "
        f"report {tot_r:,} ({rel:+.5%})")
    for d, pid, sa, sb in rows[:10]:
        log(f"  {pid} {names.meta[pid][0]!r} ({names.meta[pid][1]}): world {sa:,}, report {sb:,} ({sa - sb:+,})")
    top = sorted(qdiff.items(), key=lambda x: -abs(x[1]))[:10]
    log(f"  by quest (world minus report): {top}")
    if out_json:
        write_text(out_json, json.dumps({"day": day, "places": len(both), "equal": exact, "openWorld": tot_w,
                                         "openReport": tot_r, "rel": rel, "worst": rows[:100],
                                         "byQuest": dict(top)}, indent=1) + "\n")
    return 0


# --- upload ------------------------------------------------------------------------------------------------------

def upload(out: Path, print_only: bool) -> int:
    """the new folders first (immutable), latest.json last (it points at them), then old folders deleted"""
    latest = json.loads((out / "latest.json").read_text(encoding="utf-8"))
    remote = f"r2:{BUCKET}"
    common = ["--transfers", "64", "--checkers", "64", "--fast-list", "--size-only", "--stats-one-line",
              "--stats", "60s"]
    cmds = [
        ["copy", str(out / latest["place"]), f"{remote}/{latest['place']}",
         "--header-upload", f"Cache-Control: {CACHE_IMMUTABLE}", *JSON_TYPE, *common],
        ["copy", str(out / latest["latest"]), f"{remote}/{latest['latest']}",
         "--header-upload", f"Cache-Control: {CACHE_IMMUTABLE}", *JSON_TYPE, *common],
        ["copyto", str(out / "latest.json"), f"{remote}/latest.json",
         "--header-upload", f"Cache-Control: {CACHE_LATEST_JSON}", *JSON_TYPE],
    ]
    local_latest = {p.name for p in (out / "latest").iterdir() if p.is_dir()}
    local_place = {p.name for p in (out / "place").iterdir() if p.is_dir()}
    if print_only:
        for c in cmds:
            print("rclone " + " ".join(f'"{x}"' if " " in x else x for x in c))
        print(f"then: purge {remote}/latest/<d> for d not in {sorted(local_latest)}, "
              f"place/<b> for b not in {sorted(local_place)}")
        return 0
    sys.path.insert(0, str(ROOT / "tools"))
    import cloud_publish as cp
    env = cp.rclone_env(cp.read_env())
    for c in cmds:
        log("rclone " + " ".join(c[:3]))
        r = subprocess.run(["rclone", *c], env=env, capture_output=True, text=True)
        if r.returncode:
            log(f"FAILED: {r.stderr.strip()[-1000:]}")
            return 1
    for folder, keep in (("latest", local_latest), ("place", local_place)):
        r = subprocess.run(["rclone", "lsf", "--dirs-only", f"{remote}/{folder}"], env=env,
                           capture_output=True, text=True)
        for name in r.stdout.split():
            name = name.rstrip("/")
            if name and name not in keep:
                log(f"purge {folder}/{name}")
                subprocess.run(["rclone", "purge", f"{remote}/{folder}/{name}"], env=env, check=False)
    log(f"uploaded {latest['date']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["build", "verify", "crosscheck", "upload"])
    ap.add_argument("--world", type=Path, default=WORLD)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--work", type=Path, default=WORK)
    ap.add_argument("--places", type=Path, default=PLACES)
    ap.add_argument("--first", default=FIRST)
    ap.add_argument("--through", help="build as of this day (default: the newest gated day)")
    ap.add_argument("--sample", type=int, default=2000)
    ap.add_argument("--print", action="store_true", help="upload: print the rclone commands, run nothing")
    ap.add_argument("--report", type=Path, default=ROOT.parent / "sc-open-quests" / ".scratch" / "planet"
                    / "world-places" / "report.json", help="crosscheck: the whole count's report.json")
    ap.add_argument("--day", default="2026-11-08", help="crosscheck: the report's instant")
    ap.add_argument("--json", type=Path, help="crosscheck: write the result here too")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # place names; python -I ignores PYTHONIOENCODING
    if a.cmd == "build":
        build(a.world, a.out, a.work, a.places, a.first, a.through)
        return 0
    if a.cmd == "verify":
        return verify(a.world, a.out, a.places, a.sample)
    if a.cmd == "crosscheck":
        return crosscheck(a.world, a.places, a.report, a.day, a.json)
    return upload(a.out, a.print)


if __name__ == "__main__":
    sys.exit(main())
