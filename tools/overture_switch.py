"""Switch the world to a new Overture release: the staged registry (tools/overture_release.py) goes live with a
reseed, the world recounted from the store at its day D with the release's places (owner, 2026-11-26: monthly, on
the 1st; the first, 12-01 with 2026-11-18.0, watched by the owner).

    python tools/overture_switch.py prepare RELEASE    any time, new folders only: the pull, the squares, the name
                                                       layer, the world's places, the new world's plan and parts cache
    python tools/overture_switch.py cutover RELEASE    under the HOLD, the loop done with day D: storecut at D, notes,
                                                       count --state, world_state seed, the counts at D, the gate at D,
                                                       the old world's days joined in, old against new at D
    python tools/overture_switch.py adopt RELEASE      the live files flipped: registry (old one backed up), pin,
                                                       pull, squares, name layer, data/world.json. The HOLD stays:
                                                       lifting it is the owner's, and the first day on the new world
                                                       is the point of no return (the store's update cannot be undone)
    python tools/overture_switch.py status RELEASE

Every step leaves a marker in <new world>/switch/ and is skipped once done, so a stopped run is resumed by running the
same command again. Run long ones detached (a background job dies at 2 h), ONE quoted -c argument:
    Start-Process -WindowStyle Hidden 'C:\\Program Files\\Git\\bin\\bash.exe' -ArgumentList
      '-c "cd /c/Users/kk/Code/sc-open-quests && .scratch/overture/.venv/Scripts/python tools/overture_switch.py
       cutover 2026-11-18.0 >> logs/switch.log 2>&1"'

Folders, for RELEASE R: the pull data/overture/R (adopt renames it to data/overture/world, the old one to its own
release), the squares and the backups in data/place-ids/releases/R/, the name layer .scratch/switch/R/places
(adopt swaps it into docs/places), the world's places .scratch/world-places/R (stays: the world's paths point into
it), the new world .scratch/planet/world-R."""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import place_ids  # noqa: E402

PY = ROOT / ".scratch" / "overture" / ".venv" / "Scripts" / "python.exe"   # duckdb, timezonefinder, the engine's runs
SYS_PY = "python"   # the world loop's own interpreter (kk-SCOpenQuests-planetstore)
JAVA_HOME = r"C:\Program Files\Android\Android Studio\jbr"
STORE = ROOT / ".scratch" / "planet-cut" / "store"
CUT = ROOT / ".scratch" / "planet-cut"
HOLD, RUNNING = CUT / "HOLD", CUT / "RUNNING"
POINTER = ROOT / "data" / "world.json"
FILE_NODES = "115e6"   # the plan's file size since the 11-08 world (chain4.sh)
CANARY = "f47"


def log(msg: str) -> None:
    free = shutil.disk_usage(ROOT).free / 1e9
    print(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg} (free {free:.0f} GB)", flush=True)


def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, p)


class Paths:
    def __init__(self, release: str, root: Path = ROOT):
        self.release = release
        self.pull = root / "data" / "overture" / release
        self.rel = root / "data" / "place-ids" / "releases" / release
        self.names = root / ".scratch" / "switch" / release / "places"
        self.places = root / ".scratch" / "world-places" / release
        self.world = root / ".scratch" / "planet" / f"world-{release}"
        self.marks = self.world / "switch"


def old_world(root: Path = ROOT) -> Path:
    return root / read_json(root / "data" / "world.json")["world"]


def done(paths: Paths, step: str) -> bool:
    return (paths.marks / f"{step}.done").exists()


def mark(paths: Paths, step: str, info: dict | None = None) -> None:
    write_json(paths.marks / f"{step}.done", {"at": dt.datetime.now().isoformat(timespec="seconds"), **(info or {})})


def run(cmd: list, py: str | Path = SYS_PY) -> None:
    env = dict(os.environ, JAVA_HOME=JAVA_HOME, PYTHONIOENCODING="utf-8")
    cmd = [str(py)] + [str(c) for c in cmd]
    log("run: " + " ".join(cmd))
    t = time.time()
    r = subprocess.run(cmd, cwd=ROOT, env=env)
    if r.returncode:
        raise SystemExit(f"FAILED ({r.returncode}) after {time.time() - t:.0f} s: {' '.join(cmd)}")
    log(f"ended in {time.time() - t:.0f} s")


def step(paths: Paths, name: str, fn, *args) -> None:
    if done(paths, name):
        return
    log(f"step {name}")
    info = fn(*args)
    mark(paths, name, info if isinstance(info, dict) else None)


def city_ids() -> str:
    return ",".join(c["id"] for c in read_json(ROOT / "config" / "cities.json")["cities"])


