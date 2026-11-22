"""A checkpoint of the world's working state: its 128 row files, off this disk, in the private archive bucket.

DESIGN.md, "Storage: facts, serving, working state": the row files are a cache with a checkpoint, not a backup;
the node store and the tile store are never copied (a planet file and diffs rebuild them). Two steps, so the world
day loop need not stand still for the upload:

    python tools/state_checkpoint.py link              between two days (HOLD, no run going): each file's rows
                                                       hard-linked into .scratch/planet/checkpoint/<clock>/, the
                                                       small files copied. Seconds, no bytes of rows copied: the
                                                       loop's writes replace a file, so a link keeps what it was.
    python tools/state_checkpoint.py upload --from-world  with the loop held: straight from the world's files
    python tools/state_checkpoint.py upload [--dry-run] the newest linked checkpoint to
                                                       r2:sc-open-quests-archive/state/<clock>/; may run beside the loop
    python tools/state_checkpoint.py prune [--keep 2]   older checkpoints: the local links, and in the bucket all but
                                                       the newest --keep that are complete (a `done` object)
    python tools/state_checkpoint.py list

**The links cost disk.** A link keeps a file's old bytes alive once the loop has replaced it, so a linked
checkpoint grows to the rows' whole size (52.5 GiB on 2026-11-14) within a day, beside the day's own `before/` copy
of the same size. On 2026-11-22 that filled the disk and stopped the loop at 01:43 (HANDOFF, "The loop stopped on a
full disk"). So: `link` refuses unless the disk has room for it (twice the rows and LINK_SPARE_GIB), `upload`
removes the links it uploaded, and where the disk has no such room the checkpoint is taken with the loop held:
`upload --from-world` (HOLD there, no run going) reads the world's own files, no links at all, at the price of the
loop standing still for the upload (about an hour and a half).

To restore: rclone copy r2:sc-open-quests-archive/state/<clock> <folder>, then the loop's own `restore` shape:
files/<id>/world.bin into the world's files, the small files beside them, world-keys.npy derived from the rows
(tools/stream/planet_store_day.py `restore`). The diffs after <clock> bring it forward a day at a time.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive_backup  # noqa: E402
import cloud_publish  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORLD = archive_backup.WORLD
LOCAL = ROOT / ".scratch" / "planet" / "checkpoint"
RUNNING = ROOT / ".scratch" / "planet-cut" / "RUNNING"
BUCKET = archive_backup.BUCKET
PREFIX = "state"
HOLD = ROOT / ".scratch" / "planet-cut" / "HOLD"
LINK_SPARE_GIB = 40          # beside twice the rows: a day's work and what the store adds
ROWS = "world.bin"                                   # tools/stream/world_state.py WORLD_BIN
SMALL = ("world.json", "place-sets.json", "touched.npy", "rects.npy", "plan.json")   # the loop's SMALL, and the plan


def log(msg: str) -> None:
    print(f"[checkpoint] {msg}", flush=True)


def clock_of(world: Path) -> str:
    return json.loads((world / "world.json").read_text(encoding="utf-8"))["clock"]


def link(world: Path = WORLD, local: Path = LOCAL, running: Path = RUNNING, spare_check: bool = True) -> Path:
    if running.exists():
        raise RuntimeError(f"{running} exists: a run is moving the world; link between two days, under HOLD")
    clock = clock_of(world)
    out = local / clock[:10]
    if (out / "done").exists():
        log(f"{out} is already there")
        return out
    rows = sum((world / "files" / f["id"] / ROWS).stat().st_size
               for f in json.loads((world / "plan.json").read_text(encoding="utf-8"))["files"])
    local.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(local).free
    need = 2 * rows + (LINK_SPARE_GIB << 30)
    if spare_check and free < need:
        raise RuntimeError(f"{free / 2**30:.0f} GiB free, {need / 2**30:.0f} needed to hold a linked checkpoint through a "
                           f"day (twice the rows' {rows / 2**30:.1f} GiB and {LINK_SPARE_GIB}): hold the loop and run "
                           f"`upload --from-world` instead")
    shutil.rmtree(out, ignore_errors=True)
    ids = [f["id"] for f in json.loads((world / "plan.json").read_text(encoding="utf-8"))["files"]]
    size = 0
    for fid in ids:
        d = out / "files" / fid
        d.mkdir(parents=True)
        os.link(world / "files" / fid / ROWS, d / ROWS)
        size += (d / ROWS).stat().st_size
    for n in SMALL:
        if (world / n).exists():
            shutil.copy2(world / n, out / n)
    if clock_of(world) != clock:
        shutil.rmtree(out, ignore_errors=True)
        raise RuntimeError("the world's clock moved while it was linked")
    (out / "done").write_text(json.dumps({"clock": clock, "files": len(ids), "rowBytes": size}) + "\n", encoding="utf-8")
    log(f"linked the world at {clock}: {len(ids)} files, {size / 2**30:.1f} GiB of rows, into {out}")
    return out


def newest(local: Path = LOCAL) -> Path:
    done = sorted(p for p in local.iterdir() if (p / "done").exists()) if local.is_dir() else []
    if not done:
        raise RuntimeError(f"no linked checkpoint under {local}: run `link` between two days first")
    return done[-1]


def staged(world: Path, local: Path) -> Path:
    """a folder in a checkpoint's shape whose rows ARE the world's files (links made now, to be removed when the
    upload ends): only under HOLD with no run going, so nothing replaces a file meanwhile and no old bytes are kept"""
    return link(world, local, RUNNING, spare_check=False)


def upload(local: Path = LOCAL, dry_run: bool = False, bucket: str = BUCKET, from_world: bool = False,
           world: Path = WORLD, hold: Path = HOLD, running: Path = RUNNING) -> None:
    if from_world:
        if not hold.exists() or running.exists():
            raise RuntimeError(f"--from-world needs {hold} in place and no run going ({running}): the world must stand still")
        src = staged(world, local)
    else:
        src = newest(local)
    info = json.loads((src / "done").read_text(encoding="utf-8"))
    if bucket == cloud_publish.BUCKET:
        raise RuntimeError(f"{bucket} is the site's bucket, which the daily sync prunes to docs/")
    cf = cloud_publish.read_env()
    if not dry_run:
        import spend_breaker
        # 64 MiB parts: a write per part, and a few per file
        spend_breaker.gate(planned_class_a=int(info["rowBytes"] / (64 << 20)) + 4 * info["files"] + 100, env=cf)
        archive_backup.ensure_bucket(cf, bucket)
    env = cloud_publish.rclone_env(cf)
    dest = f"r2:{bucket}/{PREFIX}/{src.name}"
    # `done` goes last and alone: a checkpoint in the bucket without it is not whole
    args = ["copy", str(src), dest, "--exclude", "/done", "--transfers", "4", "--s3-chunk-size", "64M",
            "--s3-upload-concurrency", "4", "--stats-one-line", "--stats", "0", "-v"]
    r = cloud_publish.rclone(args + (["--dry-run"] if dry_run else []), env)
    if r.returncode != 0:
        raise RuntimeError(f"rclone copy failed (exit {r.returncode}):\n" + "\n".join((r.stderr or "").splitlines()[-15:]))
    copied = sum(1 for l in (r.stderr or "").splitlines() if ": Copied" in l or ": Skipped copy" in l)
    if dry_run:
        log(f"would upload {copied} files of {src.name} ({info['rowBytes'] / 2**30:.1f} GiB of rows) to {dest}")
        return
    c = cloud_publish.rclone(["check", str(src), dest, "--exclude", "/done", "--one-way", "--size-only"], env)
    if c.returncode != 0:
        raise RuntimeError("the bucket does not hold every file at its size:\n" + "\n".join((c.stderr or "").splitlines()[-10:]))
    d = cloud_publish.rclone(["copyto", str(src / "done"), f"{dest}/done"], env)
    if d.returncode != 0:
        raise RuntimeError(f"writing {dest}/done failed: {(d.stderr or '').strip()[-300:]}")
    shutil.rmtree(src, ignore_errors=True)       # the bucket is the checkpoint: links left here would keep old rows alive
    log(f"uploaded {src.name} to {dest}; every file there at its size; done written; the local links removed")


def remote(env: dict, bucket: str = BUCKET) -> list[tuple[str, bool]]:
    """the checkpoints in the bucket, oldest first, each with whether it is whole"""
    r = cloud_publish.rclone(["lsf", f"r2:{bucket}/{PREFIX}/", "--dirs-only"], env)
    if r.returncode != 0:
        raise RuntimeError(f"rclone lsf failed: {(r.stderr or '').strip()[-300:]}")
    out = []
    for name in sorted(x.strip("/") for x in (r.stdout or "").splitlines() if x.strip()):
        d = cloud_publish.rclone(["lsf", f"r2:{bucket}/{PREFIX}/{name}/done"], env)
        out.append((name, d.returncode == 0 and bool((d.stdout or "").strip())))
    return out


def to_drop(found: list[tuple[str, bool]], keep: int) -> list[str]:
    """what `prune` deletes: whole checkpoints older than the newest `keep` whole ones, and nothing else (one that
    is not whole may be an upload still going)"""
    whole = [n for n, ok in found if ok]
    return whole[:-keep] if keep > 0 and len(whole) > keep else []


def prune(local: Path = LOCAL, keep: int = 2, dry_run: bool = False, bucket: str = BUCKET) -> None:
    env = cloud_publish.rclone_env(cloud_publish.read_env())
    found = remote(env, bucket)
    for name in to_drop(found, keep):
        log(f"{'would delete' if dry_run else 'deleting'} {PREFIX}/{name} from the bucket")
        if not dry_run:
            r = cloud_publish.rclone(["purge", f"r2:{bucket}/{PREFIX}/{name}"], env)
            if r.returncode != 0:
                raise RuntimeError(f"rclone purge failed: {(r.stderr or '').strip()[-300:]}")
    uploaded = {n for n, ok in found if ok}
    mine = sorted(p for p in local.iterdir() if p.is_dir()) if local.is_dir() else []
    for p in mine[:-1]:                      # the newest local one stays: it may not be uploaded yet
        if p.name in uploaded:
            log(f"{'would remove' if dry_run else 'removing'} the local links {p}")
            if not dry_run:
                shutil.rmtree(p, ignore_errors=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("link")
    u = sub.add_parser("upload")
    u.add_argument("--dry-run", action="store_true")
    u.add_argument("--from-world", action="store_true", help="under HOLD: the world's own files, no links kept")
    pr = sub.add_parser("prune")
    pr.add_argument("--keep", type=int, default=2)
    pr.add_argument("--dry-run", action="store_true")
    sub.add_parser("list")
    a = p.parse_args()
    try:
        if a.cmd == "link":
            link()
        elif a.cmd == "upload":
            upload(dry_run=a.dry_run, from_world=a.from_world)
        elif a.cmd == "prune":
            prune(keep=a.keep, dry_run=a.dry_run)
        else:
            for name, ok in remote(cloud_publish.rclone_env(cloud_publish.read_env())):
                log(f"{name}: {'whole' if ok else 'not whole (no done)'}")
        return 0
    except RuntimeError as e:
        log(f"FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
