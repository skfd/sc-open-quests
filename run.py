"""Daily pipeline for sc-open-quests. Python standard library only.

Subcommands:
  download   refresh each distinct shared extract of the regions and the planet notes dump via
             ~/Code/osm-extracts (it skips unchanged ones)
  count      run the engine on each region's newest shared extract
             -> data/archive/<region>/snapshots/<asOfDate>.json + quests.json (skipped when a snapshot
             of this extract already exists, unless it lacks notes and a notes dump now reaches it).
             Needs a notes dump that reaches the extract.
  backfill   count every dated extract of every region still in the shared store
  history    rebuild docs/data/history/<cityId>.json, cities.json, quests.json and compare/<quest>.json
             from the archive of all regions, and copy each region's newest snapshot into docs/data
  migrate-archive  move snapshots published before 2026-10-24 (docs/data/<region>/snapshots/) into
             data/archive/; count and history do it too, so it is idempotent and needs no flag
  update     download + backfill + history, then commit "data <asOfDate>" and push; last, check-release
  weekly     refresh the planet history file (osm-extracts fetch planet-history; a failure leaves it as it
             is), count the weekly regions from it (tools/backfill_history.py weekly: clip, the months not
             yet counted, a slice at the file's timestamp), merge, history, then commit
             "data weekly <date>" and push. With no weekly region it only refreshes the history file
  check-release  compare the pinned StreetComplete tag (engine/SC-VERSION.txt) with the newest stable
             GitHub release; if the app moved on, open a GitHub issue "Repin to StreetComplete vX.Y"
             (once; see REPIN.md) and refresh docs/data/sc-releases.json. Network and `gh` failures
             are logged, never fatal.

Regions are config/regions.json; a city names its region in config/cities.json. A region is one engine
run (one time zone) over one shared extract: its "extract" key, default its id; several regions may share
one, and an extract osm-extracts does not know by name comes with a "url". A region with "cadence":
"weekly" has no extract: `weekly` counts it from the planet history file, and download, count, backfill
and update leave it alone (default "daily", the Geofabrik path). Extracts and notes dumps live
in the shared store (~/Code/.osm-data, see ~/Code/osm-extracts/README.md); this project never downloads
them itself. A notes dump is clipped to every region in one pass, into data/notes/. Every snapshot is kept
in data/archive/<region>/ (not committed); docs/data, which GitHub Pages publishes, holds only the newest
per region. The contract between engine, pipeline and site is DATA-FORMAT.md.
"""
from __future__ import annotations

import argparse
import contextlib
import glob
import json
import math
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
ARCHIVE_DIR = ROOT / "data" / "archive"  # every snapshot, <region>/snapshots/<asOfDate>.json; not committed
NOTES_DIR = ROOT / "data" / "notes"
GRID_DIR = ROOT / "data" / "grid"  # counted quests per z14 tile, <region>/<asOfDate>.json.gz; not committed
REGION_CITIES_DIR = ROOT / "data" / "cities"  # the engine's cities file per region; not committed
CLIP_NOTES = ROOT / "tools" / "clip_notes.py"

ENGINE_DIR = ROOT / "engine"
SC_VERSION_FILE = ENGINE_DIR / "SC-VERSION.txt"
TOOLS_DIR = ROOT / "tools"
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
    """config/regions.json: {id, name, group, timeZone, poly, source[, extract][, url][, cadence]}. A region
    is one engine run: one time zone, its own cities and output folder. Several regions may share an extract."""
    return read_json(path)["regions"]


CADENCES = ("daily", "weekly")


def region_cadence(region: dict) -> str:
    """How a region is counted: "daily" (the default) from its Geofabrik extract by `update`, or "weekly"
    from the planet history file by `weekly`."""
    cadence = region.get("cadence", "daily")
    if cadence not in CADENCES:
        raise ValueError(f"region {region['id']}: cadence {cadence!r} is not one of {', '.join(CADENCES)}")
    return cadence


def regions_by_cadence(cadence: str, regs: list[dict] | None = None) -> list[dict]:
    """The regions with this cadence, in config order (every region's cadence checked)."""
    return [r for r in (regions() if regs is None else regs) if region_cadence(r) == cadence]