def cells_of(plan: dict) -> list:
    return [(f["id"], [(c["id"], c["rect"]) for c in f["cells"]], f["bbox"]) for f in plan["files"]]


# --- prepare -----------------------------------------------------------------------------------------------------

def setup_world(p: Paths, old: Path) -> dict:
    """the new world's folder: the old world's node grid, the release's places, a plan with the same files and cells
    (the node grid decides them; the places only fill each cell's parts)"""
    p.world.mkdir(parents=True, exist_ok=True)
    shutil.copy2(old / "nodegrid.json", p.world / "nodegrid.json")
    shutil.copy2(p.places / "places.json", p.world / "places.json")
    run(["tools/world_cells.py", "plan", "--grid", p.world / "nodegrid.json", "--out", p.world, "--cities", city_ids(),
         "--file-nodes", FILE_NODES], PY)
    if cells_of(read_json(old / "plan.json")) != cells_of(read_json(p.world / "plan.json")):
        raise SystemExit("plan: files or cells differ from the old world's: stopped")
    if (old / "cities.poly").exists() and not (p.world / "cities.poly").exists():
        shutil.copy2(old / "cities.poly", p.world / "cities.poly")
    pl = read_json(p.world / "places.json")
    if pl.get("overture") != p.release:
        raise SystemExit(f"{p.world / 'places.json'} is {pl.get('overture')}, not {p.release}")
    return {"places": len(pl["places"]), "files": len(read_json(p.world / "plan.json")["files"])}


def prepare(release: str) -> None:
    p = Paths(release)
    inputs = place_ids.release_inputs(release)
    if inputs.live:
        raise SystemExit(f"{release} is the pinned release: nothing to switch to")
    old = old_world()
    log(f"prepare {release}: the old world {old.relative_to(ROOT)}, the new {p.world.relative_to(ROOT)}")
    p.marks.mkdir(parents=True, exist_ok=True)
    step(p, "pull-world", run, ["tools/overture_pull.py", release, "--world", "--out", p.pull], PY)
    step(p, "pull-outlines", run, ["tools/overture_pull.py", release, "--outlines", "--out", p.pull], PY)
    step(p, "squares", run, ["tools/small_squares.py", "build", "--release", release], PY)
    step(p, "names", run, ["tools/places.py", "build", "--release", release, "--out", p.names,
                           "--report", p.rel / "cities-report.txt"], PY)
    step(p, "places", run, ["tools/world_cells.py", "places", "--release", release, "--out", p.places], PY)
    step(p, "world", setup_world, p, old)
    step(p, "partcache", run, ["tools/world_cells.py", "partcache", "--out", p.world], PY)
    log(f"prepare {release} done: {p.world.relative_to(ROOT)} is ready for the cutover")


# --- cutover -----------------------------------------------------------------------------------------------------

def store_day() -> str:
    return read_json(STORE / "store.json")["generations"][-1]["day"]


def world_day(w: Path) -> str:
    return read_json(w / "world.json")["clock"][:10]


def loop_alive() -> bool:
    if not RUNNING.exists():
        return False
    try:
        pid = int(RUNNING.read_text(encoding="utf-8").split()[-1])
    except (ValueError, IndexError):
        return True
    r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
    return str(pid) in r.stdout


def gate_ok(w: Path, day: str) -> bool:
    for g in (w / "days" / day / "gate.json", w / "counts" / day / "gate1101.json"):
        if g.exists() and read_json(g).get("ok"):
            return True
    return False


def join_days(old: Path, new: Path, before: str) -> int:
    """the old world's days before the seed day, hard-linked into the new world, so the published history walks one
    folder without gaps (world_publish.gated_days): counts/<day>/ and days/<day>/"""
    n = 0
    for sub in ("counts", "days"):
        for d in sorted((old / sub).iterdir()) if (old / sub).is_dir() else []:
            if not d.is_dir() or len(d.name) != 10 or d.name >= before:
                continue
            for f in d.rglob("*"):
                if f.is_file():
                    t = new / sub / d.name / f.relative_to(d)
                    if not t.exists():
                        t.parent.mkdir(parents=True, exist_ok=True)
                        os.link(f, t)
            n += sub == "counts"
    return n


def open_by_part(day_dir: Path) -> dict[str, int]:
    """{part: its open quests} of one counts day (measure 0 summed over quests)"""
    import numpy as np
    meta = read_json(day_dir / "counts.json")
    z = np.load(day_dir / "counts.npz")
    sums = np.bincount(z["part"], weights=z["m"][:, 0], minlength=len(meta["parts"]))
    return {name: int(v) for name, v in zip(meta["parts"], sums.tolist())}


