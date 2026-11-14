"""The world's stream state (DESIGN.md, "The world state store"): the world seed's own files, one per plan.json file,
each sorted by (key, quest, kind) so a day's touched keys are found with searchsorted, and a manifest of each
file's rect, rows and key range.

    python tools/stream/world_state.py sort WORLD_DIR [--workers 4]
        sort every files/<f>/state.bin in place (atomically, a file at a time; a sorted file is skipped) and write
        WORLD_DIR/world-state.json, plus world-state-shared.npy: the keys found in more than one file
    python tools/stream/world_state.py find WORLD_DIR KEYS.npy
        how many of these keys each file holds, and the time it took
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REC = np.dtype([("key", "<i8"), ("lat", "<i4"), ("lon", "<i4"), ("quest", "<u2"), ("flags", "u1"), ("kind", "u1"), ("due", "<i4")])
ORDER = ["key", "quest", "kind"]


def is_sorted(r: np.ndarray) -> bool:
    """sorted by (key, quest, kind): key never falls, and within a key the (quest, kind) pair never falls"""
    k = r["key"]
    dk = np.diff(k)
    if (dk < 0).any():
        return False
    same = dk == 0
    qk = r["quest"].astype(np.int32) * 256 + r["kind"]
    return not (same & (np.diff(qk) < 0)).any()


def sort_file(p: Path) -> dict:
    t = time.time()
    r = np.fromfile(p, REC)
    if len(r) and not is_sorted(r):
        r = np.sort(r, order=ORDER)
        tmp = p.with_suffix(".bin.sorting")
        r.tofile(tmp)
        os.replace(tmp, p)
        state = "sorted"
    else:
        state = "already sorted"
    k = r["key"]
    keys = np.unique(k)  # k is sorted: unique is a linear pass
    np.save(p.with_name("state-keys.npy"), keys)
    return {"id": p.parent.name, "rows": int(len(r)), "keys": int(len(keys)),
            "minKey": int(k[0]) if len(k) else None, "maxKey": int(k[-1]) if len(k) else None,
            "state": state, "seconds": round(time.time() - t, 1)}


def files_of(w: Path) -> list[dict]:
    return json.loads((w / "plan.json").read_text(encoding="utf-8"))["files"]


def sort_all(w: Path, workers: int):
    t = time.time()
    plan = {f["id"]: f for f in files_of(w)}
    paths = [w / "files" / i / "state.bin" for i in plan]
    missing = [p for p in paths if not p.exists()]
    if missing:
        sys.exit(f"{len(missing)} files have no state.bin, e.g. {missing[0]}")
    out = []
    with ProcessPoolExecutor(workers) as ex:
        for n, m in enumerate(ex.map(sort_file, paths), 1):
            out.append(m)
            print(f"[{time.time() - t:6.0f} s] {n}/{len(paths)} {m['id']}: {m['rows']:,} rows, {m['keys']:,} keys, "
                  f"{m['state']} in {m['seconds']} s", flush=True)
    allk = np.concatenate([np.load(w / "files" / m["id"] / "state-keys.npy") for m in out])
    allk.sort()
    shared = np.unique(allk[1:][allk[1:] == allk[:-1]])
    np.save(w / "world-state-shared.npy", shared)
    manifest = {"record": "key i64, lat i32, lon i32, quest u16, flags u8, kind u8, due i32",
                "sortedBy": ORDER, "rows": sum(m["rows"] for m in out), "keys": int(len(allk)),
                "sharedKeys": int(len(shared)),
                "files": [{**m, "rect": plan[m["id"]]["rect"]} for m in out]}
    for m in manifest["files"]:
        m.pop("state"), m.pop("seconds")
    (w / "world-state.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"world state: {manifest['rows']:,} rows, {len(out)} files, {len(shared):,} keys in more than one file; "
          f"{time.time() - t:.0f} s", flush=True)


def find(w: Path, keys_path: Path):
    keys = np.unique(np.load(keys_path))
    t = time.time()
    hits = 0
    for f in json.loads((w / "world-state.json").read_text(encoding="utf-8"))["files"]:
        k = np.load(w / "files" / f["id"] / "state-keys.npy", mmap_mode="r")
        i = np.searchsorted(k, keys)
        hits += int((k[np.minimum(i, len(k) - 1)] == keys).sum()) if len(k) else 0
    print(f"{len(keys):,} keys: {hits:,} found in the files' key lists in {time.time() - t:.1f} s")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sort")
    s.add_argument("world", type=Path)
    s.add_argument("--workers", type=int, default=4)
    f = sub.add_parser("find")
    f.add_argument("world", type=Path)
    f.add_argument("keys", type=Path)
    a = ap.parse_args()
    if a.cmd == "sort":
        sort_all(a.world, a.workers)
    else:
        find(a.world, a.keys)


if __name__ == "__main__":
    main()
