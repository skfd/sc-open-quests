"""Monthly history backfill from the planet full-history file. Python standard library + Docker.

Geofabrik keeps no old dailies, so past months come from ~/Code/.osm-data/planet/history-<YYMMDD>.osm.pbf:
clip it to a region once, then cut one snapshot per month with `osmium time-filter` and count it with the
engine, as run.py counts a Geofabrik extract. The counts use today's quest registry on past data: they
answer "what would this SC version have shown then", not "what did the app of that time show". Every
subcommand takes --region (config/regions.json; default ontario); `clip` takes several and reads the
planet once for all of them.

  clip     planet history -> .osm-data/<region>-history/<region>-history-<YYMMDD>.osh.pbf (an hour, once)
  check    slice at an existing daily extract's replication time, count both, print the differences
  months   slice and count the 1st of each month (12:00Z) into data/backfill/<region>/snapshots/, deleting
           each slice
  recount  recount the published snapshots (all but the newest) with today's engine into
           data/backfill/<region>/recount/
  merge    copy the staged and recounted snapshots into docs/data/<region>/snapshots/ (then run
           `run.py history`)

Slices and staged snapshots live in data/backfill/<region>/ (gitignored). The daily pipeline never sees
them until merge. osmium runs in the name-ru-repair-osmium image (osmium-tool 1.18, built by
../name-ru-repair/tools).
"""
from __future__ import annotations

import argparse
import contextlib
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
PLANET_URL = f"https://planet.openstreetmap.org/pbf/full-history/{PLANET}.osm.pbf"
IMAGE = "name-ru-repair-osmium"

BACKFILL = run.ROOT / "data" / "backfill"

# The scheduled update runs at 13:15 and takes a few minutes; don't start an engine run across it.
QUIET = ((12, 55), (13, 50))  # 12 regions and a 3.4 GB download since 2026-10-21; an Ontario month takes 5 min


class Region:
    """A region of config/regions.json, and where its history file, slices and staged snapshots go."""

    def __init__(self, region_id: str):
        regions = {r["id"]: r for r in run.regions()}
        if region_id not in regions:
            raise SystemExit(f"no region {region_id} in {run.REGIONS_CONFIG.name}")
        self.id = region_id
        self.config = regions[region_id]
        self.history_dir = run.OSM_DATA_DIR / f"{region_id}-history"
        self.history = self.history_dir / f"{region_id}-{PLANET}.osh.pbf"
        self.poly = self.history_dir / f"{region_id}.poly"  # a copy of config's: osmium sees only /osm
        self.backfill = BACKFILL / region_id
        self.staged = self.backfill / "snapshots"
        self.recount = self.backfill / "recount"
        self.published = run.DATA_DIR / region_id / "snapshots"


def osmium(script: str) -> None:
    """Run a shell line in the osmium image, with the shared store at /osm and data/backfill at /out."""
    BACKFILL.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "--rm", "--entrypoint", "sh",
           "-v", f"{run.OSM_DATA_DIR}:/osm", "-v", f"{BACKFILL}:/out", IMAGE, "-c", script]
    subprocess.run(cmd, check=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})


