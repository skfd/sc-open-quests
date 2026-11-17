"""The world state's rows with their places (DESIGN.md, "Release 1: the world day", step 5).

An engine run with parts and --dump-state writes `state.bin` (24-byte records, stream.REC), `state.bin.places` (a u32
per record, aligned: the run's own place-set number) and `state.bin.places.json` (the run's sets as indices into its
`parts`, the part ids). The world state keeps one table of place sets for the whole world, append-only, so a row's
set number means the same in every file and every day:

    WORLD/place-sets.json   {"parts": [part id, ...], "sets": [[part index, ...], ...]}   set 0 is no place

and its rows as WREC: the engine's record plus `place`, the world set number. `ingest(dump)` reads an engine dump into
WREC rows with world numbers, interning any set the table lacks; `PlaceSets.save()` writes the table back (atomically).
Sets are sorted, distinct part indices; two runs that found the same parts for a position give the same number.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

REC = np.dtype([("key", "<i8"), ("lat", "<i4"), ("lon", "<i4"), ("quest", "<u2"), ("flags", "u1"), ("kind", "u1"), ("due", "<i4")])
WREC = np.dtype(REC.descr + [("place", "<u4")])


class PlaceSets:
    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.exists():
            d = json.loads(self.path.read_text(encoding="utf-8"))
            self.parts: list[str] = d["parts"]
            self.sets: list[tuple[int, ...]] = [tuple(s) for s in d["sets"]]
        else:
            self.parts, self.sets = [], [()]
        assert self.sets[0] == (), "set 0 must be the empty set"
        self.part_index = {p: i for i, p in enumerate(self.parts)}
        self.set_index = {s: i for i, s in enumerate(self.sets)}
        self.dirty = False

    def part(self, pid: str) -> int:
        i = self.part_index.get(pid)
        if i is None:
            i = self.part_index[pid] = len(self.parts)
            self.parts.append(pid)
            self.dirty = True
        return i

    def intern(self, part_ids) -> int:
        """the world number of the set of these part ids (any order, repeats allowed)"""
        key = tuple(sorted({self.part(p) for p in part_ids}))
        i = self.set_index.get(key)
        if i is None:
            i = self.set_index[key] = len(self.sets)
            self.sets.append(key)
            self.dirty = True
        return i

    def remap(self, run_sets: dict) -> np.ndarray:
        """a run's places.json as a lookup array: run set number -> world set number"""
        parts = run_sets["parts"]
        return np.array([self.intern(parts[p] for p in s) for s in run_sets["sets"]], dtype=np.uint32)

    def ids_of(self, world_set: int) -> list[str]:
        return [self.parts[i] for i in self.sets[world_set]]

    def save(self):
        if not self.dirty and self.path.exists():
            return
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"parts": self.parts, "sets": [list(s) for s in self.sets]}), encoding="utf-8")
        os.replace(tmp, self.path)
        self.dirty = False


def ingest(dump: Path, sets: PlaceSets) -> np.ndarray:
    """an engine dump (state.bin and, if the run had parts, its .places files) as WREC rows with world set numbers;
    a run without parts gives every row set 0"""
    rows = np.fromfile(dump, dtype=REC)
    out = np.zeros(len(rows), dtype=WREC)
    for name in REC.names:
        out[name] = rows[name]
    pf, pj = Path(str(dump) + ".places"), Path(str(dump) + ".places.json")
    if pf.exists():
        local = np.fromfile(pf, dtype="<u4")
        assert len(local) == len(rows), f"{pf}: {len(local)} place sets for {len(rows)} records"
        out["place"] = sets.remap(json.loads(pj.read_text(encoding="utf-8")))[local]
    return out
