"""Daily pipeline for sc-open-quests. Python standard library only.

Subcommands:
  download   Geofabrik Ontario PBF -> data/osm/ (skipped when Last-Modified is unchanged)
  count      run the engine on the PBF -> docs/data/snapshots/<asOfDate>.json + quests.json
             (skipped when a snapshot of this extract already exists)
  history    rebuild docs/data/history/<cityId>.json and docs/data/cities.json from all snapshots
  update     download + count + history, then commit "data <asOfDate>" and push

The contract between engine, pipeline and site is DATA-FORMAT.md.
"""
from __future__ import annotations

import argparse
import contextlib
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PBF_URL = "https://download.geofabrik.de/north-america/canada/ontario-latest.osm.pbf"
OSM_DIR = ROOT / "data" / "osm"
PBF_PATH = OSM_DIR / "ontario-latest.osm.pbf"
META_PATH = OSM_DIR / "meta.json"
LOCK_PATH = OSM_DIR / "refresh.lock"

QUESTS_DIR = ROOT / "data" / "quests"
CITIES_CONFIG = ROOT / "config" / "cities.json"
DATA_DIR = ROOT / "docs" / "data"

ENGINE_DIR = ROOT / "engine"
ENGINE_INSTALL = ENGINE_DIR / "build" / "install" / "sc-open-quests-engine"
ENGINE_BAT = ENGINE_INSTALL / "bin" / "sc-open-quests-engine.bat"
JAVA_HOME = r"C:\Program Files\Android\Android Studio\jbr"

CHUNK = 1 << 20
HTTP_TIMEOUT = 60
USER_AGENT = "sc-open-quests (+https://github.com/skfd/sc-open-quests)"


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
    """PID lock in data/osm/refresh.lock. Re-entrant within this process."""
    global _lock_depth
    if _lock_depth == 0:
        OSM_DIR.mkdir(parents=True, exist_ok=True)
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


# --- download -------------------------------------------------------------------------------------

def http_head(url: str) -> dict[str, str]:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return {k.lower(): v for k, v in r.headers.items()}


def http_download(url: str, dest: Path) -> tuple[str, int]:
    """Stream url to dest via dest.partial, hashing on the way. Returns (sha256, bytes)."""
    tmp = dest.with_name(dest.name + ".partial")
    sha, total, next_log = hashlib.sha256(), 0, 100 * CHUNK
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r, open(tmp, "wb") as f:
        size = int(r.headers.get("Content-Length") or 0)
        while chunk := r.read(CHUNK):
            f.write(chunk)
            sha.update(chunk)
            total += len(chunk)
            if total >= next_log:
                pct = f" ({100 * total // size}%)" if size else ""
                log(f"  {total >> 20} MiB{pct}")
                next_log += 100 * CHUNK
    if size and total != size:
        raise IOError(f"short download: {total} of {size} bytes")
    tmp.replace(dest)
    return sha.hexdigest(), total


def read_meta() -> dict | None:
    try:
        return read_json(META_PATH)
    except (OSError, ValueError):
        return None