def region_extract(region: dict) -> str:
    """The shared-store extract a region is counted from: its "extract" key, default its id. It names
    the store folder (~/Code/.osm-data/<extract>/) and the osm-extracts fetch."""
    return region.get("extract") or region["id"]


def extract_fetches(regs: list[dict]) -> list[tuple[str, str | None]]:
    """(extract, url) to fetch for these regions: each distinct extract once, in config order. url is
    None for an extract osm-extracts knows by name. Regions sharing an extract must agree on its url."""
    urls: dict[str, str | None] = {}
    for r in regs:
        ex, url = region_extract(r), r.get("url")
        if ex in urls and urls[ex] != url:
            raise ValueError(f"regions disagree on the url of extract {ex}: {urls[ex]} and {url}")
        urls[ex] = url
    return list(urls.items())


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
    """Ask osm-extracts to refresh each distinct shared extract once. It HEAD-checks the source and holds
    its own fetch lock, so sibling projects refreshing at the same time don't both download."""
    for extract, url in extract_fetches(regions_by_cadence("daily")):
        cmd = [sys.executable, str(OSM_EXTRACTS_TOOL), "fetch", extract] + (["--url", url] if url else [])
        log(f"refreshing shared extract: {' '.join(cmd[1:])}")
        subprocess.run(cmd, check=True)
    log(f"refreshing notes dump: {OSM_EXTRACTS_TOOL} fetch notes")
    subprocess.run([sys.executable, str(OSM_EXTRACTS_TOOL), "fetch", "notes"], check=True)


def latest_extract(region: dict) -> tuple[Path, Path]:
    """(pbf, meta) for a region's newest extract, by its dated name; never the <extract>-latest hardlink."""
    region_dir = OSM_DATA_DIR / region_extract(region)
    latest = read_json(region_dir / "latest.json")
    pbf = region_dir / latest["file"]
    return pbf, extract_meta(pbf)


def dated_extracts(region: dict) -> list[tuple[Path, Path]]:
    """Every dated extract of a region in the store, oldest first."""
    extract = region_extract(region)
    files = sorted((OSM_DATA_DIR / extract).glob(f"{extract}-????-??-??.osm.pbf"))
    return [(p, extract_meta(p)) for p in files]


def extract_meta(pbf: Path) -> Path:
    meta = pbf.with_name(pbf.name.removesuffix(".osm.pbf") + ".meta.json")
    if not pbf.exists() or not meta.exists():
        raise FileNotFoundError(f"{pbf} or its meta is missing from the shared store")
    return meta


# --- notes ----------------------------------------------------------------------------------------

NOTE_BOX_PADDING_M = 1000.0  # the engine's AREA_PADDING_M (AreaPass.kt): what it sees around a city


def notes_dump() -> Path | None:
    """The newest planet notes dump in the shared store, or None."""
    latest_path = OSM_DATA_DIR / "notes" / "latest.json"
    if not latest_path.exists():
        return None
    return OSM_DATA_DIR / "notes" / read_json(latest_path)["file"]


def clip_path(dump: Path, region: dict) -> Path:
    return NOTES_DIR / (dump.name.removesuffix(".osn.bz2") + f"-{region['id']}.jsonl")


def city_bbox(boundary: Path, relation: int) -> tuple[float, float, float, float]:
    """(minLon, minLat, maxLon, maxLat) of a city boundary file: its way members' geometry, which is the
    engine's polygon (Polygon.fromOverpassJson), and Overpass's "bounds", whichever reaches further."""
    root = read_json(boundary)
    rel = next(e for e in root.get("elements", [root]) if e.get("type") == "relation" and e.get("id") == relation)
    lats = [p["lat"] for m in rel["members"] if m["type"] == "way" for p in m["geometry"]]
    lons = [p["lon"] for m in rel["members"] if m["type"] == "way" for p in m["geometry"]]
    if b := rel.get("bounds"):
        lats += [b["minlat"], b["maxlat"]]
        lons += [b["minlon"], b["maxlon"]]
    return min(lons), min(lats), max(lons), max(lats)


