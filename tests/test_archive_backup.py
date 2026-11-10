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
