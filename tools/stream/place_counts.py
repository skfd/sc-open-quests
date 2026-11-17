"""Counts per place from the world state at a clock (DESIGN.md, "Release 1: the world day", step 5).

Rows are placesets.WREC (the engine's --dump-state record plus its world place set). A row counts at clock T, as the
engine's snapshot would count it had it run at T:

- never if HIDDEN (an open note at the row's position hides it; the engine counts it nowhere);
- kind MATCH: in each setting whose bit the engine set (M_NOW, M_05, M_2), and in that setting's aged-only count if
  its aged bit is set (M_AGED, M_AGED_05, M_AGED_2): exactly Counts.add;
- kind DUE: in the setting the row is dated for (flags M_NOW, M_05 or M_2; no setting bit, the dumps from before the
  0.5 and 2 dates, is the default) once `due` <= T, and then always aged-only (the clock alone opened it).

At T = the dump's asOf no DUE row is open (dates are whole days after asOf), so the counts are the engine's own.
The measures, per (place, quest):

    open nodes ways relations agedOnly open05 aged05 open2 aged2

`open` is nodes + ways + relations: the note quest is not in the state (its counts come from the notes layer, the
`extra` hook). `open05`..`aged2` are the raw bits: the engine sets M_05 and M_2 only for a quest that uses age, so for
any other quest they are 0 here, and the snapshot (which writes them only for those quests) means "same as open".

A place is a part id of the world's place-sets.json (the counted places, and each engine city as `city:<id>`), so a
cell's totals and a neighbourhood's come out of the same sum. Per file: one pass over its rows, a unique over
(set, quest) codes and a bincount per measure; then the files' (set, quest) sums added; then each set expanded to its
parts (sets are few, a few per place). Output, `write()`: counts.npz with `part` (u32, index into the place-sets
table's parts), `quest` (u16, index into `quests`) and `m` (int64, one column per measure), and counts.json with the
clock, the measures, the quests and the parts list, so the pair stands alone.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

MEASURES = ["open", "nodes", "ways", "relations", "agedOnly", "open05", "aged05", "open2", "aged2"]
M_NOW, M_AGED, M_05, M_AGED_05, M_2, M_AGED_2 = 1, 2, 4, 8, 16, 32
HIDDEN, MATCH, DUE = 64, 0, 1


def masks(rows: np.ndarray, clock_min: int) -> list[np.ndarray]:
    """one boolean array per measure, in MEASURES order"""
    fl = rows["flags"].astype(np.int32)
    vis = fl & HIDDEN == 0
    match = vis & (rows["kind"] == MATCH)
    due = vis & (rows["kind"] == DUE) & (rows["due"] <= clock_min)
    sb = fl & 63
    d_now = due & ((sb == 0) | (sb & M_NOW > 0))
    d_05 = due & (sb & M_05 > 0)
    d_2 = due & (sb & M_2 > 0)
    open_ = (match & (fl & M_NOW > 0)) | d_now
    typ = rows["key"] & 3
    return [open_, open_ & (typ == 0), open_ & (typ == 1), open_ & (typ == 2),
            (match & (fl & M_AGED > 0)) | d_now,
            (match & (fl & M_05 > 0)) | d_05, (match & (fl & M_AGED_05 > 0)) | d_05,
            (match & (fl & M_2 > 0)) | d_2, (match & (fl & M_AGED_2 > 0)) | d_2]


def by_set(rows: np.ndarray, clock_min: int, n_quests: int) -> tuple[np.ndarray, np.ndarray]:
    """(codes, sums): code = place set * n_quests + quest for every pair with a row counted in some measure, and
    their sums, one column per measure"""
    ms = masks(rows, clock_min)
    anym = np.logical_or.reduce(ms)
    code = rows["place"][anym].astype(np.int64) * n_quests + rows["quest"][anym]
    codes, inv = np.unique(code, return_inverse=True)
    sums = np.zeros((len(codes), len(MEASURES)), np.int64)
    for j, m in enumerate(ms):
        sums[:, j] = np.bincount(inv, weights=m[anym], minlength=len(codes)).astype(np.int64)
    return codes, sums


def add_up(parts_list: list[tuple[np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray]:
    """several (codes, sums) added into one"""
    parts_list = [p for p in parts_list if len(p[0])]
    if not parts_list:
        return np.zeros(0, np.int64), np.zeros((0, len(MEASURES)), np.int64)
    codes = np.concatenate([c for c, _ in parts_list])
    sums = np.concatenate([s for _, s in parts_list])
    # unique then np.add.at: measured faster than a stable sort and reduceat (25 s against 82 s, 40M codes)
    u, inv = np.unique(codes, return_inverse=True)
    out = np.zeros((len(u), sums.shape[1]), np.int64)
    np.add.at(out, inv, sums)
    return u, out


def expand(codes: np.ndarray, sums: np.ndarray, sets: list[tuple[int, ...]], n_quests: int):
    """(set, quest) sums to (part, quest) sums: each set's sums added to every part in it"""
    lens = np.array([len(s) for s in sets], np.int64)
    offs = np.zeros(len(sets) + 1, np.int64)
    offs[1:] = np.cumsum(lens)
    members = np.fromiter((p for s in sets for p in s), np.int64, int(offs[-1]))
    st, q = codes // n_quests, codes % n_quests
    reps = lens[st]
    idx = np.repeat(offs[st], reps) + (np.arange(int(reps.sum())) - np.repeat(np.cumsum(reps) - reps, reps))
    part = members[idx]
    pcode = part * n_quests + np.repeat(q, reps)
    return add_up([(pcode, np.repeat(sums, reps, axis=0))])


def count_files(paths: list[Path], dtype, clock_min: int, sets: list[tuple[int, ...]], n_quests: int,
                extra: list[tuple[int, int, np.ndarray]] | None = None):
    """the world's counts per (part, quest) from its files at the clock; `extra`: (part index, quest index, sums)
    added after the expansion (the notes layer's note quests, counted per place by itself)"""
    per = []
    for p in paths:
        rows = np.fromfile(p, dtype)
        per.append(by_set(rows, clock_min, n_quests))
    codes, sums = expand(*add_up(per), sets, n_quests)
    if extra:
        ec = np.array([pi * n_quests + qi for pi, qi, _ in extra], np.int64)
        es = np.array([s for _, _, s in extra], np.int64).reshape(-1, len(MEASURES))
        codes, sums = add_up([(codes, sums), (ec, es)])
    return codes, sums


def write(out: Path, codes: np.ndarray, sums: np.ndarray, n_quests: int, clock: str, quests: list[str], parts: list[str]):
    out.mkdir(parents=True, exist_ok=True)
    np.savez(out / "counts.npz", part=(codes // n_quests).astype(np.uint32), quest=(codes % n_quests).astype(np.uint16), m=sums)
    (out / "counts.json").write_text(json.dumps({"clock": clock, "measures": MEASURES, "quests": quests, "parts": parts}),
                                     encoding="utf-8")


def as_dict(codes: np.ndarray, sums: np.ndarray, n_quests: int, parts: list[str], quests: list[str]) -> dict:
    """{part id: {quest: {measure: n}}} with zero measures left out: for checks and small worlds, not the planet"""
    out: dict = {}
    for c, row in zip(codes.tolist(), sums.tolist()):
        d = {m: v for m, v in zip(MEASURES, row) if v}
        if d:
            out.setdefault(parts[c // n_quests], {})[quests[c % n_quests]] = d
    return out
