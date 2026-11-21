"""tools/stream/day_metrics.py: an engine's log as numbers, and the lopsided engine said."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools" / "stream"))
import day_metrics as dm  # noqa: E402

HEAD = """startup: registry and cities 1.2 s, parts 0.8 s (355 outlines from parts.cache, 0 parsed), engine and its indexes 2.0 s
193 quests in v64.1.json (192 counted: 140 filter, 52 ported custom), 3 cities (7 parts in 3); threads=24 maxHeap=8192 MB
relation member scan      0.1 s  38635 member ways of tagged relations
nodes                     2.7 s  8415010 nodes
ways                      2.0 s  38635 member ways kept
relations                 1.2 s
"""


def log_of(folder: Path, areas: list[tuple[float, float, int]], total: float | None) -> None:
    folder.mkdir(parents=True)
    text = HEAD + "".join(f"area: c{i}               {s} s  (map data {md} s: 1500 nodes, 40 ways, {rel} relations)\n"
                          for i, (s, md, rel) in enumerate(areas))
    if total is not None:
        text += f"pass {total - 4} s, total {total} s; peak heap (sum of pool peaks) 3029 MB\n"
    (folder / "engine.log").write_text(text, encoding="utf-8")


def test_an_engine_and_the_lopsided_one(tmp_path):
    work = tmp_path / "work"
    for i in range(6):
        log_of(work / "t2" / "groups" / f"f{i}" / "old", [(1.0, 0.5, 0), (2.0, 0.5, 1)], 30.0)
    log_of(work / "t2" / "groups" / "f9" / "old", [(400.0, 398.0, 4), (200.0, 199.0, 2), (1.0, 0.0, 0)], 620.0)
    log_of(work / "t2" / "groups" / "f9" / "new", [(1.0, 0.5, 0)], None)        # still running
    log_of(work / "t1" / "f0", [], 8.0)
    rec = dm.harvest(work)
    e = rec["engines"]["t2/groups/f9/old"]
    assert (e["areas"], e["with relations"], e["area s"], e["map data s"], e["map data s with relations"]) == \
        (3, 2, 601.0, 597.0, 597.0)
    assert e["quests s"] == 4.0 and e["heap MB"] == 3029 and e["cities"] == 3 and e["startup s"] == 4.0
    assert e["main"] == {"relation member scan": 0.1, "nodes": 2.7, "ways": 2.0, "relations": 1.2}
    assert e["slowest areas"][0] == {"id": "c0", "s": 400.0, "nodes": 1500, "ways": 40, "relations": 4}
    assert rec["unfinished"] == ["t2/groups/f9/new"]
    assert set(rec["phases"]) == {"t1", "t2 old"}
    p = rec["phases"]["t2 old"]
    assert (p["engines"], p["median s"], p["max s"], p["slowest"][0]) == (7, 30.0, 620.0, "t2/groups/f9/old")
    assert len(rec["watch"]) == 1 and rec["watch"][0].startswith("t2/groups/f9/old: 620 s, 3 areas; 21 times")
    assert "map data 597 s of it" in rec["watch"][0]

    said = []
    out = dm.write(tmp_path / "world", "2026-11-14", work, said.append)
    assert json.loads(out.read_text(encoding="utf-8"))["day"] == "2026-11-14"
    assert any(s.startswith("watch: t2/groups/f9/old") for s in said)
    assert any(s.startswith("engines, t2 old: 7 in") for s in said)
