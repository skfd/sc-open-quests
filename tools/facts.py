"""The facts: every count as rows of Parquet, one folder per source and day, for cities and the world alike.

DESIGN.md, "Storage: facts, serving, working state". Written from what the counting already leaves behind (the
cities' snapshots in data/archive/, the world's counts in .scratch/planet/world-1101/counts/), so nothing that
counts has to change yet. Layout, under data/facts/ (not in git), in hive form so DuckDB reads `source` and
`date` off the path:

    counts/source=<S>/date=<D>/data.parquet   one row per place and quest that has a count
    places/source=<S>/date=<D>/data.parquet   one row per place counted that day, also those with nothing open

`<S>` is a region id (ontario, europe-west, ...) or `world`. Both files of a day carry, in the Parquet key-value
metadata under `sc-open-quests`, the run as JSON: for a region the snapshot's header (everything but `cities`),
for the world its clock, measures and quest order, and the day's gate. A day is whole, never a delta.

counts columns: place, within, quest, then the measures as nullable int32 (null: not measured, which is not 0):
open, nodes, ways, relations, aged_only, open05, aged05, open2, aged2, open_all_notes.
  - a city's row: place = the city id, within null.
  - a part's row (a neighbourhood counted inside a city): place = the place id, within = the city id; only open
    and aged_only are measured, and aged_only is null where the snapshot has no aged split for the part.
  - a world row: place as the world names it (a 12-hex place id, `city:<cell>`, `osm-<city>`), within null.
places columns: place, within, kind (city, part, world), the city denominators (land_area_km2, population,
tagged_nodes, tagged_ways, highway_km), json_int (the denominators the snapshot wrote as integers, kept so a
snapshot can be rebuilt as it was), has_parts and has_aged (whether the snapshot had `parts` / an aged split).

    python tools/facts.py cities [--region R] [--force]   snapshots without facts, or newer than theirs
    python tools/facts.py world  [--world W] [--force]    the world's gated days
    python tools/facts.py verify [--source S] [--sample N] [--world W]
                                  rebuild each snapshot / each world day from its facts and compare with the
                                  original: every key, value and order. Exit 1 on any difference.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive_backup  # noqa: E402  (which world days are gated)

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "data" / "archive"
FACTS = ROOT / "data" / "facts"
WORLD = archive_backup.WORLD
SCHEMA = 1
META = b"sc-open-quests"
# a snapshot's name for a measure, and the column's
MEASURES = [("open", "open"), ("nodes", "nodes"), ("ways", "ways"), ("relations", "relations"),
            ("agedOnly", "aged_only"), ("open05", "open05"), ("aged05", "aged05"), ("open2", "open2"),
            ("aged2", "aged2"), ("openAllNotes", "open_all_notes")]
COLUMN = dict(MEASURES)
DENOMINATORS = [("landAreaKm2", "land_area_km2", pa.float64()), ("population", "population", pa.int64()),
                ("taggedNodes", "tagged_nodes", pa.int64()), ("taggedWays", "tagged_ways", pa.int64()),
                ("highwayKm", "highway_km", pa.float64())]
COUNTS_SCHEMA = pa.schema([("place", pa.string()), ("within", pa.string()), ("quest", pa.string())] +
                          [(c, pa.int32()) for _, c in MEASURES])
PLACES_SCHEMA = pa.schema([("place", pa.string()), ("within", pa.string()), ("kind", pa.string())] +
                          [(c, t) for _, c, t in DENOMINATORS] +
                          [("json_int", pa.list_(pa.string())), ("has_parts", pa.bool_()), ("has_aged", pa.bool_())])


def log(msg: str) -> None:
    print(f"[facts] {msg}", flush=True)


def day_files(facts: Path, source: str, day: str) -> tuple[Path, Path]:
    return (facts / "counts" / f"source={source}" / f"date={day}" / "data.parquet",
            facts / "places" / f"source={source}" / f"date={day}" / "data.parquet")


def _write(table: pa.Table, path: Path, run: dict) -> None:
    """whole or not at all: written beside, then moved over"""
    meta = {META: json.dumps({"schema": SCHEMA, "run": run}, ensure_ascii=False, separators=(",", ":")).encode()}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".partial")
    pq.write_table(table.replace_schema_metadata(meta), tmp, compression="zstd", row_group_size=1 << 20,
                   use_dictionary=["place", "within", "quest", "kind"])
    os.replace(tmp, path)


def read_run(path: Path) -> dict:
    return json.loads(pq.read_schema(path).metadata[META])["run"]


# --- cities: a region's snapshot ---------------------------------------------------------------------------------

def snapshot_tables(snap: dict) -> tuple[pa.Table, pa.Table, dict]:
    """a snapshot as (counts, places, run); rows in the snapshot's own order, so it can be rebuilt as it was"""
    counts = {name: [] for name in COUNTS_SCHEMA.names}
    places = {name: [] for name in PLACES_SCHEMA.names}

    def count(place, within, quest, values: dict) -> None:
        counts["place"].append(place)
        counts["within"].append(within)
        counts["quest"].append(quest)
        for _, c in MEASURES:
            counts[c].append(values.get(c))

    def place(pid, within, kind, den: dict | None, has_parts, has_aged) -> None:
        places["place"].append(pid)
        places["within"].append(within)
        places["kind"].append(kind)
        ints = []
        for key, c, t in DENOMINATORS:
            v = None if den is None else den[key]
            if t == pa.float64() and isinstance(v, int):
                ints.append(key)
                v = float(v)
            places[c].append(v)
        places["json_int"].append(ints if den is not None else None)
        places["has_parts"].append(has_parts)
        places["has_aged"].append(has_aged)

    for cid, city in snap["cities"].items():
        unknown = set(city) - {"denominators", "quests", "parts", "partsAged"}
        if unknown or set(city["denominators"]) != {k for k, _, _ in DENOMINATORS}:
            raise RuntimeError(f"{cid}: a city shape these facts do not hold: {sorted(unknown)}, "
                               f"{sorted(city['denominators'])}")
        parts, aged = city.get("parts"), city.get("partsAged")
        place(cid, None, "city", city["denominators"], parts is not None, aged is not None)
        for quest, m in city["quests"].items():
            if set(m) - set(COLUMN):
                raise RuntimeError(f"{cid} {quest}: measures these facts do not hold: {sorted(set(m) - set(COLUMN))}")
            count(cid, None, quest, {COLUMN[k]: v for k, v in m.items()})
        for pid, quests in (parts or {}).items():
            split = None if aged is None else aged.get(pid)
            place(pid, cid, "part", None, None, split is not None)
            for quest, n in quests.items():
                count(pid, cid, quest, {"open": n, "aged_only": None if split is None else split.get(quest, 0)})
        for pid, quests in (aged or {}).items():   # what the loop above cannot hold
            for quest in quests:
                if quest not in (parts or {}).get(pid, {}):
                    raise RuntimeError(f"{cid}: part {pid} has aged {quest} with nothing open")
    run = {k: v for k, v in snap.items() if k != "cities"}
    return (pa.table(counts, schema=COUNTS_SCHEMA), pa.table(places, schema=PLACES_SCHEMA), run)