def compare(old: Path, new: Path, day: str) -> dict:
    """old against new at the seed day: the cities (their outlines do not change) and every place both count"""
    a, b = open_by_part(old / "counts" / day), open_by_part(new / "counts" / day)
    both = set(a) & set(b)
    cities = sorted(k for k in both if k.startswith(("osm-", "city:")))
    city_diff = {k: b[k] - a[k] for k in cities if a[k] != b[k]}
    places = [k for k in both if k not in cities]
    moved = sorted(((b[k] - a[k]) / max(a[k], 1), k) for k in places if abs(b[k] - a[k]) > max(10, a[k] // 100))
    out = {"day": day, "cities": len(cities), "cities differing": city_diff, "places in both": len(places),
           "only old (ended)": len(set(a) - set(b)), "only new": len(set(b) - set(a)),
           "places moving over 1%": len(moved), "largest moves": [k for _, k in (moved[:10] + moved[-10:])]}
    return out


def cutover(release: str) -> None:
    p = Paths(release)
    if not done(p, "partcache"):
        raise SystemExit(f"prepare {release} first")
    old = old_world()
    if old == p.world:
        raise SystemExit("the new world is already live")
    if not HOLD.exists():
        HOLD.write_text(f"{dt.datetime.now().isoformat(timespec='seconds')} pid {os.getpid()}: overture_switch "
                        f"cutover {release}: the world is being reseeded; the owner lifts this after adopt\n",
                        encoding="utf-8", newline="\n")
        log("HOLD written")
    if loop_alive():
        raise SystemExit("the world loop is running (RUNNING): wait until it ends its day")
    d = store_day()
    if not done(p, "seed-day"):
        wd = world_day(old)
        if wd != d:
            raise SystemExit(f"the store is at {d}, the old world at {wd}: the loop must finish its day first")
        if not gate_ok(old, d):
            raise SystemExit(f"the old world's day {d} has no passing gate: the loop must finish its day first")
        mark(p, "seed-day", {"day": d})
    day = read_json(p.marks / "seed-day.done")["day"]
    if d != day:
        raise SystemExit(f"the store moved from {day} to {d} during the cutover: the reseed cannot go on")
    log(f"cutover {release} at {day}")
    sys.path.insert(0, str(ROOT / "tools" / "stream"))
    import planet_store_day as PSD
    step(p, "pin", PSD.pins_edit, [f"europe-{day}.osm.pbf"])
    step(p, "storecut", run, ["tools/world_cells.py", "storecut", "--store", STORE, "--out", p.world, "--at", day])
    step(p, "notes", run, ["tools/world_cells.py", "notes", "--out", p.world])
    step(p, "canary", run, ["tools/world_cells.py", "count", "--out", p.world, "--state", "--engines", "1",
                            "--heap-gb", "30", "--only", CANARY, "--give-up-h", "10"], PY)
    step(p, "count", count_all, p)
    step(p, "seed", run, ["tools/stream/world_state.py", "seed", p.world])
    step(p, "counts", run, ["tools/overture_switch.py", "counts-at", p.world, day])
    step(p, "gate", gate, p, day)
    step(p, "join", lambda: {"days": join_days(old, p.world, day)})
    step(p, "compare", lambda: compare(old, p.world, day))
    log(f"cutover {release} done: {p.world.relative_to(ROOT)} seeded at {day}, its gate passed. Next: adopt {release}")


def count_all(p: Paths) -> dict:
    base = ["tools/world_cells.py", "count", "--out", p.world, "--state", "--give-up-h", "10"]
    try:
        run(base + ["--engines", "2", "--heap-gb", "30"], PY)
    except SystemExit as e:
        log(f"{e}; once more with one engine at 40 GB")
        run(base[:-1] + ["4", "--engines", "1", "--heap-gb", "40"], PY)
    plan = read_json(p.world / "plan.json")
    missing = [f["id"] for f in plan["files"] if not (p.world / "files" / f["id"] / "state-done.json").exists()]
    if missing:
        raise SystemExit(f"files without a state: {missing}")
    for f in (p.world / "cut").glob("*.osm.pbf"):
        f.unlink()
    return {"files": len(plan["files"])}


def gate(p: Paths, day: str) -> dict:
    run(["tools/stream/world_gate.py", p.world, day, "--out", p.world / "days" / day])
    g = read_json(p.world / "days" / day / "gate.json")
    if not g.get("ok"):
        raise SystemExit(f"the new world's gate at {day} failed: {p.world / 'days' / day / 'gate.json'}")
    return {"ok": True}


def counts_at(w: Path, day: str) -> None:
    """the seed's counts with the note quests, as each world day counts them (.scratch/planet/notes1101.py)"""
    sys.path.insert(0, str(ROOT / "tools" / "stream"))
    import placesets as P
    import world_day as WD
    meta = read_json(w / "world.json")
    names = meta["quests"]
    t = time.time()
    d = WD.counts_at(w, f"{day}T00:00:00Z", P.PlaceSets(w / "place-sets.json"), names, w / "notes-work")
    if names != meta["quests"]:
        meta["quests"] = names
        (w / "world.json").write_text(json.dumps(meta, indent=1), encoding="utf-8", newline="\n")
    log(f"counts with the note quests in {d}: {time.time() - t:.0f} s")


# --- adopt -------------------------------------------------------------------------------------------------------

def adopt(release: str) -> None:
    p = Paths(release)
    if not done(p, "compare"):
        raise SystemExit(f"cutover {release} first")
    if not HOLD.exists():
        raise SystemExit("no HOLD: adopt flips the world under the HOLD")
    old_rel = place_ids.pinned()
    day = read_json(p.marks / "seed-day.done")["day"]
    log(f"adopt {release} (from {old_rel}), the world seeded at {day}")
    backup = p.rel / "before-adopt"
    live = ROOT / "data" / "place-ids" / "registry.tsv.gz"

    def registry():
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(live, backup / "registry.tsv.gz")
        shutil.copy2(p.rel / "registry.tsv.gz", live)
        for n in ("former-names.tsv",):
            if (p.rel / n).exists():
                shutil.copy2(p.rel / n, live.parent / n)
        reg = place_ids.load(live)
        problems = reg.check()
        if problems:
            raise SystemExit(f"the adopted registry has problems: {problems[:5]}")
        return {"places": len(reg.places)}

    def squares():
        shutil.copy2(ROOT / "config" / "small-squares.json", backup / "small-squares.json")
        shutil.copy2(p.rel / "small-squares.json", ROOT / "config" / "small-squares.json")

    def pull():
        world, kept = ROOT / "data" / "overture" / "world", ROOT / "data" / "overture" / old_rel
        if not kept.exists():
            os.replace(world, kept)
        if not world.exists():
            os.replace(p.pull, world)

    def names():
        docs, kept = ROOT / "docs" / "places", p.rel / "before-adopt" / "places"
        if not kept.exists():
            shutil.copytree(docs, kept)
        shutil.rmtree(docs)
        shutil.copytree(p.names, docs)

    def pin():
        write_json(ROOT / "config" / "places.json", {"overture": release})
        write_json(POINTER, {"world": p.world.relative_to(ROOT).as_posix(), "seeded": day, "overture": release})

    step(p, "adopt-registry", registry)
    step(p, "adopt-squares", squares)
    step(p, "adopt-pull", pull)
    step(p, "adopt-names", names)
    step(p, "adopt-pin", pin)
    log(f"adopt {release} done. Commit data/place-ids, config/places.json, config/small-squares.json, docs/places and "
        f"data/world.json; back up (archive_backup.py --only place-ids). The HOLD stays: the owner lifts it, and the "
        f"first day on {p.world.relative_to(ROOT)} has no way back. Rollback before that day: data/world.json and "
        f"config/places.json back, the registry, squares and name layer from {backup.relative_to(ROOT)}, the pulls renamed.")


def status(release: str) -> str:
    p = Paths(release)
    steps = ["pull-world", "pull-outlines", "squares", "names", "places", "world", "partcache", "seed-day", "pin",
             "storecut", "notes", "canary", "count", "seed", "counts", "gate", "join", "compare", "adopt-registry",
             "adopt-squares", "adopt-pull", "adopt-names", "adopt-pin"]
    lines = [f"{release}: the new world {p.world.relative_to(ROOT)}; live world {old_world().relative_to(ROOT)}"]
    for s in steps:
        m = p.marks / f"{s}.done"
        lines.append(f"  {s:15} {'done ' + read_json(m)['at'] if m.exists() else '-'}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["prepare", "cutover", "adopt", "status", "counts-at"])
    ap.add_argument("release", help="an Overture release, or for counts-at the world folder")
    ap.add_argument("day", nargs="?", help="counts-at only")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if a.cmd == "counts-at":
        counts_at(Path(a.release), a.day)
    elif a.cmd == "prepare":
        prepare(a.release)
    elif a.cmd == "cutover":
        cutover(a.release)
    elif a.cmd == "adopt":
        adopt(a.release)
    else:
        print(status(a.release))
    return 0


if __name__ == "__main__":
    sys.exit(main())
