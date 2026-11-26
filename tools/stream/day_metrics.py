"""What a world day's engines did, kept after the day's work is deleted: W/days/<D>/engines.json.

Why: on 2026-11-21 tier 2's engines turned out to spend 96 to 100% of a slow run making the same relations again
for every rectangle (HANDOFF, "Storage redesign", (c)). The engines had logged it all along, a line per rectangle,
but `engine.log` went with the day's work, the batch engine's speed-up rounds measured a file of 18 large cells
where a relation is made 18 times, and the loop's log named no engine. So: each engine's numbers are read off its
log before the work goes, and anything lopsided is said in the loop's log (a line starting `watch:`).

And the day's steps, W/days/<D>/steps.json: every step the loop's log times, whatever ran it (the Rust tile store's
update, loc advance, loc check, cut, subcmp, compact, punch; the Python steps of prepare and finish; the gate; the
store's own numbers for the update and the packs), with the day's wall time and what is left of it unaccounted
(waits beside the daily run among it). Read from logs/planet-store.log, so days already run can be written too.

    python tools/stream/day_metrics.py harvest <work dir> [--out engines.json]   read a day's work as it stands
    python tools/stream/day_metrics.py steps [--day D | --all] [--world W] [--log L]   steps.json from the loop's log
    python tools/stream/day_metrics.py report [--world W]                         the kept days: engines, then steps

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
WORLD = ROOT / json.loads((ROOT / "data/world.json").read_text(encoding="utf-8"))["world"]  # the world folder: data/world.json says which (a reseed flips it there)
NAME = "engines.json"
SCHEMA = 1
AREA = re.compile(r"^area: (\S+)\s+([\d.]+) s\s+\(map data ([\d.]+) s: (\d+) nodes, (\d+) ways, (\d+) relations\)")
PASS = re.compile(r"^pass ([\d.]+) s, total ([\d.]+) s; peak heap \(sum of pool peaks\) (\d+) MB")
STEP = re.compile(r"^(relation member scan|nodes|ways|relations)\s+([\d.]+) s")
CITIES = re.compile(r"(\d+) cities \((\d+) parts")
STARTUP = re.compile(r"^startup: registry and cities ([\d.]+) s, parts ([\d.]+) s.*engine and its indexes ([\d.]+) s")
# the engine's own split of what its other lines leave unnamed (engine Timing.kt):
# `timing: <group>: <name> <seconds> s, <name> <seconds> s, ...`
TIMING = re.compile(r"^timing: ([^:]+): (.*)$")
TIMING_ITEM = re.compile(r"([^,]+?) ([\d.]+) s(?:, |$)")
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
        m = TIMING.match(line)
        if m:
            t = e.setdefault("timing", {})
            for name, s in TIMING_ITEM.findall(m[2]):
                key = f"{m[1]}: {name}"
                t[key] = round(t.get(key, 0.0) + float(s), 2)
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


def given(folder: Path) -> dict:
    """the heap the engine was given (engine_room.note_given leaves given.json beside its log): "given MB", and
    "first given MB" when a first run on less failed for memory; {} for a day run before 2026-11-26"""
    try:
        g = json.loads((folder / "given.json").read_text(encoding="utf-8"))
        return {k: int(g[k]) for k in ("given MB", "first given MB") if k in g}
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def harvest(work: Path) -> dict:
    engines, unfinished = {}, []
    for log in sorted(work.rglob("engine.log")):
        rel = log.parent.relative_to(work).as_posix()
        e = engine(log)
        if e is None:
            unfinished.append(rel)
        else:
            e.update(given(log.parent))
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
    return {"schema": SCHEMA, "phases": phases, "watch": watch, "unfinished": unfinished, "engines": engines,
            "reads": store_reads(work)}


def store_reads(work: Path) -> dict:
    """the tile store's reads of the day's map data (`tilestore read` leaves <pbf>.json beside each file it writes,
    and the json stays when the engine has dropped the pbf): per tier 2 date, the seconds of its steps summed, the
    bytes, the most memory one read took, and the three longest"""
    out: dict[str, dict] = {}
    for f in sorted(work.rglob("*.osm.pbf.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(r, dict) or "seconds" not in r:
            continue
        which = f.name.split(".")[0]                      # old / new
        o = out.setdefault(which, {"reads": 0, "seconds": 0.0, "secondsTiles": 0.0, "secondsMerge": 0.0,
                                   "secondsWrite": 0.0, "tiles": 0, "pbfBytes": 0, "peakPrivateGiB": 0.0, "longest": []})
        o["reads"] += 1
        for k in ("seconds", "secondsTiles", "secondsMerge", "secondsWrite"):
            o[k] = round(o[k] + float(r.get(k, 0)), 2)
        o["tiles"] += int(r.get("tiles", 0))
        o["pbfBytes"] += int(r.get("pbfBytes", 0))
        o["peakPrivateGiB"] = max(o["peakPrivateGiB"], float(r.get("peakPrivateGiB", 0)))
        o["longest"].append((float(r["seconds"]), f.parent.relative_to(work).as_posix(), int(r.get("pbfBytes", 0))))
    for o in out.values():
        o["longest"] = [{"group": g, "s": sec, "pbfBytes": b} for sec, g, b in sorted(o["longest"], reverse=True)[:3]]
    return out


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


# --- the day's steps, off the loop's log ---------------------------------------------------------------------------

STEPS = "steps.json"
STAMP = re.compile(r"^\[(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\] (.*)$")
EXIT = re.compile(r"^(.*?): exit (-?\d+) in ([\d.]+) s$")
WORLD_STEP = re.compile(r"^world (snapshot|prepare|finish)(?: \S+)?: ([\d.]+) s(?:; (\{.*\}))?$")
GATE = re.compile(r"^gate: (\S+) counted on \S+ in ([\d.]+) s$")
READ = re.compile(r"^tilestore read: ([\d.]+) s$")
UPDATE = re.compile(r"^update to \S+: (\{.*\})\s*$")
# a part of a step the loop times on its own (`timer: <what> <seconds> s`): inside a step or beside one, so it is
# kept under "timers" and taken off nothing
TIMER = re.compile(r"^timer: (.+?) ([\d.]+) s$")
PACK = re.compile(r"^(pack|rel) (\d+): ([\d.]+) GiB written, ([\d.]+) GiB live \(([\d.]+)% dead\)")
# a step this many times its median over the earlier kept days, and this many seconds over it, is worth a look
STEP_TIMES, STEP_SECONDS = 2.0, 300


def step_name(what: str) -> str:
    """'update 5175' -> 'update'; 'loc check against europe-...' -> 'loc check'; 'cut of europe-...' -> 'cut'"""
    w = re.sub(r" (against|of|generation|\().*$", "", what)
    return re.sub(r" \d+$", "", w).strip()


def _seconds(a: str, b: str) -> float:
    import datetime as dt
    return (dt.datetime.fromisoformat(b) - dt.datetime.fromisoformat(a)).total_seconds()


def day_steps(log_text: str, day: str) -> dict | None:
    """the last run of `day` in the loop's log, as numbers; None when the log has no such day"""
    lines = log_text.splitlines()
    # a day's last attempt begins at its last "diff N on generation G" line; a resume after a stop ("resuming",
    # "the store's checks and compaction, resumed") goes on with the same day and is read with it
    starts = [i for i, l in enumerate(lines) if f"] == day {day}: diff " in l] or              [i for i, l in enumerate(lines) if f"] == day {day}: " in l][:1]
    if not starts:
        return None
    block = lines[starts[-1]:]
    rec: dict = {"schema": SCHEMA, "day": day, "steps": {}, "gate": {}, "reads": {"n": 0, "s": 0.0}, "packs": []}
    first = last = None
    for l in block:
        m = STAMP.match(l)
        body = m[2] if m else l
        if m:
            first = first or m[1]
            last = m[1]
            if body.startswith(f"== day {day} done"):
                rec["ended"] = m[1]
                break
            if body.startswith("== day ") and not body.startswith(f"== day {day}"):
                break                                   # the next day began: this one never said done
            if body.startswith(f"== day {day}: ") and "diff " not in body:
                rec["resumes"] = rec.get("resumes", 0) + 1
        x = EXIT.match(body)
        if x:
            name = step_name(x[1])
            st = rec["steps"].setdefault(name, {"s": 0.0, "runs": 0, "exit": 0})
            st["s"] = round(st["s"] + float(x[3]), 1)
            st["runs"] += 1
            st["exit"] = int(x[2])
            continue
        x = WORLD_STEP.match(body)
        if x:
            rec["steps"][f"world {x[1]}"] = {"s": float(x[2]), "runs": 1, "exit": 0}
            if x[3]:
                try:
                    rec[x[1]] = json.loads(x[3])
                except ValueError:
                    pass
            continue
        x = GATE.match(body)
        if x:
            rec["gate"][x[1]] = float(x[2])
            continue
        x = TIMER.match(body)
        if x:
            tm = rec.setdefault("timers", {})
            tm[x[1]] = round(tm.get(x[1], 0.0) + float(x[2]), 1)
            continue
        x = READ.match(body)
        if x:
            rec["reads"]["n"] += 1
            rec["reads"]["s"] = round(rec["reads"]["s"] + float(x[1]), 1)
            continue
        x = UPDATE.match(body)
        if x:
            try:
                rec["update"] = json.loads(x[1])
            except ValueError:
                pass
            continue
        x = PACK.match(body)
        if x:
            rec["packs"].append({"file": f"{x[1]} {x[2]}", "GiB": float(x[3]), "live GiB": float(x[4]), "dead %": float(x[5])})
    rec["started"] = first
    if first and last:
        rec["wall s"] = _seconds(first, rec.get("ended", last))
        rec["unaccounted s"] = round(rec["wall s"] - sum(v["s"] for v in rec["steps"].values()) - sum(rec["gate"].values()), 1)
    return rec