def clip(regions: list[Region]) -> None:
    """Clip the planet history to each region's poly, in one pass over the planet for all of them."""
    todo = [r for r in regions if not r.history.exists()]
    for r in regions:
        if r not in todo:
            run.log(f"{r.history.name} exists")
    if todo:
        config = {"directory": "/osm", "extracts": []}
        for r in todo:
            r.history_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(run.ROOT / r.config["poly"], r.poly)
            config["extracts"].append({
                "output": f"{r.history_dir.name}/{r.history.name}.part", "output_format": "osh.pbf",
                "polygon": {"file_name": f"/osm/{r.history_dir.name}/{r.poly.name}", "file_type": "poly"}})
        name = "clip-" + "-".join(r.id for r in todo) + ".osmium.json"
        run.write_json(run.OSM_DATA_DIR / name, config)
        moves = " && ".join(f"mv {r.history_dir.name}/{r.history.name}.part {r.history_dir.name}/{r.history.name}"
                            for r in todo)
        run.log(f"clipping planet/{PLANET}.osm.pbf to {', '.join(r.id for r in todo)} (an hour or more)")
        osmium(f"cd /osm && osmium extract --with-history -s complete_ways -c {name} planet/{PLANET}.osm.pbf "
               f"--overwrite && {moves} && rm {name}")
    for r in regions:
        meta = r.history.with_name(r.history.name + ".meta.json")
        if not meta.exists():
            planet = run.read_json(run.OSM_DATA_DIR / "planet" / f"{PLANET}.meta.json")
            run.write_json(meta, {
                "made_by": f"osmium extract --with-history -s complete_ways -p {r.poly.name} (Geofabrik's poly), "
                           "sc-open-quests tools/backfill_history.py clip",
                "region": r.history_dir.name, "data_date": planet.get("data_date"),
                "replication_timestamp": planet.get("replication_timestamp"),
                "derived_from": f"planet/{PLANET}.osm.pbf", "bytes": r.history.stat().st_size,
                "made_at": datetime.now(timezone.utc).isoformat()})


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slice_at(r: Region, t: datetime) -> tuple[Path, Path]:
    """The region as of t, with t as its replication timestamp (the engine's clock), plus a meta file."""
    if not r.history.exists():
        raise FileNotFoundError(f"{r.history} is missing; run `clip` first")
    stamp = iso(t)
    name = f"{r.id}-{stamp[:10]}-from-{PLANET}"
    pbf, meta = r.backfill / f"{name}.osm.pbf", r.backfill / f"{name}.meta.json"
    if not pbf.exists():
        run.log(f"slicing {r.history.name} at {stamp}")
        r.backfill.mkdir(parents=True, exist_ok=True)
        out = f"/out/{r.id}/{pbf.name}"
        osmium(f"osmium time-filter /osm/{r.history_dir.name}/{r.history.name} {stamp} -o {out}.part -f pbf "
               f"--output-header=osmosis_replication_timestamp={stamp} --overwrite && mv {out}.part {out}")
    run.write_json(meta, {"region": r.id, "source_url": PLANET_URL, "file": f"{r.history.name}@{stamp}",
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


def count(r: Region, pbf: Path, meta: Path, out: Path) -> Path:
    """Run the engine on one extract of the region into out/snapshots/. Returns the snapshot written."""
    wait_for_quiet()
    with locked():
        if run.engine_is_stale():
            run.build_engine()
        before = set((out / "snapshots").glob("*.json"))
        cmd = [str(run.ENGINE_BAT), "count", "--pbf", str(pbf),
               "--quests", str(run.newest_quests_file().relative_to(run.ROOT)),
               "--cities", str(run.region_cities(r.config).relative_to(run.ROOT)),
               "--out", str(out), "--source-meta", str(meta)]
        clip = run.notes_clip(r.config)  # the newest dump holds every note's history, so it reaches any month
        if clip:
            cmd += ["--notes", str(clip.relative_to(run.ROOT))]
        cmd += ["--grid", str(out / "grid")]
        run.log("running engine: " + " ".join(cmd[1:]))
        subprocess.run(cmd, cwd=run.ROOT, env=run.engine_env(r.config["timeZone"]), check=True)
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


def check(r: Region, extract: str | None) -> None:
    if extract:
        pbf = run.OSM_DATA_DIR / r.id / f"{extract}.osm.pbf"
        meta = run.extract_meta(pbf)
    else:
        pbf, meta = run.dated_extracts(r.config)[0]
    t = datetime.fromisoformat(run.read_json(meta)["replication_timestamp"])
    out = r.backfill / "check"
    shutil.rmtree(out, ignore_errors=True)
    daily = count(r, pbf, meta, out / "daily")
    s_pbf, s_meta = slice_at(r, t)
    sliced = count(r, s_pbf, s_meta, out / "slice")
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


def months(r: Region, first: str, last: str, step: int, keep: bool) -> None:
    have = {p.stem for p in r.staged.glob("*.json")} | {p.stem for p in r.published.glob("*.json")}
    for d in month_starts(first, last, step):
        if d.isoformat() in have:
            run.log(f"{r.id} {d} already counted")
            continue
        t0 = time.monotonic()
        pbf, meta = slice_at(r, datetime(d.year, d.month, 1, 12, tzinfo=timezone.utc))
        snap = count(r, pbf, meta, r.backfill)
        if not keep:
            pbf.unlink()
        run.log(f"{r.id} {snap.name} in {time.monotonic() - t0:.0f} s")


def recount(r: Region) -> None:
    """Recount the published snapshots counted by an older engine, so the series has no seam where the
    history months meet them: from their Geofabrik extract if the store still has it, otherwise from a
    history slice at their replication time (equal to the extract, see DESIGN.md)."""
    history_end = datetime.fromisoformat(run.read_json(r.history.with_name(r.history.name + ".meta.json"))
                                         ["replication_timestamp"])
    by_sha = {run.read_json(m).get("sha256"): (p, m) for p, m in run.dated_extracts(r.config)}
    snaps = sorted(r.published.glob("*.json"))
    newest = snaps[-1].name
    for p in snaps:
        s = run.read_json(p)
        if p.name == newest or (r.recount / "snapshots" / p.name).exists():
            continue
        extract = by_sha.get(s["source"]["sha256"])
        t = datetime.fromisoformat(s["asOf"].replace("Z", "+00:00"))
        if extract:
            count(r, *extract, r.recount)
        elif t <= history_end:
            pbf, meta = slice_at(r, t)
            count(r, pbf, meta, r.recount)
            pbf.unlink()
        else:
            run.log(f"{r.id} {p.name}: extract gone and after the history file; left as is")


def merge(r: Region) -> None:
    """Staged months that are not published yet, and every recount (replacing the published one)."""
    dst = r.published
    dst.mkdir(parents=True, exist_ok=True)
    for p in sorted(r.staged.glob("*.json")):
        if not (dst / p.name).exists():
            shutil.copy2(p, dst / p.name)
            run.log(f"merged {r.id} {p.name}")
    for p in sorted((r.recount / "snapshots").glob("*.json")):
        shutil.copy2(p, dst / p.name)
        run.log(f"replaced {r.id} {p.name} with its recount")
    # the tile grids (heatmaps) of both; they stay out of git, in data/grid/<region>/
    grid = run.GRID_DIR / r.id
    for p in sorted((r.backfill / "grid").glob("*.json.gz")) + sorted((r.recount / "grid").glob("*.json.gz")):
        grid.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, grid / p.name)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    cl = sub.add_parser("clip")
    cl.add_argument("--region", dest="regions", action="append", help="repeatable; default ontario")
    c = sub.add_parser("check")
    c.add_argument("--extract", help="a dated extract in the shared store (default: the region's oldest)")
    m = sub.add_parser("months")
    m.add_argument("--from", dest="first", default="2017-01")
    m.add_argument("--to", dest="last", default="2026-10")  # the planet history ends 2026-10-05
    m.add_argument("--step", type=int, default=1, help="months between slices (12 = a yearly spine)")
    m.add_argument("--keep", action="store_true", help="keep the slices")
    rc = sub.add_parser("recount")
    mg = sub.add_parser("merge")
    for p in (c, m, rc, mg):
        p.add_argument("--region", default="ontario")
    a = ap.parse_args(argv)
    if a.cmd == "clip":
        clip([Region(r) for r in a.regions or ["ontario"]])
        return 0
    r = Region(a.region)
    if a.cmd == "recount":
        recount(r)
    elif a.cmd == "check":
        check(r, a.extract)
    elif a.cmd == "months":
        months(r, a.first, a.last, a.step, a.keep)
    else:
        merge(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
