"""tools/world_cities.py: the city pages' data out of the world's counts, on a made-up two-city world."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import run  # noqa: E402
import site_quests  # noqa: E402
import world_cities  # noqa: E402

MEASURES = ["open", "nodes", "ways", "relations", "agedOnly", "open05", "aged05", "open2", "aged2"]
PARTS = ["osm-aaa", "osm-bbb", "0123456789ab", "other0000000"]   # 0123456789ac, registered, is in no row and no list
QUESTS = ["AddA", "AddB", "AddOnlyDE"]
QUEST_LIST = {"scVersion": "64.1", "scCommit": "x", "quests": [
    {"name": "AddA", "support": "supported", "usesAge": True, "enabledInCountries": {"type": "AllCountries"}},
    {"name": "AddB", "support": "supported", "usesAge": False, "enabledInCountries": {"type": "AllCountries"}},
    {"name": "AddOnlyDE", "support": "supported", "usesAge": False,
     "enabledInCountries": {"type": "NoCountriesExcept", "codes": ["DE"]}}]}
CITIES = [{"id": "aaa", "name": "Aaa", "region": "ontario", "countryCodes": ["CA"], "landAreaKm2": 12.345, "population": 9},
          {"id": "bbb", "name": "Bbb", "region": "berlin", "countryCodes": ["DE"], "landAreaKm2": 1.0}]


def write_day(world: Path, day: str, rows: list[tuple[int, int, int]]) -> None:
    """rows: (part, quest, open); agedOnly is 1 wherever open is above 1"""
    d = world / "counts" / day
    d.mkdir(parents=True)
    (d / "counts.json").write_text(json.dumps({"clock": f"{day}T00:00:00Z", "measures": MEASURES, "quests": QUESTS,
                                               "parts": PARTS}), encoding="utf-8")
    m = np.zeros((len(rows), len(MEASURES)), dtype=np.int64)
    for i, (_, _, n) in enumerate(rows):
        m[i, 0] = m[i, 1] = m[i, 5] = n
        m[i, 4] = int(n > 1)
    np.savez(d / "counts.npz", part=np.array([r[0] for r in rows], dtype=np.uint32),
             quest=np.array([r[1] for r in rows], dtype=np.uint16), m=m)
    (world / "days" / day).mkdir(parents=True)
    (world / "days" / day / "gate.json").write_text('{"ok": true}', encoding="utf-8")


class WorldCitiesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.world, self.out, self.parts = self.tmp / "world", self.tmp / "out", self.tmp / "config" / "parts"
        write_day(self.world, "2026-11-01", [(0, 0, 5), (0, 2, 4), (1, 2, 3), (2, 0, 2), (2, 2, 1), (3, 0, 8)])
        write_day(self.world, "2026-11-02", [(0, 0, 4), (1, 2, 3), (3, 0, 8)])
        self.parts.mkdir(parents=True)
        run.write_json(self.parts / "aaa.json", {"city": "aaa", "parts": [
            {"id": "0123456789ab", "name": "P", "en": None, "subtype": "neighborhood"},
            {"id": "0123456789ac", "name": "Empty", "en": None, "subtype": "neighborhood"}]})
        self.config = self.tmp / "cities.json"
        run.write_json(self.config, {"cities": CITIES})
        self.archive = self.tmp / "archive"
        for region, cid in (("ontario", "aaa"), ("berlin", "bbb")):
            for day in ("2026-10-31", "2026-11-01", "2026-11-03"):   # the last two are the world's to say
                run.write_json(self.archive / region / "snapshots" / f"{day}.json", {
                    "asOf": f"{day}T21:21:00Z", "asOfDate": day, "scVersion": "64.1", "resurveyMultiplier": 1,
                    "cities": {cid: {"denominators": {"landAreaKm2": 1, "population": 1, "taggedNodes": 7, "taggedWays": 8},
                                     "quests": {"AddA": {"open": 99, "agedOnly": 0}},
                                     "parts": {"0123456789ab": {"AddA": 99}}}}})
        for name, value in [("log", lambda m: None)]:
            p = mock.patch.object(run, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(site_quests, "base", lambda *a, **k: QUEST_LIST)
        p.start()
        self.addCleanup(p.stop)

    def snapshots(self, **kw):
        return world_cities.snapshots(self.world, self.out, cities_config=self.config, parts_dir=self.parts, **kw)

    def snap(self, region, day):
        return run.read_json(self.out / region / "snapshots" / f"{day}.json")

    def test_a_city_is_its_outlines_count_and_a_quest_with_no_row_is_zero(self):
        self.assertEqual(self.snapshots(), 2)
        city = self.snap("ontario", "2026-11-02")["cities"]["aaa"]
        self.assertEqual(city["quests"], {
            "AddA": {"open": 4, "nodes": 4, "ways": 0, "relations": 0, "agedOnly": 1, "open05": 4, "aged05": 0,
                     "open2": 0, "aged2": 0},
            "AddB": {"open": 0, "nodes": 0, "ways": 0, "relations": 0, "agedOnly": 0}})
        self.assertEqual(city["denominators"], {"landAreaKm2": 12.35, "population": 9})
        self.assertEqual(self.snap("berlin", "2026-11-02")["cities"]["bbb"]["quests"]["AddOnlyDE"]["open"], 3)

    def test_a_quest_not_asked_there_is_left_out_of_the_city_and_its_parts(self):
        self.snapshots()
        city = self.snap("ontario", "2026-11-01")["cities"]["aaa"]
        self.assertNotIn("AddOnlyDE", city["quests"])
        self.assertEqual(city["parts"], {"0123456789ab": {"AddA": 2}, "0123456789ac": {}})
        self.assertEqual(city["partsAged"], {"0123456789ab": {"AddA": 1}, "0123456789ac": {}})

    def test_only_new_days_are_written_and_an_ungated_one_goes(self):
        self.snapshots()
        self.assertEqual(self.snapshots(), 0)
        (self.world / "days" / "2026-11-02" / "gate.json").unlink()
        self.snapshots()
        self.assertEqual([p.stem for p in sorted((self.out / "ontario" / "snapshots").glob("*.json"))], ["2026-11-01"])

    def test_a_city_the_world_does_not_count_is_an_error(self):
        run.write_json(self.config, {"cities": CITIES + [{**CITIES[0], "id": "ccc"}]})
        with self.assertRaisesRegex(RuntimeError, "osm-ccc"):
            self.snapshots()

    def test_history_joins_the_two_and_parts_are_the_worlds_alone(self):
        self.snapshots()
        data = self.tmp / "site" / "data"
        data.mkdir(parents=True)
        (data / "parts").mkdir()
        for day in ("2026-10-31",):   # published by the city run before
            run.write_json(data / "ontario" / "snapshots" / f"{day}.json", {})
        with mock.patch.object(run, "publish_parts", lambda *a: 0):
            def build():
                return run.history(data, self.config, self.archive, self.parts, world=self.out)
            self.assertGreater(build(), 0)
            self.assertEqual(build(), 0)
        h = run.read_json(data / "history" / "aaa.json")
        self.assertEqual(h["dates"], ["2026-10-31", "2026-11-01", "2026-11-02"])
        self.assertEqual(h["quests"]["AddA"]["open"], [99, 5, 4])
        self.assertEqual(h["quests"]["AddB"]["open"], [None, 0, 0])
        self.assertEqual(h["denominators"]["taggedNodes"], [7, None, None])
        p = run.read_json(data / "history" / "aaa" / "0123456789ab.json")
        self.assertEqual((p["dates"], p["quests"]["AddA"]["open"]), (["2026-11-01", "2026-11-02"], [2, 0]))
        e = run.read_json(data / "history" / "aaa" / "0123456789ac.json")
        self.assertEqual((e["dates"], e["quests"]), (["2026-11-01", "2026-11-02"], {}))
        self.assertEqual([x.name for x in (data / "ontario" / "snapshots").glob("*.json")], ["2026-11-02.json"])
        # the world's published snapshot is never taken into the city run's archive
        self.assertFalse((self.archive / "ontario" / "snapshots" / "2026-11-02.json").exists())

    def test_a_published_world_snapshot_is_not_migrated(self):
        self.snapshots()
        data = self.tmp / "site" / "data"
        src = self.out / "ontario" / "snapshots" / "2026-11-02.json"
        run.write_json(data / "ontario" / "snapshots" / "2026-11-02.json", run.read_json(src))
        run.write_json(data / "ontario" / "snapshots" / "2026-10-30.json", {"source": {"sha256": "x"}})
        run.migrate_archive(data, self.archive)
        self.assertEqual([p.name for p in (data / "ontario" / "snapshots").glob("*.json")], ["2026-11-02.json"])
        self.assertTrue((self.archive / "ontario" / "snapshots" / "2026-10-30.json").exists())
        self.assertFalse((self.archive / "ontario" / "snapshots" / "2026-11-02.json").exists())

    def test_the_site_is_always_made_with_the_world(self):
        class Asked(Exception):
            pass
        with mock.patch.object(run, "world_snapshots", side_effect=Asked), \
                mock.patch.object(run, "migrate_archive") as migrate, self.assertRaises(Asked):
            run.history()
        migrate.assert_not_called()

    def test_history_without_world_days_stops(self):
        with self.assertRaisesRegex(RuntimeError, "no world snapshots"):
            run.history(self.tmp / "site" / "data", self.config, self.archive, world=self.out)

    def test_the_site_is_not_written_without_live(self):
        with self.assertRaises(SystemExit):
            world_cities.main(["build", "--data-dir", str(run.DATA_DIR)])


if __name__ == "__main__":
    unittest.main()
