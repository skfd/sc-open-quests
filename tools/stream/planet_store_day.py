"""The planet tile store and the world state (tools/stream/world_day.py) moved forward together by every daily diff
they have not had, each day checked before the next (DESIGN.md, "The planet store's first day", "Compaction",
"Release 1: the world day", "The world day on the planet"; HANDOFF, "Release goals").

  python tools/stream/planet_store_day.py [--max-days N] [--no-wait]

For each day D (the store, its node file and the world all at D-1):
  1. the world's files hard-linked into the day's `before/` (the state at D-1, kept until the day is done; every
     write to a world file replaces it, so the links keep D-1's bytes), and `world_day.prepare` (the diff read, the
     old geometry and the store's answers at D-1), saved as `day.pkl`: the store's update takes generation D-1's way
     pairs away, so after it `prepare` cannot run again;
  2. `tilestore update` by the diff (--world --group-mib 512 --prune-pairs);
  3. `world_day.finish` (tiers 1 and 2, notes, the counts per place at D), the node file still at D-1;
  4. the world's gate (tools/stream/world_gate.py: the 32 European cities against the engine on the Europe clip of D,
     0.1% bar);
  5. the node file moved forward (`loc advance`) and held against that clip (`loc check`), the store's new
     generation held against a cut of it (subcmp at 2 km, every difference explained by why.py: ways the clip's
     extract drops), then `compact --min-dead 0.25` and `punch`; the clip of D unpinned, the day's work deleted
     (its day.json and gate.json kept in W/days/<D>/).
A run that stops after the update resumes: with the store at D and the world at D-1 it puts the world back from
`before/` and runs `finish` again from `day.pkl`; with both at D and the node file at D-1 it goes on from the gate.
Any failure writes STOPPED beside the store and every later run refuses until a person removes it. Two things end a
run with no STOPPED, because nothing is wrong and the next run goes on: a gate region whose engine the machine cannot
spare the heap for after the wait (run.MemoryBusy; the day resumes at its gate), and a new day the disk has no room
for (DAY_NEEDS_GB over DISK_FLOOR_GB; a resumed day is not asked). HOLD beside the
store (its text the reason) makes a run take no day, not a failure: a reader of the store
(tools/stream/store_lock.py). While a run works it keeps RUNNING beside the store, so a reader waits. Waits while
today's daily run (kk-SCOpenQuests) is still going; no engine or update starts in its window (world_day.quiet).
Log: logs/planet-store.log; each run's own prints go to logs/planet-store-<started>-<pid>.out (--console: here), so
start it without a redirect. A day ends by writing its counts as facts (tools/facts.py), a run by publishing the
gated days (run.py site, logs/site.log), also one that took no day or stopped. The store never moves without the world: there is no flag for that."""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("WORLD_T2_WORKERS", "4")  # read by world_day at import (rect_rows' default)

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / ".scratch/planet-cut/store"
LOC = ROOT / ".scratch/planet-day/planet.loc"
WORK = ROOT / ".scratch/planet-day"
STOPPED = STORE.parent / "STOPPED"
HOLD = STORE.parent / "HOLD"  # no day taken while it exists (a reader, or the store held at a seed day)
RUNNING = STORE.parent / "RUNNING"  # a run is moving the store: readers wait
DATA = Path.home() / "Code/.osm-data"
DIFF_DIRS = [DATA / "planet/diffs", ROOT / ".scratch/planet/diffs-keep"]
KEEP = ROOT / ".scratch/planet/diffs-keep"
EUROPE = DATA / "europe"
LOG = ROOT / "logs/planet-store.log"
SCHED = ROOT / "logs/scheduler.log"
EXE_SRC = ROOT / "tilestore/target/release/tilestore.exe"
EXE = WORK / "tilestore-daily.exe"
WORLD = ROOT / ".scratch/planet/world-1101"  # the world state seeded at 2026-11-01 (HANDOFF, "Release goals", step 3)
WDAYS = WORK / "world-days"  # per day: day.pkl, before/, work/, gate/
PUNCH_BELOW_GB = 60  # free GiB on the store's disk under which a day ends with `punch`
# No new day is taken with less than DAY_NEEDS_GB + DISK_FLOOR_GB free (115 GiB). A day failed in its middle for
# want of disk on 11-16 and 11-21 (HANDOFF): that is a STOPPED and a person; not taking the day is neither.
DAY_NEEDS_GB = 75    # GiB a day takes from the disk at its low: `before/` (D-1's rows, about 56) and the work.
#                      Days that began with 124 to 142 GiB free had 45 to 54 left at their low, in tier 2
DISK_FLOOR_GB = 40   # GiB free under which tilestore's update, loc advance and compact refuse (nodefile.rs)
QUESTS = "v64.1.json"  # the seed's quests file; a new StreetComplete release means a reseed, not a day
PINS = EUROPE / "pins.json"
PIN_REASON = ("sc-open-quests release 1: oracle for the world's daily backfill from 11-02 (HANDOFF, Release goals); "
              "unpin once that day is streamed and checked")

