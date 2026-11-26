"""Compare the world's counts with the daily run's city counts, day by day and quest by quest.

For each of the site's cities (config via docs/data/cities.json) and each published snapshot date D in a range,
the city's snapshot (data/archive/<region>/snapshots/<D>.json, as of about D 21:21Z) is held against the world's
counts (W/counts/<day>/counts.npz) for two parts:

- `osm-<city>`: the world's count inside the city's own OSM outline, the like-for-like check;
- the city's name-layer place (cities.json `place`, an Overture boundary): what the world pages would show.

Each against world day D (clock D 00:00Z, ~21 h before the snapshot) and D+1 (~2.6 h after it).
Measure: `open` (or `agedOnly`) at the default resurvey setting. Read-only: the .npz files are stored uncompressed and are
memory-mapped, so only the 147 cities' rows are paged in.

    python tools/world_compare.py --from 2026-11-02 --to 2026-11-06 --out .scratch/world-compare [--measure agedOnly]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / json.loads((ROOT / "data/world.json").read_text(encoding="utf-8"))["world"]  # the world folder: data/world.json says which (a reseed flips it there)


def npz_member(path: Path, name: str, mmap: bool) -> np.ndarray:
    """an uncompressed .npz member as an array (memory-mapped when asked)"""
    with zipfile.ZipFile(path) as z:
        info = z.getinfo(name)
        if info.compress_type != 0:
            assert not mmap, f"{path}:{name} is compressed"
            with z.open(name) as f:
                return np.lib.format.read_array(f)
        with z.open(name) as f:
            version = np.lib.format.read_magic(f)
            shape, fortran, dtype = (np.lib.format.read_array_header_1_0(f) if version == (1, 0)
                                     else np.lib.format.read_array_header_2_0(f))
            header = f.tell()
    with open(path, "rb") as fh:
        fh.seek(info.header_offset)
        local = fh.read(30)
        start = info.header_offset + 30 + int.from_bytes(local[26:28], "little") + int.from_bytes(local[28:30], "little")
    order = "F" if fortran else "C"
    if mmap:
        return np.memmap(path, dtype=dtype, mode="r", offset=start + header, shape=shape, order=order)
    with open(path, "rb") as fh:
        fh.seek(start + header)
        return np.fromfile(fh, dtype=dtype, count=int(np.prod(shape))).reshape(shape, order=order)


def m_rows(path: Path, rows: np.ndarray, col: int) -> np.ndarray:
    """column col of m.npy at rows (ascending): memory-mapped when stored, else streamed in chunks"""
    with zipfile.ZipFile(path) as z:
        if z.getinfo("m.npy").compress_type == 0:
            m = npz_member(path, "m.npy", mmap=True)
            return np.asarray(m[rows, col])
        with z.open("m.npy") as f:
            version = np.lib.format.read_magic(f)
            shape, fortran, dtype = (np.lib.format.read_array_header_1_0(f) if version == (1, 0)
                                     else np.lib.format.read_array_header_2_0(f))
            assert not fortran and len(shape) == 2
            width = shape[1]
            out = np.empty(len(rows), dtype=dtype)
            chunk, at, k = 1 << 20, 0, 0
            while at < shape[0] and k < len(rows):
                n = min(chunk, shape[0] - at)
                buf = np.frombuffer(f.read(n * width * dtype.itemsize), dtype=dtype).reshape(n, width)
                j = np.searchsorted(rows, at + n)
                out[k:j] = buf[rows[k:j] - at, col]
                k, at = j, at + n
            return out


def world_day(day: str, want: dict[str, str], measure: str = "open") -> dict[str, dict[str, int]]:
    """{key: {quest: measure}} for the parts named in want ({part id: key})"""
    d = W / "counts" / day
    meta = json.loads((d / "counts.json").read_text(encoding="utf-8"))
    pidx = {p: i for i, p in enumerate(meta["parts"]) if p in want}
    oi = meta["measures"].index(measure)
    part = npz_member(d / "counts.npz", "part.npy", mmap=False)
    rows = np.flatnonzero(np.isin(part, np.fromiter(pidx.values(), dtype=part.dtype)))
    partv = part[rows]
    del part
    quest = npz_member(d / "counts.npz", "quest.npy", mmap=False)[rows]
    vals = m_rows(d / "counts.npz", rows, oi)
    part_of = {i: want[p] for p, i in pidx.items()}
    out: dict[str, dict[str, int]] = {k: {} for k in want.values()}
    for p, q, v in zip(partv.tolist(), quest.tolist(), vals.tolist()):
        if v:
            out[part_of[p]][meta["quests"][q]] = int(v)
    return out


def aligned_day(asof: str) -> str:
    """the world day whose clock (00:00Z) is nearest the snapshot's asOf"""
    t = dt.datetime.fromisoformat(asof.replace("Z", "+00:00"))
    return str((t + dt.timedelta(hours=12)).date())


