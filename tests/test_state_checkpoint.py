"""tools/state_checkpoint.py: the link step and what prune would delete. No network."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import state_checkpoint as sc  # noqa: E402


def world(folder: Path) -> Path:
    (folder / "world.json").write_text(json.dumps({"clock": "2026-11-14T00:00:00Z"}), encoding="utf-8")
    (folder / "plan.json").write_text(json.dumps({"files": [{"id": "f0"}, {"id": "f1"}]}), encoding="utf-8")
    (folder / "place-sets.json").write_text("{}", encoding="utf-8")
    for fid in ("f0", "f1"):
        (folder / "files" / fid).mkdir(parents=True)
        (folder / "files" / fid / "world.bin").write_bytes(fid.encode() * 10)
        (folder / "files" / fid / "cities.json").write_text("{}", encoding="utf-8")     # not part of a checkpoint
    return folder


def test_link_keeps_what_the_world_was(tmp_path):
    w, local = world(tmp_path / "w"), tmp_path / "cp"
    out = sc.link(w, local, tmp_path / "RUNNING")
    assert out.name == "2026-11-14"
    assert os.path.samefile(out / "files" / "f0" / "world.bin", w / "files" / "f0" / "world.bin")    # no bytes copied
    assert json.loads((out / "done").read_text())["files"] == 2 and (out / "plan.json").exists()
    assert not (out / "files" / "f0" / "cities.json").exists()
    # the loop's write replaces the file: the checkpoint still has the rows of its clock
    tmp = w / "files" / "f0" / "world.bin.new"
    tmp.write_bytes(b"later")
    os.replace(tmp, w / "files" / "f0" / "world.bin")
    assert (out / "files" / "f0" / "world.bin").read_bytes() == b"f0" * 10
    assert sc.newest(local) == out
    assert sc.link(w, local, tmp_path / "RUNNING") == out                # already there: left as it is
    assert (out / "files" / "f0" / "world.bin").read_bytes() == b"f0" * 10


def test_link_refused_beside_a_run(tmp_path):
    w = world(tmp_path / "w")
    (tmp_path / "RUNNING").write_text("x")
    with pytest.raises(RuntimeError, match="a run is moving the world"):
        sc.link(w, tmp_path / "cp", tmp_path / "RUNNING")
    with pytest.raises(RuntimeError, match="no linked checkpoint"):
        sc.newest(tmp_path / "cp")


def test_prune_keeps_the_newest_whole_ones():
    found = [("2026-11-14", True), ("2026-12-14", True), ("2027-01-14", True), ("2027-02-14", False)]
    assert sc.to_drop(found, 2) == ["2026-11-14"]
    assert sc.to_drop(found[:2], 2) == []
    assert sc.to_drop([("2026-11-14", False), ("2026-12-14", True)], 1) == []     # one not whole is never deleted