sys.path.insert(0, str(ROOT / "tools/stream"))
import day_metrics as DM  # noqa: E402
import world_day as WD  # noqa: E402
import world_gate as WG  # noqa: E402
import world_state as WS  # noqa: E402

WD.EXE = EXE  # the world day's store reads and lookups by the run's own copy of the binary


def log(msg):
    line = f"[{dt.datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def own_output() -> Path:
    """This run's prints, tracebacks and its children's into logs/planet-store-<started>-<pid>.out. The task used to
    append to one planet-store.out, which a second run cannot open while a run holds it (11-19: the scheduled task
    exited 1 before Python started, beside the catch-up started by hand). The log stays one file."""
    out = LOG.with_name(f"planet-store-{dt.datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}.out")
    f = open(out, "a", encoding="utf-8", buffering=1)
    sys.stdout.flush()
    sys.stderr.flush()
    os.dup2(f.fileno(), 1)
    os.dup2(f.fileno(), 2)
    sys.stdout = sys.stderr = f
    return out


def stop(reason):
    STOPPED.write_text(f"{dt.datetime.now().isoformat(timespec='seconds')} {reason}\n", encoding="utf-8")
    log(f"STOPPED: {reason} (remove {STOPPED} once it is understood)")
    sys.exit(1)


def free_gb(path: Path | None = None) -> float:
    """GiB free on the store's disk (the world, its days' work and the node file are on it too)"""
    return shutil.disk_usage(path or STORE).free / 2**30


def day_disk_short(day: str, free=free_gb) -> str | None:
    """None when the disk has room for a new day; else the line to log instead of taking it. `free`: a reader of
    the free GiB (a test gives its own). Asked only before a new day: a resumed day's steps keep their own
    checks (the 40 GiB floor in tilestore), and what a day already holds is given back only by ending it."""
    have, need = free(), DAY_NEEDS_GB + DISK_FLOOR_GB
    if have >= need:
        return None
    return (f"day {day} not taken: {have:.0f} GiB free on the store's disk, and a day needs {need} (about "
            f"{DAY_NEEDS_GB} at its low, over the {DISK_FLOOR_GB} GiB floor update and compact refuse under); "
            f"no STOPPED, done for now: free {need - have:.0f} GiB and the next run takes it")


def run(args, what, ok_codes=(0,)):
    t = time.time()
    p = subprocess.run([str(a) for a in args], capture_output=True, text=True, cwd=ROOT)
    err = p.stderr or ""
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(err if err.endswith("\n") or not err else err + "\n")
    out = p.stdout or ""
    log(f"{what}: exit {p.returncode} in {time.time() - t:.0f} s")
    if p.returncode not in ok_codes:
        stop(f"{what} failed (exit {p.returncode})")
    return p.returncode, out