def snapshot_from(counts: pa.Table, places: pa.Table, run: dict) -> dict:
    """the snapshot these facts were written from: the same keys, values and order"""
    cities: dict = {}
    for p in places.to_pylist():
        if p["kind"] == "city":
            den = {}
            for key, c, _ in DENOMINATORS:
                v = p[c]
                den[key] = int(v) if v is not None and key in p["json_int"] else v
            city = cities[p["place"]] = {"denominators": den, "quests": {}}
            if p["has_parts"]:
                city["parts"] = {}
            if p["has_aged"]:
                city["partsAged"] = {}
        else:
            city = cities[p["within"]]
            city["parts"][p["place"]] = {}
            if p["has_aged"]:
                city["partsAged"][p["place"]] = {}
    for r in counts.to_pylist():
        if r["within"] is None:
            cities[r["place"]]["quests"][r["quest"]] = {k: r[c] for k, c in MEASURES if r[c] is not None}
        else:
            city = cities[r["within"]]
            city["parts"][r["place"]][r["quest"]] = r["open"]
            if r["aged_only"]:
                city["partsAged"][r["place"]][r["quest"]] = r["aged_only"]
    out = dict(run)
    out["cities"] = cities
    return out


def region_snapshots(archive: Path, region: str | None = None) -> list[tuple[str, str, Path]]:
    out = []
    for d in sorted(p for p in archive.iterdir() if p.is_dir()) if archive.is_dir() else []:
        if region in (None, d.name):
            out += [(d.name, f.stem, f) for f in sorted((d / "snapshots").glob("*.json"))]
    return out


