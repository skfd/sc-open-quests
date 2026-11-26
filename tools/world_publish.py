"""World places published: the world's daily counts per place, as files for the place-data bucket.

DESIGN.md, "World places published: stable paths (schema 2)". Reads the world (`W`, `.scratch/planet/world-1101`):
its gated days (`days/<D>/gate.json` ok; the first day by the seed's gate, `counts/<first>/gate1101.json`) and each
day's `counts/<D>/counts.{json,npz}` (tools/stream/place_counts.py). Writes, under `--out`, the bucket's layout:

    latest.json                          every publish: the date, and `v`, the token the page adds to each request
    place/<id[:2]>/<id>.json             a place's whole series; rewritten only when its bytes change
    children/<p[:2]>/<parent>.json       a parent's children, newest day and four weeks before (a country's
                                         parent: children/world.json); rewritten only when its bytes change
    city/<cityId>.json                   a counted city (config/cities.json), in a place file's form
    city-parts/<cityId>.json             its registered parts (config/parts), in a children file's form, and `noFile`:
                                         the parts with no place file (no quest on any day)
    cities.json                          every city's open quests, the app's defaults only
    city-quests.json                     every city's quests, in a children file's form (the compare view)
    city-trends.json                     every city's open quests on every day, the app's defaults only

Only the 12-hex Overture places the name layer (docs/places) has, and the counted cities; only `open` and `agedOnly`. A quest's series is a
list of change points `[day, open, aged]`, day counted from `first`. The paths never change, so only the files whose
bytes differ from what the bucket holds are uploaded: `work/local.json` holds each built file's hash,
`work/bucket.json` each uploaded one's.

The day's changes are cached under `--work` (`events/<D>.npz`: every (place, quest) whose values differ from the
day before; the first day against nothing), so a new day reads one counts file, not all of them.

    python tools/world_publish.py build  [--world W] [--out O] [--work K] [--through D]
    python tools/world_publish.py verify [--world W] [--out O] [--sample N]
    python tools/world_publish.py crosscheck [--world W] [--report R] [--day 2026-11-08]
    python tools/world_publish.py upload [--print] [--full] [--trial N]
    python tools/world_publish.py check  [--sample N]     the bucket over HTTPS against the local files
    python tools/world_publish.py cors [--set]
    python tools/world_publish.py daily [--sample N]   build; if anything is new, verify, upload, check (Task Scheduler)
"""
from __future__ import annotations

import argparse
import hashlib
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
OUT = ROOT / ".scratch" / "world-publish" / "site2"
WORK = ROOT / ".scratch" / "world-publish" / "work"
PLACES = ROOT / "docs" / "places"
FIRST = "2026-11-01"
SCHEMA = 2
WINDOW_DAYS = 28
BUCKET = "sc-open-quests-data"
HOST = "https://sc-data.comentality.com/"
MAX_UPLOAD = 1_500_000  # files one upload may ever plan: every place and parent (about 1.13M), with room
DAY_CAP = 200_000       # files a run may plan without --full: a day changes about 60k; more is a format or
                        # name-layer change, or a lost manifest, and somebody should look first
BATCH = 50_000          # files per rclone run; the bucket manifest is saved after each, so a failure resumes
MAX_DELETE = 2_000
CACHE_FILE = "public, max-age=86400"   # fetched as <path>?v=<latest.json v>, a new address each publish
CACHE_LATEST_JSON = "public, max-age=300"
JSON_TYPE = ["--header-upload", "Content-Type: application/json"]  # not left to rclone's guess (Windows' registry)
SUBTYPES = ["country", "dependency", "region", "county", "localadmin", "locality",
            "borough", "macrohood", "neighborhood", "microhood"]  # tools/places.py SUBTYPES
QBITS = 8  # a key is (place id as a 48-bit int) << QBITS | quest index
CITY = 1 << 48  # a counted city's "place id": this bit and 48 bits of its id's hash
CITY_PART = "osm-"  # a city's part id in the world's counts is osm-<cityId>
KINDS = ("p", "c", "s")  # the manifests' kinds: place files, children files, the cities' (by path, less .json)


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
        self.ids = idx.get("ids", "gers")  # whose place ids these are: a change makes every cached day another
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


# --- the counted cities ------------------------------------------------------------------------------------------

def city_key(cid: str) -> int:
    return CITY | int.from_bytes(hashlib.blake2b(cid.encode("utf-8"), digest_size=6).digest(), "big")