def diff_ends():
    """sequence -> (end instant, path) of every daily diff on disk"""
    out = {}
    for d in DIFF_DIRS:
        for st in d.glob("*.state.txt"):
            m = re.search(r"timestamp=(\S+)", st.read_text())
            osc = st.with_name(st.name.replace(".state.txt", ".osc.gz"))
            if m and osc.exists():
                out.setdefault(int(st.name.split(".")[0]), (m.group(1).replace("\\", ""), osc))
    return out


def europe_of(seq):
    for meta in EUROPE.glob("europe-????-??-??.meta.json"):
        m = json.loads(meta.read_text())
        pbf = meta.with_name(meta.name.replace(".meta.json", ".osm.pbf"))
        if m.get("replication_sequence") == seq and pbf.exists():
            return pbf
    return None


def daily_run_going():
    """today's kk-SCOpenQuests started (=== download) and has logged neither update done nor the ERROR it died of
    (11-21: the 16:46 run ran out of heap at 17:25, and the loop restarted at 21:10 waited for it)"""
    today = dt.date.today().isoformat()
    lines = [x for x in SCHED.read_text(encoding="utf-8", errors="replace").splitlines() if x.startswith(f"[{today}")]
    started = any("=== download" in x for x in lines)
    return started and not any("update done" in x or "] ERROR:" in x for x in lines[-5:])


