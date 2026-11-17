"""The planet tile store moved forward by every daily diff it has not had, each day checked before the next
(DESIGN.md, "The planet store's first day", "Compaction"; HANDOFF, "The planet store, kept daily").

  python tools/stream/planet_store_day.py [--max-days N] [--no-wait]

For each day: `tilestore update` by the next diff (--world --group-mib 512 --prune-pairs), the node file moved
forward (`loc advance`) and held against the Europe clip of the same replication sequence (`loc check`), the store's
new generation held against a cut of that clip (subcmp at 2 km, every difference explained by why.py: ways the
clip's extract drops), then `compact --min-dead 0.25` and `punch`. Any failure writes STOPPED beside the store and
every later run refuses until a person removes it. HOLD beside the store (its text the reason) makes a run take no
day, not a failure: a reader of the store (tools/stream/store_lock.py) or a hold at a seed day. While a run works it
keeps RUNNING beside the store, so a reader waits. Waits while today's daily run (kk-SCOpenQuests) is still going.
Log: logs/planet-store.log."""
import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

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


def log(msg):
    line = f"[{dt.datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def stop(reason):
    STOPPED.write_text(f"{dt.datetime.now().isoformat(timespec='seconds')} {reason}\n", encoding="utf-8")
    log(f"STOPPED: {reason} (remove {STOPPED} once it is understood)")
    sys.exit(1)


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
    """today's kk-SCOpenQuests started (=== download) and has not logged update done"""
    today = dt.date.today().isoformat()
    lines = [x for x in SCHED.read_text(encoding="utf-8", errors="replace").splitlines() if x.startswith(f"[{today}")]
    started = any("=== download" in x for x in lines)
    return started and not any("update done" in x for x in lines[-5:])


def monthly_going():
    """the monthly planet job (kk-SCOpenQuests-planet: about 170 GB while it writes the new history file) is running"""
    p = subprocess.run(["schtasks", "/query", "/tn", "kk-SCOpenQuests-planet", "/fo", "csv", "/nh"], capture_output=True, text=True)
    return '"Running"' in (p.stdout or "")


def one_day():
    if HOLD.exists():
        log(f"held: {HOLD} says {HOLD.read_text(encoding='utf-8').strip()}; no day taken")
        return False
    meta = json.loads((STORE / "store.json").read_text())
    gen = meta["generations"][-1]["gen"]
    day = meta["generations"][-1]["day"]
    at = f"{day}T00:00:00Z"
    held = (Path(str(LOC) + ".state")).read_text().strip()
    if held != at:
        stop(f"the node file holds {held}, the store {at}")
    ends = diff_ends()
    nxt = (dt.date.fromisoformat(day) + dt.timedelta(days=1)).isoformat()
    seqs = [s for s, (e, _) in ends.items() if e == f"{nxt}T00:00:00Z"]
    if not seqs:
        log(f"store at {day}, generation {gen}: no diff to {nxt} on disk yet; done for now")
        return False
    seq = seqs[0]
    osc = ends[seq][1]
    oracle = europe_of(seq)
    if oracle is None:
        stop(f"no Europe clip of sequence {seq} to check day {nxt} against (they age out after 14 days)")
    # keep the diff: osm-extracts deletes diffs once no pass or clip needs them
    KEEP.mkdir(parents=True, exist_ok=True)
    for f in (osc, osc.with_name(osc.name.replace(".osc.gz", ".state.txt"))):
        k = KEEP / f.name
        if not k.exists():
            try:
                k.hardlink_to(f)
            except OSError:
                shutil.copy2(f, k)
    log(f"== day {nxt}: diff {seq} on generation {gen}; check against {oracle.name}")
    run([EXE, "update", "--store", STORE, "--diff", osc, "--before-loc", LOC, "--day", nxt, "--world", "--group-mib", "512",
         "--prune-pairs"], f"update {seq}")
    run([EXE, "loc", "advance", "--loc", LOC, "--diff", osc, "--at", f"{nxt}T00:00:00Z"], f"loc advance {seq}")
    run([EXE, "loc", "check", "--loc", LOC, "--pbf", oracle], f"loc check against {oracle.name}")
    clip = WORK / f"clip-{seq}"
    shutil.rmtree(clip, ignore_errors=True)
    run([EXE, "cut", "--pbf", oracle, "--out", clip, "--day", nxt], f"cut of {oracle.name}")
    g = gen + 1
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
    run([EXE, "punch", "--store", STORE], "punch")
    log(f"== day {nxt} done: generation {g}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-days", type=int, default=40)
    ap.add_argument("--no-wait", action="store_true")
    a = ap.parse_args()
    if STOPPED.exists():
        log(f"refusing: {STOPPED} says {STOPPED.read_text().strip()}")
        sys.exit(1)
    waited = 0
    while not a.no_wait and daily_run_going() and waited < 180:
        if waited == 0:
            log("today's daily run is going: waiting for it (up to 3 h)")
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
    shutil.copy2(EXE_SRC, EXE)  # a rebuild of tilestore/ while this runs does not touch the binary in use
    log(f"planet store run started; binary {EXE_SRC} copied")
    n = 0
    RUNNING.write_text(f"{dt.datetime.now().isoformat(timespec='seconds')}\n", encoding="utf-8")
    try:
        while n < a.max_days and one_day():
            n += 1
    finally:
        RUNNING.unlink(missing_ok=True)
    log(f"planet store run ended: {n} days")


if __name__ == "__main__":
    main()