def cities(archive: Path = ARCHIVE, facts: Path = FACTS, region: str | None = None, force: bool = False) -> int:
    done = 0
    for source, day, f in region_snapshots(archive, region):
        cf, pf = day_files(facts, source, day)
        if not force and cf.exists() and pf.exists() and min(cf.stat().st_mtime, pf.stat().st_mtime) >= f.stat().st_mtime:
            continue
        counts, places, run = snapshot_tables(json.loads(f.read_text(encoding="utf-8")))
        _write(places, pf, run)
        _write(counts, cf, run)      # last: a day with its counts file is a whole day
        done += 1
    log(f"cities: {done} snapshot(s) written" + (f" for {region}" if region else ""))
    return done


# --- the world: a gated day's counts -----------------------------------------------------------------------------

def _snake(name: str) -> str:
    return COLUMN.get(name, name)


def world_tables(day_dir: Path, gate: dict | None, day: dict | None) -> tuple[pa.Table, pa.Table, dict]:
    head = json.loads((day_dir / "counts.json").read_text(encoding="utf-8"))
    z = np.load(day_dir / "counts.npz")
    part, quest, m = z["part"], z["quest"], z["m"]
    cols = [_snake(x) for x in head["measures"]]
    if set(cols) - set(COUNTS_SCHEMA.names) or m.shape[1] != len(cols):
        raise RuntimeError(f"{day_dir}: measures these facts do not hold: {head['measures']}")
    if m.size and (m.min() < 0 or m.max() > np.iinfo(np.int32).max):
        raise RuntimeError(f"{day_dir}: a count outside int32")
    parts = pa.array(head["parts"], pa.string())
    arrays = {
        "place": pa.DictionaryArray.from_arrays(pa.array(part.astype(np.int32)), parts),
        "within": pa.nulls(len(part), pa.string()),
        "quest": pa.DictionaryArray.from_arrays(pa.array(quest.astype(np.int32)), pa.array(head["quests"], pa.string())),
    }
    for _, c in MEASURES:
        arrays[c] = (pa.array(np.ascontiguousarray(m[:, cols.index(c)]).astype(np.int32)) if c in cols
                     else pa.nulls(len(part), pa.int32()))
    counts = pa.table([arrays[n].cast(COUNTS_SCHEMA.field(n).type) if n in ("place", "quest") else arrays[n]
                       for n in COUNTS_SCHEMA.names], schema=COUNTS_SCHEMA)
    n = len(head["parts"])
    places = pa.table({"place": parts, "within": pa.nulls(n, pa.string()), "kind": pa.array(["world"] * n),
                       **{c: pa.nulls(n, t) for _, c, t in DENOMINATORS},
                       "json_int": pa.nulls(n, pa.list_(pa.string())), "has_parts": pa.nulls(n, pa.bool_()),
                       "has_aged": pa.nulls(n, pa.bool_())}, schema=PLACES_SCHEMA)
    run = {k: v for k, v in head.items() if k != "parts"}
    run["gate"], run["day"] = gate, day
    return counts, places, run


def world_arrays(counts: pa.Table, places: pa.Table, run: dict) -> tuple[dict, np.ndarray, np.ndarray, np.ndarray]:
    """(counts.json's content, part, quest, m) as the world wrote them"""
    parts = places.column("place").to_pylist()
    head = {k: v for k, v in run.items() if k not in ("gate", "day")}
    head["parts"] = parts
    pi = pa.compute.index_in(counts.column("place"), pa.array(parts)).to_numpy().astype(np.uint32)
    qi = pa.compute.index_in(counts.column("quest"), pa.array(run["quests"])).to_numpy().astype(np.uint16)
    m = np.stack([counts.column(_snake(x)).to_numpy() for x in run["measures"]], axis=1).astype(np.int64)
    return head, pi, qi, m