class Cities:
    """the counted cities: the key, name and parts of each, and which quests its totals cover (asked there, and on
    in the app by default)"""

    def __init__(self, cities: list[dict], parts: dict[str, list[str]], quests: list[dict]):
        sys.path.insert(0, str(ROOT / "tools"))
        import site_quests
        self.keys = {c["id"]: city_key(c["id"]) for c in cities}
        self.ids = {k: c for c, k in self.keys.items()}
        if len(self.ids) != len(self.keys):
            raise SystemExit("two cities have the same key")
        self.names = {c["id"]: c["name"] for c in cities}
        self.parts = {c: sorted(parts.get(c, [])) for c in self.keys}   # [] for a city with none
        self.totalled = {c["id"]: {q["name"] for q in quests if not q.get("defaultDisabled")
                                   and site_quests.status(q, c) == "counted"} for c in cities}

    @classmethod
    def load(cls) -> "Cities":
        sys.path.insert(0, str(ROOT / "tools"))
        import run
        import site_quests
        return cls(run.read_json(run.CITIES_CONFIG)["cities"],
                   {p.stem: [x["id"] for x in run.read_json(p)["parts"]] for p in sorted(run.PARTS_CONFIG.glob("*.json"))},
                   site_quests.base(archive=run.ARCHIVE_DIR)["quests"])

    def city_of(self, part: str) -> int | None:
        return self.keys.get(part[len(CITY_PART):]) if part.startswith(CITY_PART) else None


NO_CITIES = Cities([], {}, [])


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


def day_state(world: Path, day: str, quests: list[str], names: NameLayer, cities: Cities = NO_CITIES) -> tuple[np.ndarray, ...]:
    """the day's published (place, quest) values: sorted keys, open, aged (rows 0 in both dropped), and the
    published places the world counted that day (sorted keys)"""
    meta = json.loads((world / "counts" / day / "counts.json").read_text(encoding="utf-8"))
    qmap = np.full(len(meta["quests"]), -1, dtype=np.int64)
    for i, q in enumerate(meta["quests"]):
        if q in quests:
            qmap[i] = quests.index(q)
    pkey = np.array([int(p, 16) if len(p) == 12 and p in names.meta else cities.city_of(p) or -1
                     for p in meta["parts"]], dtype=np.int64)
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


def counted_quests(world: Path, day: str) -> list[str]:
    """the quests the world counted that day. Read off the head of counts.json: its `parts`, after them, are 30 MB"""
    p = world / "counts" / day / "counts.json"
    with open(p, encoding="utf-8") as fh:
        head = fh.read(1 << 16)
    i = head.find('"quests":')
    try:
        return json.JSONDecoder().raw_decode(head, head.index("[", i))[0] if i >= 0 else _all_quests(p)
    except ValueError:   # the list is longer than the head
        return _all_quests(p)


def _all_quests(p: Path) -> list[str]:
    return json.loads(p.read_text(encoding="utf-8"))["quests"]


def quests_from(world: Path, days: list[str], quests: list[str]) -> dict[str, int]:
    """of the newest day's quests, those not counted on the first day (a StreetComplete release added them): the
    number of the first day each was. Their 0 before it is no count"""
    out, left = {}, set(quests)
    for di, day in enumerate(days):
        for q in left & set(counted_quests(world, day)):
            left.discard(q)
            if di:
                out[q] = di
        if not left:
            break
    return {q: out[q] for q in quests if q in out}


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

def load_events(world: Path, work: Path, days: list[str], quests: list[str], names: NameLayer, cities: Cities = NO_CITIES):
    """every day's changes, cached: (keys, day index, open, aged) sorted by key then day; and the published places
    counted on any of the days (sorted keys) with the index of the first day each was counted"""
    ev = work / "events"
    ev.mkdir(parents=True, exist_ok=True)
    stamp = dumps({"quests": quests, "first": days[0], "overture": names.overture, "ids": names.ids,
                   **({"cities": sorted(cities.keys)} if cities.keys else {})})
    sfile = work / "events.key"
    if not sfile.exists() or sfile.read_text(encoding="utf-8") != stamp:
        shutil.rmtree(ev, ignore_errors=True)
        ev.mkdir(parents=True)
        write_text(sfile, stamp)
    prev = None
    ck, cf = np.zeros(0, np.int64), np.zeros(0, np.int32)
    out_k, out_d, out_o, out_a = [], [], [], []
    for di, day in enumerate(days):
        f = ev / f"{day}.npz"
        if not f.exists():
            if prev is None:
                prev = (day_state(world, days[di - 1], quests, names, cities)[:3]
                        if di > 0 else (np.zeros(0, np.int64), np.zeros(0, np.int32), np.zeros(0, np.int32)))
            t = time.time()
            k, o, a, counted = day_state(world, day, quests, names, cities)
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
            out_d.append(np.full(len(z["keys"]), di, np.int32))
            new = np.setdiff1d(z["counted"], ck)
        if len(new):
            ck = np.concatenate([ck, new]); cf = np.concatenate([cf, np.full(len(new), di, np.int32)])
            order = np.argsort(ck, kind="stable")
            ck, cf = ck[order], cf[order]
    k = np.concatenate(out_k); d = np.concatenate(out_d)
    o = np.concatenate(out_o); a = np.concatenate(out_a)
    order = np.lexsort((d, k))
    return k[order], d[order], o[order], a[order], ck, cf


