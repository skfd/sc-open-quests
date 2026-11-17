"""The world day rehearsed on the Europe clip (DESIGN.md, "Release 1: the world day": steps 2-6 held against a
clip-sized store first). Rerunnable: every stage skips what is done.

  python tools/stream/world_europe_r1.py setup        grid, plan, the clip store at 11-09, the node index, the seed
  python tools/stream/world_europe_r1.py days [N]     days 11-10.. (diffs 5172..), each by world_day.run, then checked
  python tools/stream/world_europe_r1.py oracle D     the whole count of the plan on the Europe clip of day D

Out dir: .scratch/r1/eu/ (W = world/, the stream's state; store/, the clip store; nodes/, the node index;
oracle/<D>/, each day's whole count; days/<D>/, each day's work and check). Heap: HEAP_GB (8 by default, 30 once the
machine is free: a cell file is cut to about 10M nodes so 8 GB is enough).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "stream"))

OUT = ROOT / ".scratch" / "r1" / "eu"
W = OUT / "world"
STORE = OUT / "store"
NODES = OUT / "nodes"
EUROPE = Path.home() / "Code" / ".osm-data" / "europe"
POLYGON = EUROPE / "polygon.geojson"
DIFFS = ROOT / ".scratch" / "planet" / "diffs-keep"
VENV_PY = ROOT / ".scratch" / "overture" / ".venv" / "Scripts" / "python.exe"
EXE = ROOT / "tilestore" / "target" / "release" / "tilestore.exe"
ENGINE = ROOT / "engine" / "build" / "install" / "sc-open-quests-engine" / "bin" / "sc-open-quests-engine.bat"
SEED_DAY = "2026-11-09"
FIRST_DIFF = 5172  # 11-09 -> 11-10
CITIES = ("amsterdam,antwerpen,athens,barcelona,bratislava,budapest,dublin,goteborg,helsinki,istanbul,kobenhavn,"
          "krakow,kyiv,lisboa,london-gb,milano,minsk,moscow,munchen,oslo,paris,praha,riga,salzburg,sofia,stockholm,"
          "toulouse,vilnius,warszawa,wien,zagreb,zurich")
FILE_NODES, CELL_NODES = 10e6, 5e6
HEAP_GB = int(os.environ.get("HEAP_GB", "8"))


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def clip(day: str) -> Path:
    return EUROPE / f"europe-{day}.osm.pbf"


def sh(args, **kw):
    log(" ".join(str(a) for a in args))
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True, **kw)


def world_cells(*args, py=sys.executable):
    sh([py, ROOT / "tools" / "world_cells.py", *args])


def plan_into(d: Path):
    """the plan's files and cells (and their parts) for another world dir: plan.json copied, files/<f>/cities.json and
    parts/ hard-linked (the counts write their own files beside them); nodegrid and places stay W's"""
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(W / "plan.json", d / "plan.json")
    for f in json.loads((W / "plan.json").read_text(encoding="utf-8"))["files"]:
        src, dst = W / "files" / f["id"], d / "files" / f["id"]
        (dst / "parts").mkdir(parents=True, exist_ok=True)
        if not (dst / "cities.json").exists():
            os.link(src / "cities.json", dst / "cities.json")
        for p in (src / "parts").glob("*.json"):
            if not (dst / "parts" / p.name).exists():
                os.link(p, dst / "parts" / p.name)
        # the seed's notes clips: the same dump on both sides (a newer one may arrive between days)
        if (src / "notes.jsonl").exists() and not (dst / "notes.jsonl").exists():
            os.link(src / "notes.jsonl", dst / "notes.jsonl")
    if (W / "notes.done").exists() and not (d / "notes.done").exists():
        (d / "notes.done").write_text("the seed's clips, linked\n")


