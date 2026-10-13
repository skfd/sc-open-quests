"""Monthly history backfill from the planet full-history file. Python standard library + Docker.

Geofabrik keeps no old dailies, so past months come from ~/Code/.osm-data/planet/history-<YYMMDD>.osm.pbf:
clip it to Ontario once, then cut one snapshot per month with `osmium time-filter` and count it with the
engine, as run.py counts a Geofabrik extract. The counts use today's quest registry on past data: they
answer "what would this SC version have shown then", not "what did the app of that time show".

  clip     planet history -> .osm-data/ontario-history/ontario-history-<YYMMDD>.osh.pbf (hours, once)
  check    slice at an existing daily extract's replication time, count both, print the differences
  months   slice and count the 1st of each month (12:00Z) into data/backfill/snapshots/, deleting each slice
  recount  recount the published snapshots (all but the newest) with today's engine into data/backfill/recount/
  merge    copy the staged and recounted snapshots into docs/data/snapshots/ (then run `run.py history`)

Slices and staged snapshots live in data/backfill/ (gitignored). The daily pipeline never sees them until merge.
osmium runs in the name-ru-repair-osmium image (osmium-tool 1.18, built by ../name-ru-repair/tools).
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, time as dtime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run  # noqa: E402

PLANET = "history-261005"
HISTORY_DIR = run.OSM_DATA_DIR / "ontario-history"
HISTORY = HISTORY_DIR / f"ontario-{PLANET}.osh.pbf"
PLANET_URL = f"https://planet.openstreetmap.org/pbf/full-history/{PLANET}.osm.pbf"
POLY = HISTORY_DIR / "ontario.poly"  # https://download.geofabrik.de/north-america/canada/ontario.poly
IMAGE = "name-ru-repair-osmium"

BACKFILL = run.ROOT / "data" / "backfill"
STAGED = BACKFILL / "snapshots"

# The scheduled update runs at 13:15 and takes a few minutes; don't start an engine run across it.
QUIET = ((13, 5), (13, 45))


def osmium(script: str) -> None:
    """Run a shell line in the osmium image, with the shared store at /osm and data/backfill at /out."""
    BACKFILL.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "--rm", "--entrypoint", "sh",
           "-v", f"{run.OSM_DATA_DIR}:/osm", "-v", f"{BACKFILL}:/out", IMAGE, "-c", script]
    subprocess.run(cmd, check=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})


def clip() -> None:
    if HISTORY.exists():
        run.log(f"{HISTORY.name} exists")
        return
    part = f"ontario-history/{HISTORY.name}.part"
    run.log(f"clipping planet/{PLANET}.osm.pbf to Ontario (hours)")
    osmium(f"cd /osm && osmium extract --with-history -s complete_ways -p ontario-history/{POLY.name} "
           f"planet/{PLANET}.osm.pbf -f osh.pbf -o {part} --overwrite && mv {part} ontario-history/{HISTORY.name}")


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slice_at(t: datetime) -> tuple[Path, Path]:
    """Ontario as of t, with t as its replication timestamp (the engine's clock), plus a meta file."""
    if not HISTORY.exists():
        raise FileNotFoundError(f"{HISTORY} is missing; run `clip` first")
    stamp = iso(t)
    name = f"ontario-{stamp[:10]}-from-{PLANET}"
    pbf, meta = BACKFILL / f"{name}.osm.pbf", BACKFILL / f"{name}.meta.json"
    if not pbf.exists():
        run.log(f"slicing {HISTORY.name} at {stamp}")
        osmium(f"osmium time-filter /osm/ontario-history/{HISTORY.name} {stamp} -o /out/{pbf.name}.part -f pbf "
               f"--output-header=osmosis_replication_timestamp={stamp} --overwrite && mv /out/{pbf.name}.part /out/{pbf.name}")
    run.write_json(meta, {"region": "ontario", "source_url": PLANET_URL, "file": f"{HISTORY.name}@{stamp}",
                          "replication_timestamp": stamp, "derived_from": f"planet/{PLANET}.osm.pbf"})
    return pbf, meta


def wait_for_quiet() -> None:
    start, end = (dtime(*hm) for hm in QUIET)
    while True:
        if not start <= datetime.now().time() < end:
            return
        run.log("waiting out the scheduled update window")
        time.sleep(300)


@contextlib.contextmanager
def locked():
    """run.pipeline_lock, waiting while another process (say, a second backfill) holds it."""
    while True:
        try:
            with run.pipeline_lock():
                yield
            return
        except RuntimeError as e:
            if "another run holds" not in str(e):
                raise
            time.sleep(20)


def count(pbf: Path, meta: Path, out: Path) -> Path:
    """Run the engine on one extract into out/snapshots/. Returns the snapshot written."""
    wait_for_quiet()
    with locked():
        if run.engine_is_stale():
            run.build_engine()
        before = set((out / "snapshots").glob("*.json"))
        cmd = [str(run.ENGINE_BAT), "count", "--pbf", str(pbf),
               "--quests", str(run.newest_quests_file().relative_to(run.ROOT)),
               "--cities", str(run.CITIES_CONFIG.relative_to(run.ROOT)),
               "--out", str(out), "--source-meta", str(meta)]
        clip = run.notes_clip()  # the newest dump holds every note's history, so it reaches any month
        if clip:
            cmd += ["--notes", str(clip.relative_to(run.ROOT))]
        run.log("running engine: " + " ".join(cmd[1:]))
        subprocess.run(cmd, cwd=run.ROOT, env=run.engine_env(), check=True)
    snaps = sorted((out / "snapshots").glob("*.json"), key=lambda p: p.stat().st_mtime)
    new = [p for p in snaps if p not in before] or snaps[-1:]
    return new[-1]


def diff(a: Path, b: Path, top: int = 25) -> None:
    """Print where snapshot b (a slice) differs from a (a Geofabrik daily), summed over all cities."""
    sa, sb = run.read_json(a), run.read_json(b)
    per_quest: dict[str, list[int]] = {}
    for city, ca in sa["cities"].items():
        cb = sb["cities"].get(city, {"quests": {}})
        for q, va in ca["quests"].items():
            vb = cb["quests"].get(q, {}).get("open", 0)
            per_quest.setdefault(q, [0, 0])
            per_quest[q][0] += va["open"]
            per_quest[q][1] += vb
    total_a = sum(v[0] for v in per_quest.values())
    total_b = sum(v[1] for v in per_quest.values())
    off = sum(abs(v[1] - v[0]) for v in per_quest.values())
    print(f"{a.name}: {total_a} open; {b.name}: {total_b} open; sum of |differences| {off} "
          f"({100 * off / max(total_a, 1):.3f}%)")
    rows = sorted(((v[1] - v[0], q, v[0]) for q, v in per_quest.items() if v[0] != v[1]), key=lambda r: -abs(r[0]))
    for d, q, va in rows[:top]:
        print(f"  {q:40} {va:9} {d:+7}")
    dens = ("taggedNodes", "taggedWays", "highwayKm")
    for city in sorted(sa["cities"]):
        da, db = sa["cities"][city]["denominators"], sb["cities"].get(city, {}).get("denominators", {})
        changed = [f"{k} {da.get(k)} -> {db.get(k)}" for k in dens if da.get(k) != db.get(k)]
        if changed:
            print(f"  {city}: " + ", ".join(changed))


def check(extract: str) -> None:
    pbf = run.OSM_DATA_DIR / run.REGION / f"{extract}.osm.pbf"
    meta = run.extract_meta(pbf)
    t = datetime.fromisoformat(run.read_json(meta)["replication_timestamp"])
    out = BACKFILL / "check"
    shutil.rmtree(out, ignore_errors=True)
    daily = count(pbf, meta, out / "daily")
    s_pbf, s_meta = slice_at(t)
    sliced = count(s_pbf, s_meta, out / "slice")
    diff(daily, sliced)


def month_starts(first: str, last: str, step: int) -> list[date]:
    y, m = map(int, first.split("-"))
    ly, lm = map(int, last.split("-"))
    out = []
    while (y, m) <= (ly, lm):
        out.append(date(y, m, 1))
        m += step
        while m > 12:
            y, m = y + 1, m - 12
    return out


def months(first: str, last: str, step: int, keep: bool) -> None:
    have = {p.stem for p in STAGED.glob("*.json")} | {p.stem for p in (run.DATA_DIR / "snapshots").glob("*.json")}
    for d in month_starts(first, last, step):
        if d.isoformat() in have:
            run.log(f"{d} already counted")
            continue
        t0 = time.monotonic()
        pbf, meta = slice_at(datetime(d.year, d.month, 1, 12, tzinfo=timezone.utc))
        snap = count(pbf, meta, BACKFILL)
        if not keep:
            pbf.unlink()
        run.log(f"{snap.name} in {time.monotonic() - t0:.0f} s")


RECOUNT = BACKFILL / "recount"


def recount() -> None:
    """Recount the published snapshots counted by an older engine, so the series has no seam where the
    history months meet them: from their Geofabrik extract if the store still has it, otherwise from a
    history slice at their replication time (equal to the extract, see DESIGN.md)."""
    history_end = datetime.fromisoformat(run.read_json(HISTORY.with_name(HISTORY.name + ".meta.json"))
                                         ["replication_timestamp"])
    by_sha = {run.read_json(m).get("sha256"): (p, m) for p, m in run.dated_extracts()}
    snaps = sorted((run.DATA_DIR / "snapshots").glob("*.json"))
    newest = snaps[-1].name
    for p in snaps:
        s = run.read_json(p)
        if p.name == newest or (RECOUNT / "snapshots" / p.name).exists():
            continue
        extract = by_sha.get(s["source"]["sha256"])
        t = datetime.fromisoformat(s["asOf"].replace("Z", "+00:00"))
        if extract:
            count(*extract, RECOUNT)
        elif t <= history_end:
            pbf, meta = slice_at(t)
            count(pbf, meta, RECOUNT)
            pbf.unlink()
        else:
            run.log(f"{p.name}: extract gone and after the history file; left as is")


def merge() -> None:
    """Staged months that are not published yet, and every recount (replacing the published one)."""
    dst = run.DATA_DIR / "snapshots"
    for p in sorted(STAGED.glob("*.json")):
        if not (dst / p.name).exists():
            shutil.copy2(p, dst / p.name)
            run.log(f"merged {p.name}")
    for p in sorted((RECOUNT / "snapshots").glob("*.json")):
        shutil.copy2(p, dst / p.name)
        run.log(f"replaced {p.name} with its recount")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("clip")
    c = sub.add_parser("check")
    c.add_argument("--extract", default="ontario-2026-08-22", help="a dated extract in the shared store")
    m = sub.add_parser("months")
    m.add_argument("--from", dest="first", default="2017-01")
    m.add_argument("--to", dest="last", default="2026-10")  # the planet history ends 2026-10-05
    m.add_argument("--step", type=int, default=1, help="months between slices (12 = a yearly spine)")
    m.add_argument("--keep", action="store_true", help="keep the slices")
    sub.add_parser("recount")
    sub.add_parser("merge")
    a = ap.parse_args(argv)
    if a.cmd == "clip":
        clip()
    elif a.cmd == "recount":
        recount()
    elif a.cmd == "check":
        check(a.extract)
    elif a.cmd == "months":
        months(a.first, a.last, a.step, a.keep)
    else:
        merge()
    return 0


if __name__ == "__main__":
    sys.exit(main())