def note_boxes(region: dict) -> list[list[float]]:
    """The region's cities' bounding boxes padded by NOTE_BOX_PADDING_M, as the engine pads them: the
    notes clip keeps every note in them even where a city sticks out of the region's simplified poly."""
    boxes = []
    for c in read_json(CITIES_CONFIG)["cities"]:
        if c["region"] != region["id"]:
            continue
        w, s, e, n = city_bbox(ROOT / c["boundary"], c["relation"])
        d_lat = NOTE_BOX_PADDING_M / 111_320.0
        d_lon = NOTE_BOX_PADDING_M / (111_320.0 * math.cos(math.radians(max(abs(s), abs(n)))))
        boxes.append([round(w - d_lon, 7), round(s - d_lat, 7), round(e + d_lon, 7), round(n + d_lat, 7)])
    return boxes


def notes_clips(dump: Path, regs: list[dict]) -> None:
    """Clip the dump to all these regions in one pass (tools/clip_notes.py --config)."""
    config = NOTES_DIR / (dump.name.removesuffix(".osn.bz2") + ".clips.json")
    write_json(config, {"clips": [{"poly": str(ROOT / r["poly"]), "out": str(clip_path(dump, r)),
                                   "boxes": note_boxes(r)} for r in regs]})
    log(f"clipping {dump.name} to {len(regs)} region(s): {', '.join(r['id'] for r in regs)}")
    try:
        subprocess.run([sys.executable, str(CLIP_NOTES), str(dump), "--config", str(config)], check=True)
    finally:
        config.unlink(missing_ok=True)


def notes_clip(region: dict) -> Path | None:
    """A region's clip of the newest notes dump in the shared store, made on first use. None if the
    store has no notes dump. The first region to need a clip of a dump makes it for every configured
    region that lacks one, in one pass over the dump. Older clips are deleted: each dump holds every
    note's whole history."""
    dump = notes_dump()
    if dump is None:
        return None
    clip = clip_path(dump, region)
    if not clip.exists():
        todo = [r for r in regions() if r["id"] != region["id"] and not clip_path(dump, r).exists()]
        notes_clips(dump, [region, *todo])
    stale = re.compile(r"planet-notes-\d{6}-" + re.escape(region["id"]) + r"\.jsonl")
    for old in NOTES_DIR.glob(f"planet-notes-*-{region['id']}.jsonl"):
        if old != clip and stale.fullmatch(old.name):
            old.unlink()
    return clip


def notes_until(clip: Path) -> datetime:
    """The newest comment in the dump the clip was cut from: notes are known up to then."""
    with open(clip, encoding="utf-8") as f:
        header = json.loads(f.readline())
    return datetime.fromisoformat(header["until"].replace("Z", "+00:00"))


# --- count ----------------------------------------------------------------------------------------

def version_tuple(v: str) -> tuple[int, ...]:
    """"v64.0", "64.0" or "v64.0.json" -> (64, 0); anything else -> ()."""
    m = re.fullmatch(r"v?(\d+(?:\.\d+)*)(?:\.json)?", v)
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def newest_quests_file(quests_dir: Path = QUESTS_DIR) -> Path:
    def version(p: Path):
        return version_tuple(p.name) if p.name.startswith("v") else None
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


# The engine's heap is what the machine can spare when it starts, not a fixed cap (the owner, 2026-10-24).
# Ontario counts in 12-16 GB and a bigger heap only makes the collector lazier (DESIGN.md, "Planet coverage:
# what was measured"); the 2026-10-17 run died at the commit limit (paging file), not at -Xmx40g.
HEAP_RESERVE_GB = 8      # left to Windows and everything else running
HEAP_MIN_GB = 12         # below this the engine waits for memory rather than start
HEAP_MAX_FRACTION = 0.75  # of physical memory, however idle the machine is
HEAP_WAIT_MINUTES = int(os.environ.get("SCOQ_HEAP_WAIT_MINUTES", "60"))
HEAP_POLL_SECONDS = 60


