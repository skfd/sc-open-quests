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


LOG = """[2026-11-20T10:00:00] == day 2026-11-12: diff 5174 on generation 10; an earlier try of the same day
[2026-11-20T10:05:00] update 5174: exit 1 in 300 s
[2026-11-21T00:00:00] == day 2026-11-12: diff 5174 on generation 10; the world at 2026-11-11T00:00:00Z
[2026-11-21T00:00:01] world snapshot: 0 s
[2026-11-21T00:15:00] world prepare 2026-11-12: 896 s; {"read diff": 188, "store context before": 465}
update to 2026-11-12: {"changedNodes":5, "reachedBy":{"node":{"tiles":7}}}
[2026-11-21T00:27:00] update 5174: exit 0 in 736 s
[2026-11-21T00:27:10] tilestore read: 6.5 s
[2026-11-21T00:27:20] tilestore read: 3.5 s
[2026-11-21T04:10:00] world finish 2026-11-12: 13366 s; {"tier 2 engine": 7365.0, "tier 1": 801.0}
[2026-11-21T04:11:00] gate: europe-west counted on europe-2026-11-12.osm.pbf in 57 s
[2026-11-21T04:13:00] gate: europe-east counted on europe-2026-11-12.osm.pbf in 43 s
[2026-11-21T04:14:00] loc advance 5174: exit 0 in 45 s
[2026-11-21T04:15:00] loc check against europe-2026-11-12.osm.pbf: exit 0 in 32 s
[2026-11-21T04:16:00] subcmp generation 11: exit 1 in 104 s
pack 0: 232.55 GiB written, 193.53 GiB live (16.8% dead), 30751965 rows
[2026-11-21T04:20:00] compact: exit 0 in 157 s
[2026-11-21T04:30:00] == day 2026-11-12 done: generation 11; the world at 2026-11-12T00:00:00Z
[2026-11-21T04:30:00] == day 2026-11-13: diff 5175 on generation 11
[2026-11-21T04:40:00] update 5175: exit 0 in 600 s
"""


def test_a_days_steps_off_the_log(tmp_path):
    r = dm.day_steps(LOG, "2026-11-12")
    assert r["started"] == "2026-11-21T00:00:00" and r["ended"] == "2026-11-21T04:30:00" and r["wall s"] == 16200
    assert r["steps"]["update"] == {"s": 736.0, "runs": 1, "exit": 0}           # the last run of the day only
    assert r["steps"]["loc check"]["s"] == 32.0 and r["steps"]["subcmp"]["exit"] == 1
    assert r["steps"]["world finish"]["s"] == 13366.0 and r["finish"]["tier 2 engine"] == 7365.0
    assert r["gate"] == {"europe-west": 57.0, "europe-east": 43.0} and r["reads"] == {"n": 2, "s": 10.0}
    assert r["update"]["reachedBy"]["node"]["tiles"] == 7 and r["packs"][0]["dead %"] == 16.8
    assert r["unaccounted s"] == 16200 - (896 + 736 + 13366 + 45 + 32 + 104 + 157) - 100
    assert dm.day_steps(LOG, "2026-11-13")["steps"]["update"]["s"] == 600.0     # not done: what it has
    assert dm.day_steps(LOG, "2026-11-01") is None
    f = dm.flat(r)
    assert f["finish: tier 2 engine"] == 7365.0 and f["gate"] == 100.0

    earlier = [{"steps": {"update": {"s": 700.0}}, "finish": {"tier 2 engine": 7000.0}} for _ in range(3)]
    slow = {"steps": {"update": {"s": 710.0}}, "finish": {"tier 2 engine": 16426.0}}
    assert dm.step_watch(slow, earlier) == [
        "finish: tier 2 engine: 16,426 s, 2.3 times its median over 3 earlier days (7,000 s)"]
    assert dm.step_watch(slow, earlier[:2]) == []                               # too few days to say

    log = tmp_path / "planet-store.log"
    log.write_text(LOG, encoding="utf-8")
    said = []
    out = dm.write_steps(tmp_path / "world", "2026-11-12", log, said.append)
    assert json.loads(out.read_text(encoding="utf-8"))["watch"] == [] and said[0].startswith("steps: the day took 16,200 s")
    assert dm.write_steps(tmp_path / "world", "2026-11-01", log) is None


def test_the_stores_reads(tmp_path):
    for g, sec in (("f1", 9.0), ("f2", 3.0)):
        d = tmp_path / "t2" / "groups" / g
        d.mkdir(parents=True)
        (d / "old.osm.pbf.json").write_text(json.dumps({"by": "tilestore (Rust)", "tiles": 10, "pbfBytes": 100,
                                                         "secondsTiles": sec - 1, "secondsMerge": 0.5, "secondsWrite": 0.5,
                                                         "seconds": sec, "peakPrivateGiB": sec / 2}), encoding="utf-8")
    (tmp_path / "t2" / "groups" / "f1" / "cities.json").write_text("{}", encoding="utf-8")
    r = dm.store_reads(tmp_path)
    assert set(r) == {"old"}
    assert (r["old"]["reads"], r["old"]["seconds"], r["old"]["tiles"], r["old"]["peakPrivateGiB"]) == (2, 12.0, 20, 4.5)
    assert r["old"]["longest"][0] == {"group": "t2/groups/f1", "s": 9.0, "pbfBytes": 100}


def test_a_resumed_day_is_read_whole():
    log = """[2026-11-22T00:00:00] == day 2026-11-16: diff 5178 on generation 14; the world at 2026-11-15T00:00:00Z
[2026-11-22T00:12:00] world prepare 2026-11-16: 794 s; {"read diff": 156}
[2026-11-22T00:24:00] update 5178: exit 0 in 707 s
[2026-11-22T01:43:35] STOPPED: world finish 2026-11-16 failed
[2026-11-22T07:12:26] planet store run started
[2026-11-22T07:12:26] == day 2026-11-16: resuming (the store at generation 15, the world at 2026-11-15)
[2026-11-22T09:45:19] world finish 2026-11-16: 9083 s; {"tier 2 engine": 2938.0}
[2026-11-22T09:59:32] == day 2026-11-16 done: generation 15
"""
    r = dm.day_steps(log, "2026-11-16")
    assert r["started"] == "2026-11-22T00:00:00" and r["resumes"] == 1
    assert r["steps"]["update"]["s"] == 707.0 and r["steps"]["world finish"]["s"] == 9083.0
    assert r["wall s"] == 9 * 3600 + 59 * 60 + 32 and r["unaccounted s"] == r["wall s"] - 794 - 707 - 9083
