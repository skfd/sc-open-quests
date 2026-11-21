"""tools/archive_backup.py: the guards. No network."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import archive_backup as ab  # noqa: E402
import cloud_publish as cp  # noqa: E402


def fill(folder: Path, n: int) -> Path:
    (folder / "ontario" / "snapshots").mkdir(parents=True)
    for i in range(n):
        (folder / "ontario" / "snapshots" / f"{i}.json").write_text("{}")
    return folder


def test_whole_archive_passes(tmp_path):
    assert ab.check_source(fill(tmp_path, ab.MIN_FILES), ab.BUCKET) == ab.MIN_FILES


def test_partial_archive_refused(tmp_path):
    with pytest.raises(RuntimeError, match="partial"):
        ab.check_source(fill(tmp_path, 3), ab.BUCKET)
    with pytest.raises(RuntimeError, match="partial"):
        ab.check_source(tmp_path / "absent", ab.BUCKET)


def test_the_sites_bucket_refused(tmp_path):
    assert ab.BUCKET != cp.BUCKET
    with pytest.raises(RuntimeError, match="site's bucket"):
        ab.check_source(fill(tmp_path, ab.MIN_FILES), cp.BUCKET)


def world(folder: Path) -> Path:
    def put(rel: str, text: str = "{}") -> None:
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(text)
    for d in ("2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04"):
        put(f"counts/{d}/counts.json")
        put(f"counts/{d}/counts.npz")
    put("counts/2026-11-01/gate1101.json")                 # the seed's day has no days/ folder
    put("days/2026-11-02/gate.json", '{"ok": true}')
    put("days/2026-11-02/day.json")
    put("days/2026-11-03/gate.json", '{"ok": false}')      # failed its gate
    put("plan.json")                                       # 11-04 has counts and no gate yet
    put("files/f0/world.bin")                              # working state
    return folder


def test_world_copies_gated_days_only(tmp_path):
    days, files = ab.world_files(world(tmp_path))
    assert days == ["2026-11-01", "2026-11-02"]
    assert files == ["counts/2026-11-01/counts.json", "counts/2026-11-01/counts.npz",
                     "counts/2026-11-01/gate1101.json", "counts/2026-11-02/counts.json",
                     "counts/2026-11-02/counts.npz", "days/2026-11-02/day.json", "days/2026-11-02/gate.json",
                     "plan.json"]


def test_world_absent_or_ungated(tmp_path):
    assert ab.world_files(tmp_path / "absent") == ([], [])
    ab.backup_world(dry_run=True, world=tmp_path / "absent")          # skipped, no network
    (tmp_path / "counts" / "2026-11-01").mkdir(parents=True)
    with pytest.raises(RuntimeError, match="no gated day"):
        ab.backup_world(dry_run=True, world=tmp_path)
