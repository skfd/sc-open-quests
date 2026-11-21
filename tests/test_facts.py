"""tools/facts.py: a snapshot and a world day come back from their facts as they were. No real data."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import facts  # noqa: E402

pq = facts.pq


def snapshot() -> dict:
    q = {"open": 5, "nodes": 4, "ways": 1, "relations": 0, "agedOnly": 2}
    aged = dict(q, open05=9, aged05=6, open2=3, aged2=0)
    return {
        "schema": 1, "asOf": "2026-11-13T21:21:00Z", "asOfDate": "2026-11-13", "timeZone": "America/Toronto",
        "scVersion": "64.0", "source": {"url": None, "file": "x.osm.pbf"}, "notes": None, "runSeconds": 1.5,
        "cities": {
            "ajax": {"denominators": {"landAreaKm2": 66.64, "population": 126666, "taggedNodes": 1, "taggedWays": 2,
                                      "highwayKm": 0},                    # an integer where a float is usual
                     "quests": {"AddBench": dict(q), "AddShelter": aged,
                                "OsmNoteQuestType": dict(q, openAllNotes=7)}},
            "toronto": {"denominators": {"landAreaKm2": 631, "population": None, "taggedNodes": 10,
                                         "taggedWays": 20, "highwayKm": 10808.696},
                        "quests": {"AddBench": dict(q, open=0, agedOnly=0)},
                        "parts": {"aaaaaaaaaaaa": {"AddBench": 3, "AddShelter": 1}, "bbbbbbbbbbbb": {},
                                  "cccccccccccc": {"AddBench": 2}},
                        "partsAged": {"aaaaaaaaaaaa": {"AddBench": 1}, "bbbbbbbbbbbb": {}}},   # c: no aged split
        },
    }


def test_snapshot_round_trip(tmp_path):
    archive, out = tmp_path / "archive", tmp_path / "facts"
    f = archive / "ontario" / "snapshots" / "2026-11-13.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps(snapshot()), encoding="utf-8")
    assert facts.cities(archive, out) == 1
    assert facts.cities(archive, out) == 0                         # nothing newer: nothing written
    cf, pf = facts.day_files(out, "ontario", "2026-11-13")
    back = facts.snapshot_from(pq.read_table(cf), pq.read_table(pf), facts.read_run(cf))
    assert json.dumps(back) == json.dumps(snapshot())               # keys, values, order, int against float
    assert facts.verify(archive, out, tmp_path / "no-world") == 0

    rows = pq.read_table(cf).to_pylist()
    part = [r for r in rows if r["within"] == "toronto"]
    assert [(r["place"], r["quest"], r["open"], r["aged_only"]) for r in part] == [
        ("aaaaaaaaaaaa", "AddBench", 3, 1), ("aaaaaaaaaaaa", "AddShelter", 1, 0), ("cccccccccccc", "AddBench", 2, None)]
    bench = next(r for r in rows if r["place"] == "ajax" and r["quest"] == "AddBench")
    assert bench["open05"] is None and bench["open"] == 5          # not measured is null, never 0


def test_a_changed_snapshot_is_noticed(tmp_path):
    archive, out = tmp_path / "archive", tmp_path / "facts"
    f = archive / "ontario" / "snapshots" / "2026-11-13.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps(snapshot()), encoding="utf-8")
    facts.cities(archive, out)
    s = snapshot()
    s["cities"]["ajax"]["quests"]["AddBench"]["open"] = 6
    f.write_text(json.dumps(s), encoding="utf-8")
    assert facts.verify(archive, out, tmp_path / "no-world") == 1
    (archive / "ontario" / "snapshots" / "2026-11-14.json").write_text(json.dumps(snapshot()), encoding="utf-8")
    assert facts.verify(archive, out, tmp_path / "no-world", source="ontario") == 2     # and a day without facts


def test_unknown_shapes_are_refused():
    s = snapshot()
    s["cities"]["ajax"]["quests"]["AddBench"]["open3"] = 1
    with pytest.raises(RuntimeError, match="measures"):
        facts.snapshot_tables(s)
    s = snapshot()
    s["cities"]["ajax"]["heat"] = {}
    with pytest.raises(RuntimeError, match="city shape"):
        facts.snapshot_tables(s)


def test_world_round_trip(tmp_path):
    world, out = tmp_path / "world", tmp_path / "facts"
    measures = ["open", "nodes", "ways", "relations", "agedOnly", "open05", "aged05", "open2", "aged2"]
    for day, ok in (("2026-11-01", None), ("2026-11-02", True), ("2026-11-03", False)):
        d = world / "counts" / day
        d.mkdir(parents=True)
        head = {"clock": f"{day}T00:00:00Z", "measures": measures, "quests": ["OsmNoteQuestType", "AddBench"],
                "parts": ["0ccc9ea0b659", "city:f0c2", "osm-wien", "ffffffffffff"]}       # the last: nothing open
        (d / "counts.json").write_text(json.dumps(head), encoding="utf-8")
        np.savez(d / "counts.npz", part=np.array([0, 0, 2], np.uint32), quest=np.array([0, 1, 1], np.uint16),
                 m=np.arange(27, dtype=np.int64).reshape(3, 9))
        if ok is None:
            (d / "gate1101.json").write_text('{"seed": true}', encoding="utf-8")
        else:
            (world / "days" / day).mkdir(parents=True)
            (world / "days" / day / "gate.json").write_text(json.dumps({"ok": ok}), encoding="utf-8")
    assert facts.world(world, out) == 2                               # 11-03 failed its gate
    assert facts.verify(tmp_path / "no-archive", out, world) == 0
    cf, pf = facts.day_files(out, "world", "2026-11-02")
    assert facts.read_run(cf)["gate"] == {"ok": True}
    assert pq.read_table(pf).num_rows == 4
    rows = pq.read_table(cf).to_pylist()
    assert (rows[2]["place"], rows[2]["quest"], rows[2]["open"], rows[2]["aged2"]) == ("osm-wien", "AddBench", 18, 26)
    assert rows[0]["open_all_notes"] is None
