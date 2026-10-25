"""Monthly history backfill from the planet full-history file. Python standard library + Docker.

Geofabrik keeps no old dailies, so past months come from the planet history file in
~/Code/.osm-data/planet/: history-<YYMMDD>.osm.pbf as the planet site publishes it, or history-<YYMMDD>.osh.pbf,
the one `osm-extracts fetch planet-history` keeps current with replication diffs. Clip it to a region once, then cut one snapshot per month with `osmium time-filter` and count it with the
engine, as run.py counts a Geofabrik extract. The counts use today's quest registry on past data: they
answer "what would this SC version have shown then", not "what did the app of that time show". Every
subcommand takes --region (config/regions.json; default ontario); `clip` takes several and reads the
planet once for all of them.

  clip     planet history -> .osm-data/<region>-history/<region>-history-<YYMMDD>.osh.pbf (an hour, once)
  check    slice at an existing daily extract's replication time, count both, print the differences
  months   slice and count the 1st of each month (12:00Z) into data/backfill/<region>/snapshots/, deleting
           each slice
  recount  recount the archived snapshots (all but the newest) with today's engine into
           data/backfill/<region>/recount/
  merge    copy the staged and recounted snapshots into data/archive/<region>/snapshots/ (then run
           `run.py history`, which publishes each region's newest)

Every subcommand also takes --planet history-<YYMMDD> (default: the newest history-<YYMMDD>.osm.pbf or .osh.pbf
in the store's planet/ folder, by date); clips, slices and their metas carry its name, so a newer history file
means new clips. `months --to` defaults to the last month whose 1st, 12:00Z, the history file reaches.
`run.py weekly` runs clip, months and a slice at the history file's own timestamp for the regions with
"cadence": "weekly" (weekly(), below).

Slices and staged snapshots live in data/backfill/<region>/ (gitignored). The daily pipeline never sees
them until merge. osmium runs in the name-ru-repair-osmium image (osmium-tool 1.18, built by
../name-ru-repair/tools).
"""
from __future__ import annotations

import argparse
import contextlib
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run  # noqa: E402

# The planet full-history file, "history-<YYMMDD>" in the store's planet/ folder; set by set_planet()
# (--planet, default the newest there) before any Region is made. PLANET_FILE is its file name: .osm.pbf for
# the dump the planet site publishes (PLANET_URL is where it came from), .osh.pbf for one osm-extracts
# brought up to date with diffs (no URL; PLANET_DERIVED_FROM, from its meta, says what it was made from).
PLANET = ""
PLANET_FILE = ""
PLANET_URL: str | None = ""
PLANET_DERIVED_FROM = None
HISTORY_FILE = re.compile(r"(history-\d{6})\.(osm|osh)\.pbf")
FIRST_MONTH = "2017-01"  # the monthly history starts here (DESIGN.md, "Monthly history")
IMAGE = "name-ru-repair-osmium"

BACKFILL = run.ROOT / "data" / "backfill"

# The scheduled update runs at 13:15 and takes a few minutes; don't start an engine run across it, nor a
# longer step (the weekly job's planet clip) that would still run then.
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
        self.history_meta = self.history.with_name(self.history.name + ".meta.json")
        self.poly = self.history_dir / f"{region_id}.poly"  # a copy of config's: osmium sees only /osm
        self.backfill = BACKFILL / region_id
        self.staged = self.backfill / "snapshots"
        self.recount = self.backfill / "recount"
        self.published = run.ARCHIVE_DIR / region_id / "snapshots"  # every snapshot, not only docs/data's newest


def planet_files(planet_dir: Path | None = None) -> dict[str, str]:
    """The planet history files in the store's planet/ folder: {"history-<YYMMDD>": file name}. Of a date
    present under both suffixes, the .osh.pbf (osm-extracts' own) wins."""
    planet_dir = planet_dir or run.OSM_DATA_DIR / "planet"
    found: dict[str, str] = {}
    for p in sorted(planet_dir.glob("history-*.pbf")):
        m = HISTORY_FILE.fullmatch(p.name)
        if m and (m.group(1) not in found or m.group(2) == "osh"):
            found[m.group(1)] = p.name
    return found


def newest_planet(planet_dir: Path | None = None) -> str:
    """The newest planet history file in the shared store, as "history-<YYMMDD>" (the name sorts by date)."""
    planet_dir = planet_dir or run.OSM_DATA_DIR / "planet"
    files = planet_files(planet_dir)
    if not files:
        raise SystemExit(f"no history-<YYMMDD>.osm.pbf or .osh.pbf in {planet_dir}; pass --planet")
    return max(files)


