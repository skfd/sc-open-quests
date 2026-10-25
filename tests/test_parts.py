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


if __name__ == "__main__":
    unittest.main()
