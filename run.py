"""Daily pipeline for sc-open-quests. Python standard library only.

Subcommands:
  download   refresh each region's shared extract and the planet notes dump via ~/Code/osm-extracts
             (it skips unchanged ones)
  count      run the engine on each region's newest shared extract
             -> docs/data/<region>/snapshots/<asOfDate>.json + quests.json (skipped when a snapshot
             of this extract already exists, unless it lacks notes and a notes dump now reaches it).
             Needs a notes dump that reaches the extract.
  backfill   count every dated extract of every region still in the shared store
  history    rebuild docs/data/history/<cityId>.json, cities.json and quests.json from all regions
  update     download + backfill + history, then commit "data <asOfDate>" and push

Regions are config/regions.json, one Geofabrik extract each; a city names its region in
config/cities.json. Extracts and notes dumps live in the shared store (~/Code/.osm-data, see
~/Code/osm-extracts/README.md); this project never downloads them itself. A notes dump is clipped to
each region once, into data/notes/. The contract between engine, pipeline and site is DATA-FORMAT.md.
"""
from __future__ import annotations

import argparse
import contextlib
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OSM_DATA_DIR = Path(os.environ.get("OSM_DATA_DIR") or Path.home() / "Code" / ".osm-data")
OSM_EXTRACTS_TOOL = Path(os.environ.get("OSM_EXTRACTS_TOOL")
                         or Path.home() / "Code" / "osm-extracts" / "osm_extracts.py")
LOCK_DIR = ROOT / "data"
LOCK_PATH = LOCK_DIR / "pipeline.lock"

QUESTS_DIR = ROOT / "data" / "quests"
CITIES_CONFIG = ROOT / "config" / "cities.json"
REGIONS_CONFIG = ROOT / "config" / "regions.json"
DATA_DIR = ROOT / "docs" / "data"
NOTES_DIR = ROOT / "data" / "notes"
GRID_DIR = ROOT / "data" / "grid"  # counted quests per z14 tile, <region>/<asOfDate>.json.gz; not committed
REGION_CITIES_DIR = ROOT / "data" / "cities"  # the engine's cities file per region; not committed
CLIP_NOTES = ROOT / "tools" / "clip_notes.py"

ENGINE_DIR = ROOT / "engine"
ENGINE_INSTALL = ENGINE_DIR / "build" / "install" / "sc-open-quests-engine"
ENGINE_BAT = ENGINE_INSTALL / "bin" / "sc-open-quests-engine.bat"
JAVA_HOME = r"C:\Program Files\Android\Android Studio\jbr"



# --- plumbing -------------------------------------------------------------------------------------

def log(msg: str) -> None:
    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    print(f"[{stamp}] {msg}", flush=True)


def read_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj, compact: bool = False) -> bool:
    """Write stable JSON (sorted keys, LF). Returns True if the bytes on disk changed."""
    layout = {"separators": (",", ":")} if compact else {"indent": 1}
    body = json.dumps(obj, sort_keys=True, ensure_ascii=False, **layout) + "\n"
    data = body.encode("utf-8")
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return True


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


_lock_depth = 0


@contextlib.contextmanager
def pipeline_lock():
    """PID lock in data/pipeline.lock. Re-entrant within this process."""
    global _lock_depth
    if _lock_depth == 0:
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        if LOCK_PATH.exists():
            try:
                pid = int(LOCK_PATH.read_text(encoding="utf-8").strip())
            except ValueError:
                pid = -1
            if pid != os.getpid() and pid_alive(pid):
                raise RuntimeError(f"another run holds {LOCK_PATH} (pid {pid}); delete it if stale")
            log(f"clearing stale lock (pid {pid})")
        LOCK_PATH.write_text(str(os.getpid()), encoding="utf-8")
    _lock_depth += 1
    try:
        yield
    finally:
        _lock_depth -= 1
        if _lock_depth == 0:
            LOCK_PATH.unlink(missing_ok=True)


# --- regions --------------------------------------------------------------------------------------

def regions(path: Path = REGIONS_CONFIG) -> list[dict]:
    """config/regions.json: {id, name, group, timeZone, poly, source}, one per Geofabrik extract."""
    return read_json(path)["regions"]


def region_cities(region: dict) -> Path:
    """The engine's cities file for one region: config/cities.json cut to the cities in it."""
    cities = [c for c in read_json(CITIES_CONFIG)["cities"] if c["region"] == region["id"]]
    if not cities:
        raise ValueError(f"no city in {CITIES_CONFIG.name} has region {region['id']}")
    path = REGION_CITIES_DIR / f"{region['id']}.json"
    write_json(path, {"cities": cities})
    return path