def planet_meta() -> dict:
    """planet/<PLANET>.meta.json, or {} once the file is retired (its clips still slice)."""
    path = run.OSM_DATA_DIR / "planet" / f"{PLANET}.meta.json"
    return run.read_json(path) if path.exists() else {}


def set_planet(name: str | None) -> str:
    """Use this planet history file (a name, history-261005, or its file name); None: the newest."""
    global PLANET, PLANET_FILE, PLANET_URL, PLANET_DERIVED_FROM
    if name:
        m = HISTORY_FILE.fullmatch(Path(name).name)
        PLANET = m.group(1) if m else Path(name).name
    else:
        PLANET = newest_planet()
    PLANET_FILE = planet_files().get(PLANET, f"{PLANET}.osm.pbf")
    PLANET_DERIVED_FROM = planet_meta().get("derived_from")
    original = PLANET_FILE.endswith(".osm.pbf") and not PLANET_DERIVED_FROM
    PLANET_URL = f"https://planet.openstreetmap.org/pbf/full-history/{PLANET}.osm.pbf" if original else None
    return PLANET


def planet_timestamp(r: Region | None = None) -> datetime:
    """How far the history file reaches: its replication timestamp, from the planet's meta, else (the
    planet file retired) from the region's clip."""
    stamp = planet_meta().get("replication_timestamp")
    if not stamp and r is not None and r.history_meta.exists():
        stamp = run.read_json(r.history_meta).get("replication_timestamp")
    if not stamp:
        raise SystemExit(f"no replication_timestamp for {PLANET}: planet/{PLANET}.meta.json is missing")
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def last_month(t: datetime) -> str:
    """"YYYY-MM" of the last month whose 1st, 12:00 UTC (a monthly slice's time), is not after t."""
    y, m = t.year, t.month
    if t < datetime(y, m, 1, 12, tzinfo=timezone.utc):
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return f"{y:04d}-{m:02d}"


def osmium(script: str) -> None:
    """Run a shell line in the osmium image, with the shared store at /osm and data/backfill at /out. Like
    the engine, it waits while memory is busy (run.engine_heap_gb: the owner's rule for heavy jobs)."""
    run.engine_heap_gb()
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
        run.log(f"clipping planet/{PLANET_FILE} to {', '.join(r.id for r in todo)} (an hour or more)")
        osmium(f"cd /osm && osmium extract --with-history -s complete_ways -c {name} planet/{PLANET_FILE} "
               f"--overwrite && {moves} && rm {name}")
    for r in regions:
        if not r.history_meta.exists():
            planet = run.read_json(run.OSM_DATA_DIR / "planet" / f"{PLANET}.meta.json")
            stamp = planet.get("replication_timestamp")
            run.write_json(r.history_meta, {
                "made_by": f"osmium extract --with-history -s complete_ways -p {r.poly.name} (Geofabrik's poly), "
                           "sc-open-quests tools/backfill_history.py clip",
                "region": r.history_dir.name, "data_date": planet.get("data_date") or (stamp or "")[:10] or None,
                "replication_timestamp": stamp,
                **({"replication_sequence": planet["replication_sequence"]} if "replication_sequence" in planet else {}),
                "derived_from": f"planet/{PLANET_FILE}",
                **({"planet_derived_from": PLANET_DERIVED_FROM} if PLANET_DERIVED_FROM else {}),
                "bytes": r.history.stat().st_size, "made_at": datetime.now(timezone.utc).isoformat()})


def prune_clips(r: Region) -> None:
    """Delete the region's clips of older planet history files: the current one holds all they do."""
    for old in r.history_dir.glob(f"{r.id}-history-*.osh.pbf"):
        if old != r.history and HISTORY_FILE.fullmatch(old.name.removeprefix(f"{r.id}-")):
            run.log(f"deleting {old.name}, superseded by {r.history.name}")
            old.unlink()
            old.with_name(old.name + ".meta.json").unlink(missing_ok=True)


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
                          "replication_timestamp": stamp, "derived_from": f"planet/{PLANET_FILE}",
                          **({"planet_derived_from": PLANET_DERIVED_FROM} if PLANET_DERIVED_FROM else {})})
    return pbf, meta


def in_quiet(now: datetime, ahead_minutes: int = 0) -> bool:
    """True if now (local time) falls in the scheduled update's window, or ahead_minutes before it."""
    now = now.replace(tzinfo=None)
    start, end = (datetime.combine(now.date(), dtime(*hm)) for hm in QUIET)
    return start - timedelta(minutes=ahead_minutes) <= now < end