def memory_status() -> tuple[float, float, float] | None:
    """(free physical, free commit charge, total physical) in GB, or None off Windows. The commit charge
    is what the paging file still allows; it ran out on 2026-10-17 with physical memory to spare."""
    if sys.platform != "win32":
        return None
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        return None
    gb = 1 << 30
    return m.ullAvailPhys / gb, m.ullAvailPageFile / gb, m.ullTotalPhys / gb


def spare_heap_gb(status: tuple[float, float, float]) -> int:
    """The heap the machine can spare now: the smaller of free memory and free commit charge, less the
    reserve, at most HEAP_MAX_FRACTION of physical memory."""
    free_phys, free_commit, total = status
    return int(min(free_phys, free_commit, total * HEAP_MAX_FRACTION) - HEAP_RESERVE_GB)


def engine_heap_gb(status=memory_status, sleep=None, wait_minutes: int | None = None) -> int | None:
    """Wait until the machine can spare HEAP_MIN_GB, then return what it can spare. None off Windows
    (the start script's default stands). Raises after wait_minutes: a skipped count is picked up by the
    next run, which goes over every stored extract; an engine that dies of memory halfway is not."""
    import time
    sleep = sleep or time.sleep
    wait_minutes = HEAP_WAIT_MINUTES if wait_minutes is None else wait_minutes
    waited = 0
    while True:
        st = status()
        if st is None:
            return None
        spare = spare_heap_gb(st)
        if spare >= HEAP_MIN_GB:
            if waited:
                log(f"memory freed after {waited} min")
            return spare
        if waited >= wait_minutes:
            raise RuntimeError(f"memory stayed busy for {waited} min: {st[0]:.0f} GB free, {st[1]:.0f} GB commit "
                               f"left, the engine needs {HEAP_MIN_GB + HEAP_RESERVE_GB}; not counting now")
        if not waited:
            log(f"memory busy ({st[0]:.0f} GB free, {st[1]:.0f} GB commit left); waiting up to "
                f"{wait_minutes} min for {HEAP_MIN_GB + HEAP_RESERVE_GB} GB")
        sleep(HEAP_POLL_SECONDS)
        waited += HEAP_POLL_SECONDS // 60


def engine_env(time_zone: str | None = None, heap: bool = False) -> dict[str, str]:
    """The engine's environment. SC's date filters use the JVM's zone, which must be the cities'
    (Main.kt); JAVA_OPTS comes after the start script's default -Duser.timezone and -Xmx, so it wins.
    With heap, -Xmx is what the machine can spare now (engine_heap_gb), which may wait for memory."""
    env = dict(os.environ)
    if os.path.isdir(JAVA_HOME):
        env["JAVA_HOME"] = JAVA_HOME
    opts = env.get("JAVA_OPTS", "")
    if heap and "-Xmx" not in opts:
        gb = engine_heap_gb()
        if gb is not None:
            log(f"engine heap: -Xmx{gb}g (what the machine can spare now)")
            opts += f" -Xmx{gb}g"
    if time_zone:
        opts += f" -Duser.timezone={time_zone}"
    if opts.strip():
        env["JAVA_OPTS"] = opts.strip()
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
        migrate_archive()
        out = ARCHIVE_DIR / region["id"]
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
        quests = newest_quests_file()
        newest = extract is None or pbf.name == latest_extract(region)[0].name
        if existing and not force:
            snap = read_json(existing)
            if not snap.get("notes"):
                log(f"{name} counts {pbf.name} without notes; recounting with {clip.name}")
            elif newest and version_tuple(snap.get("scVersion") or "0") < version_tuple(quests.stem):
                # after a repin (REPIN.md): the region's newest extract gets the new quest set; the
                # older ones in the store (backfill) keep their counts, so the break sits at the repin
                log(f"{name} counts {pbf.name} with SC {snap.get('scVersion')}; recounting with {quests.name}")
            else:
                log(f"{name} already counts {pbf.name}; skipping (--force to redo)")
                return None
        if engine_is_stale():
            build_engine()
        cmd = [str(ENGINE_BAT), "count",
               "--pbf", str(pbf),
               "--quests", str(quests.relative_to(ROOT)),
               "--cities", str(region_cities(region).relative_to(ROOT)),
               "--out", str(out.relative_to(ROOT)),
               "--source-meta", str(meta_path),
               "--notes", str(clip.relative_to(ROOT)),
               "--grid", str((GRID_DIR / region["id"]).relative_to(ROOT))]
        log("running engine: " + " ".join(cmd[1:]))
        subprocess.run(cmd, cwd=ROOT, env=engine_env(region["timeZone"], heap=True), check=True)
        snap = snapshot_for_sha(sha, out)
        if not snap:
            raise RuntimeError("engine finished but no snapshot carries this extract's sha256")
        log(f"wrote {region['id']}/snapshots/{snap.name}")
        return snap