# --- extracts (shared store) ---------------------------------------------------------------------

def download() -> None:
    """Ask osm-extracts to refresh each region's shared extract. It HEAD-checks Geofabrik and holds
    its own fetch lock, so sibling projects refreshing at the same time don't both download."""
    for region in regions():
        log(f"refreshing shared extract: {OSM_EXTRACTS_TOOL} fetch {region['id']}")
        subprocess.run([sys.executable, str(OSM_EXTRACTS_TOOL), "fetch", region["id"]], check=True)
    log(f"refreshing notes dump: {OSM_EXTRACTS_TOOL} fetch notes")
    subprocess.run([sys.executable, str(OSM_EXTRACTS_TOOL), "fetch", "notes"], check=True)


def latest_extract(region: dict) -> tuple[Path, Path]:
    """(pbf, meta) for a region's newest extract, by its dated name; never the <region>-latest hardlink."""
    region_dir = OSM_DATA_DIR / region["id"]
    latest = read_json(region_dir / "latest.json")
    pbf = region_dir / latest["file"]
    return pbf, extract_meta(pbf)


def dated_extracts(region: dict) -> list[tuple[Path, Path]]:
    """Every dated extract of a region in the store, oldest first."""
    region_dir = OSM_DATA_DIR / region["id"]
    files = sorted(region_dir.glob(f"{region['id']}-????-??-??.osm.pbf"))
    return [(p, extract_meta(p)) for p in files]


def extract_meta(pbf: Path) -> Path:
    meta = pbf.with_name(pbf.name.removesuffix(".osm.pbf") + ".meta.json")
    if not pbf.exists() or not meta.exists():
        raise FileNotFoundError(f"{pbf} or its meta is missing from the shared store")
    return meta


# --- notes ----------------------------------------------------------------------------------------

def notes_clip(region: dict) -> Path | None:
    """A region's clip of the newest notes dump in the shared store, made on first use. None if the
    store has no notes dump. Older clips are deleted: each dump holds every note's whole history."""
    latest_path = OSM_DATA_DIR / "notes" / "latest.json"
    if not latest_path.exists():
        return None
    dump = OSM_DATA_DIR / "notes" / read_json(latest_path)["file"]
    poly = ROOT / region["poly"]
    clip = NOTES_DIR / (dump.name.removesuffix(".osn.bz2") + f"-{region['id']}.jsonl")
    if not clip.exists():
        log(f"clipping {dump.name} to {poly.name}")
        subprocess.run([sys.executable, str(CLIP_NOTES), str(dump), "--poly", str(poly), "--out", str(clip)],
                       check=True)
    for old in NOTES_DIR.glob(f"planet-notes-*-{region['id']}.jsonl"):
        if old != clip:
            old.unlink()
    return clip


def notes_until(clip: Path) -> datetime:
    """The newest comment in the dump the clip was cut from: notes are known up to then."""
    with open(clip, encoding="utf-8") as f:
        header = json.loads(f.readline())
    return datetime.fromisoformat(header["until"].replace("Z", "+00:00"))


# --- count ----------------------------------------------------------------------------------------

def newest_quests_file(quests_dir: Path = QUESTS_DIR) -> Path:
    def version(p: Path):
        m = re.fullmatch(r"v(\d+(?:\.\d+)*)\.json", p.name)
        return tuple(int(x) for x in m.group(1).split(".")) if m else None
    files = [p for p in quests_dir.glob("v*.json") if version(p)]
    if not files:
        raise FileNotFoundError(f"no quest registry in {quests_dir} (run tools/sc-harness)")
    return max(files, key=version)


def snapshot_for_sha(sha: str, region_dir: Path) -> Path | None:
    """The snapshot in region_dir/snapshots/ that counts the extract with this sha256, if any."""
    for p in sorted((region_dir / "snapshots").glob("*.json")):
        try:
            if read_json(p).get("source", {}).get("sha256") == sha:
                return p
        except (OSError, ValueError):
            continue
    return None


def engine_env(time_zone: str | None = None) -> dict[str, str]:
    """The engine's environment. SC's date filters use the JVM's zone, which must be the cities'
    (Main.kt); JAVA_OPTS comes after the start script's default -Duser.timezone, so it wins."""
    env = dict(os.environ)
    if os.path.isdir(JAVA_HOME):
        env["JAVA_HOME"] = JAVA_HOME
    if time_zone:
        env["JAVA_OPTS"] = (env.get("JAVA_OPTS", "") + f" -Duser.timezone={time_zone}").strip()
    return env