def series_json(k: np.ndarray, d: np.ndarray, o: np.ndarray, a: np.ndarray, quests: list[str]) -> dict[int, str]:
    """place key -> the JSON object of its quests' change points (rows sorted by key then day)"""
    out: dict[int, str] = {}
    if not len(k):
        return out
    place = k >> QBITS
    qi = (k & ((1 << QBITS) - 1)).tolist()
    pl = place.tolist(); dl = d.tolist(); ol = o.tolist(); al = a.tolist()
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


def newest_and_back(k: np.ndarray, d: np.ndarray, o: np.ndarray, a: np.ndarray, back: int) -> dict[int, list]:
    """place key -> [(quest index, "[open,aged,openBack,agedBack]"), ...] in quest order: each pair's values on the
    newest day (its last change) and on day `back` (its last change on or before it); pairs 0 in all four left out"""
    out: dict[int, list] = {}
    if not len(k):
        return out
    last = np.ones(len(k), bool)
    last[:-1] = k[1:] != k[:-1]
    kn, on, an = k[last], o[last], a[last]
    m = d <= back
    kb, ob, ab = k[m], o[m], a[m]
    lastb = np.ones(len(kb), bool)
    lastb[:-1] = kb[1:] != kb[:-1]
    ob2, ab2 = np.zeros(len(kn), np.int32), np.zeros(len(kn), np.int32)
    at = np.searchsorted(kn, kb[lastb])
    ob2[at], ab2[at] = ob[lastb], ab[lastb]
    keep = (on != 0) | (an != 0) | (ob2 != 0) | (ab2 != 0)
    kn, on, an, ob2, ab2 = kn[keep], on[keep], an[keep], ob2[keep], ab2[keep]
    pl = (kn >> QBITS).tolist(); ql = (kn & ((1 << QBITS) - 1)).tolist()
    for p, q, vo, va, bo, ba in zip(pl, ql, on.tolist(), an.tolist(), ob2.tolist(), ab2.tolist()):
        out.setdefault(p, []).append((q, f"[{vo},{va},{bo},{ba}]"))
    return out


def idstr(key: int) -> str:
    return f"{key:012x}"


def shard(pid: str) -> str:
    return "world.json" if pid == "world" else f"{pid[:2]}/{pid}.json"


def rel(kind: str, pid: str) -> str:
    """a file's path in the bucket; kind "p" a place's own file, "c" a parent's children file, "s" a cities' file"""
    if kind == "s":
        return pid + ".json"
    return ("place/" if kind == "p" else "children/") + shard(pid)


def digest(text: str) -> str:
    return hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()


def load_manifest(path: Path) -> dict:
    if path.exists():
        m = json.loads(path.read_text(encoding="utf-8"))
        if m.get("schema") == SCHEMA:
            m.setdefault("s", {})   # a manifest from before the cities' files
            return m
    return {"schema": SCHEMA, "p": {}, "c": {}, "s": {}}


def save_manifest(path: Path, m: dict) -> None:
    tmp = path.with_suffix(".tmp")
    write_text(tmp, dumps(m) + "\n")
    os.replace(tmp, path)


def place_text(pid: str, meta: tuple[str, str, str], first: str, frm: int, series: str) -> str:
    name, subtype, cc = meta
    return (f'{{"schema":{SCHEMA},"id":"{pid}","name":{dumps(name)},"subtype":"{subtype}","cc":"{cc}",'
            f'"first":"{first}",' + (f'"from":{frm},' if frm else "") + f'"quests":{series}}}\n')


def children_text(parent: str, kids: list[str], rows: dict[int, list], quests: list[str],
                  key=lambda c: int(c, 16), more: str = "") -> str:
    """the file's quests are listed once, in the world's order, and a child's keys index that list"""
    mine = [(c, rows.get(key(c), [])) for c in sorted(kids)]
    used = sorted({q for _, r in mine for q, _ in r})
    at = {q: i for i, q in enumerate(used)}
    body = ",".join('"%s":{%s}' % (c, ",".join(f'"{at[q]}":{s}' for q, s in r)) for c, r in mine)
    return (f'{{"schema":{SCHEMA},"parent":"{parent}","quests":{dumps([quests[q] for q in used])},{more}'
            f'"places":{{{body}}}}}\n')