def backfill(force: bool = False) -> None:
    """Count every dated extract of every region still in the shared store (the store prunes old
    ones on fetch)."""
    with pipeline_lock():
        for region in regions_by_cadence("daily"):
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


def merge_quests(data_dir: Path, archive: Path | None = None) -> int:
    """Write data_dir/quests.json from each region's quests.json in the archive (default data_dir): the
    newest registry, with every region's per-city status. Returns 1 if the file changed."""
    parts = sorted((read_json(p) for p in (archive or data_dir).glob("*/quests.json")),
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
    """Turn snapshots (of every region) into {"history": {cityId: series}, "cities": index,
    "compare": {quest: {"quest", "open": {cityId: n}}}}.

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
    compare = {}  # quest -> {cityId: open in the city's newest snapshot}: what the compare view ranks
    for cid in city_ids:
        rows = [(s, s["cities"][cid]) for s in snapshots if cid in s["cities"]]
        quest_names = sorted({q for _, c in rows for q in c["quests"]})
        quests = {q: {"open": [c["quests"].get(q, {}).get("open") for _, c in rows],
                      "agedOnly": [c["quests"].get(q, {}).get("agedOnly") for _, c in rows]}
                  for q in quest_names}
        last_snap, last = rows[-1]
        for q, v in last["quests"].items():
            compare.setdefault(q, {})[cid] = v.get("open")
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
    return {"history": history, "cities": cities,
            "compare": {q: {"quest": q, "open": dict(sorted(v.items()))} for q, v in sorted(compare.items())}}


def migrate_archive(data_dir: Path = DATA_DIR, archive: Path = ARCHIVE_DIR) -> int:
    """Move the snapshots and per-region quests.json under data_dir/<region>/ into the archive. Until
    2026-10-24 every snapshot was published; docs/data now keeps each region's newest only (see
    publish_newest). A file the archive already holds byte for byte is deleted from data_dir; one that
    differs is left and logged; the region's newest stays, published. Idempotent. Returns the number of
    files moved or deleted."""
    if data_dir.resolve() == archive.resolve():
        return 0
    done = 0
    for p in sorted(data_dir.glob("*/snapshots/*.json")):
        region = p.parent.parent.name
        dst = archive / region / "snapshots" / p.name
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            p.replace(dst)
            done += 1
        elif p.name == max(q.name for q in dst.parent.glob("*.json")):
            continue   # the region's published newest; publish_newest keeps it equal to the archive's
        elif dst.read_bytes() == p.read_bytes():
            p.unlink()
            done += 1
        else:
            log(f"{region}/snapshots/{p.name} differs from the archive's copy; left in {data_dir}")
    for p in sorted(data_dir.glob("*/quests.json")):   # the engine's, gitignored; it now writes the archive's
        dst = archive / p.parent.name / "quests.json"
        if dst.exists():
            p.unlink()
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            p.replace(dst)
        done += 1
    if done:
        log(f"migrate-archive: {done} file(s) from {data_dir} into {archive}")
    return done


def publish_newest(data_dir: Path, archive: Path) -> int:
    """Copy each region's newest snapshot in the archive to data_dir/<region>/snapshots/ and delete the
    region's other published snapshots the archive holds. Returns the number of files changed."""
    changed = 0
    for region_dir in sorted(p for p in archive.iterdir() if p.is_dir()):
        snaps = sorted((region_dir / "snapshots").glob("*.json"))
        if not snaps:
            continue
        newest = snaps[-1]
        out = data_dir / region_dir.name / "snapshots" / newest.name
        data = newest.read_bytes()
        if not out.exists() or out.read_bytes() != data:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            changed += 1
        for old in out.parent.glob("*.json"):
            if old.name != newest.name and (region_dir / "snapshots" / old.name).exists():
                old.unlink()
                changed += 1
    return changed