def inputs_going():
    """`run.py inputs` is fetching the day's Europe clip, planet diff or notes dump: its lock names a live process"""
    import run as runmod
    try:
        pid = int(runmod.INPUTS_LOCK.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    return runmod.pid_alive(pid)


def monthly_going():
    """the monthly planet job (kk-SCOpenQuests-planet: about 170 GB while it writes the new history file) is running"""
    p = subprocess.run(["schtasks", "/query", "/tn", "kk-SCOpenQuests-planet", "/fo", "csv", "/nh"], capture_output=True, text=True)
    return '"Running"' in (p.stdout or "")


def world_clock() -> str:
    return json.loads((WORLD / WS.WORLD_META).read_text(encoding="utf-8"))["clock"]


def pins_edit(add: list[str] = (), drop: list[str] = ()) -> None:
    """osm-extracts' pins.json: a clip pinned is never pruned (each Europe clip is a world day's oracle until the
    day is checked; they go 14 days after their date otherwise)"""
    pins = json.loads(PINS.read_text(encoding="utf-8")) if PINS.exists() else {}
    before = dict(pins)
    for n in add:
        pins.setdefault(n, PIN_REASON)
    for n in drop:
        pins.pop(n, None)
    if pins != before:
        tmp = PINS.with_suffix(".json.writing")
        tmp.write_text(json.dumps(pins, indent=1), encoding="utf-8", newline="\n")
        os.replace(tmp, PINS)
        log(f"pins: added {[n for n in pins if n not in before]}, removed {[n for n in before if n not in pins]}")


def pin_ahead(clock_day: str) -> None:
    """every Europe clip of a day the world has not reached yet, pinned"""
    pins_edit(add=[p.name for p in EUROPE.glob("europe-????-??-??.osm.pbf") if p.name[7:17] > clock_day])


# --- the world's D-1 kept while a day runs ------------------------------------------------------------------

SMALL = ("world.json", "place-sets.json", "touched.npy", "rects.npy")


def world_files() -> list[str]:
    return [f["id"] for f in json.loads((WORLD / "plan.json").read_text(encoding="utf-8"))["files"]]


def snapshot(before: Path) -> None:
    """the world at D-1: each file's rows hard-linked (no bytes copied; world_state's writes replace a file, and
    notes_day copies a linked file before it sets flags), the small files copied. world-keys.npy is not kept (np.save
    writes into a linked file): `restore` derives it from the rows."""
    if (before / "done").exists():
        return
    shutil.rmtree(before, ignore_errors=True)
    for fid in world_files():
        d = before / "files" / fid
        d.mkdir(parents=True)
        os.link(WORLD / "files" / fid / WS.WORLD_BIN, d / WS.WORLD_BIN)
    for n in SMALL:
        if (WORLD / n).exists():
            shutil.copy2(WORLD / n, before / n)
    (before / "done").write_text(world_clock() + "\n", encoding="utf-8")


def restore(before: Path, day: str) -> None:
    """the world put back to `before/` (a finish that did not end): rows, keys, small files; D's counts dropped"""
    import numpy as np
    if not (before / "done").exists():
        stop(f"no complete copy of the world before {day} in {before}: it cannot be put back")
    n = 0
    for fid in world_files():
        src, dst = before / "files" / fid / WS.WORLD_BIN, WORLD / "files" / fid / WS.WORLD_BIN
        if dst.exists() and os.path.samefile(src, dst):
            continue
        tmp = dst.with_suffix(".bin.restore")
        tmp.unlink(missing_ok=True)
        os.link(src, tmp)
        os.replace(tmp, dst)
        k = np.fromfile(dst, WD.P.WREC)["key"]
        np.save(dst.with_name(WS.WORLD_KEYS), k[np.concatenate([[True], k[1:] != k[:-1]])] if len(k) else k)
        n += 1
    for name in SMALL:
        if (before / name).exists():
            shutil.copy2(before / name, WORLD / name)
        else:
            (WORLD / name).unlink(missing_ok=True)
    shutil.rmtree(WORLD / "counts" / day, ignore_errors=True)
    log(f"world put back to {world_clock()} from {before} ({n} files' rows)")


# --- one day --------------------------------------------------------------------------------------------------

def guarded(what, fn, *args, **kw):
    """a step of the world day: any failure (world_day raises SystemExit, asserts, CalledProcessError) is a STOP.
    Not run.MemoryBusy: no engine was started (only the gate's engines ask for a heap, storecheck_cities.engine),
    so nothing is half done; it goes up to `days`, which ends the run"""
    try:
        return fn(*args, **kw)
    except WG.run.MemoryBusy:
        raise
    except BaseException as e:  # noqa: BLE001
        if STOPPED.exists():  # a stop() inside the step: its reason stands
            raise
        import traceback
        with open(LOG, "a", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        stop(f"{what} failed: {type(e).__name__}: {str(e)[:500]}")


def world_finish(dd: Path, nxt: str) -> None:
    t = time.time()
    day = WD.load_day(dd / "day.pkl", log=log)
    log(f"timer: day.pkl load {time.time() - t:.1f} s")
    if day.today != f"{nxt}T00:00:00Z":
        stop(f"{dd / 'day.pkl'} is for {day.today}, not {nxt}")
    if (dd / "finishing").exists() or world_clock() != day.prev:  # a finish began before: its writes undone first
        restore(dd / "before", nxt)
    WD.quiet(30)
    (dd / "finishing").write_text(dt.datetime.now().isoformat(timespec="seconds") + "\n", encoding="utf-8")
    t = time.time()
    rec = WD.finish(day)
    log(f"world finish {nxt}: {time.time() - t:.0f} s; {json.dumps(rec['seconds'])}")


def world_gate(dd: Path, nxt: str, oracle: Path) -> None:
    if (dd / "gate" / "gate.json").exists() and json.loads((dd / "gate" / "gate.json").read_text())["ok"]:
        return
    res = WG.gate(WORLD, nxt, oracle, dd / "gate", log=log)
    if not res["ok"]:
        stop(f"the world's gate for {nxt} failed: {res['equal']} of {res['cities']} cities equal, open "
             f"{res['open world']:,} against {res['open clip']:,} ({res['rel']:.4%}), worst city {res['worst city rel']:.4%}, "
             f"missing {res['missing']} (see {dd / 'gate' / 'gate.json'})")


def store_tail(dd: Path, nxt: str, seq: int, osc: Path, oracle: Path, g: int) -> None:
    """the node file to D and the store's own checks of D, then compaction; the day's work given back"""
    if (Path(str(LOC) + ".state")).read_text().strip() != f"{nxt}T00:00:00Z":
        run([EXE, "loc", "advance", "--loc", LOC, "--diff", osc, "--at", f"{nxt}T00:00:00Z"], f"loc advance {seq}")
    run([EXE, "loc", "check", "--loc", LOC, "--pbf", oracle], f"loc check against {oracle.name}")
    clip = WORK / f"clip-{seq}"
    shutil.rmtree(clip, ignore_errors=True)
    run([EXE, "cut", "--pbf", oracle, "--out", clip, "--day", nxt], f"cut of {oracle.name}")
    sc = WORK / f"subcmp-{seq}.json"
    _, out = run([sys.executable, ROOT / "tools/stream/tilecheck/subcmp.py", "--clip", clip, "--planet", STORE, "--gp", g,
                  "--poly", EUROPE / "polygon.geojson", "--inset-km", "2"], f"subcmp generation {g}", ok_codes=(0, 1))
    sc.write_text(out, encoding="utf-8")
    r = json.loads(sc.read_text())
    log(f"subcmp: interior {r['interior']}, same {r['same']}, differ {r['differ']}, only planet {r['onlyPlanet']}, only clip {r['onlyClip']}")
    if r["onlyClip"]:
        stop(f"{r['onlyClip']} tiles only in the clip")
    _, out = run([sys.executable, ROOT / "tools/stream/tilecheck/why.py", sc, clip, STORE, g], "why", ok_codes=(0, 1))
    w = json.loads(out)
    log(f"why: {w['explained']} of {w['tiles']} explained; extra ways {w['extraWays']}")
    if w["notExplained"]:
        stop(f"day {nxt}: tiles not explained by ways the clip lacks: {w['notExplained']}")
    shutil.rmtree(clip, ignore_errors=True)
    run([EXE, "compact", "--store", STORE, "--min-dead", "0.25"], "compact")
    # the day's record kept with the world; its work (both dates' map data, the dumps, D-1's rows) given back
    keep = WORLD / "days" / nxt
    keep.mkdir(parents=True, exist_ok=True)
    t = time.time()
    try:  # what each engine did, read off its log before the logs go (day_metrics.py); never a stop
        DM.write(WORLD, nxt, dd / "work", log)
    except Exception as e:  # noqa: BLE001
        log(f"engines: not recorded ({type(e).__name__}: {e})")
    log(f"timer: engines harvest {time.time() - t:.1f} s")
    for src in (dd / "work" / "day.json", dd / "gate" / "gate.json"):
        if src.exists():
            shutil.copy2(src, keep / src.name)
    pins_edit(drop=[oracle.name])
    (WORLD / WD.NOTES_PREV).unlink(missing_ok=True)  # the day after a notes refresh is done: D-1's clip not needed
    t = time.time()
    shutil.rmtree(dd, ignore_errors=True)
    log(f"timer: day's work deleted {time.time() - t:.1f} s")
    # punch only gives dead space in pack-0000 back to the disk, at about 0.5 s a dead range on the planet (11-02's first:
    # 15,654 ranges; 11-03's daily one: over 16,000 in 2 h, both stopped by hand), so it runs only when the disk is
    # short, measured after the day's work (D-1's links, about 56 GB) is given back
    free_gb = shutil.disk_usage(STORE).free / 2**30
    if free_gb < PUNCH_BELOW_GB:
        run([EXE, "punch", "--store", STORE], f"punch ({free_gb:.0f} GiB free, under {PUNCH_BELOW_GB})")
    else:
        log(f"punch skipped: {free_gb:.0f} GiB free (it runs under {PUNCH_BELOW_GB})")
    log(f"== day {nxt} done: generation {g}; the world at {world_clock()}")


def one_day():
    if HOLD.exists():
        log(f"held: {HOLD} says {HOLD.read_text(encoding='utf-8').strip()}; no day taken")
        return False
    meta = json.loads((STORE / "store.json").read_text())
    gen = meta["generations"][-1]["gen"]
    day = meta["generations"][-1]["day"]
    loc_at = (Path(str(LOC) + ".state")).read_text().strip()[:10]
    wclock = world_clock()
    w_at = wclock[:10]
    if wclock != f"{w_at}T00:00:00Z":
        stop(f"the world's clock {wclock} is not a day's start")
    pin_ahead(w_at)
    prev = (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat()
    ends = diff_ends()

    def diff_to(d):
        seqs = [s for s, (e, _) in ends.items() if e == f"{d}T00:00:00Z"]
        if not seqs:
            return None, None, None
        s = seqs[0]
        o = europe_of(s)
        if o is None:
            stop(f"no Europe clip of sequence {s} to check day {d} against (they age out after 14 days)")
        return s, ends[s][1], o

    # a day that stopped after the store's update: the store at D, the node file at D-1, the world at D-1 or D
    if loc_at == prev and w_at in (prev, day):
        dd = WDAYS / day
        seq, osc, oracle = diff_to(day)
        if seq is None or not (dd / "day.pkl").exists():
            stop(f"the store is at {day}, the node file at {loc_at}, the world at {w_at}, and {dd / 'day.pkl'} or the "
                 f"diff to {day} is missing: the day cannot be resumed")
        log(f"== day {day}: resuming (the store at generation {gen}, the world at {w_at})")
        if w_at == prev or not (dd / "finished").exists():
            guarded(f"world finish {day}", world_finish, dd, day)
            (dd / "finished").write_text("", encoding="utf-8")
        guarded(f"world gate {day}", world_gate, dd, day, oracle)
        store_tail(dd, day, seq, osc, oracle, gen)
        return True
    if not (loc_at == day == w_at):
        stop(f"the store is at {day}, the node file at {loc_at}, the world at {w_at}: not a state a day starts or "
             f"resumes from")
    if (WDAYS / day).exists():  # D's store checks or compaction stopped after the node file moved: finish them
        seq, osc, oracle = diff_to(day)
        if seq is not None and (WDAYS / day / "finished").exists():
            log(f"== day {day}: the store's checks and compaction, resumed")
            guarded(f"world gate {day}", world_gate, WDAYS / day, day, oracle)
            store_tail(WDAYS / day, day, seq, osc, oracle, gen)
    nxt = (dt.date.fromisoformat(day) + dt.timedelta(days=1)).isoformat()
    seq, osc, oracle = diff_to(nxt)
    if seq is None:
        log(f"store and world at {day}, generation {gen}: no diff to {nxt} on disk yet; done for now")
        return False
    short = day_disk_short(nxt)  # before anything of the day is written (the notes refresh, the diff kept, before/)
    if short:
        log(short)
        return False
    if f"{nxt}T00:00:00Z" > WD.notes_until(WORLD):  # the world's notes end before D: cut them from a newer dump
        dump = run_notes_dump()
        if dump is None or dump.name == WG.world_dump(WORLD).name:
            log(f"day {nxt}: the world's notes end at {WD.notes_until(WORLD)} and no newer notes dump is in the store "
                f"yet; done for now")
            return False
        guarded(f"notes refresh from {dump.name}", WD.refresh_notes, WORLD, dump, log)
        if f"{nxt}T00:00:00Z" > WD.notes_until(WORLD):
            log(f"day {nxt}: the newest notes dump ends at {WD.notes_until(WORLD)}; done for now")
            return False
    if run_quests().name != QUESTS:
        stop(f"the newest quests file is {run_quests().name}, the world's is {QUESTS}: a new StreetComplete release "
             f"means a reseed (DESIGN.md, 'Before release 1, two rules')")
    # keep the diff: osm-extracts deletes diffs once no pass or clip needs them
    KEEP.mkdir(parents=True, exist_ok=True)
    for f in (osc, osc.with_name(osc.name.replace(".osc.gz", ".state.txt"))):
        k = KEEP / f.name
        if not k.exists():
            try:
                k.hardlink_to(f)
            except OSError:
                shutil.copy2(f, k)
    log(f"== day {nxt}: diff {seq} on generation {gen}; the world at {wclock}; check against {oracle.name}")
    dd = WDAYS / nxt
    dd.mkdir(parents=True, exist_ok=True)
    t = time.time()
    guarded("world snapshot", snapshot, dd / "before")
    log(f"world snapshot: {time.time() - t:.0f} s")
    t = time.time()
    d_ = guarded(f"world prepare {nxt}", WD.prepare, WORLD, STORE, osc, f"{nxt}T00:00:00Z", LOC, dd / "work", 8,
                 None, log)
    ts = time.time()
    guarded("save the prepared day", WD.save_day, d_, dd / "day.pkl")
    t_save, ts = time.time() - ts, time.time()
    back = guarded("load the prepared day", WD.load_day, dd / "day.pkl", log)
    t_load = time.time() - ts
    if (back.diff, back.gen_before, back.today, len(back.last_node), len(back.old_rows)) != \
            (d_.diff, d_.gen_before, d_.today, len(d_.last_node), len(d_.old_rows)):
        stop(f"{dd / 'day.pkl'} does not read back as the prepared day")
    del back
    log(f"timer: day.pkl save {t_save:.1f} s")
    log(f"timer: day.pkl read back {t_load:.1f} s")
    log(f"world prepare {nxt}: {time.time() - t:.0f} s; {json.dumps({k: round(v) for k, v in d_.T.items()})}")
    del d_  # finish reads the day back, as a resume does; the update (about 20 GiB) gets the memory
    import gc
    gc.collect()
    WD.quiet(20)  # the update not beside the daily run
    run([EXE, "update", "--store", STORE, "--diff", osc, "--before-loc", LOC, "--day", nxt, "--world", "--group-mib", "512",
         "--prune-pairs"], f"update {seq}")
    guarded(f"world finish {nxt}", world_finish, dd, nxt)
    (dd / "finished").write_text("", encoding="utf-8")
    guarded(f"world gate {nxt}", world_gate, dd, nxt, oracle)
    store_tail(dd, nxt, seq, osc, oracle, gen + 1)
    try:  # the day's steps, whatever ran them, read off this log (day_metrics.py); never a stop
        DM.write_steps(WORLD, nxt, LOG, log)
    except Exception as e:  # noqa: BLE001
        log(f"steps: not recorded ({type(e).__name__}: {e})")
    write_facts()
    return True


def write_facts() -> None:
    """every gated day that has no facts yet, as Parquet (tools/facts.py, DESIGN.md "Storage: facts, serving, working
    state"). A process of its own (a day's counts are GBs in memory), and never a stop: the facts are written from
    counts/<D>/, which stays, so `python tools/facts.py world` makes up for a failure."""
    t = time.time()
    try:
        p = subprocess.run([sys.executable, str(ROOT / "tools" / "facts.py"), "world", "--world", str(WORLD)],
                           capture_output=True, text=True, cwd=ROOT, timeout=3600)
        tail = " | ".join((p.stdout or "").strip().splitlines()[-2:])
        log(f"facts: exit {p.returncode} in {time.time() - t:.0f} s; {tail}" +
            (f"; {(p.stderr or '').strip()[-300:]}" if p.returncode else ""))
    except (OSError, subprocess.TimeoutExpired) as e:
        log(f"facts: not written ({e}); python tools/facts.py world makes up for it")


def publish() -> None:
    """the gated days go up: the place files, then the site (run.py site). After RUNNING is gone: it reads only the
    world's gated counts, so a reader of the store need not wait for the upload (half an hour). Never a stop: `run.py
    inputs` (11:15) and the next run of this loop make up for a failure."""
    t = time.time()
    try:
        with open(ROOT / "logs" / "site.log", "ab") as out:
            p = subprocess.run([sys.executable, str(ROOT / "run.py"), "site"], stdout=out, stderr=subprocess.STDOUT,
                               cwd=ROOT, timeout=3 * 3600)
        log(f"publish: exit {p.returncode} in {time.time() - t:.0f} s (logs/site.log)")
    except (OSError, subprocess.TimeoutExpired) as e:
        log(f"publish: not done ({e}); python run.py site makes up for it")


def run_quests() -> Path:
    sys.path.insert(0, str(ROOT))
    import run as runmod
    return runmod.newest_quests_file()


def run_notes_dump() -> Path | None:
    import run as runmod
    return runmod.notes_dump()


def days(max_days: int, day=None) -> int:
    """day after day until one says there is no more to do (`day`: one_day; a test gives its own); the days done.
    run.MemoryBusy ends the run and is not a STOP: it comes from the gate before an engine starts (world_gate.
    clip_side), with the store and the world at D, `finished` written and the node file at D-1, which is the state
    one_day resumes from ("resuming", then the gate only: gate.json is not there yet, the regions already counted
    keep their `done`), so the next run does the gate again and nothing else of the day twice."""
    n = 0
    try:
        while n < max_days and (day or one_day)():
            n += 1
    except WG.run.MemoryBusy as e:
        # not the text "STOPPED:" in this line: store_lock.run_going reads that in the log as a run's end by a stop
        log(f"not now: {e}. No STOPPED written, since nothing failed and nothing is half written; the next run "
            f"resumes the day at its gate")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-days", type=int, default=40)
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--console", action="store_true", help="print here, not into an output file of this run's own")
    a = ap.parse_args()
    if not a.console:
        own_output()
    if STOPPED.exists():
        log(f"refusing: {STOPPED} says {STOPPED.read_text().strip()}")
        sys.exit(1)
    waited = 0
    while not a.no_wait and daily_run_going() and waited < 180:
        if waited == 0:
            log("today's daily run is going: waiting for it (up to 3 h)")
        time.sleep(60)
        waited += 1
    waited = 0
    while not a.no_wait and inputs_going() and waited < 60:
        if waited == 0:
            log("today's inputs are being fetched: waiting for them (up to 1 h)")
        time.sleep(60)
        waited += 1
    # the monthly planet job and this one both need tens of GB at once: wait for it, or leave the day to the next
    # run (each run catches up every day it finds missing)
    waited = 0
    while not a.no_wait and monthly_going():
        if waited == 0:
            log("the monthly planet job is running: waiting for it (up to 8 h)")
        if waited >= 480:
            log("the monthly planet job is still running after 8 h: no days this run; the next run catches up")
            return
        time.sleep(60)
        waited += 1
    if RUNNING.exists():  # another run (the scheduled task beside a catch-up started by hand) is moving the store
        try:
            pid = int(RUNNING.read_text(encoding="utf-8").split()[1])
        except (IndexError, ValueError):
            pid = None
        alive = pid is not None and str(pid) in subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                                                capture_output=True, text=True).stdout
        if alive or pid is None:
            log(f"another run holds {RUNNING} ({RUNNING.read_text(encoding='utf-8').strip()}): not starting")
            return
        log(f"{RUNNING} left by a run that is gone (pid {pid}): taking over")
    shutil.copy2(EXE_SRC, EXE)  # a rebuild of tilestore/ while this runs does not touch the binary in use
    log(f"planet store run started; binary {EXE_SRC} copied")
    n = 0
    RUNNING.write_text(f"{dt.datetime.now().isoformat(timespec='seconds')} {os.getpid()}\n", encoding="utf-8")
    try:
        n = days(a.max_days)
    finally:
        RUNNING.unlink(missing_ok=True)
        log(f"planet store run ended: {n} days")
        publish()


if __name__ == "__main__":
    main()
