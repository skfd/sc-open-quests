"""Make the R2 bucket that serves street-complete-statistics.comentality.com equal to docs/.

    python tools/cloud_publish.py            sync docs/ to the bucket (uploads changed files, deletes gone ones)
    python tools/cloud_publish.py --dry-run  say what it would do
    python tools/cloud_publish.py --check    compare every file over HTTPS through the site, change nothing

The Cloudflare token lives outside the repo, in ~/.config/sc-open-quests/cloudflare.env
(CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID); SC_OPEN_QUESTS_CLOUDFLARE_ENV names another file.
R2's S3 credentials are derived from it (access key = the token's id, secret = SHA-256 of its value),
so there is one secret, not two. Needs rclone on PATH.

It refuses a docs/ that looks partial (no index.html or data/cities.json, or far fewer files than the
bucket holds) and never deletes more than MAX_DELETE objects in one run, so a broken checkout cannot
empty the site.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
BUCKET = "sc-open-quests"
SITE = "https://street-complete-statistics.comentality.com"
ENV_FILE = Path(os.environ.get("SC_OPEN_QUESTS_CLOUDFLARE_ENV",
                               Path.home() / ".config" / "sc-open-quests" / "cloudflare.env"))
MAX_DELETE = 2000          # a day retires a few hundred snapshot files at most
MIN_SHARE = 0.5            # docs/ must hold at least half as many files as the bucket


def log(msg: str) -> None:
    print(f"[cloud] {msg}", flush=True)


def read_env(path: Path = ENV_FILE) -> dict[str, str]:
    if not path.exists():
        raise RuntimeError(f"no Cloudflare token file at {path}")
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        if not env.get(k):
            raise RuntimeError(f"{path} lacks {k}")
    return env


def token_id(token: str) -> str:
    req = urllib.request.Request("https://api.cloudflare.com/client/v4/user/tokens/verify",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if not d.get("success") or d["result"].get("status") != "active":
        raise RuntimeError(f"Cloudflare token not active: {d.get('errors')}")
    return d["result"]["id"]


def rclone_env(env: dict[str, str]) -> dict[str, str]:
    token = env["CLOUDFLARE_API_TOKEN"]
    out = dict(os.environ)
    out.update({
        "RCLONE_CONFIG_R2_TYPE": "s3",
        "RCLONE_CONFIG_R2_PROVIDER": "Cloudflare",
        "RCLONE_CONFIG_R2_ACCESS_KEY_ID": token_id(token),
        "RCLONE_CONFIG_R2_SECRET_ACCESS_KEY": hashlib.sha256(token.encode()).hexdigest(),
        "RCLONE_CONFIG_R2_ENDPOINT": f"https://{env['CLOUDFLARE_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        "RCLONE_CONFIG_R2_NO_CHECK_BUCKET": "true",
    })
    return out


def local_files(docs: Path = DOCS) -> list[str]:
    return sorted(p.relative_to(docs).as_posix() for p in docs.rglob("*") if p.is_file())


def check_source(files: list[str], remote_count: int) -> None:
    """Raise unless docs/ looks whole."""
    for need in ("index.html", "app.js", "data/cities.json"):
        if need not in files:
            raise RuntimeError(f"docs/{need} is missing; refusing to publish a partial site")
    if remote_count and len(files) < MIN_SHARE * remote_count:
        raise RuntimeError(f"docs/ holds {len(files)} files against {remote_count} in the bucket; "
                           "refusing to publish what looks like a partial site")


def rclone(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(["rclone", *args], env=env, capture_output=True, text=True)


def remote_count(env: dict[str, str]) -> int:
    r = rclone(["size", "--json", f"r2:{BUCKET}"], env)
    if r.returncode != 0:
        raise RuntimeError(f"rclone size failed: {r.stderr.strip()[-500:]}")
    return int(json.loads(r.stdout)["count"])


def sync(dry_run: bool = False, docs: Path = DOCS) -> None:
    env = rclone_env(read_env())
    files = local_files(docs)
    count = remote_count(env)
    check_source(files, count)
    log(f"docs/ {len(files)} files, bucket {count} objects; syncing")
    args = ["sync", str(docs), f"r2:{BUCKET}", "--checksum", "--transfers", "16", "--checkers", "32",
            "--max-delete", str(MAX_DELETE), "--stats-one-line", "--stats", "0", "-v",
            "--exclude", ".DS_Store", "--exclude", "Thumbs.db"]
    if dry_run:
        args.append("--dry-run")
    r = rclone(args, env)
    lines = (r.stderr or "").splitlines()
    copied = sum(1 for l in lines if ": Copied" in l or ": Skipped copy" in l)
    deleted = sum(1 for l in lines if ": Deleted" in l or ": Skipped delete" in l)
    if r.returncode != 0:
        tail = "\n".join(lines[-15:])
        raise RuntimeError(f"rclone sync failed (exit {r.returncode}):\n{tail}")
    log(f"{'would copy' if dry_run else 'copied'} {copied}, {'would delete' if dry_run else 'deleted'} {deleted}")


# The comentality.com zone has Cloudflare Web Analytics on, which adds one beacon script before </body>
# of every HTML page; the check takes it out again before comparing.
BEACON = re.compile(rb'<script[^>]*static\.cloudflareinsights\.com/beacon[^>]*></script>\n?')


def _fetch_md5(rel: str, tries: int = 4) -> tuple[str, str | None, int | str]:
    """The file's MD5 as served, retrying dropped connections and 5xx (a blip is not a difference)."""
    url = SITE + "/" + urllib.parse.quote(rel)
    req = urllib.request.Request(url, headers={"User-Agent": "sc-open-quests-check"})
    result: tuple[str, str | None, int | str] = (rel, None, "not fetched")
    for attempt in range(tries):
        if attempt:
            time.sleep(2 * attempt)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
                if rel.endswith(".html"):
                    body = BEACON.sub(b"", body)
                return rel, hashlib.md5(body).hexdigest(), r.status
        except urllib.error.HTTPError as e:
            result = (rel, None, e.code)
            if e.code < 500:
                return result
        except Exception as e:  # noqa: BLE001  (connection reset, timeout)
            result = (rel, None, str(e))
    return result


def check(docs: Path = DOCS, workers: int = 16) -> int:
    """Fetch every file of docs/ through the site and compare bytes. Returns the number that differ."""
    files = local_files(docs)
    want = {f: hashlib.md5((docs / f).read_bytes()).hexdigest() for f in files}
    bad = []
    with concurrent.futures.ThreadPoolExecutor(workers) as ex:
        for rel, got, status in ex.map(_fetch_md5, files):
            if got != want[rel]:
                bad.append((rel, status))
    for rel, status in bad[:20]:
        log(f"differs: {rel} ({status})")
    log(f"checked {len(files)} files over {SITE}: {len(files) - len(bad)} equal, {len(bad)} differ")
    return len(bad)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--check", action="store_true", help="compare every file over HTTPS; change nothing")
    a = p.parse_args()
    try:
        if a.check:
            return 1 if check() else 0
        sync(dry_run=a.dry_run)
        return 0
    except RuntimeError as e:
        log(f"FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