def history(data_dir: Path = DATA_DIR, cities_config: Path = CITIES_CONFIG, archive: Path | None = None) -> int:
    """Rewrite history/*.json, cities.json, quests.json and compare/*.json under data_dir from the
    snapshots in archive (default: ARCHIVE_DIR for docs/data, else data_dir itself, as the test fixtures
    have it). With a separate archive, first migrate anything published the old way, then publish each
    region's newest snapshot. Returns the number of files changed."""
    archive = archive or (ARCHIVE_DIR if data_dir.resolve() == DATA_DIR.resolve() else data_dir)
    separate = archive.resolve() != data_dir.resolve()
    changed = migrate_archive(data_dir, archive) if separate else 0
    snapshots = load_snapshots(archive)
    if not snapshots:
        log(f"no snapshots in {archive}/*/snapshots; nothing to do")
        return 0
    published = data_dir / "cities.json"
    if published.exists():
        lost = set(read_json(published).get("dates") or []) - {s["asOfDate"] for s in snapshots}
        if lost:  # a fresh clone, or a lost archive: rebuilding would cut the published history short
            raise RuntimeError(f"{archive} lacks {len(lost)} snapshot date(s) the published history has "
                               f"(e.g. {min(lost)}); restore the archive (git history holds the snapshots "
                               f"published until 2026-10-24) or delete {published} to rebuild from what is there")
    changed += merge_quests(data_dir, archive)
    out = build_history(snapshots, read_json(cities_config)["cities"], default_disabled(data_dir), regions())
    for cid, series in out["history"].items():
        changed += write_json(data_dir / "history" / f"{cid}.json", series, compact=True)
    for stale in (data_dir / "history").glob("*.json"):
        if stale.stem not in out["history"]:
            stale.unlink()
            changed += 1
    for quest, per_city in out["compare"].items():
        changed += write_json(data_dir / "compare" / f"{quest}.json", per_city, compact=True)
    for stale in (data_dir / "compare").glob("*.json"):
        if stale.stem not in out["compare"]:
            stale.unlink()
            changed += 1
    changed += write_json(data_dir / "cities.json", out["cities"], compact=True)
    if separate:
        changed += publish_newest(data_dir, archive)
    log(f"history: {len(out['history'])} cities over {len(snapshots)} snapshot(s), {changed} file(s) changed")
    return changed


# --- update ---------------------------------------------------------------------------------------

def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=check)


def publish(data_dir: Path = DATA_DIR, message: str | None = None, push: bool = True) -> bool:
    """Commit docs/data as message (default "data <asOfDate>") and push, unless push is False (--no-push).
    Returns True if a commit was made."""
    rel = data_dir.relative_to(ROOT).as_posix()
    git("add", "--", rel)
    if git("diff", "--cached", "--quiet", "--", rel, check=False).returncode == 0:
        log("docs/data unchanged; nothing to commit")
        return False
    if message is None:
        message = f"data {read_json(data_dir / 'cities.json').get('asOfDate') or 'unknown'}"
    git("commit", "-m", message, "--", rel)
    log(f"committed: {message}")
    if not push:
        log("not pushed (--no-push)")
        return True
    push = git("push", check=False)
    if push.returncode != 0:
        raise RuntimeError(f"git push failed: {push.stderr.strip()}")
    log("pushed")
    return True


def update(force: bool = False, push: bool = True) -> None:
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
        publish(push=push)
    log("=== check-release ===")
    try:
        check_release()
    except Exception as e:  # the day's data is published; a GitHub hiccup must not fail the run
        log(f"check-release failed (ignored): {e}")
    log("update done")


