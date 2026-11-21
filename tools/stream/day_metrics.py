"""What a world day's engines did, kept after the day's work is deleted: W/days/<D>/engines.json.

Why: on 2026-11-21 tier 2's engines turned out to spend 96 to 100% of a slow run making the same relations again
for every rectangle (HANDOFF, "Storage redesign", (c)). The engines had logged it all along, a line per rectangle,
but `engine.log` went with the day's work, the batch engine's speed-up rounds measured a file of 18 large cells
where a relation is made 18 times, and the loop's log named no engine. So: each engine's numbers are read off its
log before the work goes, and anything lopsided is said in the loop's log (a line starting `watch:`).

    python tools/stream/day_metrics.py harvest <work dir> [--out engines.json]   read a day's work as it stands
    python tools/stream/day_metrics.py report [--world W]                         the kept days, one line each

Reads text only; nothing here can stop a day (the loop calls `write` inside a try).
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / ".scratch" / "planet" / "world-1101"
NAME = "engines.json"
SCHEMA = 1
AREA = re.compile(r"^area: (\S+)\s+([\d.]+) s\s+\(map data ([\d.]+) s: (\d+) nodes, (\d+) ways, (\d+) relations\)")
PASS = re.compile(r"^pass ([\d.]+) s, total ([\d.]+) s; peak heap \(sum of pool peaks\) (\d+) MB")
STEP = re.compile(r"^(relation member scan|nodes|ways|relations)\s+([\d.]+) s")
CITIES = re.compile(r"(\d+) cities \((\d+) parts")
STARTUP = re.compile(r"^startup: registry and cities ([\d.]+) s, parts ([\d.]+) s.*engine and its indexes ([\d.]+) s")
# an engine is worth a look when it is this many times the phase's median and at least this long
WATCH_TIMES, WATCH_SECONDS = 10, 120
# or when one step holds this share of an engine that long
WATCH_SHARE = 0.5


def engine(log: Path) -> dict | None:
    """one engine.log as numbers; None for a run that did not end (no `pass` line)"""
    e: dict = {"main": {}, "areas": 0, "area s": 0.0, "map data s": 0.0, "with relations": 0,
               "map data s with relations": 0.0}
    slow: list[tuple[float, str, int, int, int]] = []
    done = False
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        m = AREA.match(line)
        if m:
            s, md, rel = float(m[2]), float(m[3]), int(m[6])
            e["areas"] += 1
            e["area s"] += s
            e["map data s"] += md
            if rel:
                e["with relations"] += 1
                e["map data s with relations"] += md
            slow.append((s, m[1], int(m[4]), int(m[5]), rel))
            continue
        m = PASS.match(line)
        if m:
            e["pass s"], e["total s"], e["heap MB"] = float(m[1]), float(m[2]), int(m[3])
            done = True
            continue
        m = STEP.match(line)
        if m:
            e["main"][m[1]] = float(m[2])
            continue
        m = STARTUP.match(line)
        if m:
            e["startup s"] = round(float(m[1]) + float(m[2]) + float(m[3]), 1)
            continue
        m = CITIES.search(line) if "cities (" in line and "quests in" in line else None
        if m:
            e["cities"], e["parts"] = int(m[1]), int(m[2])
    if not done:
        return None
    slow.sort(reverse=True)
    e["slowest areas"] = [{"id": i, "s": s, "nodes": n, "ways": w, "relations": r} for s, i, n, w, r in slow[:3]]
    for k in ("area s", "map data s", "map data s with relations"):
        e[k] = round(e[k], 1)
    e["quests s"] = round(e["area s"] - e["map data s"], 1)   # what an area's time is besides its map data
    return e


def phase_of(rel: str) -> str:
    """t2/groups/f31/new -> 't2 new'; t1/f0 -> 't1'; anything else by its first folder"""
    p = rel.split("/")
    if p[0] == "t2" and p[-1] in ("old", "new"):
        return f"t2 {p[-1]}"
    return p[0]


def harvest(work: Path) -> dict:
    engines, unfinished = {}, []
    for log in sorted(work.rglob("engine.log")):
        rel = log.parent.relative_to(work).as_posix()
        e = engine(log)
        if e is None:
            unfinished.append(rel)
        else:
            engines[rel] = e
    phases: dict[str, dict] = {}
    watch: list[str] = []
    for ph in sorted({phase_of(r) for r in engines}):
        es = {r: e for r, e in engines.items() if phase_of(r) == ph}
        secs = sorted(e["total s"] for e in es.values())
        med, total = statistics.median(secs), sum(secs)
        top = sorted(es, key=lambda r: -es[r]["total s"])[:5]
        phases[ph] = {"engines": len(es), "sum s": round(total, 1), "median s": round(med, 1), "max s": secs[-1],
                      "top 5 share": round(sum(es[r]["total s"] for r in top) / total, 3) if total else 0.0,
                      "slowest": top, "max heap MB": max(e["heap MB"] for e in es.values()),
                      "map data s": round(sum(e["map data s"] for e in es.values()), 1),
                      "quests s": round(sum(e["quests s"] for e in es.values()), 1),
                      "main s": round(sum(sum(e["main"].values()) for e in es.values()), 1)}
        for r in top:
            e = es[r]
            if e["total s"] < WATCH_SECONDS:
                continue
            why = []
            if med and e["total s"] >= WATCH_TIMES * med:
                why.append(f"{e['total s'] / med:.0f} times the phase's median ({med:.0f} s)")
            for name, s in (("map data", e["map data s"]), ("the quests' runs", e["quests s"]),
                            ("the main pass", sum(e["main"].values()))):
                if s >= WATCH_SHARE * e["total s"]:
                    why.append(f"{name} {s:.0f} s of it")
            if why and (len(why) > 1 or "times" in why[0]):
                watch.append(f"{r}: {e['total s']:.0f} s, {e['areas']} areas; " + "; ".join(why))
    return {"schema": SCHEMA, "phases": phases, "watch": watch, "unfinished": unfinished, "engines": engines}


def write(world: Path, day: str, work: Path, log=None) -> Path:
    """the day's engines.json beside its day.json; the lopsided engines said in the loop's log"""
    rec = harvest(work)
    rec["day"] = day
    out = world / "days" / day / NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".partial")
    tmp.write_text(json.dumps(rec, separators=(",", ":")), encoding="utf-8", newline="\n")
    tmp.replace(out)
    if log:
        for ph, p in rec["phases"].items():
            log(f"engines, {ph}: {p['engines']} in {p['sum s']:,.0f} s summed (median {p['median s']:.0f} s, longest "
                f"{p['max s']:.0f} s, the five longest {p['top 5 share']:.0%}); map data {p['map data s']:,.0f} s, "
                f"quests {p['quests s']:,.0f} s, main pass {p['main s']:,.0f} s; heap up to {p['max heap MB']:,} MB")
        for w in rec["watch"]:
            log(f"watch: {w}")
    return out


def report(world: Path) -> None:
    rows = []
    for f in sorted((world / "days").glob(f"*/{NAME}")):
        r = json.loads(f.read_text(encoding="utf-8"))
        for ph, p in r["phases"].items():
            rows.append((f.parent.name, ph, p["engines"], p["sum s"], p["median s"], p["max s"], p["top 5 share"],
                         p["map data s"], p["quests s"], p["max heap MB"], len(r["watch"])))
    print(f"{'day':10} {'phase':8} {'engines':>7} {'sum s':>9} {'median':>7} {'longest':>8} {'top 5':>6} "
          f"{'map data':>9} {'quests':>8} {'heap MB':>8} {'watch':>5}")
    for r in rows:
        print(f"{r[0]:10} {r[1]:8} {r[2]:>7} {r[3]:>9,.0f} {r[4]:>7.0f} {r[5]:>8.0f} {r[6]:>6.0%} {r[7]:>9,.0f} "
              f"{r[8]:>8,.0f} {r[9]:>8,} {r[10]:>5}")
    if not rows:
        print(f"no {NAME} under {world / 'days'} yet")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("harvest")
    h.add_argument("work", type=Path)
    h.add_argument("--out", type=Path)
    r = sub.add_parser("report")
    r.add_argument("--world", type=Path, default=WORLD)
    a = p.parse_args()
    if a.cmd == "report":
        report(a.world)
        return 0
    rec = harvest(a.work)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(rec, separators=(",", ":")), encoding="utf-8", newline="\n")
    for ph, ph_rec in rec["phases"].items():
        print(ph, json.dumps({k: v for k, v in ph_rec.items() if k != "slowest"}))
    for w in rec["watch"]:
        print("watch:", w)
    print(f"{len(rec['engines'])} engines read, {len(rec['unfinished'])} not ended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
