"""Copy data/archive/ (every counted snapshot) and data/grid/ (every z14 tile grid), which are not in
git and exist only on this disk, to their own private R2 bucket.

    python tools/archive_backup.py            copy new and changed files up; never deletes
    python tools/archive_backup.py --dry-run  say what it would do
    python tools/archive_backup.py --check    compare every local file with the bucket, change nothing

The bucket is sc-open-quests-archive, never the site's (tools/cloud_publish.py prunes that one to
docs/ every day). Files land under archive/ and grid/. It is a copy, not a sync: a file deleted here stays
there. A file that a rerun rewrote is kept too: the bucket's old version moves to
replaced/<today>/archive/... before the new one goes up, so a bad run cannot overwrite the backup.
The per-region quests.json files are rewritten on every count, about 1.6 MB a day into replaced/.

To restore: rclone copy r2:sc-open-quests-archive/archive data/archive (and grid the same), with the RCLONE_CONFIG_R2_*
variables cloud_publish.rclone_env() builds from the token file.

Same token file and rclone as cloud_publish.py. The bucket is made on the first run.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cloud_publish  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "data" / "archive"
BUCKET = "sc-open-quests-archive"
GRID = ROOT / "data" / "grid"
SOURCES = [(ARCHIVE, "archive"), (GRID, "grid")]   # folder, its prefix in the bucket
MIN_FILES = 1000           # the archive held 1,497 files when it was split off; fewer is a broken checkout


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


def check_source(archive: Path, bucket: str) -> int:
    """Raise unless this is the archive going to its own bucket. Returns the number of local files."""
    if bucket == cloud_publish.BUCKET:
        raise RuntimeError(f"{bucket} is the site's bucket, which the daily sync prunes to docs/")
    n = sum(1 for p in archive.rglob("*") if p.is_file()) if archive.is_dir() else 0
    if n < MIN_FILES:
        raise RuntimeError(f"{archive} holds {n} files, under {MIN_FILES}; not backing up what looks partial")
    return n


def backup(dry_run: bool = False, archive: Path = ARCHIVE, bucket: str = BUCKET, prefix: str = "archive") -> None:
    n = check_source(archive, bucket)
    cf = cloud_publish.read_env()
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


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--check", action="store_true", help="compare with the bucket; change nothing")
    a = p.parse_args()
    try:
        if a.check:
            return 1 if sum(check(folder, prefix=prefix) for folder, prefix in SOURCES) else 0
        for folder, prefix in SOURCES:
            backup(dry_run=a.dry_run, archive=folder, prefix=prefix)
        return 0
    except RuntimeError as e:
        log(f"FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