# --- weekly: the planet history file -----------------------------------------------------------------

def fetch_planet_history() -> bool:
    """Ask osm-extracts to bring the planet history file up to date with replication diffs. A failure
    (most likely too little disk for the second copy) is logged, not raised: the history file as it is
    stays a valid source, only older. Returns True on success."""
    cmd = [sys.executable, str(OSM_EXTRACTS_TOOL), "fetch", "planet-history"]
    log(f"refreshing the planet history file: {' '.join(cmd[1:])}")
    done = subprocess.run(cmd, check=False)
    if done.returncode != 0:
        log(f"fetch planet-history failed (exit {done.returncode}; its message is above); "
            "counting from the history file as it is")
        return False
    return True


def weekly(push: bool = True) -> None:
    """The weekly job: refresh the planet history file, count the weekly regions from it, merge them into
    the archive, rebuild history and publish. Each step that touches data/ takes the pipeline lock, and
    no step starts that would run into the daily update's window (backfill_history.wait_for_quiet), so the
    two never overlap and the daily never finds the lock held. The fetch touches only the shared store,
    which osm-extracts locks itself."""
    sys.path.insert(0, str(TOOLS_DIR))
    import backfill_history as bh  # noqa: E402  (tools/backfill_history.py; it imports this module)
    log("=== planet history ===")
    bh.wait_for_quiet(ahead_minutes=120)  # a week of diffs over the planet: about 1-1.5 h
    fetch_planet_history()
    weekly_regions = regions_by_cadence("weekly")
    try:
        bh.set_planet(None)
        log(f"planet history: planet/{bh.PLANET_FILE}, up to {bh.iso(bh.planet_timestamp())}")
    except SystemExit as e:  # no history file, or no meta: fatal only if a region needs it
        if weekly_regions:
            raise RuntimeError(str(e)) from None
        log(str(e))
    if not weekly_regions:
        log(f'no region is weekly ("cadence" in {REGIONS_CONFIG.name}); the planet history file was all to do')
        return
    log(f"=== count: {', '.join(r['id'] for r in weekly_regions)} ===")
    try:
        t = bh.weekly([r["id"] for r in weekly_regions])
    except SystemExit as e:
        raise RuntimeError(str(e)) from None
    bh.wait_for_quiet()
    with bh.locked():
        log("=== merge ===")
        for r in weekly_regions:
            bh.merge(bh.Region(r["id"]))
        log("=== history ===")
        history()
        log("=== publish ===")
        publish(message=f"data weekly {t.date().isoformat()}", push=push)
    log("weekly done")


# --- SC releases ----------------------------------------------------------------------------------