def engine_is_stale() -> bool:
    """True if the installed engine is missing or older than any engine source file."""
    jars = list((ENGINE_INSTALL / "lib").glob("*.jar"))
    if not ENGINE_BAT.exists() or not jars:
        return True
    built = min(p.stat().st_mtime for p in jars)
    sources = [ENGINE_DIR / "build.gradle.kts", ENGINE_DIR / "settings.gradle.kts",
               ENGINE_DIR / "gradle.properties"]
    sources += [Path(p) for p in glob.glob(str(ENGINE_DIR / "src" / "**" / "*"), recursive=True)]
    return any(p.is_file() and p.stat().st_mtime > built for p in sources)


def build_engine() -> None:
    log("building engine (gradlew installDist)")
    gradlew = ENGINE_DIR / ("gradlew.bat" if os.name == "nt" else "gradlew")
    subprocess.run([str(gradlew), "installDist", "--console=plain"], cwd=ENGINE_DIR,
                   env=engine_env(), check=True)


def count(region: dict, force: bool = False, extract: tuple[Path, Path] | None = None) -> Path | None:
    """Run the engine on one extract of a region (default: its newest). Returns the snapshot, or
    None if skipped."""
    with pipeline_lock():
        pbf, meta_path = extract or latest_extract(region)
        meta = read_json(meta_path)
        sha = meta["sha256"]
        out = DATA_DIR / region["id"]
        clip = notes_clip(region)
        replicated = datetime.fromisoformat(meta["replication_timestamp"])
        if clip is None or notes_until(clip) < replicated:
            # the dump of the next morning reaches it; a later scheduled run counts it. The mirror can
            # lag the dump by more than half a day, so a day's wait is normal; three are not.
            age = datetime.now(timezone.utc) - replicated
            if age.days >= 3:
                raise RuntimeError(f"no notes dump reaches {pbf.name} after {age.days} days; is `fetch notes` working?")
            log(f"no notes dump reaches {pbf.name} ({meta['replication_timestamp']}) yet; not counting it")
            return None
        existing = snapshot_for_sha(sha, out)
        name = f"{region['id']}/snapshots/{existing.name}" if existing else None
        if existing and not force:
            if read_json(existing).get("notes"):
                log(f"{name} already counts {pbf.name}; skipping (--force to redo)")
                return None
            log(f"{name} counts {pbf.name} without notes; recounting with {clip.name}")
        if engine_is_stale():
            build_engine()
        quests = newest_quests_file()
        cmd = [str(ENGINE_BAT), "count",
               "--pbf", str(pbf),
               "--quests", str(quests.relative_to(ROOT)),
               "--cities", str(region_cities(region).relative_to(ROOT)),
               "--out", str(out.relative_to(ROOT)),
               "--source-meta", str(meta_path),
               "--notes", str(clip.relative_to(ROOT)),
               "--grid", str((GRID_DIR / region["id"]).relative_to(ROOT))]
        log("running engine: " + " ".join(cmd[1:]))
        subprocess.run(cmd, cwd=ROOT, env=engine_env(region["timeZone"]), check=True)
        snap = snapshot_for_sha(sha, out)
        if not snap:
            raise RuntimeError("engine finished but no snapshot carries this extract's sha256")
        log(f"wrote {region['id']}/snapshots/{snap.name}")
        return snap


def backfill(force: bool = False) -> None:
    """Count every dated extract of every region still in the shared store (the store prunes old
    ones on fetch)."""
    with pipeline_lock():
        for region in regions():
            for extract in dated_extracts(region):
                count(region, force=force, extract=extract)


# --- history --------------------------------------------------------------------------------------

def load_snapshots(data_dir: Path) -> list[dict]:
    """All snapshots of all regions (data_dir/<region>/snapshots/), ascending by asOfDate. Each gets
    a "region" key from the folder it is in."""
    snaps = []
    for p in data_dir.glob("*/snapshots/*.json"):
        snap = read_json(p)
        snap["region"] = p.parent.parent.name
        snaps.append(snap)
    return sorted(snaps, key=lambda s: (s["asOfDate"], s["region"]))


def merge_quests(data_dir: Path) -> int:
    """Write data_dir/quests.json from each region's quests.json: the newest registry, with every
    region's per-city status. Returns 1 if the file changed."""
    parts = sorted((read_json(p) for p in data_dir.glob("*/quests.json")),
                   key=lambda q: tuple(int(x) for x in q["scVersion"].split(".")))
    if not parts:
        return 0
    merged = parts[-1]
    for q in merged["quests"]:
        status = {}
        for part in parts:
            status.update(next((o["status"] for o in part["quests"] if o["name"] == q["name"]), {}))
        q["status"] = dict(sorted(status.items()))
    return write_text(data_dir / "quests.json", quests_json(merged))