def pct(a: float, b: float) -> float | None:
    return None if not b else 100.0 * (a - b) / b


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--from", dest="d0", default="2026-11-02")
    a.add_argument("--to", dest="d1", default="2026-11-06")
    a.add_argument("--out", type=Path, default=ROOT / ".scratch/world-compare")
    a.add_argument("--measure", default="open", choices=["open", "agedOnly"])
    o = a.parse_args()
    o.out.mkdir(parents=True, exist_ok=True)

    cities = json.loads((ROOT / "docs/data/cities.json").read_text(encoding="utf-8"))["cities"]
    region = {c["id"]: c["region"] for c in cities}
    name = {c["id"]: c["name"] for c in cities}
    want = {f"osm-{c['id']}": f"osm:{c['id']}" for c in cities}
    want.update({c["place"]: f"place:{c['id']}" for c in cities if c.get("place")})
    worlddays = sorted(p.name for p in (W / "counts").iterdir() if (p / "counts.npz").is_file())

    d0, d1 = dt.date.fromisoformat(o.d0), dt.date.fromisoformat(o.d1)
    days = [str(d0 + dt.timedelta(n)) for n in range((d1 - d0).days + 1)]
    need = sorted({d for D in days for d in (D, str(dt.date.fromisoformat(D) + dt.timedelta(1))) if d in worlddays})
    world = {}
    for d in need:
        print("world", d, flush=True)
        world[d] = world_day(d, want, o.measure)

    rows = []  # one per (city, snapshot day, world day, part kind)
    for D in days:
        snaps = {}
        for r in sorted(set(region.values())):
            f = ROOT / "data/archive" / r / "snapshots" / f"{D}.json"
            if f.is_file():
                s = json.loads(f.read_text(encoding="utf-8"))
                for cid, c in s["cities"].items():
                    snaps[cid] = (s["asOf"], {q: v.get(o.measure, 0) for q, v in c["quests"].items()})
        for wd in (D, str(dt.date.fromisoformat(D) + dt.timedelta(1))):
            if wd not in world:
                continue
            for cid in sorted(region):
                if cid not in snaps:
                    continue
                asof, cq = snaps[cid]
                for kind in ("osm", "place"):
                    wq = world[wd].get(f"{kind}:{cid}")
                    if wq is None or (kind == "osm" and f"osm-{cid}" not in want):
                        continue
                    if not wq and kind == "place":
                        continue
                    wquests = set(json.loads((W / "counts" / wd / "counts.json").read_text(encoding="utf-8"))["quests"]) \
                        if "_wq" not in world[wd] else world[wd]["_wq"]
                    world[wd]["_wq"] = wquests
                    common = wquests & set(cq)
                    per = {q: (wq.get(q, 0), cq.get(q, 0)) for q in sorted(common) if wq.get(q, 0) or cq.get(q, 0)}
                    wt = sum(v[0] for v in per.values())
                    ct = sum(v[1] for v in per.values())
                    rows.append({"city": cid, "snap": D, "asOf": asof, "world": wd, "kind": kind,
                                 "aligned": wd == aligned_day(asof),
                                 "w": wt, "c": ct, "diff": wt - ct, "pct": pct(wt, ct),
                                 "onlyCity": {q: v for q, v in cq.items() if q not in wquests and v},
                                 "per": per})
    sfx = "" if o.measure == "open" else "-aged"
    (o.out / f"rows{sfx}.json").write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8", newline="\n")
    write_report(o.out / f"report{sfx}.md", rows, name, days, o.measure)