def city_totals(k: np.ndarray, d: np.ndarray, o: np.ndarray, n: int, quests: list[str], cities: Cities) -> dict[str, list]:
    """each city's open quests on each of the n days, over the quests its total covers"""
    out = {}
    at = {q: i for i, q in enumerate(quests)}
    for cid, key in cities.keys.items():
        lo, hi = np.searchsorted(k, [key << QBITS, (key + 1) << QBITS])
        total = np.zeros(n, np.int64)
        for q in cities.totalled[cid]:
            if q not in at:
                continue
            a, b = lo + np.searchsorted(k[lo:hi], [key << QBITS | at[q], (key << QBITS | at[q]) + 1])
            if a == b:
                continue
            step = np.zeros(n, np.int64)
            step[d[a:b]] = np.diff(o[a:b].astype(np.int64), prepend=0)
            total += np.cumsum(step)
        out[cid] = total.tolist()
    return out


def build(world: Path, out: Path, work: Path, places: Path, first: str, through: str | None,
          cities: Cities = NO_CITIES) -> dict:
    """every file's text is made, and a file is written only when its hash differs from the last build's
    (`work/local.json`), so `out` mirrors what the bucket should hold"""
    t0 = time.time()
    days = gated_days(world, first)
    if through:
        days = [d for d in days if d <= through]
    day, di = days[-1], len(days) - 1
    if days != [(date.fromisoformat(days[0]) + timedelta(days=i)).isoformat() for i in range(len(days))]:
        raise SystemExit("the gated days have a gap: a day number would not be a date")
    back = max(0, di - WINDOW_DAYS)
    quests = counted_quests(world, day)
    late = quests_from(world, days, quests)
    names = NameLayer(places)
    log(f"{len(days)} gated days {days[0]}..{day}; children against {days[back]}; {len(names.meta):,} named places")
    k, d, o, a, ck, cf = load_events(world, work, days, quests, names, cities)
    log(f"{len(k):,} change points, {len(ck):,} published places")
    old = load_manifest(work / "local.json")
    if old.get("out") != str(out.resolve()) or not (out / "latest.json").exists():
        old = {kind: {} for kind in KINDS}   # another folder, or an emptied one: every file is written
    new = {"schema": SCHEMA, "out": str(out.resolve()), **{kind: {} for kind in KINDS}}
    wrote = dict.fromkeys(KINDS, 0)

    def put(kind: str, pid: str, text: str) -> None:
        h = digest(text)
        new[kind][pid] = h
        if old[kind].get(pid) != h:
            write_text(out / rel(kind, pid), text)
            wrote[kind] += 1

    t = time.time()
    ser = series_json(k, d, o, a, quests)
    children: dict[str, list[str]] = {}
    city_from = {}
    for key, frm in zip(ck.tolist(), cf.tolist()):
        if key in cities.ids:
            city_from[cities.ids[key]] = frm
            continue
        pid = idstr(key)
        if pid not in names.meta:   # the events cache is older than the name layer, which dropped the place
            continue
        put("p", pid, place_text(pid, names.meta[pid], days[0], frm, ser.get(key, "{}")))
        for p in names.parents.get(pid, []):
            children.setdefault(p, []).append(pid)
    for cid, frm in city_from.items():
        put("s", f"city/{cid}", f'{{"schema":{SCHEMA},"id":"{cid}","name":{dumps(cities.names[cid])},"first":"{days[0]}",' +
            (f'"from":{frm},' if frm else "") + f'"quests":{ser.get(cities.keys[cid], "{}")}}}\n')
    del ser
    log(f"place/: {len(new['p']):,} files, {wrote['p']:,} written ({time.time() - t:.0f} s)")
    t = time.time()
    rows = newest_and_back(k, d, o, a, back)
    for parent, kids in children.items():
        put("c", parent, children_text(parent, kids, rows, quests))
    log(f"children/: {len(new['c']):,} files, {wrote['c']:,} written ({time.time() - t:.0f} s)")
    if cities.keys:
        if missing := sorted(set(cities.keys) - set(city_from)):
            raise SystemExit(f"cities the world does not count: {missing}")
        for cid, parts in cities.parts.items():
            none = [p for p in parts if p not in new["p"]]
            put("s", f"city-parts/{cid}", children_text(cid, parts, rows, quests, more=f'"noFile":{dumps(none)},'))
        put("s", "city-quests", children_text("cities", list(cities.keys), rows, quests, key=cities.keys.get))
        totals = city_totals(k, d, o, len(days), quests, cities)
        put("s", "cities", dumps({"schema": SCHEMA, "open": {c: v[-1] for c, v in totals.items()}}) + "\n")
        put("s", "city-trends", dumps({"schema": SCHEMA, "first": days[0], "open": totals}) + "\n")
        log(f"cities: {len(new['s']):,} files, {wrote['s']:,} written")
    gone = [(kind, pid) for kind in KINDS for pid in old[kind] if pid not in new[kind]]
    for kind, pid in gone:
        (out / rel(kind, pid)).unlink(missing_ok=True)
    if gone:
        log(f"{len(gone):,} files no longer published: removed")
    v = hashlib.blake2b(digest_size=6)
    v.update(day.encode())
    for kind in KINDS:
        for pid in sorted(new[kind]):
            v.update(pid.encode()); v.update(new[kind][pid].encode())
    sc = json.loads((world / "world.json").read_text(encoding="utf-8")) if (world / "world.json").exists() else {}
    latest = {"schema": SCHEMA, "v": v.hexdigest(), "date": day, "first": days[0], "back": days[back],
              "scVersion": sc.get("scVersion") or _sc_version(), "resurveyMultiplier": 1,
              "overture": names.overture, "quests": quests, **({"questsFrom": late} if late else {}),
              "place": "place/", "children": "children/",
              **({"city": "city/", "cityParts": "city-parts/"} if cities.keys else {})}
    write_text(out / "latest.json", json.dumps(latest, ensure_ascii=False, indent=1) + "\n")
    new["v"], new["date"] = latest["v"], day
    save_manifest(work / "local.json", new)
    log(f"built {out} for {day} (v {latest['v']}) in {time.time() - t0:.0f} s")
    return latest