def quests_json(doc: dict) -> str:
    """quests.json in the engine's layout (Output.kt questsJson): one quest per line."""
    def value(key, v):
        if key == "enabledInCountries":
            return json.dumps(v, separators=(",", ":"), ensure_ascii=False)
        if key == "elementTypes":
            return "[" + ",".join(json.dumps(x) for x in v) + "]"
        if key == "status":
            return "{ " + ", ".join(f"{json.dumps(c)}: {json.dumps(s)}" for c, s in v.items()) + " }"
        return json.dumps(v, ensure_ascii=False)
    lines = ["    { " + ", ".join(f"{json.dumps(k)}: {value(k, v)}" for k, v in q.items()) + " }"
             for q in doc["quests"]]
    head = "".join(f"  {json.dumps(k)}: {json.dumps(v)},\n" for k, v in doc.items() if k != "quests")
    return "{\n" + head + '  "quests": [\n' + ",\n".join(lines) + "\n  ]\n}\n"


def write_text(path: Path, text: str) -> bool:
    """Write text as UTF-8 with LF. Returns True if the bytes on disk changed."""
    data = text.encode("utf-8")
    if path.exists() and path.read_bytes() == data:
        return False
    path.write_bytes(data)
    return True


def default_disabled(data_dir: Path) -> set[str]:
    """Names of default-disabled quests: from quests.json, else the newest registry dump."""
    path = data_dir / "quests.json"
    if not path.exists():
        path = newest_quests_file()
    return {q["name"] for q in read_json(path)["quests"] if q.get("defaultDisabled")}


def total_open(city: dict, leave_out: set[str]) -> int | None:
    """Open quests in one city's snapshot entry over the quests not left out; None if none has a count."""
    counts = [q.get("open") for k, q in city["quests"].items() if k not in leave_out]
    counts = [n for n in counts if n is not None]
    return sum(counts) if counts else None


def build_history(snapshots: list[dict], city_config: list[dict], disabled: set[str],
                  region_config: list[dict] | None = None) -> dict:
    """Turn snapshots (of every region) into {"history": {cityId: series}, "cities": index}.

    A city's series has one entry per snapshot that contains the city; a city missing from a
    snapshot (added to the config later, say) has no entry for that date rather than a row of
    nulls. Within a city, a quest missing from one snapshot (not counted under that SC version,
    or new in a later one) is null at that index, never 0.
    """
    names = {c["id"]: c["name"] for c in city_config}
    city_regions = {c["id"]: c.get("region") for c in city_config}
    dates = sorted({s["asOfDate"] for s in snapshots})  # each region has its own snapshot of a date
    city_ids = sorted({cid for s in snapshots for cid in s["cities"]})
    history, index = {}, []
    for cid in city_ids:
        rows = [(s, s["cities"][cid]) for s in snapshots if cid in s["cities"]]
        quest_names = sorted({q for _, c in rows for q in c["quests"]})
        quests = {q: {"open": [c["quests"].get(q, {}).get("open") for _, c in rows],
                      "agedOnly": [c["quests"].get(q, {}).get("agedOnly") for _, c in rows]}
                  for q in quest_names}
        last_snap, last = rows[-1]
        den = last["denominators"]
        series = {
            "city": cid,
            "name": names.get(cid, cid),
            "dates": [s["asOfDate"] for s, _ in rows],
            "meta": [{"scVersion": s["scVersion"], "resurveyMultiplier": s["resurveyMultiplier"],
                      **({"areaUnit": s["areaUnit"]} if "areaUnit" in s else {}),
                      **({"notes": True} if s.get("notes") else {})}
                     for s, _ in rows],
            "quests": quests,
            "denominators": {
                "landAreaKm2": den.get("landAreaKm2"),
                "population": den.get("population"),
                "highwayKm": [c["denominators"].get("highwayKm") for _, c in rows],
                "taggedNodes": [c["denominators"].get("taggedNodes") for _, c in rows],
                "taggedWays": [c["denominators"].get("taggedWays") for _, c in rows],
            },
        }
        history[cid] = series
        headline = {k: v for k, v in last["quests"].items() if k not in disabled}
        # totals on every snapshot date, null where the city wasn't counted, for the site's sparklines
        by_date = {s["asOfDate"]: c for s, c in rows}
        trend = [total_open(by_date[d], disabled) if d in by_date else None for d in dates]
        trend_all = [total_open(by_date[d], set()) if d in by_date else None for d in dates]
        index.append({
            "id": cid,
            "name": series["name"],
            **({"region": city_regions[cid]} if city_regions.get(cid) else {}),
            "asOfDate": last_snap["asOfDate"],
            "scVersion": last_snap["scVersion"],
            "landAreaKm2": den.get("landAreaKm2"),
            "population": den.get("population"),
            "highwayKm": den.get("highwayKm"),
            "open": sum(q.get("open") or 0 for q in headline.values()),
            "agedOnly": sum(q.get("agedOnly") or 0 for q in headline.values()),
            "openAll": sum(q.get("open") or 0 for q in last["quests"].values()),
            "questsCounted": len(last["quests"]),
            "trend": trend,
            "trendAll": trend_all,
        })
    index.sort(key=lambda c: c["name"])
    latest = snapshots[-1] if snapshots else {}
    cities = {"asOfDate": latest.get("asOfDate"), "scVersion": latest.get("scVersion"),
              "resurveyMultiplier": latest.get("resurveyMultiplier"),
              "dates": dates, "cities": index}
    if region_config:
        cities["regions"] = [{k: r[k] for k in ("id", "name", "group", "source")} for r in region_config]
    return {"history": history, "cities": cities}


