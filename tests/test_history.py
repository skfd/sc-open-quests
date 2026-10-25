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

    def test_city_index_trends_cover_every_snapshot_date(self):
        idx = self.load("cities.json")
        self.assertEqual(idx["dates"], ["2026-07-16", "2026-07-17", "2026-07-18"])
        ottawa, toronto = idx["cities"]
        self.assertEqual(ottawa["trend"][0], None)   # not in the first snapshot
        self.assertEqual(toronto["trend"][-1], toronto["open"])
        self.assertEqual(toronto["trendAll"][-1], toronto["openAll"])
        self.assertEqual(toronto["trend"][1], 9 + 6 + 4)   # AddC counted that day only

    def test_rerun_changes_nothing(self):
        before = {p: p.read_bytes() for p in self.data.rglob("*.json")}
        self.assertEqual(run.history(self.data, self.config), 0)
        self.assertEqual(before, {p: p.read_bytes() for p in self.data.rglob("*.json")})

    def test_history_of_a_removed_city_is_deleted(self):
        (self.data / "history" / "gone.json").write_text("{}", encoding="utf-8")
        run.history(self.data, self.config)
        self.assertFalse((self.data / "history" / "gone.json").exists())

    def test_compare_has_each_citys_newest_open_per_quest(self):
        self.assertEqual(self.load("compare/AddA.json"), {"quest": "AddA", "open": {"ottawa": 2, "toronto": 8}})
        self.assertEqual(self.load("compare/AddD.json")["open"], {"toronto": 6})   # default-disabled too
        # counted on 07-17 only: in no city's newest snapshot, so no file (the site reads that as no count)
        self.assertFalse((self.data / "compare" / "AddC.json").exists())
        (self.data / "compare" / "AddGone.json").write_text("{}", encoding="utf-8")
        run.history(self.data, self.config)
        self.assertFalse((self.data / "compare" / "AddGone.json").exists())


class ArchiveTest(unittest.TestCase):
    """docs/data published every snapshot until 2026-10-24; now the archive holds them and the
    published data dir the newest per region."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data, self.archive = self.tmp / "docs-data", self.tmp / "archive"
        shutil.copytree(FIXTURE, self.data)   # the old layout: every snapshot under the data dir
        self.config = self.data / "cities-config.json"
        self.reference = self.tmp / "reference"
        shutil.copytree(FIXTURE, self.reference)
        run.history(self.reference, self.config)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_migration_moves_snapshots_and_keeps_the_newest_published(self):
        run.history(self.data, self.config, self.archive)
        self.assertEqual(sorted(p.name for p in (self.archive / "ontario" / "snapshots").glob("*.json")),
                         ["2026-07-16.json", "2026-07-17.json", "2026-07-18.json"])
        self.assertTrue((self.archive / "ontario" / "quests.json").exists())
        self.assertEqual(sorted(p.name for p in (self.data / "ontario").rglob("*.json")), ["2026-07-18.json"])
        self.assertEqual((self.data / "ontario" / "snapshots" / "2026-07-18.json").read_bytes(),
                         (FIXTURE / "ontario" / "snapshots" / "2026-07-18.json").read_bytes())

    def test_moving_the_source_changes_no_output_byte(self):
        run.history(self.data, self.config, self.archive)
        for rel in ["cities.json", "quests.json", "history/toronto.json", "history/ottawa.json", "compare/AddA.json"]:
            self.assertEqual((self.data / rel).read_bytes(), (self.reference / rel).read_bytes(), rel)

    def test_migration_is_idempotent(self):
        run.history(self.data, self.config, self.archive)
        before = {p: p.read_bytes() for p in self.tmp.rglob("*.json")}
        self.assertEqual(run.migrate_archive(self.data, self.archive), 0)
        self.assertEqual(run.history(self.data, self.config, self.archive), 0)
        self.assertEqual(before, {p: p.read_bytes() for p in self.tmp.rglob("*.json")})

    def test_a_newer_snapshot_replaces_the_published_one(self):
        run.history(self.data, self.config, self.archive)
        newer = json.loads((self.archive / "ontario" / "snapshots" / "2026-07-18.json").read_text(encoding="utf-8"))
        newer["asOfDate"] = "2026-07-19"
        run.write_json(self.archive / "ontario" / "snapshots" / "2026-07-19.json", newer)
        run.history(self.data, self.config, self.archive)
        self.assertEqual(sorted(p.name for p in (self.data / "ontario" / "snapshots").glob("*.json")),
                         ["2026-07-19.json"])
        self.assertEqual(len(list((self.archive / "ontario" / "snapshots").glob("*.json"))), 4)

    def test_a_recount_of_the_newest_is_published_not_migrated(self):
        run.history(self.data, self.config, self.archive)
        newest = self.archive / "ontario" / "snapshots" / "2026-07-18.json"
        recount = json.loads(newest.read_text(encoding="utf-8"))
        recount["runSeconds"] = 99.9
        run.write_json(newest, recount)
        self.assertEqual(run.migrate_archive(self.data, self.archive), 0)
        run.history(self.data, self.config, self.archive)
        self.assertEqual((self.data / "ontario" / "snapshots" / "2026-07-18.json").read_bytes(), newest.read_bytes())

    def test_an_archive_missing_published_dates_is_refused(self):
        run.history(self.data, self.config, self.archive)
        before = (self.data / "history" / "toronto.json").read_bytes()
        (self.archive / "ontario" / "snapshots" / "2026-07-16.json").unlink()
        with self.assertRaises(RuntimeError):
            run.history(self.data, self.config, self.archive)
        self.assertEqual((self.data / "history" / "toronto.json").read_bytes(), before)


class HelpersTest(unittest.TestCase):
    def test_newest_quests_file_compares_versions_numerically(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ["v63.4.json", "v63.10.json", "v9.9.json", "notes.json"]:
                (Path(d) / name).write_text("{}", encoding="utf-8")
            self.assertEqual(run.newest_quests_file(Path(d)).name, "v63.10.json")

    def test_snapshot_for_sha(self):
        self.assertEqual(run.snapshot_for_sha("sha-2026-07-17", FIXTURE / "ontario").name, "2026-07-17.json")
        self.assertIsNone(run.snapshot_for_sha("nope", FIXTURE / "ontario"))


if __name__ == "__main__":
    unittest.main()