def download(force: bool = False, url: str = PBF_URL) -> bool:
    """Fetch the extract if Geofabrik has a new one. Returns True if a new file was downloaded."""
    with pipeline_lock():
        log(f"HEAD {url}")
        headers = http_head(url)
        last_modified = headers.get("last-modified", "")
        log(f"source Last-Modified: {last_modified or '(none)'}, {headers.get('content-length', '?')} bytes")
        prior = read_meta() or {}
        if (not force and last_modified and PBF_PATH.exists()
                and prior.get("source_last_modified") == last_modified):
            log("extract unchanged; skipping download")
            return False
        log(f"downloading to {PBF_PATH.relative_to(ROOT)}")
        sha, size = http_download(url, PBF_PATH)
        write_json(META_PATH, {
            "source_url": url,
            "source_last_modified": last_modified,
            "source_bytes": size,
            "pbf_sha256": sha,
            "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        log(f"downloaded {size:,} bytes, sha256 {sha[:16]}…")
        return True


# --- count ----------------------------------------------------------------------------------------

def newest_quests_file(quests_dir: Path = QUESTS_DIR) -> Path:
    def version(p: Path):
        m = re.fullmatch(r"v(\d+(?:\.\d+)*)\.json", p.name)
        return tuple(int(x) for x in m.group(1).split(".")) if m else None
    files = [p for p in quests_dir.glob("v*.json") if version(p)]
    if not files:
        raise FileNotFoundError(f"no quest registry in {quests_dir} (run tools/sc-harness)")
    return max(files, key=version)


def snapshot_for_sha(sha: str, data_dir: Path = DATA_DIR) -> Path | None:
    for p in sorted((data_dir / "snapshots").glob("*.json")):
        try:
            if read_json(p).get("source", {}).get("sha256") == sha:
                return p
        except (OSError, ValueError):
            continue
    return None


def engine_env() -> dict[str, str]:
    env = dict(os.environ)
    if os.path.isdir(JAVA_HOME):
        env["JAVA_HOME"] = JAVA_HOME
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


def count(force: bool = False) -> Path | None:
    """Run the engine on the current extract. Returns the snapshot path, or None if skipped."""
    with pipeline_lock():
        meta = read_meta()
        if not meta or not PBF_PATH.exists():
            raise FileNotFoundError("no extract in data/osm/; run `python run.py download` first")
        existing = snapshot_for_sha(meta["pbf_sha256"])
        if existing and not force:
            log(f"{existing.relative_to(ROOT)} already counts this extract; skipping (--force to redo)")
            return None
        if engine_is_stale():
            build_engine()
        quests = newest_quests_file()
        cmd = [str(ENGINE_BAT), "count",
               "--pbf", str(PBF_PATH.relative_to(ROOT)),
               "--quests", str(quests.relative_to(ROOT)),
               "--cities", str(CITIES_CONFIG.relative_to(ROOT)),
               "--out", str(DATA_DIR.relative_to(ROOT)),
               "--source-meta", str(META_PATH.relative_to(ROOT))]
        log("running engine: " + " ".join(cmd[1:]))
        subprocess.run(cmd, cwd=ROOT, env=engine_env(), check=True)
        snap = snapshot_for_sha(meta["pbf_sha256"])
        if not snap:
            raise RuntimeError("engine finished but no snapshot carries this extract's sha256")
        log(f"wrote {snap.relative_to(ROOT)}")
        return snap


# --- history --------------------------------------------------------------------------------------

def load_snapshots(data_dir: Path) -> list[dict]:
    """All snapshots, ascending by asOfDate."""
    snaps = [read_json(p) for p in (data_dir / "snapshots").glob("*.json")]
    return sorted(snaps, key=lambda s: s["asOfDate"])


def default_disabled(data_dir: Path) -> set[str]:
    """Names of default-disabled quests: from quests.json, else the newest registry dump."""
    path = data_dir / "quests.json"
    if not path.exists():
        path = newest_quests_file()
    return {q["name"] for q in read_json(path)["quests"] if q.get("defaultDisabled")}


def build_history(snapshots: list[dict], city_config: list[dict], disabled: set[str]) -> dict:
    """Turn snapshots into {"history": {cityId: series}, "cities": index}.

    A city's series has one entry per snapshot that contains the city; a city missing from a
    snapshot (added to the config later, say) has no entry for that date rather than a row of
    nulls. Within a city, a quest missing from one snapshot (not counted under that SC version,
    or new in a later one) is null at that index, never 0.
    """
    names = {c["id"]: c["name"] for c in city_config}
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
            "meta": [{"scVersion": s["scVersion"], "resurveyMultiplier": s["resurveyMultiplier"]}
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
        index.append({
            "id": cid,
            "name": series["name"],
            "asOfDate": last_snap["asOfDate"],
            "scVersion": last_snap["scVersion"],
            "landAreaKm2": den.get("landAreaKm2"),
            "population": den.get("population"),
            "highwayKm": den.get("highwayKm"),
            "open": sum(q.get("open") or 0 for q in headline.values()),
            "agedOnly": sum(q.get("agedOnly") or 0 for q in headline.values()),
            "openAll": sum(q.get("open") or 0 for q in last["quests"].values()),
            "questsCounted": len(last["quests"]),
        })
    index.sort(key=lambda c: c["name"])
    latest = snapshots[-1] if snapshots else {}
    cities = {"asOfDate": latest.get("asOfDate"), "scVersion": latest.get("scVersion"),
              "resurveyMultiplier": latest.get("resurveyMultiplier"), "cities": index}
    return {"history": history, "cities": cities}


def history(data_dir: Path = DATA_DIR, cities_config: Path = CITIES_CONFIG) -> int:
    """Rewrite history/*.json and cities.json under data_dir. Returns the number of files changed."""
    snapshots = load_snapshots(data_dir)
    if not snapshots:
        log(f"no snapshots in {data_dir / 'snapshots'}; nothing to do")
        return 0
    out = build_history(snapshots, read_json(cities_config)["cities"], default_disabled(data_dir))
    changed = 0
    for cid, series in out["history"].items():
        changed += write_json(data_dir / "history" / f"{cid}.json", series, compact=True)
    for stale in (data_dir / "history").glob("*.json"):
        if stale.stem not in out["history"]:
            stale.unlink()
            changed += 1
    changed += write_json(data_dir / "cities.json", out["cities"])
    log(f"history: {len(out['history'])} cities over {len(snapshots)} snapshot(s), {changed} file(s) changed")
    return changed


# --- update ---------------------------------------------------------------------------------------

def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=check)


def publish(data_dir: Path = DATA_DIR) -> bool:
    """Commit docs/data as "data <asOfDate>" and push. Returns True if a commit was made."""
    rel = str(data_dir.relative_to(ROOT))
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
        download()  # never forced here: --force recounts, it does not refetch 1 GB
        log("=== count ===")
        count(force=force)
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
    for name, help_ in [("download", "fetch the Geofabrik Ontario extract if it changed"),
                        ("count", "run the engine on the extract"),
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
            download(force=args.force)
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