def flat(rec: dict) -> dict[str, float]:
    """every timed thing of a day by one name: the loop's steps, and finish's own parts under 'finish: '"""
    out = {k: v["s"] for k, v in rec.get("steps", {}).items()}
    out.update({f"finish: {k}": float(v) for k, v in (rec.get("finish") or {}).items()})
    if rec.get("gate"):
        out["gate"] = round(sum(rec["gate"].values()), 1)
    return out


def step_watch(rec: dict, earlier: list[dict]) -> list[str]:
    out = []
    now = flat(rec)
    for name, s in sorted(now.items(), key=lambda kv: -kv[1]):
        before = [f[name] for f in map(flat, earlier) if name in f]
        if len(before) < 3:
            continue
        med = statistics.median(before)
        if s >= STEP_TIMES * med and s - med >= STEP_SECONDS:
            out.append(f"{name}: {s:,.0f} s, {s / med:.1f} times its median over {len(before)} earlier days ({med:,.0f} s)")
    return out


def kept_steps(world: Path, before: str | None = None) -> list[dict]:
    out = []
    for f in sorted((world / "days").glob(f"*/{STEPS}")):
        if before is None or f.parent.name < before:
            out.append(json.loads(f.read_text(encoding="utf-8")))
    return out


def write_steps(world: Path, day: str, log_file: Path, log=None) -> Path | None:
    rec = day_steps(log_file.read_text(encoding="utf-8", errors="replace"), day)
    if rec is None:
        return None
    rec["watch"] = step_watch(rec, kept_steps(world, before=day))
    out = world / "days" / day / STEPS
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".partial")
    tmp.write_text(json.dumps(rec, separators=(",", ":")), encoding="utf-8", newline="\n")
    tmp.replace(out)
    if log:
        top = sorted(flat(rec).items(), key=lambda kv: -kv[1])[:6]
        log(f"steps: the day took {rec.get('wall s', 0):,.0f} s, {rec.get('unaccounted s', 0):,.0f} s of it in no step; "
            + ", ".join(f"{k} {v:,.0f}" for k, v in top))
        for w in rec["watch"]:
            log(f"watch: {w}")
    return out