def history(data_dir: Path = DATA_DIR, cities_config: Path = CITIES_CONFIG) -> int:
    """Rewrite history/*.json, cities.json and quests.json under data_dir. Returns the number of
    files changed."""
    snapshots = load_snapshots(data_dir)
    if not snapshots:
        log(f"no snapshots in {data_dir}/*/snapshots; nothing to do")
        return 0
    changed = merge_quests(data_dir)
    out = build_history(snapshots, read_json(cities_config)["cities"], default_disabled(data_dir), regions())
    for cid, series in out["history"].items():
        changed += write_json(data_dir / "history" / f"{cid}.json", series, compact=True)
    for stale in (data_dir / "history").glob("*.json"):
        if stale.stem not in out["history"]:
            stale.unlink()
            changed += 1
    changed += write_json(data_dir / "cities.json", out["cities"], compact=True)
    log(f"history: {len(out['history'])} cities over {len(snapshots)} snapshot(s), {changed} file(s) changed")
    return changed


# --- update ---------------------------------------------------------------------------------------

def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=check)


def publish(data_dir: Path = DATA_DIR) -> bool:
    """Commit docs/data as "data <asOfDate>" and push. Returns True if a commit was made."""
    rel = data_dir.relative_to(ROOT).as_posix()
    git("add", "--", rel)
    if git("diff", "--cached", "--quiet", "--", rel, check=False).returncode == 0:
        log("docs/data unchanged; nothing to commit")
        return False
    as_of = read_json(data_dir / "cities.json").get("asOfDate") or "unknown"
    git("commit", "-m", f"data {as_of}", "--", rel)
    log(f"committed: data {as_of}")
    push = git("push", check=False)
    if push.returncode != 0:
        raise RuntimeError(f"git push failed: {push.stderr.strip()}")
    log("pushed")
    return True


def update(force: bool = False) -> None:
    with pipeline_lock():
        log("=== download ===")
        download()
        log("=== count ===")
        # every stored extract, not only the newest: one counted before its notes dump existed is
        # recounted once a dump reaches it; the rest are skipped
        backfill(force=force)
        log("=== history ===")
        history()
        log("=== publish ===")
        publish()
    log("update done")


# --- CLI ------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python run.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download", help="refresh the shared Ontario extract (osm-extracts fetch)")
    for name, help_ in [("count", "run the engine on the newest shared extract"),
                        ("backfill", "count every dated extract in the shared store"),
                        ("update", "download + count + history + commit + push "
                                   "(--force recounts but does not re-download)")]:
        p = sub.add_parser(name, help=help_)
        p.add_argument("--force", action="store_true", help="redo even if nothing changed")
    h = sub.add_parser("history", help="rebuild history/ and cities.json from snapshots")
    h.add_argument("--data-dir", type=Path, default=DATA_DIR)
    h.add_argument("--cities", type=Path, default=CITIES_CONFIG)
    args = parser.parse_args(argv)
    try:
        if args.command == "download":
            download()
        elif args.command == "backfill":
            backfill(force=args.force)
        elif args.command == "count":
            count(force=args.force)
        elif args.command == "history":
            history(args.data_dir, args.cities)
        elif args.command == "update":
            update(force=args.force)
        return 0
    except Exception as e:  # one line in the scheduler log, non-zero exit for Task Scheduler
        log(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