def _sc_version() -> str | None:
    q = ROOT / "docs" / "data" / "quests.json"
    return json.loads(q.read_text(encoding="utf-8")).get("scVersion") if q.exists() else None


# --- verify: the published files read back, against counts.npz ---------------------------------------------------

def decode(points: list, n: int) -> tuple[list[int], list[int]]:
    """change points to columns of length n (the reader's rule, written apart from the writer): a point past
    the last day is ignored, which is how a file newer than latest.json reads as the older day"""
    o, a = [0] * n, [0] * n
    pts = sorted(p for p in points if p[0] < n)
    for j, (i, vo, va) in enumerate(pts):
        end = pts[j + 1][0] if j + 1 < len(pts) else n
        for t in range(i, end):
            o[t], a[t] = vo, va
    return o, a


def day_list(latest: dict) -> list[str]:
    first, last = date.fromisoformat(latest["first"]), date.fromisoformat(latest["date"])
    return [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


def read_place(out: Path, latest: dict, pid: str) -> dict[str, dict[str, tuple[int, int]]]:
    """what the page sees for one place: date -> quest -> (open, aged), from its own file alone, from the day it
    was first counted to latest.json's date"""
    return read_series(json.loads((out / latest["place"] / shard(pid)).read_text(encoding="utf-8")), latest)


def read_series(pf: dict, latest: dict) -> dict[str, dict[str, tuple[int, int]]]:
    days = day_list(latest)
    seen: dict[str, dict[str, tuple[int, int]]] = {dt: {} for dt in days[pf.get("from", 0):]}
    for q, pts in pf["quests"].items():
        o, a = decode(pts, len(days))
        for t in range(pf.get("from", 0), len(days)):
            seen[days[t]][q] = (o[t], a[t])
    return seen


def read_children(out: Path, latest: dict, pid: str, parent: str) -> tuple[dict, dict]:
    """the place as its parent's children file gives it: quest -> (open, aged) on the date, and on `back`"""
    cf = json.loads((out / latest["children"] / shard(parent)).read_text(encoding="utf-8"))
    if pid not in cf["places"]:
        raise SystemExit(f"{pid} missing from its parent's children file {parent}")
    row = {cf["quests"][int(i)]: v for i, v in cf["places"][pid].items()}
    return ({q: (v[0], v[1]) for q, v in row.items()}, {q: (v[2], v[3]) for q, v in row.items()})


def read_city(out: Path, latest: dict, cid: str) -> dict[str, dict[str, tuple[int, int]]]:
    return read_series(json.loads((out / latest["city"] / f"{cid}.json").read_text(encoding="utf-8")), latest)


def verify(world: Path, out: Path, work: Path, places: Path, sample: int, seed: int = 1, cities: Cities = NO_CITIES) -> int:
    latest = json.loads((out / "latest.json").read_text(encoding="utf-8"))
    names = NameLayer(places)
    quests = latest["quests"]
    ids = sorted(load_manifest(work / "local.json")["p"])
    rng = np.random.default_rng(seed)
    pick = [ids[i] for i in rng.choice(len(ids), size=min(sample, len(ids)), replace=False)]
    seen = {pid: read_place(out, latest, pid) for pid in pick}
    # every parent's file too (a place in two region files is under both)
    views = [(f"{pid} in {par}", pid, read_children(out, latest, pid, par))
             for pid in pick for par in names.parents[pid]]
    want = set(hexkey(pick).tolist()) | set(cities.ids)
    for cid in cities.keys:   # every city, every time, and its row of the compare view
        seen[cid] = read_city(out, latest, cid)
    cq = json.loads((out / "city-quests.json").read_text(encoding="utf-8")) if cities.keys else None
    bad = 0

    def nz(row: dict) -> dict:
        return {q: v for q, v in row.items() if v != (0, 0)}

    for day in day_list(latest):
        k, o, a, _ = day_state(world, day, quests, names, cities)
        place = k >> QBITS
        m = np.isin(place, list(want))
        truth: dict[str, dict[str, tuple[int, int]]] = {}
        for kk, vo, va in zip(k[m].tolist(), o[m].tolist(), a[m].tolist()):
            truth.setdefault(cities.ids.get(kk >> QBITS) or idstr(kk >> QBITS), {})[quests[kk & 255]] = (vo, va)
        for pid in [*pick, *cities.keys]:
            got = nz(seen[pid].get(day, {}))
            exp = truth.get(pid, {})
            if got != exp:
                bad += 1
                if bad <= 5:
                    diff = {q: (exp.get(q), got.get(q)) for q in set(exp) | set(got) if exp.get(q) != got.get(q)}
                    log(f"MISMATCH {day} {pid}: {list(diff.items())[:5]}")
        for cid in cities.keys if day == latest["date"] else ():
            row = nz({cq["quests"][int(i)]: (v[0], v[1]) for i, v in cq["places"][cid].items()})
            if row != truth.get(cid, {}):
                bad += 1
                log(f"MISMATCH {day} {cid}: its row of city-quests.json")
        for which, at in ((0, latest["date"]), (1, latest["back"])):
            if day != at:
                continue
            for label, pid, view in views:
                got, exp = nz(view[which]), truth.get(pid, {})
                if got != exp:
                    bad += 1
                    if bad <= 5:
                        log(f"MISMATCH {day} {label} (children file, {'back' if which else 'newest'}): "
                            f"{exp} != {got}")
        log(f"verify {day}: {len(pick)} places checked")
    log(f"verify: {bad} mismatches over {len(pick)} places, {len(cities.keys)} cities, {len(views)} children views "
        f"and {len(day_list(latest))} days")
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

def plan(out: Path, work: Path) -> tuple[list[tuple[str, str]], list[tuple[str, str]], dict, dict]:
    """the files to upload (their hash differs from the bucket's) and to delete (the bucket's, no longer built),
    each (kind, id) sorted by path; and both manifests"""
    local, bucket = load_manifest(work / "local.json"), load_manifest(work / "bucket.json")
    if local.get("out") != str(out.resolve()):
        raise SystemExit(f"{work / 'local.json'} was not built into {out}: build first")
    todo = sorted(((kind, pid) for kind in KINDS for pid, h in local[kind].items()
                   if bucket[kind].get(pid) != h), key=lambda x: rel(*x))
    gone = sorted(((kind, pid) for kind in KINDS for pid in bucket[kind] if pid not in local[kind]),
                  key=lambda x: rel(*x))
    return todo, gone, local, bucket


def upload(out: Path, work: Path, print_only: bool = False, full: bool = False, trial: int = 0,
           max_delete: int = MAX_DELETE, keep_gone: bool = False) -> int:
    """the changed files in batches (the bucket manifest saved after each), then latest.json, which
    carries the new `v`, so no page asks for the new files before all are there, and last the gone ones deleted"""
    todo, gone, local, bucket = plan(out, work)
    remote = f"r2:{BUCKET}"
    log(f"plan: {len(todo):,} files to upload of {len(local['p']) + len(local['c']):,}, {len(gone):,} to delete; "
        f"bucket at {bucket.get('date')} (v {bucket.get('v')}), local {local.get('date')} (v {local.get('v')})")
    if print_only:
        for kind, pid in todo[:10]:
            print(rel(kind, pid))
        print(f"rclone copy {out} {remote} --files-from <list> --no-traverse --no-check-dest "
              f'--header-upload "Cache-Control: {CACHE_FILE}"   (batches of {BATCH:,})')
        return 0
    if len(todo) + 1 > MAX_UPLOAD:
        log(f"FAILED: {len(todo):,} files is past MAX_UPLOAD {MAX_UPLOAD:,}; a run this big is a bug")
        return 1
    if len(todo) > DAY_CAP and not full and not trial:
        log(f"FAILED: {len(todo):,} files is past DAY_CAP {DAY_CAP:,}; a day changes about 60,000. If the format, "
            f"the name layer or the quest list changed, look at the plan (--print) and pass --full")
        return 1
    if keep_gone:   # the old files stay in the bucket and in its manifest: a later upload without it deletes them
        log(f"{len(gone):,} files no longer built are kept")
        gone = []
    if len(gone) > max_delete:
        log(f"FAILED: {len(gone):,} files to delete is past the cap of {max_delete:,} (--max-delete raises it, for a "
            f"change of every place id)")
        return 1
    if trial:   # a few of each kind, and neither deletes nor latest.json: the bucket's pages see nothing
        todo = ([x for x in todo if x[0] == "p"][:trial // 2] + [x for x in todo if x[0] == "c"][:trial - trial // 2])
    sys.path.insert(0, str(ROOT / "tools"))
    import cloud_publish as cp
    import spend_breaker
    try:
        spend_breaker.gate(planned_class_a=len(todo) + 1, strict=True)
    except spend_breaker.Tripped as e:
        log(f"FAILED: {e}")
        return 1
    env = cp.rclone_env(cp.read_env())
    listing = work / "upload-list.txt"
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        write_text(listing, "".join(rel(kind, pid) + "\n" for kind, pid in batch))
        log(f"rclone copy: files {i + 1:,} to {i + len(batch):,} of {len(todo):,}")
        r = subprocess.run(["rclone", "copy", str(out), remote, "--files-from", str(listing), "--no-traverse",
                            "--no-check-dest", "--header-upload", f"Cache-Control: {CACHE_FILE}", *JSON_TYPE,
                            "--transfers", "64", "--stats-one-line", "--stats", "60s"],
                           env=env, capture_output=True, text=True)
        if r.returncode:
            log(f"FAILED: {r.stderr.strip()[-1000:]}")
            return 1
        for kind, pid in batch:
            bucket[kind][pid] = local[kind][pid]
        save_manifest(work / "bucket.json", bucket)
    if trial:
        log(f"trial: {len(todo):,} files uploaded; latest.json untouched")
        return 0
    log("rclone copyto latest.json")
    r = subprocess.run(["rclone", "copyto", str(out / "latest.json"), f"{remote}/latest.json",
                        "--header-upload", f"Cache-Control: {CACHE_LATEST_JSON}", *JSON_TYPE],
                       env=env, capture_output=True, text=True)
    if r.returncode:
        log(f"FAILED: {r.stderr.strip()[-1000:]}")
        return 1
    # latest.json first: no page asks for a file that is about to go
    for i in range(0, len(gone), BATCH):
        batch = gone[i:i + BATCH]
        write_text(listing, "".join(rel(kind, pid) + "\n" for kind, pid in batch))
        log(f"rclone delete: files {i + 1:,} to {i + len(batch):,} of {len(gone):,}")
        r = subprocess.run(["rclone", "delete", remote, "--files-from", str(listing), "--no-traverse",
                            "--transfers", "64"], env=env, capture_output=True, text=True)
        if r.returncode:
            log(f"FAILED: delete: {r.stderr.strip()[-1000:]}")
            return 1
        for kind, pid in batch:
            del bucket[kind][pid]
        save_manifest(work / "bucket.json", bucket)
    bucket["v"], bucket["date"] = local.get("v"), local.get("date")
    save_manifest(work / "bucket.json", bucket)
    log(f"uploaded {local.get('date')} (v {local.get('v')})")
    return 0


def check_live(out: Path, work: Path, sample: int, host: str = HOST, seed: int | None = None) -> int:
    """the bucket as a page reads it, against the local files: latest.json's `v`, then a sample of the files the
    bucket manifest says it holds (most of them skipped by the last upload as unchanged), byte for byte"""
    import urllib.error
    import urllib.request

    def get(path: str) -> bytes | None:
        req = urllib.request.Request(host + path, headers={"User-Agent": "curl/8.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError) as e:
            log(f"  {path}: {e}")
            return None

    bucket = load_manifest(work / "bucket.json")
    v = bucket.get("v")
    raw = get(f"latest.json?fresh={int(time.time())}")   # its own address, so not the edge's five-minute copy
    live = json.loads(raw) if raw else {}
    bad = 0
    if live.get("v") != v:
        log(f"MISMATCH latest.json: the bucket serves v {live.get('v')}, the manifest says {v}")
        bad += 1
    keys = [(kind, pid) for kind in KINDS for pid in bucket[kind]]
    rng = np.random.default_rng(seed)
    for i in rng.choice(len(keys), size=min(sample, len(keys)), replace=False):
        path = rel(*keys[i])
        got = get(f"{path}?v={v}")
        if got is None or got != (out / path).read_bytes():
            bad += 1
            if bad <= 5:
                log(f"MISMATCH {path}: the bucket's copy is {'missing' if got is None else 'not the local file'}")
    log(f"check: {bad} mismatches over latest.json and {min(sample, len(keys))} files at {host}")
    return 1 if bad else 0


SITE_ORIGIN = "https://street-complete-statistics.comentality.com"  # cloudflare/wrangler.jsonc routes
CORS_RULES = {"rules": [{"id": "site-reads", "allowed": {"origins": [SITE_ORIGIN], "methods": ["GET", "HEAD"]},
                         "maxAgeSeconds": 86400}]}


def cors(set_rule: bool) -> int:
    """The bucket's CORS rule: the site reads the bucket from another origin. Prints it; --set writes CORS_RULES."""
    import urllib.error
    import urllib.request
    sys.path.insert(0, str(ROOT / "tools"))
    import cloud_publish as cp
    env = cp.read_env()
    url = (f"https://api.cloudflare.com/client/v4/accounts/{env['CLOUDFLARE_ACCOUNT_ID']}"
           f"/r2/buckets/{BUCKET}/cors")

    def call(method: str, body: dict | None = None) -> dict:
        req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                     headers={"Authorization": f"Bearer {env['CLOUDFLARE_API_TOKEN']}",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            return {"success": False, "status": e.code, "body": e.read().decode(errors="replace")[:500]}

    if set_rule:
        r = call("PUT", CORS_RULES)
        if not r.get("success"):
            log(f"FAILED: {r}")
            return 1
        log("set")
    r = call("GET")
    log(json.dumps(r.get("result", r)))
    return 0


def daily(world: Path, out: Path, work: Path, places: Path, first: str, sample: int, cities: Cities) -> int:
    """The world loop's last step (run.py site): build to the newest gated day; if the bucket is behind, verify a sample, upload the
    changed files and read a sample back over HTTPS. `work/daily.lock` keeps two runs apart. Never --full: a plan
    past DAY_CAP stops here and waits for somebody."""
    work.mkdir(parents=True, exist_ok=True)
    lock = work / "daily.lock"
    if lock.exists() and time.time() - lock.stat().st_mtime < 12 * 3600:
        log(f"FAILED: {lock} is held (another build or upload); stale after 12 h")
        return 1
    lock.write_text(str(os.getpid()), encoding="utf-8")
    try:
        latest = build(world, out, work, places, first, None, cities)
        todo, gone, _, bucket = plan(out, work)
        if not todo and not gone and bucket.get("v") == latest["v"]:
            log(f"nothing new: {latest['date']} is uploaded")
            return 0
        if verify(world, out, work, places, sample, cities=cities):
            log("FAILED: verify found mismatches; not uploading")
            return 1
        if upload(out, work):
            return 1
        return check_live(out, work, 40)
    finally:
        lock.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["build", "verify", "crosscheck", "upload", "check", "cors", "daily"])
    ap.add_argument("--world", type=Path, default=WORLD)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--work", type=Path, default=WORK)
    ap.add_argument("--places", type=Path, default=PLACES)
    ap.add_argument("--first", default=FIRST)
    ap.add_argument("--through", help="build as of this day (default: the newest gated day)")
    ap.add_argument("--sample", type=int, help="verify: places read back (default 2000); check: files fetched (40)")
    ap.add_argument("--print", action="store_true", help="upload: print the plan, run nothing")
    ap.add_argument("--full", action="store_true", help="upload: allow a plan past DAY_CAP (the first upload)")
    ap.add_argument("--keep-gone", action="store_true", help="upload: delete nothing")
    ap.add_argument("--max-delete", type=int, default=MAX_DELETE, help="upload: the most files it may delete")
    ap.add_argument("--trial", type=int, default=0, help="upload: only this many files, and not latest.json")
    ap.add_argument("--set", action="store_true", help="cors: write the rule (without: print it)")
    ap.add_argument("--report", type=Path, default=ROOT.parent / "sc-open-quests" / ".scratch" / "planet"
                    / "world-places" / "report.json", help="crosscheck: the whole count's report.json")
    ap.add_argument("--day", default="2026-11-08", help="crosscheck: the report's instant")
    ap.add_argument("--json", type=Path, help="crosscheck: write the result here too")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # place names; python -I ignores PYTHONIOENCODING
    if a.cmd == "build":
        build(a.world, a.out, a.work, a.places, a.first, a.through, Cities.load())
        return 0
    if a.cmd == "verify":
        return verify(a.world, a.out, a.work, a.places, a.sample or 2000, cities=Cities.load())
    if a.cmd == "crosscheck":
        return crosscheck(a.world, a.places, a.report, a.day, a.json)
    if a.cmd == "daily":
        return daily(a.world, a.out, a.work, a.places, a.first, a.sample or 2000, Cities.load())
    if a.cmd == "cors":
        return cors(a.set)
    if a.cmd == "check":
        return check_live(a.out, a.work, a.sample or 40)
    return upload(a.out, a.work, a.print, a.full, a.trial, a.max_delete, a.keep_gone)


if __name__ == "__main__":
    sys.exit(main())