def _json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def world_gate(world: Path, day: str) -> dict | None:
    return _json(world / "days" / day / "gate.json") or _json(world / "counts" / day / "gate1101.json")


def world(world_dir: Path = WORLD, facts: Path = FACTS, force: bool = False) -> int:
    days, _ = archive_backup.world_files(world_dir)
    done = 0
    for day in days:
        cf, pf = day_files(facts, "world", day)
        src = world_dir / "counts" / day
        if not force and cf.exists() and pf.exists() and \
                min(cf.stat().st_mtime, pf.stat().st_mtime) >= (src / "counts.npz").stat().st_mtime:
            continue
        t = time.time()
        counts, places, run = world_tables(src, world_gate(world_dir, day), _json(world_dir / "days" / day / "day.json"))
        _write(places, pf, run)
        _write(counts, cf, run)
        done += 1
        log(f"world {day}: {counts.num_rows:,} rows, {places.num_rows:,} places, "
            f"{cf.stat().st_size / 1e6:.0f} MB in {time.time() - t:.0f} s")
    log(f"world: {done} day(s) written of {len(days)} gated")
    return done


# --- the proof ---------------------------------------------------------------------------------------------------

def verify(archive: Path = ARCHIVE, facts: Path = FACTS, world_dir: Path = WORLD, source: str | None = None,
           sample: int | None = None) -> int:
    """How many days differ from what they were written from, or have no facts."""
    bad = checked = 0
    todo = [] if source == "world" else region_snapshots(archive, source)
    if sample is not None and len(todo) > sample:
        todo = sorted(random.Random(0).sample(todo, sample))
    for src, day, f in todo:
        cf, pf = day_files(facts, src, day)
        if not cf.exists() or not pf.exists():
            log(f"{src} {day}: no facts")
            bad += 1
            continue
        snap = json.loads(f.read_text(encoding="utf-8"))
        back = snapshot_from(pq.read_table(cf), pq.read_table(pf), read_run(cf))
        checked += 1
        if json.dumps(back, ensure_ascii=False) != json.dumps(snap, ensure_ascii=False):   # order too
            log(f"{src} {day}: the facts do not give the snapshot back")
            bad += 1
    if source in (None, "world") and world_dir.is_dir():
        days, _ = archive_backup.world_files(world_dir)
        if sample is not None and len(days) > sample:
            days = sorted(random.Random(0).sample(days, sample))
        for day in days:
            cf, pf = day_files(facts, "world", day)
            if not cf.exists() or not pf.exists():
                log(f"world {day}: no facts")
                bad += 1
                continue
            src = world_dir / "counts" / day
            head, pi, qi, m = world_arrays(pq.read_table(cf), pq.read_table(pf), read_run(cf))
            z = np.load(src / "counts.npz")
            checked += 1
            same = (head == json.loads((src / "counts.json").read_text(encoding="utf-8"))
                    and np.array_equal(pi, z["part"]) and np.array_equal(qi, z["quest"]) and np.array_equal(m, z["m"]))
            if not same:
                log(f"world {day}: the facts do not give the counts back")
                bad += 1
    log(f"verify: {checked} day(s) rebuilt from their facts, {bad} different or missing")
    return bad


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cities")
    c.add_argument("--region")
    w = sub.add_parser("world")
    v = sub.add_parser("verify")
    v.add_argument("--source", help="a region id or world; default: everything")
    v.add_argument("--sample", type=int, help="this many days of each kind, chosen the same way every time")
    for x in (c, w, v):
        x.add_argument("--facts", type=Path, default=FACTS)
    for x in (c, w):
        x.add_argument("--force", action="store_true", help="write again what is already there")
    for x in (c, v):
        x.add_argument("--archive", type=Path, default=ARCHIVE)
    for x in (w, v):
        x.add_argument("--world", type=Path, default=WORLD)
    a = p.parse_args()
    try:
        if a.cmd == "cities":
            cities(a.archive, a.facts, a.region, a.force)
        elif a.cmd == "world":
            world(a.world, a.facts, a.force)
        else:
            return 1 if verify(a.archive, a.facts, a.world, a.source, a.sample) else 0
        return 0
    except RuntimeError as e:
        log(f"FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