def report_steps(world: Path) -> None:
    recs = kept_steps(world)
    if not recs:
        print(f"no {STEPS} under {world / 'days'} yet")
        return
    names: dict[str, float] = {}
    for r in recs:
        for k, v in flat(r).items():
            names[k] = max(names.get(k, 0.0), v)
    cols = [k for k, _ in sorted(names.items(), key=lambda kv: -kv[1]) if k != "world finish"][:14]
    print()
    print(f"{'day':10} {'wall s':>8} {'no step':>8}  " + "  ".join(f"{c.replace('finish: ', '')[:18]:>18}" for c in cols))
    for r in recs:
        f = flat(r)
        print(f"{r['day']:10} {r.get('wall s', 0):>8,.0f} {r.get('unaccounted s', 0):>8,.0f}  "
              + "  ".join(f"{f.get(c, 0):>18,.0f}" for c in cols))
    for r in recs:
        for w in r.get("watch", []):
            print(f"watch {r['day']}: {w}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("harvest")
    h.add_argument("work", type=Path)
    h.add_argument("--out", type=Path)
    r = sub.add_parser("report")
    r.add_argument("--world", type=Path, default=WORLD)
    st = sub.add_parser("steps")
    st.add_argument("--day")
    st.add_argument("--all", action="store_true", help="every day the world keeps a record of")
    st.add_argument("--world", type=Path, default=WORLD)
    st.add_argument("--log", type=Path, default=ROOT / "logs" / "planet-store.log")
    a = p.parse_args()
    if a.cmd == "report":
        report(a.world)
        report_steps(a.world)
        return 0
    if a.cmd == "steps":
        days = sorted(d.name for d in (a.world / "days").iterdir() if d.is_dir()) if a.all else [a.day]
        for d in days:                      # oldest first: a day's watch reads the days before it
            out = write_steps(a.world, d, a.log, print)
            print(f"{d}: {'written' if out else 'not in the log'}")
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