def wait_for_quiet(ahead_minutes: int = 0) -> None:
    """Wait out the scheduled update's window; with ahead_minutes, also a step that long would reach it."""
    while True:
        if not in_quiet(datetime.now(), ahead_minutes):
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
        subprocess.run(cmd, cwd=run.ROOT, env=run.engine_env(r.config["timeZone"], heap=True), check=True)
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
        pbf = run.OSM_DATA_DIR / run.region_extract(r.config) / f"{extract}.osm.pbf"
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


def counted_dates(r: Region) -> set[str]:
    """The dates the region has a snapshot of, staged or in the archive."""
    return {p.stem for p in r.staged.glob("*.json")} | {p.stem for p in r.published.glob("*.json")}


def months(r: Region, first: str, last: str, step: int, keep: bool) -> None:
    have = counted_dates(r)
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


def count_at(r: Region, t: datetime) -> Path | None:
    """Slice the region at t, count it into data/backfill/<region>/snapshots/ and delete the slice; None
    (and nothing done) if the region already has a snapshot of t's date in its time zone."""
    day = t.astimezone(ZoneInfo(r.config["timeZone"])).date().isoformat()
    if day in counted_dates(r):
        run.log(f"{r.id} {day} already counted")
        return None
    pbf, meta = slice_at(r, t)
    snap = count(r, pbf, meta, r.backfill)
    pbf.unlink()
    run.log(f"{r.id} {snap.name}: the history file at {iso(t)}")
    return snap


def weekly(region_ids: list[str]) -> datetime:
    """The weekly regions' counting from the newest planet history file: clip them all in one pass (their
    older clips deleted), count each 1st of the month since FIRST_MONTH not yet counted, then a slice at the
    history file's own timestamp. Everything lands in data/backfill/<region>/; merge() then copies it into
    the archive. Returns the history file's timestamp."""
    set_planet(None)
    t = planet_timestamp()
    regions = [Region(i) for i in region_ids]
    wait_for_quiet(ahead_minutes=90)  # a planet clip takes an hour or more
    clip(regions)
    for r in regions:
        prune_clips(r)
    for r in regions:
        # the months first: a history file ending on a 1st must not take that date from its 12:00Z slice
        months(r, FIRST_MONTH, last_month(t), 1, keep=False)
        count_at(r, t)
    return t


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
    # the per-city quest status (run.py history merges every region's): a daily region's own count wrote
    # one; a weekly region has only the engine's from its slices
    quests, archived = r.backfill / "quests.json", dst.parent / "quests.json"
    if quests.exists() and (not archived.exists() or run.region_cadence(r.config) == "weekly"):
        shutil.copy2(quests, archived)
    # the tile grids (heatmaps) of both; they stay out of git, in data/grid/<region>/
    grid = run.GRID_DIR / r.id
    for p in sorted((r.backfill / "grid").glob("*.json.gz")) + sorted((r.recount / "grid").glob("*.json.gz")):
        grid.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, grid / p.name)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--planet", help="history-<YYMMDD> in the store's planet/ folder (default: the newest)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    cl = sub.add_parser("clip", parents=[common])
    cl.add_argument("--region", dest="regions", action="append", help="repeatable; default ontario")
    c = sub.add_parser("check", parents=[common])
    c.add_argument("--extract", help="a dated extract in the shared store (default: the region's oldest)")
    m = sub.add_parser("months", parents=[common])
    m.add_argument("--from", dest="first", default=FIRST_MONTH)
    m.add_argument("--to", dest="last", help="YYYY-MM (default: the last month whose 1st, 12:00Z, the history "
                   "file reaches; 2026-10 for history-261005)")
    m.add_argument("--step", type=int, default=1, help="months between slices (12 = a yearly spine)")
    m.add_argument("--keep", action="store_true", help="keep the slices")
    rc = sub.add_parser("recount", parents=[common])
    mg = sub.add_parser("merge", parents=[common])
    for p in (c, m, rc, mg):
        p.add_argument("--region", default="ontario")
    a = ap.parse_args(argv)
    set_planet(a.planet)
    if a.cmd == "clip":
        clip([Region(r) for r in a.regions or ["ontario"]])
        return 0
    r = Region(a.region)
    run.migrate_archive()  # snapshots published before 2026-10-24 still in docs/data count as published
    if a.cmd == "recount":
        recount(r)
    elif a.cmd == "check":
        check(r, a.extract)
    elif a.cmd == "months":
        months(r, a.first, a.last or last_month(planet_timestamp(r)), a.step, a.keep)
    else:
        merge(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