def pinned_sc_tag(path: Path = SC_VERSION_FILE) -> str:
    """The StreetComplete tag the engine is pinned to ("v64.0"), from engine/SC-VERSION.txt."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("tag="):
            return line[len("tag="):].strip()
    raise ValueError(f"no tag= line in {path}")


def newer_release(pinned: str, releases: list[dict]) -> dict | None:
    """The newest of [releases] ({"version": "v64.0", "date": ...}) whose version is above [pinned],
    or None. Pure, for the tests."""
    newer = [r for r in releases if version_tuple(r["version"]) > version_tuple(pinned)]
    return max(newer, key=lambda r: version_tuple(r["version"])) if newer else None


def repin_issue_title(version: str) -> str:
    return f"Repin to StreetComplete {version}"


def gh(*args: str) -> str:
    """Run the GitHub CLI in the repo; stdout, or a RuntimeError with its stderr."""
    r = subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def repin_issue_exists(title: str) -> bool:
    """True if an issue with exactly this title exists, open or closed (closed means done or declined;
    don't nag again)."""
    out = gh("issue", "list", "--state", "all", "--search", f'"{title}" in:title', "--json", "title")
    return any(i.get("title") == title for i in json.loads(out or "[]"))


def open_repin_issue(release: dict, pinned: str) -> str:
    """Open the issue; returns its URL."""
    version = release["version"]
    url = f"https://github.com/streetcomplete/StreetComplete/releases/tag/{version}"
    body = (f"StreetComplete {version} was released on {release['date']} ({url}); the engine is pinned "
            f"to {pinned} (engine/SC-VERSION.txt), so the daily counts use the {pinned} quest set.\n\n"
            f"Repin it: the routine is REPIN.md. Until then every snapshot carries `scVersion` {pinned[1:]}, "
            f"and the chart marks the break when the first {version[1:]} snapshot lands.\n\n"
            f"Opened by `python run.py check-release` (the scheduled update's last step).")
    return gh("issue", "create", "--title", repin_issue_title(version), "--body", body).strip()


def check_release() -> dict | None:
    """Compare the pinned SC tag with the newest stable GitHub release. Rewrites
    docs/data/sc-releases.json (the timeline pins; the next publish commits it) and, when the app has
    moved on, opens the "Repin to StreetComplete vX.Y" issue once. Returns the newer release, if any."""
    sys.path.insert(0, str(TOOLS_DIR))
    import sc_releases  # noqa: E402  (tools/sc_releases.py)
    releases = sc_releases.stable_releases()
    if sc_releases.write(releases):
        log(f"sc-releases.json: {len(releases)} stable releases, newest {releases[-1]['version']}")
    pinned = pinned_sc_tag()
    release = newer_release(pinned, releases)
    if release is None:
        log(f"pinned {pinned} is the newest stable StreetComplete release")
        return None
    title = repin_issue_title(release["version"])
    if repin_issue_exists(title):
        log(f"{release['version']} is out ({release['date']}), engine pinned to {pinned}; issue \"{title}\" exists")
    else:
        url = open_repin_issue(release, pinned)
        log(f"{release['version']} is out ({release['date']}), engine pinned to {pinned}; opened {url}")
    return release


# --- CLI ------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python run.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download", help="refresh each region's shared extract (osm-extracts fetch)")
    for name, help_ in [("count", "run the engine on each region's newest shared extract"),
                        ("backfill", "count every dated extract in the shared store"),
                        ("update", "download + count + history + commit + push "
                                   "(--force recounts but does not re-download)")]:
        p = sub.add_parser(name, help=help_)
        p.add_argument("--force", action="store_true", help="redo even if nothing changed")
        if name == "update":
            p.add_argument("--no-push", dest="push", action="store_false", help="commit but do not push")
    w = sub.add_parser("weekly", help="planet history + the weekly regions + history + commit + push")
    w.add_argument("--no-push", dest="push", action="store_false", help="commit but do not push")
    h = sub.add_parser("history", help="rebuild history/, cities.json and compare/ from the archived snapshots")
    h.add_argument("--data-dir", type=Path, default=DATA_DIR)
    h.add_argument("--cities", type=Path, default=CITIES_CONFIG)
    h.add_argument("--archive", type=Path, default=None,
                   help=f"where the snapshots are (default {ARCHIVE_DIR.relative_to(ROOT).as_posix()} with the "
                        "default --data-dir, else --data-dir itself)")
    sub.add_parser("migrate-archive", help="move snapshots published in docs/data into data/archive")
    sub.add_parser("check-release", help="open the repin issue if StreetComplete has a newer stable release")
    args = parser.parse_args(argv)
    try:
        if args.command == "download":
            download()
        elif args.command == "backfill":
            backfill(force=args.force)
        elif args.command == "count":
            for region in regions_by_cadence("daily"):
                count(region, force=args.force)
        elif args.command == "history":
            with pipeline_lock():
                history(args.data_dir, args.cities, args.archive)
        elif args.command == "migrate-archive":
            with pipeline_lock():
                migrate_archive()
        elif args.command == "update":
            update(force=args.force, push=args.push)
        elif args.command == "weekly":
            weekly(push=args.push)
        elif args.command == "check-release":
            check_release()
        return 0
    except Exception as e:  # one line in the scheduler log, non-zero exit for Task Scheduler
        log(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    # one module, not two: tools/backfill_history.py imports `run`, and must share this one's lock and paths
    sys.modules.setdefault("run", sys.modules[__name__])
    sys.exit(main())
