"""history: snapshots -> per-city series and the city index. Run: python -m unittest"""
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


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "data"
        shutil.copytree(FIXTURE, self.data)
        self.config = self.data / "cities-config.json"
        run.history(self.data, self.config)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def load(self, rel):
        return json.loads((self.data / rel).read_text(encoding="utf-8"))

    def test_dates_ascending_with_meta_per_date(self):
        t = self.load("history/toronto.json")
        self.assertEqual(t["name"], "Toronto")
        self.assertEqual(t["dates"], ["2026-07-16", "2026-07-17", "2026-07-18"])
        self.assertEqual([m["scVersion"] for m in t["meta"]], ["63.4", "63.4", "63.5"])
        self.assertEqual([m["resurveyMultiplier"] for m in t["meta"]], [1, 1, 1])

    def test_series_values(self):
        q = self.load("history/toronto.json")["quests"]
        self.assertEqual(q["AddA"], {"open": [10, 9, 8], "agedOnly": [0, 0, 0]})
        self.assertEqual(q["AddB"], {"open": [5, 6, 6], "agedOnly": [2, 3, 2]})

    def test_quest_missing_from_a_snapshot_is_null_not_zero(self):
        q = self.load("history/toronto.json")["quests"]
        self.assertEqual(q["AddC"], {"open": [None, 4, None], "agedOnly": [None, 0, None]})

    def test_city_missing_from_a_snapshot_has_no_entry_for_that_date(self):
        o = self.load("history/ottawa.json")
        self.assertEqual(o["dates"], ["2026-07-17", "2026-07-18"])
        self.assertEqual(o["quests"]["AddA"]["open"], [1, 2])
        self.assertEqual(o["denominators"]["highwayKm"], [50.0, 51.0])

    def test_denominators(self):
        d = self.load("history/toronto.json")["denominators"]
        self.assertEqual(d["landAreaKm2"], 665.9)
        self.assertEqual(d["highwayKm"], [100.0, 101.0, 102.0])

    def test_city_index_totals_exclude_default_disabled(self):
        idx = self.load("cities.json")
        self.assertEqual(idx["asOfDate"], "2026-07-18")
        self.assertEqual(idx["scVersion"], "63.5")
        self.assertEqual([c["id"] for c in idx["cities"]], ["ottawa", "toronto"])
        t = idx["cities"][1]
        self.assertEqual(t["open"], 8 + 6)        # AddD is default-disabled
        self.assertEqual(t["openAll"], 8 + 6 + 6)
        self.assertEqual(t["agedOnly"], 2)
        self.assertEqual(t["highwayKm"], 102.0)
        self.assertEqual(t["questsCounted"], 3)

    def test_rerun_changes_nothing(self):
        before = {p: p.read_bytes() for p in self.data.rglob("*.json")}
        self.assertEqual(run.history(self.data, self.config), 0)
        self.assertEqual(before, {p: p.read_bytes() for p in self.data.rglob("*.json")})

    def test_history_of_a_removed_city_is_deleted(self):
        (self.data / "history" / "gone.json").write_text("{}", encoding="utf-8")
        run.history(self.data, self.config)
        self.assertFalse((self.data / "history" / "gone.json").exists())


class HelpersTest(unittest.TestCase):
    def test_newest_quests_file_compares_versions_numerically(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ["v63.4.json", "v63.10.json", "v9.9.json", "notes.json"]:
                (Path(d) / name).write_text("{}", encoding="utf-8")
            self.assertEqual(run.newest_quests_file(Path(d)).name, "v63.10.json")

    def test_snapshot_for_sha(self):
        self.assertEqual(run.snapshot_for_sha("sha-2026-07-17", FIXTURE).name, "2026-07-17.json")
        self.assertIsNone(run.snapshot_for_sha("nope", FIXTURE))


if __name__ == "__main__":
    unittest.main()