def count_world(d: Path, store: Path, day: str):
    """the plan counted whole at `day` from `store` (at that day): storecut, notes, count --state with parts"""
    if not (d / "cut" / "storecut.json").exists() or len(list((d / "cut").glob("*.osm.pbf"))) < len(
            json.loads((d / "plan.json").read_text(encoding="utf-8"))["files"]):
        world_cells("storecut", "--store", store, "--out", d, "--at", day)
    if not (d / "notes.done").exists():
        world_cells("notes", "--out", d)
        (d / "notes.done").write_text("done\n")
    world_cells("count", "--out", d, "--engines", "1", "--heap-gb", str(HEAP_GB), "--state", "--give-up-h", "4")


def setup():
    OUT.mkdir(parents=True, exist_ok=True)
    W.mkdir(parents=True, exist_ok=True)
    c0 = clip(SEED_DAY)
    if not (W / "nodegrid.json").exists():
        env = dict(os.environ, JAVA_OPTS="-Xmx6g", JAVA_HOME=r"C:\Program Files\Android\Android Studio\jbr")
        sh([ENGINE, "nodegrid", "--pbf", c0, "--out", W / "nodegrid.json.part", "--step", "0.1"], env=env)
        (W / "nodegrid.json.part").rename(W / "nodegrid.json")
    if not (W / "places.json").exists():  # the world's places as parts (their geometry stays under world-places)
        os.link(ROOT / ".scratch" / "world-places" / "world" / "places.json", W / "places.json")
    if not (W / "plan.json").exists():
        world_cells("plan", "--grid", W / "nodegrid.json", "--out", W, "--cities", CITIES,
                    "--file-nodes", str(FILE_NODES), "--cell-nodes", str(CELL_NODES), py=VENV_PY)
    if not (STORE / "store.json").exists():
        sh([EXE, "cut", "--pbf", c0, "--out", STORE, "--day", SEED_DAY])
    if not (NODES / "nodes.idx").exists():
        import stream as S
        NODES.mkdir(parents=True, exist_ok=True)
        S.nodes(c0, NODES)
    count_world(W, STORE, SEED_DAY)
    if not (W / "world.json").exists():
        import world_state as WS
        WS.seed_w(W)
    # day 0: the seed counted through the stream's own counting (rows, place sets, note quests by the engine) and
    # checked against the seed count's own snapshots: what every later check stands on
    d0 = OUT / "days" / SEED_DAY
    if not (d0 / "check.json").exists():
        import placesets as P
        import world_day as WD
        meta = json.loads((W / "world.json").read_text(encoding="utf-8"))
        names = meta["quests"]
        WD.counts_at(W, meta["clock"], P.PlaceSets(W / "place-sets.json"), names, d0 / "notes", ENGINE, HEAP_GB)
        meta["quests"] = names
        (W / "world.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        WD.check(W, W, d0, log=log)
    log("setup done")


def oracle(day: str) -> Path:
    """the whole count of day D: a fresh clip store cut from D's clip, the plan counted from it"""
    d = OUT / "oracle" / day
    st = d / "store"
    if not (st / "store.json").exists():
        sh([EXE, "cut", "--pbf", clip(day), "--out", st, "--day", day])
    plan_into(d)
    count_world(d, st, day)
    return d


def days(n: int):
    import world_day as WD
    meta = json.loads((W / "world.json").read_text(encoding="utf-8"))
    for k in range(n):
        seq = FIRST_DIFF + k
        diff = DIFFS / f"{seq}.osc.gz"
        state = (DIFFS / f"{seq}.state.txt").read_text()
        today = state.split("timestamp=")[1].split()[0].replace("\\:", ":")
        day = today[:10]
        prev = meta["clock"][:10]
        if diff.name in meta["applied"]:
            log(f"{diff.name} ({day}) applied before")
        else:
            WD.run(W, STORE, diff, today, nodes=NODES, before_clip=clip(prev), polygon=POLYGON,
                   work=OUT / "days" / day, heap_gb=HEAP_GB, engine=ENGINE, log=log)
            meta = json.loads((W / "world.json").read_text(encoding="utf-8"))
        o = oracle(day)
        WD.check(W, o, OUT / "days" / day, log=log)


def main():
    cmd = sys.argv[1]
    if cmd == "setup":
        setup()
    elif cmd == "days":
        days(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
    elif cmd == "oracle":
        oracle(sys.argv[2])


if __name__ == "__main__":
    main()
