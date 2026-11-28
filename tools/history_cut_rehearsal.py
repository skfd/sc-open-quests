"""Rehearse release 2's history cut on one region's history clip (journal/2026-11-27-rehearsing-the-history-cut-on-berlin.md).

The world's monthly backfill would cut the planet history file once into the world plan's files with history
(`osmium extract --with-history`, which has no `smart` strategy: complete_ways), then slice each file at a month with
`osmium time-filter` and count it. Today's way slices first and cuts the slice with `-s smart`. This tool does both on
a history clip already on disk and counts them with the same cells, parts, notes and JVM flags:

  A  the clip sliced at T, counted as the region's own whole cities (as backfill_history `months` does): the link to
     the published monthly point
  X  A's slice cut into the plan's files with -s smart (today's order: slice, then cut)
  Y  the clip cut with --with-history into the plan's files in two stages, region then files (as world_cells.cut does
     for a planet), then each file sliced at T (the release-2 order: cut once, then slice)

  python tools/history_cut_rehearsal.py setup   --out DIR --plan PLAN.json --main MAIN --files f4,f113 --bbox w,s,e,n
  python tools/history_cut_rehearsal.py cut     --out DIR --clip CLIP.osh.pbf
  python tools/history_cut_rehearsal.py slice   --out DIR --clip CLIP.osh.pbf --at 2026-09-01T12:00:00Z
  python tools/history_cut_rehearsal.py count   --out DIR --at ... --city berlin --notes NOTES.jsonl [--quests v64.0]
  python tools/history_cut_rehearsal.py compare --out DIR --at ... [--published SNAPSHOT.json]
  python tools/history_cut_rehearsal.py objdiff --out DIR --at ...

MAIN is the main checkout: the plan's cell boundaries and place outlines are copied from it (relative to MAIN), never
linked, and the engine is MAIN's installed one, run by absolute path (no build, no notes re-clip). Docker mounts the
clip's folder read-only. Every step's seconds and bytes go to DIR/timings.json.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JAVA_HOME = r"C:\Program Files\Android\Android Studio\jbr"
IMAGE = "name-ru-repair-osmium"
HEADER = {k: None for k in ("osmosis_replication_timestamp", "osmosis_replication_sequence_number",
                            "osmosis_replication_base_url", "timestamp")}  # null: copied from the input


def rj(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def wj(p: Path, o) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


def rel(p: Path) -> str:
    return p.resolve().relative_to(ROOT).as_posix()


def tag(at: str) -> str:
    return at[:10]


def record(out: Path, step: str, secs: float, **extra) -> None:
    t = out / "timings.json"
    d = rj(t) if t.exists() else {}
    d[step] = {"seconds": round(secs, 1), **extra}
    wj(t, d)
    print(f"{step}: {secs:.1f} s {extra}", flush=True)


def size(*ps: Path) -> int:
    return sum(p.stat().st_size for p in ps)


def docker(out: Path, clipdir: Path, args: list[str], name: str) -> float:
    """osmium in the image, the clip's folder at /in (read-only), DIR at /out. Returns the seconds."""
    safe = "".join(ch if ch.isalnum() else "-" for ch in name)
    cmd = ["docker", "run", "--rm", "--name", f"rehearsal-{safe}-{os.getpid()}","-v", f"{clipdir.resolve()}:/in:ro",
           "-v", f"{out.resolve()}:/out", "--entrypoint", "osmium", IMAGE, *args]
    t = time.time()
    subprocess.run(cmd, check=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    return time.time() - t


def bbox_meets(a, b) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def geo_bbox(p: Path):
    xs, ys = [], []

    def walk(o):
        if isinstance(o, list) and o and isinstance(o[0], (int, float)):
            xs.append(o[0]); ys.append(o[1])
        elif isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            for k, v in o.items():
                if k in ("coordinates", "geometry", "features", "geometries") or isinstance(v, (list, dict)):
                    walk(v)
    walk(rj(p))
    return [min(xs), min(ys), max(xs), max(ys)] if xs else None


# --- setup ---------------------------------------------------------------------------------------

def setup(out: Path, plan_path: Path, main: Path, fids: list[str], box: list[float]) -> None:
    """A plan of only these files and, in each, only the cells meeting box; each cell's parts are the city parts
    and places whose outline meets box. Boundaries and outlines are copied into DIR/geo/."""
    p = rj(plan_path)
    files = [f for f in p["files"] if f["id"] in fids]
    regions = [dict(r, files=[x for x in r["files"] if x in fids]) for r in p["regions"]
               if any(x in fids for x in r["files"])]
    wj(out / "plan.json", {**{k: v for k, v in p.items() if k not in ("files", "regions", "cityParts", "cellZones")},
                           "files": files, "regions": regions, "from": str(plan_path)})
    world = plan_path.parent
    geo = out / "geo"
    kept = Counter()
    for f in files:
        cities = rj(world / "files" / f["id"] / "cities.json")["cities"]
        mine = []
        for c in cities:
            src = main / c["boundary"]
            b = rj(src)["bounds"]
            if not bbox_meets([b["minlon"], b["minlat"], b["maxlon"], b["maxlat"]], box):
                continue
            dst = geo / "cells" / f"{c['id']}.json"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            mine.append({**c, "boundary": rel(dst)})
            parts = rj(world / "files" / f["id"] / "parts" / f"{c['id']}.json")
            keep = []
            for part in parts["parts"]:
                g = main / part["geometry"]
                gb = geo_bbox(g)
                if gb and bbox_meets(gb, box):
                    d = geo / "parts" / Path(part["geometry"]).name
                    d.parent.mkdir(parents=True, exist_ok=True)
                    if not d.exists():
                        shutil.copy2(g, d)
                    keep.append({**part, "geometry": rel(d)})
            kept[c["id"]] = len(keep)
            wj(out / "files" / f["id"] / "parts" / f"{c['id']}.json", {**parts, "parts": keep})
        wj(out / "files" / f["id"] / "cities.json", {"cities": mine})
    print(f"setup: {len(files)} files, cells and parts kept: {dict(kept)}")


# --- cut (Y's first half) ------------------------------------------------------------------------

def extract(out: Path, src_dir: Path, src: str, outputs: list[tuple[str, list]], strategy: str, history: bool,
            step: str) -> None:
    cfg = {"directory": "/out", "extracts": [
        {"output": n, "output_format": "osh.pbf" if history else "pbf", "bbox": b, "output_header": HEADER}
        for n, b in outputs]}
    conf = f"extract-{step}.json"
    wj(out / conf, cfg)
    args = ["extract", "-c", f"/out/{conf}", "-s", strategy, "--overwrite", *(["--with-history"] if history else []),
            f"/in/{src}"]
    secs = docker(out, src_dir, args, step)
    outs = [out / n for n, _ in outputs]
    record(out, step, secs, input_bytes=(src_dir / src).stat().st_size, output_bytes=size(*outs),
           outputs={n: (out / n).stat().st_size for n, _ in outputs})


def cut(out: Path, clip: Path) -> None:
    """Two stages, as world_cells.cut does for a planet: each region from the clip, then its files from the region."""
    p = rj(out / "plan.json")
    by_id = {f["id"]: f for f in p["files"]}
    (out / "hist").mkdir(exist_ok=True)
    extract(out, clip.parent, clip.name, [(f"hist/{r['id']}.osh.pbf", r["bbox"]) for r in p["regions"]],
            "complete_ways", True, "cut-regions")
    for r in p["regions"]:
        extract(out, out, f"hist/{r['id']}.osh.pbf", [(f"hist/{fid}.osh.pbf", by_id[fid]["bbox"]) for fid in r["files"]],
                "complete_ways", True, f"cut-{r['id']}")


# --- slice ---------------------------------------------------------------------------------------

def time_filter(out: Path, src_dir: Path, src: str, at: str, dst: str, step: str) -> None:
    args = ["time-filter", f"/in/{src}", at, "-o", f"/out/{dst}", "-f", "pbf",
            f"--output-header=osmosis_replication_timestamp={at}", "--overwrite"]
    secs = docker(out, src_dir, args, step)
    record(out, step, secs, input_bytes=(src_dir / src).stat().st_size, output_bytes=(out / dst).stat().st_size)


def slice_(out: Path, clip: Path, at: str) -> None:
    d = tag(at)
    p = rj(out / "plan.json")
    (out / d / "Y").mkdir(parents=True, exist_ok=True)
    (out / d / "X").mkdir(parents=True, exist_ok=True)
    time_filter(out, clip.parent, clip.name, at, f"{d}/A.osm.pbf", f"{d} slice A (whole clip)")
    for f in p["files"]:
        time_filter(out, out, f"hist/{f['id']}.osh.pbf", at, f"{d}/Y/{f['id']}.osm.pbf", f"{d} slice Y {f['id']}")
    extract(out, out / d, "A.osm.pbf", [(f"{d}/X/{f['id']}.osm.pbf", f["bbox"]) for f in p["files"]],
            "smart", False, f"{d} cut X (smart, of A)")


# --- count ---------------------------------------------------------------------------------------

def engine(main: Path, args: list[str], tz: str, log: Path, heap_gb: int = 12) -> float:
    bat = main / "engine" / "build" / "install" / "sc-open-quests-engine" / "bin" / "sc-open-quests-engine.bat"
    env = dict(os.environ, JAVA_HOME=JAVA_HOME)
    # world_cells.engine's flags (areaCities 2, the GC pause), the plan's zone
    env["JAVA_OPTS"] = f"-Xmx{heap_gb}g -Dopenquests.areaCities=2 -XX:MaxGCPauseMillis=5000 -Duser.timezone={tz}"
    t = time.time()
    with open(log, "w", encoding="utf-8") as fh:
        r = subprocess.run([str(bat), *args], cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT)
    if r.returncode:
        raise SystemExit(f"engine failed ({r.returncode}): see {log}")
    return time.time() - t


def count(out: Path, main: Path, at: str, city: str, notes: Path, quests: str | None) -> None:
    d = tag(at)
    p = rj(out / "plan.json")
    q = ROOT / "data" / "quests" / f"{quests or newest_quests()}.json"
    qs = rel(q)
    conf = [c for c in rj(ROOT / "config" / "cities.json")["cities"] if c["id"] == city]
    cities = out / f"{city}-cities.json"
    wj(cities, {"cities": conf})
    suffix = f"-{quests}" if quests else ""
    a_out = out / d / f"A{suffix}-count"
    shutil.rmtree(a_out, ignore_errors=True)
    a_out.mkdir(parents=True)
    secs = engine(main, ["count", "--pbf", rel(out / d / "A.osm.pbf"), "--quests", qs, "--cities", rel(cities),
                         "--out", rel(a_out), "--notes", str(notes), "--parts", "config/parts"],
                  conf[0]["timeZone"], a_out / "log.txt")
    record(out, f"{d} count A{suffix}", secs)
    if quests:
        return
    for kind in ("X", "Y"):
        for f in p["files"]:
            fo = out / d / f"{kind}-count" / f["id"]
            shutil.rmtree(fo, ignore_errors=True)
            fo.mkdir(parents=True)
            fd = out / "files" / f["id"]
            secs = engine(main, ["count", "--pbf", rel(out / d / kind / f"{f['id']}.osm.pbf"), "--quests", qs,
                                 "--cities", rel(fd / "cities.json"), "--out", rel(fo), "--notes", str(notes),
                                 "--parts", rel(fd / "parts")], p["timeZone"], fo / "log.txt")
            record(out, f"{d} count {kind} {f['id']}", secs)


def newest_quests() -> str:
    sys.path.insert(0, str(ROOT))
    import run
    return run.newest_quests_file().stem


# --- compare -------------------------------------------------------------------------------------

def snap(d: Path) -> dict:
    return rj(sorted((d / "snapshots").glob("*.json"))[-1])


def leaves(o, pre=()):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from leaves(v, pre + (k,))
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        yield pre, o


def cells_of(out: Path, d: str, kind: str) -> dict:
    """Every number of every cell of the files' snapshots: {(cell, *path): value}."""
    p = rj(out / "plan.json")
    nums = {}
    for f in p["files"]:
        s = snap(out / d / f"{kind}-count" / f["id"])
        for cid, c in s["cities"].items():
            for path, v in leaves(c):
                nums[(cid, *path)] = v
    return nums


def city_quests(c: dict) -> Counter:
    return Counter({q: v["open"] if isinstance(v, dict) else v for q, v in c["quests"].items()})


def compare(out: Path, at: str, published: Path | None, city: str) -> None:
    d = tag(at)
    x, y = cells_of(out, d, "X"), cells_of(out, d, "Y")
    keys = set(x) | set(y)
    diff = sorted(k for k in keys if x.get(k) != y.get(k))
    print(f"== {d}: X (slice, then smart cut) against Y (history cut, then slice): {len(keys):,} numbers, "
          f"{len(diff):,} differ")
    for k in diff[:40]:
        print(f"   {'/'.join(map(str, k))}: X {x.get(k)} Y {y.get(k)}")
    by_part = Counter()
    for kind, nums in (("X", x), ("Y", y)):
        for k, v in nums.items():
            if len(k) == 4 and k[1] == "parts" and k[2] == f"osm-{city}":
                by_part[(kind, k[3])] += v
    a = snap(out / d / "A-count")["cities"][city]
    aq = city_quests(a)
    for kind in ("X", "Y"):
        pq = Counter({q: by_part[(kind, q)] for (k, q) in by_part if k == kind})
        dq = {q: pq[q] - aq[q] for q in set(pq) | set(aq) if pq[q] != aq[q]}
        print(f"== {d}: {kind}'s osm-{city} part summed over the cells against A ({city} whole): "
              f"{sum(pq.values()):,} against {sum(aq.values()):,}; {len(dq)} quests differ, "
              f"sum of |diff| {sum(abs(v) for v in dq.values()):,}")
        for q, v in sorted(dq.items(), key=lambda t: -abs(t[1]))[:10]:
            print(f"   {q}: {v:+,} (A {aq[q]:,})")
    if published:
        pub = rj(published)["cities"][city]
        pq = city_quests(pub)
        dq = {q: aq[q] - pq[q] for q in set(pq) | set(aq) if pq[q] != aq[q]}
        print(f"== {d}: A against the published point {published.name}: {sum(aq.values()):,} against "
              f"{sum(pq.values()):,}; {len(dq)} quests differ, sum of |diff| {sum(abs(v) for v in dq.values()):,}")
        for q, v in sorted(dq.items(), key=lambda t: -abs(t[1]))[:15]:
            print(f"   {q}: {v:+,} (published {pq[q]:,})")
        for k in sorted(set(a["denominators"]) | set(pub["denominators"])):
            if a["denominators"].get(k) != pub["denominators"].get(k):
                print(f"   denominator {k}: A {a['denominators'].get(k)} published {pub['denominators'].get(k)}")
        for alt in sorted((out / d).glob("A-*-count")):
            bq = city_quests(snap(alt)["cities"][city])
            dq = {q: bq[q] - pq[q] for q in set(pq) | set(bq) if pq[q] != bq[q]}
            print(f"== {d}: {alt.name} against the published point: {sum(bq.values()):,}; {len(dq)} quests differ, "
                  f"sum of |diff| {sum(abs(v) for v in dq.values()):,}")
            for q, v in sorted(dq.items(), key=lambda t: -abs(t[1]))[:15]:
                print(f"   {q}: {v:+,} (published {pq[q]:,})")


# --- objdiff -------------------------------------------------------------------------------------

def objdiff(out: Path, at: str) -> None:
    """What the history cut's files hold that the smart cut's do not, and back: osmium diff of X against Y."""
    d = tag(at)
    p = rj(out / "plan.json")
    for f in p["files"]:
        xf, yf = f"/out/{d}/X/{f['id']}.osm.pbf", f"/out/{d}/Y/{f['id']}.osm.pbf"
        res = subprocess.run(["docker", "run", "--rm", "-v", f"{out.resolve()}:/out", "--entrypoint", "osmium", IMAGE,
                              "diff", "-s", "-c", "-f", "opl", "-o", f"/out/{d}/diff-{f['id']}.opl", "--overwrite",
                              xf, yf], capture_output=True, text=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
        print(f"== {d} {f['id']}: osmium diff X Y (exit {res.returncode}: 0 same, 1 differ)\n{res.stdout}{res.stderr}")
        lines = (out / d / f"diff-{f['id']}.opl").read_text(encoding="utf-8").splitlines()
        c = Counter((ln[0], ln[1]) for ln in lines if ln)
        print(f"   lines by (side, type): {dict(c)}  (- only in X, + only in Y, * in both but different)")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["setup", "cut", "slice", "count", "compare", "objdiff"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--main", type=Path, default=Path.home() / "Code" / "sc-open-quests")
    ap.add_argument("--files")
    ap.add_argument("--bbox")
    ap.add_argument("--clip", type=Path)
    ap.add_argument("--at")
    ap.add_argument("--city", default="berlin")
    ap.add_argument("--notes", type=Path)
    ap.add_argument("--quests", help="a registry other than the newest (data/quests/<name>.json): A only")
    ap.add_argument("--published", type=Path)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "setup":
        setup(a.out, a.plan, a.main, a.files.split(","), [float(v) for v in a.bbox.split(",")])
    elif a.cmd == "cut":
        cut(a.out, a.clip)
    elif a.cmd == "slice":
        slice_(a.out, a.clip, a.at)
    elif a.cmd == "count":
        count(a.out, a.main, a.at, a.city, a.notes, a.quests)
    elif a.cmd == "compare":
        compare(a.out, a.at, a.published, a.city)
    else:
        objdiff(a.out, a.at)


if __name__ == "__main__":
    main()