def write_report(path: Path, rows: list, name: dict, days: list, measure: str = "open") -> None:
    def sel(kind, lag):
        return [r for r in rows if r["kind"] == kind and r["aligned"] == bool(lag)]

    L = ["# World vs the daily run's city counts", "",
         f"Snapshots {days[0]} to {days[-1]} (`data/archive/<region>/snapshots/<D>.json`, as of about D 21:21Z) "
         f"against the world's counts (`.scratch/planet/world-1101/counts/<day>/`, clock day 00:00Z), `{measure}` at the "
         "default resurvey setting, over the quests both sides count. Made by `tools/world_compare.py`.", "",
         "- **osm**: the world's `osm-<city>` part, the city's own OSM outline (like for like).",
         "- **place**: the city's name-layer place (`cities.json` `place`, Overture boundary): what a world page shows.",
         "- **aligned**: the world day whose clock is nearest the snapshot's asOf: the same day D for the Europe "
         "snapshots (as of D 00:00Z, the same clock), D+1 for Canada and Germany (as of D ~21:21Z, ~2.6 h before "
         "the world's clock). **off by a day**: the other one of D and D+1, to show what timing alone does.", "",
         "## Summary", "",
         "| part | aligned | rows | cities | median abs % | p90 abs % | max abs % | exact | Σ world | Σ city |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for kind in ("osm", "place"):
        for lag in (0, 1):
            s = sel(kind, lag)
            if not s:
                continue
            ap = sorted(abs(r["pct"]) for r in s if r["pct"] is not None)
            L.append(f"| {kind} | {lag} | {len(s)} | {len({r['city'] for r in s})} | {statistics.median(ap):.3f} | "
                     f"{ap[int(0.9 * (len(ap) - 1))]:.3f} | {ap[-1]:.3f} | {sum(r['diff'] == 0 for r in s)} | "
                     f"{sum(r['w'] for r in s):,} | {sum(r['c'] for r in s):,} |")
    L += [""]

    best = sel("osm", 1)
    L += ["## Per day (osm, aligned)", "", "| snapshot | cities | Σ world | Σ city | diff | % | exact | worst |",
          "|---|---|---|---|---|---|---|---|"]
    for D in days:
        s = [r for r in best if r["snap"] == D]
        if not s:
            L.append(f"| {D} | 0 | | | | | | no aligned world day |")
            continue
        w, c = sum(r["w"] for r in s), sum(r["c"] for r in s)
        worst = max(s, key=lambda r: abs(r["pct"] or 0))
        L.append(f"| {D} | {len(s)} | {w:,} | {c:,} | {w - c:+,} | {pct(w, c):+.4f} | {sum(r['diff'] == 0 for r in s)} | "
                 f"{name[worst['city']]} {worst['pct']:+.3f}% |")
    L += [""]

    # per city table: osm lag1 and lag0, place lag1, averaged over days
    L += ["## Per city (mean over the days)", "",
          f"| city | city {measure} | osm aligned % | osm off by a day % | place aligned % | biggest quest gaps (osm aligned, world−city, summed over days) |",
          "|---|---|---|---|---|---|"]
    by = {}
    for r in rows:
        lag = int(r["aligned"])
        by.setdefault((r["city"], r["kind"], lag), []).append(r)
    for cid in sorted({r["city"] for r in rows}, key=lambda c: name[c]):
        def m(kind, lag):
            s = by.get((cid, kind, lag), [])
            v = [r["pct"] for r in s if r["pct"] is not None]
            return f"{statistics.mean(v):+.3f}" if v else "-"
        s1 = by.get((cid, "osm", 1), [])
        gaps = {}
        for r in s1:
            for q, (w, c) in r["per"].items():
                if w != c:
                    gaps[q] = gaps.get(q, 0) + w - c
        top = sorted(gaps.items(), key=lambda kv: -abs(kv[1]))[:3]
        cnt = statistics.mean(r["c"] for r in s1) if s1 else 0
        L.append(f"| {name[cid]} ({cid}) | {cnt:,.0f} | {m('osm', 1)} | {m('osm', 0)} | {m('place', 1)} | "
                 + ", ".join(f"{q} {v:+}" for q, v in top) + " |")
    L += [""]

    # quests across all cities (osm lag 1)
    qa = {}
    for r in best:
        for q, (w, c) in r["per"].items():
            t = qa.setdefault(q, [0, 0])
            t[0] += w
            t[1] += c
    L += ["## Per quest, all cities and days (osm, aligned), largest gaps", "", "| quest | Σ world | Σ city | diff | % |",
          "|---|---|---|---|---|"]
    for q, (w, c) in sorted(qa.items(), key=lambda kv: -abs(kv[1][0] - kv[1][1]))[:25]:
        L.append(f"| {q} | {w:,} | {c:,} | {w - c:+,} | {pct(w, c) if c else 0:+.3f} |")
    only = {}
    for r in best:
        for q, v in r["onlyCity"].items():
            only[q] = only.get(q, 0) + v
    L += ["", "Quests only the city snapshots count (open, summed over cities and days): "
          + (", ".join(f"{q} {v:,}" for q, v in sorted(only.items())) or "none") + ".", ""]
    intro = path.parent / ("findings.md" if measure == "open" else f"findings-{measure}.md")  # the hand-written verdict, kept on top across reruns
    head = intro.read_text(encoding="utf-8") if intro.is_file() else ""
    path.write_text(head + "\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
