"""Copy data/archive/ (every counted snapshot), data/grid/ (every z14 tile grid), data/facts/ (every count as
Parquet) and the world's gated days (its counts per place), which are not in git and exist only on this disk, to their own private R2 bucket.

    python tools/archive_backup.py            copy new and changed files up; never deletes
    python tools/archive_backup.py --dry-run  say what it would do
    python tools/archive_backup.py --check    compare every local file with the bucket, change nothing

The bucket is sc-open-quests-archive, never the site's (tools/cloud_publish.py prunes that one to
docs/ every day). Files land under archive/, grid/, facts/ and world/. It is a copy, not a sync: a file deleted here stays
there. A file that a rerun rewrote is kept too: the bucket's old version moves to
replaced/<today>/archive/... before the new one goes up, so a bad run cannot overwrite the backup.
The per-region quests.json files are rewritten on every count, about 1.6 MB a day into replaced/.

To restore: rclone copy r2:sc-open-quests-archive/archive data/archive (and grid the same), with the RCLONE_CONFIG_R2_*
variables cloud_publish.rclone_env() builds from the token file.

The world (DESIGN.md, "Storage: facts, serving, working state", step 1): of .scratch/planet/world-1101, each day
whose gate passed: counts/<D>/ (counts.json, counts.npz, the seed's gate) and days/<D>/ (day.json, gate.json, engines.json, steps.json),
plus plan.json and world.json. A day without a passed gate is not copied: its counts may still be written. The
row files, the node store and the tile store are working state and are not copied here. A checkout without the
world folder skips it. --only names one of archive, grid, facts, world.

Same token file and rclone as cloud_publish.py. The bucket is made on the first run.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cloud_publish  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "data" / "archive"
BUCKET = "sc-open-quests-archive"
GRID = ROOT / "data" / "grid"
FACTS = ROOT / "data" / "facts"   # tools/facts.py: every count as Parquet, cities and world
PLACE_IDS = ROOT / "data" / "place-ids"   # tools/place_ids.py: our place ids, random, so the only copy there is
SOURCES = [(ARCHIVE, "archive"), (GRID, "grid"), (FACTS, "facts"), (PLACE_IDS, "place-ids")]   # folder, its prefix in the bucket
WORLD = ROOT / json.loads((ROOT / "data/world.json").read_text(encoding="utf-8"))["world"]  # the world folder: data/world.json says which (a reseed flips it there)
WORLD_TOP = ["plan.json", "world.json"]   # what a day's counts are read with: the cells, the world's clock
MIN_FILES = 1000          # the archive held 1,497 files when it was split off; fewer is a broken checkout


def log(msg: str) -> None:
    print(f"[backup] {msg}", flush=True)


def ensure_bucket(env: dict[str, str], bucket: str = BUCKET) -> bool:
    """Make the bucket if the account lacks it. Returns True if it was made now."""
    base = f"https://api.cloudflare.com/client/v4/accounts/{env['CLOUDFLARE_ACCOUNT_ID']}/r2/buckets"
    headers = {"Authorization": f"Bearer {env['CLOUDFLARE_API_TOKEN']}", "Content-Type": "application/json"}
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{base}/{bucket}", headers=headers), timeout=30):
            return False
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise RuntimeError(f"asking for bucket {bucket}: HTTP {e.code}") from e
    body = json.dumps({"name": bucket, "locationHint": "enam"}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(base, data=body, headers=headers, method="POST"),
                                    timeout=30) as r:
            if not json.load(r).get("success"):
                raise RuntimeError(f"making bucket {bucket} did not succeed")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"making bucket {bucket}: HTTP {e.code} {e.read()[:300]!r}") from e
    return True


def least(archive: Path) -> int:
    """how many files a source must hold: the registry is one file, the others are many"""
    return 1 if archive == PLACE_IDS else MIN_FILES


def check_source(archive: Path, bucket: str) -> int:
    """Raise unless this is the archive going to its own bucket. Returns the number of local files."""
    if bucket == cloud_publish.BUCKET:
        raise RuntimeError(f"{bucket} is the site's bucket, which the daily sync prunes to docs/")
    n = sum(1 for p in archive.rglob("*") if p.is_file()) if archive.is_dir() else 0
    if n < least(archive):
        raise RuntimeError(f"{archive} holds {n} files, under {least(archive)}; not backing up what looks partial")
    return n


def backup(dry_run: bool = False, archive: Path = ARCHIVE, bucket: str = BUCKET, prefix: str = "archive") -> None:
    n = check_source(archive, bucket)
    cf = cloud_publish.read_env()
    if not dry_run:
        import spend_breaker
        spend_breaker.gate(planned_class_a=2 * n + 100, env=cf)   # each file and its replaced/ copy, at most
    if not dry_run and ensure_bucket(cf, bucket):
        log(f"made bucket {bucket}")
    env = cloud_publish.rclone_env(cf)
    today = datetime.date.today().isoformat()
    args = ["copy", str(archive), f"r2:{bucket}/{prefix}", "--checksum", "--transfers", "16", "--checkers", "32",
            "--backup-dir", f"r2:{bucket}/replaced/{today}/{prefix}",
            "--stats-one-line", "--stats", "0", "-v"]
    if dry_run:
        args.append("--dry-run")
    r = cloud_publish.rclone(args, env)
    lines = (r.stderr or "").splitlines()
    if r.returncode != 0:
        raise RuntimeError(f"rclone copy failed (exit {r.returncode}):\n" + "\n".join(lines[-15:]))
    # rclone keeps a replaced file by a server-side copy into --backup-dir, logged as a copy too
    kept = sum(1 for l in lines if "server-side copy" in l or ": Moved" in l or ": Skipped move" in l)
    copied = sum(1 for l in lines if ": Copied" in l or ": Skipped copy" in l) -         sum(1 for l in lines if "server-side copy" in l)
    verb = "would upload" if dry_run else "uploaded"
    log(f"{n} files in data/{archive.name}; {verb} {copied}, {kept} replaced version(s) kept under replaced/{today}/")


def check(archive: Path = ARCHIVE, bucket: str = BUCKET, prefix: str = "archive") -> int:
    """Compare every local file with the bucket by checksum. Returns how many are missing or differ."""
    n = check_source(archive, bucket)
    env = cloud_publish.rclone_env(cloud_publish.read_env())
    r = cloud_publish.rclone(["check", str(archive), f"r2:{bucket}/{prefix}", "--one-way", "--checkers", "32"], env)
    lines = (r.stderr or "").splitlines()
    bad = [l for l in lines if "ERROR" in l and ("not found" in l or "differ" in l)]
    for l in bad[:20]:
        log(l.split("ERROR :", 1)[-1].strip())
    if r.returncode != 0 and not bad:
        raise RuntimeError(f"rclone check failed (exit {r.returncode}):\n" + "\n".join(lines[-15:]))
    log(f"checked {n} files of data/{archive.name} against {bucket}: {n - len(bad)} equal, {len(bad)} missing or different")
    return len(bad)


def world_files(world: Path = WORLD) -> tuple[list[str], list[str]]:
    """The gated days of the world, and the files to copy, as paths under `world` with forward slashes."""
    days, files = [], []
    counts = world / "counts"
    for d in sorted(p.name for p in counts.iterdir() if p.is_dir()) if counts.is_dir() else []:
        gate = world / "days" / d / "gate.json"
        ok = (counts / d / "gate1101.json").exists()      # the seed's day, gated against the whole count
        if not ok and gate.exists():
            ok = bool(json.loads(gate.read_text(encoding="utf-8")).get("ok"))
        if not ok or not (counts / d / "counts.npz").exists():
            continue
        days.append(d)
        files += [f"counts/{d}/{p.name}" for p in sorted((counts / d).iterdir()) if p.is_file()]
        files += [f"days/{d}/{n}" for n in ("day.json", "gate.json", "engines.json", "steps.json") if (world / "days" / d / n).exists()]
    if days:
        files += [n for n in WORLD_TOP if (world / n).exists()]
    return days, files


def _files_from(files: list[str]) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8", newline="\n") as f:
        f.write("\n".join(files) + "\n")
        return f.name


def backup_world(dry_run: bool = False, world: Path = WORLD, bucket: str = BUCKET, prefix: str = "world") -> None:
    if not world.is_dir():
        log(f"no world at {world}; skipped")
        return
    if bucket == cloud_publish.BUCKET:
        raise RuntimeError(f"{bucket} is the site's bucket, which the daily sync prunes to docs/")
    days, files = world_files(world)
    if not days:
        raise RuntimeError(f"{world} has no gated day; not backing up what looks partial")
    cf = cloud_publish.read_env()
    if not dry_run:
        import spend_breaker
        spend_breaker.gate(planned_class_a=2 * len(files) + 100, env=cf)
    if not dry_run and ensure_bucket(cf, bucket):
        log(f"made bucket {bucket}")
    env = cloud_publish.rclone_env(cf)
    today = datetime.date.today().isoformat()
    listing = _files_from(files)
    try:
        args = ["copy", str(world), f"r2:{bucket}/{prefix}", "--files-from", listing, "--checksum",
                "--transfers", "4", "--backup-dir", f"r2:{bucket}/replaced/{today}/{prefix}",
                "--stats-one-line", "--stats", "0", "-v"]
        if dry_run:
            args.append("--dry-run")
        r = cloud_publish.rclone(args, env)
    finally:
        Path(listing).unlink(missing_ok=True)
    lines = (r.stderr or "").splitlines()
    if r.returncode != 0:
        raise RuntimeError(f"rclone copy failed (exit {r.returncode}):\n" + "\n".join(lines[-15:]))
    kept = sum(1 for l in lines if "server-side copy" in l or ": Moved" in l or ": Skipped move" in l)
    copied = sum(1 for l in lines if ": Copied" in l or ": Skipped copy" in l) - kept
    verb = "would upload" if dry_run else "uploaded"
    log(f"world: {len(days)} gated days {days[0]} to {days[-1]}, {len(files)} files; {verb} {copied}, "
        f"{kept} replaced version(s) kept under replaced/{today}/")


def check_world(world: Path = WORLD, bucket: str = BUCKET, prefix: str = "world") -> int:
    """Compare the world's files with the bucket by checksum. Returns how many are missing or differ."""
    if not world.is_dir():
        log(f"no world at {world}; skipped")
        return 0
    days, files = world_files(world)
    env = cloud_publish.rclone_env(cloud_publish.read_env())
    listing = _files_from(files)
    try:
        r = cloud_publish.rclone(["check", str(world), f"r2:{bucket}/{prefix}", "--one-way",
                                  "--files-from", listing], env)
    finally:
        Path(listing).unlink(missing_ok=True)
    lines = (r.stderr or "").splitlines()
    bad = [l for l in lines if "ERROR" in l and ("not found" in l or "differ" in l)]
    for l in bad[:20]:
        log(l.split("ERROR :", 1)[-1].strip())
    if r.returncode != 0 and not bad:
        raise RuntimeError(f"rclone check failed (exit {r.returncode}):\n" + "\n".join(lines[-15:]))
    log(f"checked {len(files)} files of the world's {len(days)} gated days against {bucket}: "
        f"{len(files) - len(bad)} equal, {len(bad)} missing or different")
    return len(bad)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--check", action="store_true", help="compare with the bucket; change nothing")
    p.add_argument("--only", choices=["archive", "grid", "facts", "place-ids", "world"], help="one source instead of all")
    p.add_argument("--world", type=Path, default=WORLD, help="the world folder (default: this checkout's)")
    a = p.parse_args()
    sources = [(f, x) for f, x in SOURCES if a.only in (None, x)]
    if a.only is None and not PLACE_IDS.is_dir():   # before the ids are minted there is nothing to copy
        sources = [(f, x) for f, x in sources if f != PLACE_IDS]
    failed = 0
    try:
        if a.check:
            failed = sum(check(folder, prefix=prefix) for folder, prefix in sources)
        else:
            for folder, prefix in sources:
                backup(dry_run=a.dry_run, archive=folder, prefix=prefix)
    except RuntimeError as e:
        log(f"FAILED: {e}")
        failed = 1
    if a.only in (None, "world"):     # on its own: the archive's failure must not leave the world uncopied
        try:
            if a.check:
                failed += check_world(a.world)
            else:
                backup_world(dry_run=a.dry_run, world=a.world)
        except RuntimeError as e:
            log(f"FAILED: {e}")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
