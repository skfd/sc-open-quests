"""The engine on a read of the planet store against the engine on the Europe clip of the same instant, city for city
and row for row (HANDOFF, "Release goals", plan step 1: the first check of counting from the store).

  python tools/stream/storecheck_cities.py --out .scratch/storecheck/D [--regions europe-west,...] [--ring 2000]

For each Europe region: its cities (config/cities.json, as run.py gives them to the engine) counted (a) on
~/Code/.osm-data/europe/europe-<D>.osm.pbf, D the store's newest day, and (b) on `tilestore read` of the store with
the same cities, padded by --ring, stamped D 00:00Z. Same quests file, same notes clip, `--dump-state` on both.
Then the snapshots' `cities` are compared field by field, and the state rows as sets; differing rows are listed by
element so each can be traced. The store is held while it is read (store_lock); the clip runs need no hold.
Expected: nodes and ways equal; a relation or a row at the edge of the read may differ (the store keeps every kept
relation's member ways whole; the clip's extract completes only multipolygons) and is to be traced, not waved off."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools/stream"))
import run  # noqa: E402
import store_lock  # noqa: E402
from stream import REC  # noqa: E402

EXE = ROOT / "tilestore/target/release/tilestore.exe"
EUROPE = Path.home() / "Code/.osm-data/europe"
REGIONS = ["europe-west", "europe-central", "europe-east", "europe-msk"]
KIND = {0: "n", 1: "w", 2: "r"}


def engine(pbf: Path, cities: Path, out: Path, notes: Path, tz: str, quests: Path, today: str) -> float:
    """the clock given, not taken from the file's header: an oracle cut from a history file keeps the history's"""
    out.mkdir(parents=True, exist_ok=True)
    cmd = [str(run.ENGINE_BAT), "count", "--pbf", str(pbf), "--quests", str(quests), "--cities", str(cities),
           "--out", str(out / "out"), "--notes", str(notes), "--dump-state", str(out / "state.bin"), "--today", today]
    t = time.time()
    with open(out / "log.txt", "w", encoding="utf-8") as f:
        subprocess.run(cmd, cwd=ROOT, env=run.engine_env(tz, heap=True), stdout=f, stderr=subprocess.STDOUT, check=True)
    return time.time() - t


def snap_cities(d: Path) -> dict:
    snaps = sorted((d / "out" / "snapshots").glob("*.json"))
    assert len(snaps) == 1, f"{d}: {len(snaps)} snapshots"
    return json.loads(snaps[0].read_text(encoding="utf-8"))["cities"]


def diff(a, b, path="") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k in ("runSeconds", "timings"):
                continue
            out += diff(a.get(k), b.get(k), f"{path}.{k}")
        return out
    return [] if a == b else [f"{path}: clip {a!r}, store {b!r}"]


def rows(p: Path) -> np.ndarray:
    x = np.fromfile(p, dtype=REC)
    x.sort(order=["key", "quest", "kind", "lat", "lon", "flags", "due"])
    return x


def compare(clip: Path, store: Path) -> int:
    quest_names = json.loads((clip / "state.bin.json").read_text(encoding="utf-8"))["quests"]
    assert quest_names == json.loads((store / "state.bin.json").read_text(encoding="utf-8"))["quests"], "quest numbering"
    bad = diff(snap_cities(clip), snap_cities(store))
    for line in bad[:200]:
        print("  snapshot", line)
    if len(bad) > 200:
        print(f"  ... {len(bad) - 200} more")
    a, b = rows(clip / "state.bin"), rows(store / "state.bin")
    va, vb = a.view(np.void), b.view(np.void)  # whole records as bytes, for set operations
    only_a = a[~np.isin(va, vb)]
    only_b = b[~np.isin(vb, va)]
    print(f"  state rows: clip {len(a):,}, store {len(b):,}; only in clip {len(only_a):,}, only in store {len(only_b):,}")
    for side, xs in (("clip", only_a), ("store", only_b)):
        for r in xs[:40]:
            k = int(r["key"])
            q = quest_names[r["quest"]] if r["quest"] < len(quest_names) else r["quest"]
            print(f"    only in {side}: key {k} quest {q} kind {r['kind']} at {r['lat'] / 1e7:.5f},{r['lon'] / 1e7:.5f}"
                  f" flags {r['flags']} due {r['due']}")
    return len(bad) + len(only_a) + len(only_b)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--regions", default=",".join(REGIONS))
    ap.add_argument("--ring", type=float, default=2000.0)
    ap.add_argument("--store", type=Path, default=store_lock.STORE)
    ap.add_argument("--clip", type=Path, help="the Europe clip of the store's day, when .osm-data keeps none (an oracle "
                    "cut from a history file at that instant); its day is then not checked against a meta file")
    a = ap.parse_args()
    meta = json.loads((a.store / "store.json").read_text())
    day = meta["generations"][-1]["day"]
    clip_pbf = a.clip or EUROPE / f"europe-{day}.osm.pbf"
    assert clip_pbf.exists(), f"no Europe clip of the store's day {day}"
    stamp = f"{day}T00:00:00Z"
    if not a.clip:
        cmeta = json.loads((EUROPE / f"europe-{day}.meta.json").read_text())
        assert cmeta["replication_timestamp"] == stamp, (cmeta["replication_timestamp"], stamp)
    quests = run.newest_quests_file()
    print(f"store day {day} (generation {meta['generations'][-1]['gen']}), clip {clip_pbf.name}, quests {quests.name}")
    total = 0
    for rid in a.regions.split(","):
        region = next(r for r in run.read_json(run.REGIONS_CONFIG)["regions"] if r["id"] == rid)
        cities = run.region_cities(region).relative_to(ROOT)
        notes = run.notes_clip(region)
        d = a.out / rid
        d.mkdir(parents=True, exist_ok=True)
        if not (d / "clip" / "state.bin").exists():
            s = engine(clip_pbf, cities, d / "clip", notes, region["timeZone"], quests.relative_to(ROOT), stamp)
            print(f"{rid}: clip counted in {s:.0f} s", flush=True)
        read_pbf = d / "read.osm.pbf"
        if not read_pbf.exists():
            t = time.time()
            with store_lock.reading(f"storecheck_cities {rid} (read of {day})"):
                assert json.loads((a.store / "store.json").read_text())["generations"][-1]["day"] == day, "the store moved"
                subprocess.run([str(EXE), "read", "--store", str(a.store), "--cities", str(cities), "--base", str(ROOT),
                                "--ring", str(a.ring), "--out", str(read_pbf) + ".part", "--stamp", stamp],
                               cwd=ROOT, check=True)
            Path(str(read_pbf) + ".part").rename(read_pbf)
            print(f"{rid}: read {read_pbf.stat().st_size / 2**20:.0f} MiB in {time.time() - t:.0f} s", flush=True)
        if not (d / "store" / "state.bin").exists():
            s = engine(read_pbf, cities, d / "store", notes, region["timeZone"], quests.relative_to(ROOT), stamp)
            print(f"{rid}: store read counted in {s:.0f} s", flush=True)
        print(f"{rid}:", flush=True)
        n = compare(d / "clip", d / "store")
        total += n
        print(f"{rid}: {'EQUAL' if n == 0 else f'{n} differences'}", flush=True)
    print("storecheck: " + ("all equal" if total == 0 else f"{total} differences to trace"))
    sys.exit(0 if total == 0 else 1)


if __name__ == "__main__":
    main()
