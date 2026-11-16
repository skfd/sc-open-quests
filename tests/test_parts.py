"""Parts: the published part names (run.py history) and the engine's --parts. Run: python -m unittest"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "history"


def feature(coords):
    return {"type": "Feature", "properties": {}, "geometry": {"type": "MultiPolygon", "coordinates": coords}}


class PublishPartsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "data"
        shutil.copytree(FIXTURE, self.data)
        self.config = self.data / "cities-config.json"
        self.city = run.read_json(self.config)["cities"][0]["id"]
        self.parts = self.tmp / "repo" / "config" / "parts"
        geo = self.tmp / "repo" / "data" / "boundaries" / "parts" / self.city
        geo.mkdir(parents=True)
        self.parts.mkdir(parents=True)
        (geo / "r1.geojson").write_text(json.dumps(feature(
            [[[[-79.41234, 43.65], [-79.3, 43.65], [-79.3, 43.712345], [-79.41234, 43.65]]],
             [[[-79.5, 43.6], [-79.45, 43.6], [-79.45, 43.62], [-79.5, 43.6]]]])))
        self.registry = {"schema": 1, "city": self.city, "overture": "2026-10-21.0", "parts": [
            {"id": "0123456789ab", "gers": "01234567-89ab-cdef-0000-000000000000", "name": "Annex", "en": None,
             "subtype": "neighborhood", "osm": "r1", "geometry": f"data/boundaries/parts/{self.city}/r1.geojson"}]}
        (self.parts / f"{self.city}.json").write_text(json.dumps(self.registry))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_history_writes_names_and_bboxes_from_the_registry(self):
        run.history(self.data, self.config, parts_dir=self.parts)
        out = run.read_json(self.data / "parts" / f"{self.city}.json")
        self.assertEqual(out, {"schema": 1, "city": self.city, "parts": [
            {"id": "0123456789ab", "name": "Annex", "en": None, "subtype": "neighborhood",
             "bbox": [-79.5, 43.6, -79.3, 43.7123]}]})
        self.assertEqual(run.history(self.data, self.config, parts_dir=self.parts), 0)

    def test_a_city_without_a_registry_loses_its_file(self):
        stale = self.data / "parts" / "gone.json"
        stale.parent.mkdir(parents=True)
        stale.write_text("{}")
        run.history(self.data, self.config, parts_dir=self.parts)
        self.assertFalse(stale.exists())
        self.assertTrue((self.data / "parts" / f"{self.city}.json").exists())

    def test_without_a_parts_dir_nothing_is_written(self):
        run.history(self.data, self.config)
        self.assertFalse((self.data / "parts").exists())

    def test_engine_gets_parts_only_when_there_is_a_registry(self):
        self.assertEqual(run.parts_args(ROOT / "no-such-dir"), [])
        here = ROOT / "config"
        self.assertEqual(run.parts_args(here), ["--parts", "config"])


def snap(date, city):
    return {"asOfDate": date, "cities": {"x": city}}


class PartHistoryTest(unittest.TestCase):
    REG = {"x": {"parts": [{"id": "aaaaaaaaaaa1", "name": "Annex", "en": None, "subtype": "neighborhood"},
                           {"id": "aaaaaaaaaaa2", "name": "Later", "en": "Later", "subtype": "microhood"},
                           {"id": "aaaaaaaaaaa3", "name": "Never", "en": None, "subtype": "neighborhood"}]}}
    SNAPS = [
        # before parts were counted: no entry
        snap("2026-10-20", {"quests": {"A": {"open": 9, "agedOnly": 1}}}),
        # parts, no aged split yet; B is not counted in the city
        snap("2026-10-27", {"quests": {"A": {"open": 9, "agedOnly": 1}},
                            "parts": {"aaaaaaaaaaa1": {"A": 4}}}),
        # B counted now; aaaaaaaaaaa1 has no B (a zero left out), aaaaaaaaaaa2 appears
        snap("2026-10-28", {"quests": {"A": {"open": 9, "agedOnly": 1}, "B": {"open": 3, "agedOnly": None}},
                            "parts": {"aaaaaaaaaaa1": {"A": 5}, "aaaaaaaaaaa2": {"B": 3}}, "partsAged": {"aaaaaaaaaaa1": {"A": 1}}}),
        # aaaaaaaaaaa1 drops to zero on everything: left out of parts, but still counted
        snap("2026-10-29", {"quests": {"A": {"open": 2, "agedOnly": 0}, "B": {"open": 3, "agedOnly": None}},
                            "parts": {"aaaaaaaaaaa2": {"A": 2, "B": 3}}, "partsAged": {}}),
    ]

    def test_zeros_nulls_and_dates(self):
        out = run.build_part_history(self.SNAPS, self.REG)["x"]
        self.assertEqual(set(out), {"aaaaaaaaaaa1", "aaaaaaaaaaa2"})   # aaaaaaaaaaa3 never had a count
        aaaaaaaaaaa1 = out["aaaaaaaaaaa1"]
        self.assertEqual(aaaaaaaaaaa1["dates"], ["2026-10-27", "2026-10-28", "2026-10-29"])
        self.assertEqual(aaaaaaaaaaa1["quests"], {"A": {"open": [4, 5, 0], "agedOnly": [None, 1, 0]}})
        self.assertEqual((aaaaaaaaaaa1["city"], aaaaaaaaaaa1["part"], aaaaaaaaaaa1["name"]), ("x", "aaaaaaaaaaa1", "Annex"))
        aaaaaaaaaaa2 = out["aaaaaaaaaaa2"]
        self.assertEqual(aaaaaaaaaaa2["dates"], ["2026-10-28", "2026-10-29"])   # not counted before it appeared
        self.assertEqual(aaaaaaaaaaa2["quests"], {"A": {"open": [0, 2], "agedOnly": [0, 0]},
                                        "B": {"open": [3, 3], "agedOnly": [None, None]}})

    def test_files_written_and_stale_ones_removed(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            parts = tmp / "parts"
            parts.mkdir()
            (parts / "x.json").write_text(json.dumps(self.REG["x"]))
            stale = tmp / "data" / "history" / "gone" / "p9.json"
            stale.parent.mkdir(parents=True)
            stale.write_text("{}")
            city_file = tmp / "data" / "history" / "x.json"
            city_file.write_text("{}")
            shard = tmp / "places" / "ca" / "r1.json"
            shard.parent.mkdir(parents=True)
            shard.write_text('{"schema":1,"region":"r1","places":[\n["r1","R",2,-1,0,0,1,1,null,null],\n'
                             '["aaaaaaaaaaa1","Annex",8,0,0,0,1,1,null,"x/aaaaaaaaaaa1"]]}')
            self.assertEqual(run.write_part_history(tmp / "data", self.SNAPS, parts), 3)
            self.assertFalse(stale.parent.exists())
            self.assertTrue(city_file.exists())          # a city's own series is not a part's
            got = run.read_json(tmp / "data" / "history" / "x" / "aaaaaaaaaaa1.json")
            self.assertEqual(got["quests"]["A"]["open"], [4, 5, 0])
            self.assertEqual(got["in"], "ca/r1")
            self.assertNotIn("in", run.read_json(tmp / "data" / "history" / "x" / "aaaaaaaaaaa2.json"))
            self.assertEqual(run.write_part_history(tmp / "data", self.SNAPS, parts), 0)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
