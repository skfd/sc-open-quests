"""The world planner's k-d cut (tools/world_cells.py, DESIGN.md "The whole planet, made ready")."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import world_cells as w  # noqa: E402


def _grid(seed=1, n=4000):
    rnd = random.Random(seed)
    # a dense town, a sparse spread and a far-off island: the shape that made Germany's giant box
    items = {}
    for _ in range(n):
        r, c = rnd.randint(500, 520), rnd.randint(100, 130)
        items[(r, c)] = items.get((r, c), 0) + rnd.randint(1, 50_000)
    for _ in range(200):
        r, c = rnd.randint(400, 700), rnd.randint(-300, 300)
        items[(r, c)] = items.get((r, c), 0) + rnd.randint(1, 100)
    items[(650, -400)] = 7
    return [(r, c, n) for (r, c), n in items.items()]


def _whole(items):
    return (min(r for r, _, _ in items), max(r for r, _, _ in items), min(c for _, c, _ in items), max(c for _, c, _ in items))


def test_leaves_tile_the_box_and_keep_every_square():
    items = _grid()
    whole = _whole(items)
    leaves = w.kd(items, 0.05, whole, 2_000_000, cap=200)
    area = sum((r1 - r0 + 1) * (c1 - c0 + 1) for (r0, r1, c0, c1), _ in leaves)
    assert area == (whole[1] - whole[0] + 1) * (whole[3] - whole[2] + 1)  # no gap, no overlap (with disjointness below)
    seen = sorted(it for _, its in leaves for it in its)
    assert seen == sorted(items)
    for (r0, r1, c0, c1), its in leaves:
        assert all(r0 <= r <= r1 and c0 <= c <= c1 for r, c, _ in its)
    rects = [rect for rect, _ in leaves]
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            assert a[1] < b[0] or b[1] < a[0] or a[3] < b[2] or b[3] < a[2]


def test_limit_and_cap():
    items = _grid()
    leaves = w.kd(items, 0.05, _whole(items), 2_000_000, cap=200)
    for (r0, r1, c0, c1), its in leaves:
        assert r1 - r0 + 1 <= 200 and c1 - c0 + 1 <= 200
        assert w.rect_nodes(its) <= 2_000_000 or (r0 == r1 and c0 == c1)
    # without the cap the sparse corner stays one long cell
    uncapped = w.kd(items, 0.05, _whole(items), 2_000_000)
    assert max(c1 - c0 + 1 for (_, _, c0, c1), _ in uncapped) > 200


def _count_setup(tmp_path, monkeypatch, free, outcomes):
    """A plan of files a, b, c; a fake engine that answers from `outcomes` (file id -> list of
    (exit code, log text)) and a commit headroom read from `free` (a list, last value repeats)."""
    w.write_json(tmp_path / "plan.json", {"timeZone": "UTC", "files": [{"id": i} for i in "abc"]})
    for i in "abc":
        (tmp_path / "files" / i).mkdir(parents=True)
    started = []

    def engine(args, tz, heap_gb, log, commit_all=False):
        fid = log.parent.name
        started.append((fid, commit_all))
        code, text = outcomes[fid].pop(0) if outcomes.get(fid) else (0, "ok")
        log.write_text(text, encoding="utf-8")
        return code, 1.0

    monkeypatch.setattr(w, "engine", engine)
    monkeypatch.setattr(w, "commit_free_gb", lambda: free.pop(0) if len(free) > 1 else free[0])
    monkeypatch.setattr(w, "quiet", lambda ahead_minutes=0: None)
    monkeypatch.setattr(w, "rel", str)
    monkeypatch.setattr(w.run, "newest_quests_file", lambda: tmp_path / "q.json")
    monkeypatch.setattr(w.run, "log", lambda msg: None)
    monkeypatch.setattr(w, "STARTUP_S", 0)
    monkeypatch.setattr(w.time, "sleep", lambda s: None)
    return started


def test_count_queues_again_a_file_windows_refused_memory(tmp_path, monkeypatch):
    started = _count_setup(tmp_path, monkeypatch, [100.0],
                           {"b": [(1, "error='The paging file is too small for this operation'")]})
    w.count(tmp_path, engines=2, heap_gb=30)
    assert sorted(f for f, _ in started) == ["a", "b", "b", "c"]
    assert all(commit_all for _, commit_all in started)  # each engine commits its heap up front
    assert all((tmp_path / "files" / i / "done.json").exists() for i in "abc")


def test_count_gives_up_when_memory_never_comes(tmp_path, monkeypatch):
    started = _count_setup(tmp_path, monkeypatch, [10.0], {})
    import pytest
    with pytest.raises(SystemExit, match="3 file"):
        w.count(tmp_path, engines=2, heap_gb=30, give_up_s=0)
    assert started == []


def test_count_still_fails_a_real_engine_error(tmp_path, monkeypatch):
    _count_setup(tmp_path, monkeypatch, [100.0], {"a": [(1, "java.lang.OutOfMemoryError: Java heap space")]})
    import pytest
    with pytest.raises(SystemExit, match="1 file.*a"):
        w.count(tmp_path, engines=1, heap_gb=30)
