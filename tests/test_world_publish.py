import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import world_publish as wp  # noqa: E402

MEASURES = ["open", "nodes", "ways", "relations", "agedOnly", "open05", "aged05", "open2", "aged2"]
QUESTS = ["OsmNoteQuestType", "AddBench", "AddLit"]
C, R, A, B, X = "aa0000000001", "bb0000000002", "cc0000000003", "cd0000000004", "dd0000000005"
E = "ee0000000006"


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), encoding="utf-8", newline="\n")


def name_layer(root: Path) -> Path:
    places = root / "places"
    write_json(places / "index.json", {"schema": 1, "overture": "test", "countries": [
        {"id": C, "cc": "DE", "en": "Testland", "bbox": [0, 0, 1, 1],
         "regions": [{"id": R, "name": "Region", "file": "de/r.json", "n": 3}]},
        {"id": None, "cc": "PS", "en": "Headless", "bbox": [0, 0, 1, 1],
         "regions": [{"id": "_", "name": "-", "file": "ps/_.json", "n": 1}]}]})
    write_json(places / "ps" / "_.json", {"schema": 1, "region": "_", "places": [
        [E, "Village", 5, -1, 0, 0, 1, 1, None, None]]})
    # rows: [id, name, st, parentIdx, xmin, ymin, xmax, ymax, en, counted]; A under the region, B under A
    write_json(places / "de" / "r.json", {"schema": 1, "region": R, "places": [
        [R, "Region", 2, -1, 0, 0, 1, 1, None, None],
        [A, "Town", 5, 0, 0, 0, 1, 1, None, None],
        [B, "Quarter", 8, 1, 0, 0, 1, 1, None, None]]})
    return places


def world_day(world: Path, day: str, rows: dict, compressed: bool, gate: str = "days") -> None:
    """rows: (part, quest) -> (open, aged); X is counted but not in the name layer, `city:` a cell"""
    parts = [C, R, A, B, X, E, "city:f0", "osm-town"]
    d = world / "counts" / day
    write_json(d / "counts.json", {"clock": day + "T00:00:00Z", "measures": MEASURES, "quests": QUESTS,
                                   "parts": parts})
    keys = sorted(rows)
    m = np.zeros((len(keys), 9), np.int64)
    for i, k in enumerate(keys):
        m[i, 0], m[i, 4] = rows[k]
        m[i, 1] = 99  # nodes: not published
    part = np.array([parts.index(p) for p, _ in keys], np.uint32)
    quest = np.array([QUESTS.index(q) for _, q in keys], np.uint16)
    (np.savez_compressed if compressed else np.savez)(d / "counts.npz", part=part, quest=quest, m=m)
    if gate == "seed":
        write_json(d / "gate1101.json", {"x": {}})
    elif gate == "days":
        write_json(world / "days" / day / "gate.json", {"day": day, "ok": True})
    elif gate == "failed":
        write_json(world / "days" / day / "gate.json", {"day": day, "ok": False})


DAYS = {
    "2026-10-30": {(A, "AddBench"): (5, 1), (B, "AddBench"): (2, 0), (C, "AddLit"): (7, 0),
                   ("city:f0", "AddBench"): (9, 9), (X, "AddBench"): (3, 0)},
    "2026-10-31": {(A, "AddBench"): (5, 1), (B, "AddBench"): (1, 0), (C, "AddLit"): (7, 0), (A, "AddLit"): (0, 0)},
    "2026-11-01": {(A, "AddBench"): (4, 2), (C, "AddLit"): (7, 0), (A, "OsmNoteQuestType"): (1, 0)},
    "2026-11-02": {(A, "AddBench"): (4, 2), (B, "AddBench"): (6, 0), (C, "AddLit"): (8, 1), (E, "AddLit"): (2, 0)},
    "2026-11-03": {(A, "AddBench"): (0, 0)},
}


class WorldPublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.places = name_layer(root)
        self.world = root / "world"
        for i, (day, rows) in enumerate(DAYS.items()):
            gate = "seed" if i == 0 else ("failed" if day == "2026-11-03" else "days")
            world_day(self.world, day, rows, compressed=bool(i % 2), gate=gate)
        self.out, self.work = root / "out", root / "work"

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, through=None):
        return wp.build(self.world, self.out, self.work, self.places, "2026-10-30", through)

    def test_layout_and_values(self):
        latest = self.build()
        self.assertEqual(latest["date"], "2026-11-02")  # 11-03's gate failed
        self.assertEqual(latest["base"], "2026-11-01")
        self.assertEqual(latest["place"], "place/2026-11-01/")
        place = json.loads((self.out / "place/2026-11-01/cc/cc0000000003.json").read_text(encoding="utf-8"))
        self.assertEqual(place["dates"], ["2026-10-30", "2026-10-31", "2026-11-01"])
        self.assertEqual(place["subtype"], "locality")
        self.assertEqual(place["quests"]["AddBench"], [[0, 5, 1], [2, 4, 2]])
        self.assertEqual(place["quests"]["OsmNoteQuestType"], [[2, 1, 0]])
        self.assertNotIn("AddLit", place["quests"])  # (0, 0) rows are not published
        self.assertFalse((self.out / "place/2026-11-01/dd").exists())  # not in the name layer
        self.assertEqual(len(list((self.out / "place/2026-11-01").glob("*/*.json"))), 5)
        # a country with no Overture id is addressed by its code, as the page's countryId does
        ps = json.loads((self.out / "latest/2026-11-02/ps/ps.json").read_text(encoding="utf-8"))
        self.assertEqual(ps["places"], {E: {"AddLit": [[3, 2, 0]]}})
        # B's parent is A: A's latest file holds B, from the window's start (the first day) to the date
        la = json.loads((self.out / "latest/2026-11-02/cc/cc0000000003.json").read_text(encoding="utf-8"))
        self.assertEqual(la["dates"], ["2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"])
        self.assertEqual(la["places"], {B: {"AddBench": [[0, 2, 0], [1, 1, 0], [2, 0, 0], [3, 6, 0]]}})
        world = json.loads((self.out / "latest/2026-11-02/world.json").read_text(encoding="utf-8"))
        self.assertEqual(world["places"][C], {"AddLit": [[0, 7, 0], [3, 8, 1]]})
        self.assertIn(R, json.loads((self.out / "latest/2026-11-02/aa/aa0000000001.json")
                                    .read_text(encoding="utf-8"))["places"])
        self.assertEqual(wp.verify(self.world, self.out, self.places, sample=10), 0)

    def test_incremental_equals_whole(self):
        self.build(through="2026-11-01")
        self.build()
        a = {p.relative_to(self.out).as_posix(): p.read_bytes() for p in self.out.rglob("*.json")}
        out2 = Path(self.tmp.name) / "out2"
        wp.build(self.world, out2, Path(self.tmp.name) / "work2", self.places, "2026-10-30", None)
        b = {p.relative_to(out2).as_posix(): p.read_bytes() for p in out2.rglob("*.json")}
        # out keeps place/2026-11-01 from the first build; latest/2026-11-01 is kept as well (KEEP_LATEST)
        for k, v in b.items():
            self.assertEqual(a.get(k), v, k)

    def test_window_starts_at_base_or_28_days(self):
        self.assertEqual(wp.start_of("2026-12-20", "2026-12-01", "2026-11-01"), "2026-11-22")
        self.assertEqual(wp.start_of("2026-12-31", "2026-12-01", "2026-11-01"), "2026-12-01")
        self.assertEqual(wp.start_of("2026-11-10", "2026-11-01", "2026-11-01"), "2026-11-01")
        self.assertEqual(wp.base_of("2026-11-30", "2026-11-01"), "2026-11-01")
        self.assertEqual(wp.base_of("2026-10-31", "2026-10-30"), "2026-10-30")

    def test_decode(self):
        self.assertEqual(wp.decode([[1, 3, 1], [3, 0, 0]], 5), ([0, 3, 3, 0, 0], [0, 1, 1, 0, 0]))


if __name__ == "__main__":
    unittest.main()
