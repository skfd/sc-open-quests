"""The weekly planet job: history file naming, the months' end, cadence, run.py weekly. Run: python -m unittest"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import run  # noqa: E402
import backfill_history as bh  # noqa: E402

DUMP_META = {"region": "planet", "data_date": "2026-10-05", "replication_timestamp": "2026-10-05T00:00:03+00:00"}
DIFFED_META = {"replication_timestamp": "2026-10-07T00:00:00Z", "replication_sequence": 5138,
               "derived_from": "planet/history-261005.osm.pbf + day 5137-5138"}
BREMEN = {"id": "bremen", "name": "Bremen", "group": "Germany", "timeZone": "Europe/Berlin",
          "poly": "config/bremen.poly", "source": "Geofabrik Bremen"}


def utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class StoreCase(unittest.TestCase):
    """A scratch shared store with a planet/ folder; backfill_history's globals restored after."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = self.tmp / "store"
        self.planet = self.store / "planet"
        self.planet.mkdir(parents=True)
        saved = {k: getattr(bh, k) for k in ("PLANET", "PLANET_FILE", "PLANET_URL", "PLANET_DERIVED_FROM", "BACKFILL")}
        self.addCleanup(lambda: [setattr(bh, k, v) for k, v in saved.items()])
        for patch in (mock.patch.object(run, "OSM_DATA_DIR", self.store),
                      mock.patch.object(bh, "BACKFILL", self.tmp / "backfill"),
                      mock.patch.object(run, "ARCHIVE_DIR", self.tmp / "archive")):
            patch.start()
            self.addCleanup(patch.stop)
        self.addCleanup(shutil.rmtree, self.tmp)

    def history_file(self, name: str, meta: dict | None):
        (self.planet / name).write_bytes(b"")
        if meta is not None:
            stem = name.split(".")[0]
            (self.planet / f"{stem}.meta.json").write_text(json.dumps(meta), encoding="utf-8")


class PlanetNamingTest(StoreCase):
    def test_the_dump_alone_is_used_as_before(self):
        self.history_file("history-261005.osm.pbf", DUMP_META)
        self.assertEqual(bh.set_planet(None), "history-261005")
        self.assertEqual(bh.PLANET_FILE, "history-261005.osm.pbf")
        self.assertEqual(bh.PLANET_URL, "https://planet.openstreetmap.org/pbf/full-history/history-261005.osm.pbf")
        self.assertIsNone(bh.PLANET_DERIVED_FROM)

    def test_the_newest_by_date_wins_across_suffixes(self):
        self.history_file("history-261005.osm.pbf", DUMP_META)
        self.history_file("history-261007.osh.pbf", DIFFED_META)
        for junk in ("history-261012.osh.pbf.part", "history-latest.osm.pbf", "history-2610.osh.pbf"):
            (self.planet / junk).write_bytes(b"")
        self.assertEqual(bh.newest_planet(), "history-261007")
        bh.set_planet(None)
        self.assertEqual(bh.PLANET_FILE, "history-261007.osh.pbf")
        self.assertIsNone(bh.PLANET_URL)  # no download URL for a file made with diffs
        self.assertEqual(bh.PLANET_DERIVED_FROM, DIFFED_META["derived_from"])

    def test_an_older_history_file_by_name_or_file_name(self):
        self.history_file("history-261005.osm.pbf", DUMP_META)
        self.history_file("history-261007.osh.pbf", DIFFED_META)
        for name in ("history-261005", "history-261005.osm.pbf", "planet/history-261005.osm.pbf"):
            self.assertEqual(bh.set_planet(name), "history-261005")
            self.assertEqual(bh.PLANET_FILE, "history-261005.osm.pbf")
        self.assertEqual(bh.set_planet("history-261007.osh.pbf"), "history-261007")
        self.assertEqual(bh.PLANET_FILE, "history-261007.osh.pbf")

    def test_same_date_under_both_suffixes_takes_the_osh(self):
        self.history_file("history-261007.osm.pbf", None)
        self.history_file("history-261007.osh.pbf", DIFFED_META)
        self.assertEqual(bh.planet_files(), {"history-261007": "history-261007.osh.pbf"})

    def test_a_retired_history_file_still_names_its_clips(self):
        bh.set_planet("history-261005")  # neither file nor meta in the store
        self.assertEqual(bh.PLANET_FILE, "history-261005.osm.pbf")

    def test_no_history_file(self):
        with self.assertRaises(SystemExit):
            bh.newest_planet()

    def test_a_new_history_file_means_new_clips(self):
        self.history_file("history-261005.osm.pbf", DUMP_META)
        bh.set_planet(None)
        old = bh.Region("bremen").history
        self.history_file("history-261007.osh.pbf", DIFFED_META)
        bh.set_planet(None)
        new = bh.Region("bremen")
        self.assertEqual(old.name, "bremen-history-261005.osh.pbf")
        self.assertEqual(new.history.name, "bremen-history-261007.osh.pbf")
        self.assertEqual(new.history_meta.name, "bremen-history-261007.osh.pbf.meta.json")
        # the weekly path deletes the superseded clip once the new one is there
        for p in (old, old.with_name(old.name + ".meta.json"), new.history, new.history_meta, new.poly):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"")
        bh.prune_clips(new)
        self.assertEqual(sorted(p.name for p in new.history_dir.iterdir()),
                         ["bremen-history-261007.osh.pbf", "bremen-history-261007.osh.pbf.meta.json", "bremen.poly"])

    def test_slice_meta_of_the_dump_is_unchanged(self):
        self.history_file("history-261005.osm.pbf", DUMP_META)
        bh.set_planet(None)
        r = bh.Region("bremen")
        r.history.parent.mkdir(parents=True)
        r.history.write_bytes(b"")
        (r.backfill).mkdir(parents=True)
        (r.backfill / "bremen-2026-10-01-from-history-261005.osm.pbf").write_bytes(b"")  # no docker
        pbf, meta = bh.slice_at(r, utc("2026-10-01T12:00:00Z"))
        self.assertEqual(run.read_json(meta), {
            "region": "bremen", "source_url": "https://planet.openstreetmap.org/pbf/full-history/history-261005.osm.pbf",
            "file": "bremen-history-261005.osh.pbf@2026-10-01T12:00:00Z",
            "replication_timestamp": "2026-10-01T12:00:00Z", "derived_from": "planet/history-261005.osm.pbf"})

    def test_slice_meta_of_a_diffed_file_records_its_lineage(self):
        self.history_file("history-261007.osh.pbf", DIFFED_META)
        bh.set_planet(None)
        r = bh.Region("bremen")
        r.history.parent.mkdir(parents=True)
        r.history.write_bytes(b"")
        r.backfill.mkdir(parents=True)
        (r.backfill / "bremen-2026-10-07-from-history-261007.osm.pbf").write_bytes(b"")
        _, meta = bh.slice_at(r, utc("2026-10-07T00:00:00Z"))
        m = run.read_json(meta)
        self.assertIsNone(m["source_url"])
        self.assertEqual(m["derived_from"], "planet/history-261007.osh.pbf")
        self.assertEqual(m["planet_derived_from"], DIFFED_META["derived_from"])


class LastMonthTest(StoreCase):
    def test_last_month(self):
        cases = {"2026-10-05T00:00:03+00:00": "2026-10", "2026-10-01T12:00:00Z": "2026-10",
                 "2026-10-01T11:59:59Z": "2026-09", "2026-10-07T00:00:00Z": "2026-10",
                 "2027-01-01T00:00:00Z": "2026-12", "2026-11-30T23:00:00Z": "2026-11"}
        for stamp, month in cases.items():
            self.assertEqual(bh.last_month(utc(stamp)), month, stamp)

    def months_to(self, argv):
        with mock.patch.object(bh, "months") as months, mock.patch.object(run, "migrate_archive"):
            bh.main(["months", "--region", "bremen", *argv])
        return months.call_args.args[2]

    def test_months_to_default_follows_the_history_file(self):
        self.history_file("history-261005.osm.pbf", DUMP_META)
        self.assertEqual(self.months_to([]), "2026-10")  # what the hard-coded default was
        self.history_file("history-261102.osh.pbf", {**DIFFED_META, "replication_timestamp": "2026-11-02T00:00:00Z"})
        self.assertEqual(self.months_to([]), "2026-11")
        self.assertEqual(self.months_to(["--planet", "history-261005"]), "2026-10")
        self.assertEqual(self.months_to(["--to", "2020-05"]), "2020-05")

    def test_months_to_from_the_clip_once_the_planet_file_is_retired(self):
        bh.set_planet("history-261005")
        r = bh.Region("bremen")
        r.history_meta.parent.mkdir(parents=True)
        r.history_meta.write_text(json.dumps({"replication_timestamp": DUMP_META["replication_timestamp"]}))
        self.assertEqual(self.months_to(["--planet", "history-261005"]), "2026-10")


class CountAtTest(StoreCase):
    def test_the_date_is_the_regions_and_counted_once(self):
        self.history_file("history-261007.osh.pbf", DIFFED_META)
        bh.set_planet(None)
        r = bh.Region("bremen")
        r.staged.mkdir(parents=True)
        (r.staged / "2026-10-07.json").write_text("{}")
        with mock.patch.object(bh, "slice_at") as slice_at:
            self.assertIsNone(bh.count_at(r, utc("2026-10-06T22:30:00Z")))  # 00:30 in Berlin
            slice_at.assert_not_called()

    def test_weekly_counts_the_months_first_then_now(self):
        self.history_file("history-261007.osh.pbf", DIFFED_META)
        calls = []
        with mock.patch.object(bh, "clip"), mock.patch.object(bh, "prune_clips"), \
                mock.patch.object(bh, "wait_for_quiet"), \
                mock.patch.object(bh, "months", side_effect=lambda r, *a, **k: calls.append(("months", r.id, *a))), \
                mock.patch.object(bh, "count_at", side_effect=lambda r, t: calls.append(("now", r.id, bh.iso(t)))):
            t = bh.weekly(["bremen"])
        self.assertEqual(t, utc("2026-10-07T00:00:00Z"))
        self.assertEqual(calls, [("months", "bremen", "2017-01", "2026-10", 1), ("now", "bremen", "2026-10-07T00:00:00Z")])


class QuietTest(unittest.TestCase):
    def test_window_and_lookahead(self):
        at = lambda hm: datetime(2026, 10, 26, *hm)  # noqa: E731
        self.assertTrue(bh.in_quiet(at((13, 0))))
        self.assertFalse(bh.in_quiet(at((12, 54))))
        self.assertFalse(bh.in_quiet(at((13, 50))))
        self.assertTrue(bh.in_quiet(at((11, 30)), ahead_minutes=90))
        self.assertFalse(bh.in_quiet(at((11, 20)), ahead_minutes=90))
        self.assertFalse(bh.in_quiet(at((7, 30)), ahead_minutes=120))


class CadenceTest(unittest.TestCase):
    def test_default_is_daily_and_todays_regions_are_all_daily(self):
        self.assertEqual(run.region_cadence(BREMEN), "daily")
        self.assertEqual(run.regions_by_cadence("daily"), run.regions())
        self.assertEqual(run.regions_by_cadence("weekly"), [])

    def test_weekly_and_unknown(self):
        weekly = {**BREMEN, "id": "bremen-weekly", "cadence": "weekly"}
        self.assertEqual(run.region_cadence(weekly), "weekly")
        self.assertEqual(run.regions_by_cadence("weekly", [BREMEN, weekly]), [weekly])
        with self.assertRaises(ValueError):
            run.region_cadence({**BREMEN, "cadence": "monthly"})

    def test_daily_paths_leave_weekly_regions_alone(self):
        weekly = {**BREMEN, "id": "bremen-weekly", "cadence": "weekly"}
        calls, counted = [], []
        with mock.patch.object(run, "regions", return_value=[BREMEN, weekly]), \
                mock.patch.object(run.subprocess, "run", side_effect=lambda cmd, **kw: calls.append(cmd[2:])), \
                mock.patch.object(run, "dated_extracts", side_effect=lambda r: [r["id"]]), \
                mock.patch.object(run, "count", side_effect=lambda r, **kw: counted.append(r["id"])), \
                mock.patch.object(run, "pipeline_lock"):
            run.download()
            run.backfill()
        self.assertEqual(calls, [["fetch", "bremen"], ["fetch", "notes"]])
        self.assertEqual(counted, ["bremen"])


class WeeklyRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / "planet").mkdir()
        (self.tmp / "planet" / "history-261005.osm.pbf").write_bytes(b"")
        (self.tmp / "planet" / "history-261005.meta.json").write_text(json.dumps(DUMP_META))
        self.lock = self.tmp / "pipeline.lock"
        for patch in (mock.patch.object(run, "OSM_DATA_DIR", self.tmp),
                      mock.patch.object(run, "LOCK_DIR", self.tmp), mock.patch.object(run, "LOCK_PATH", self.lock),
                      mock.patch.object(bh, "wait_for_quiet")):
            patch.start()
            self.addCleanup(patch.stop)
        self.logs = []
        p = mock.patch.object(run, "log", side_effect=self.logs.append)
        p.start()
        self.addCleanup(p.stop)

    def fetch(self, returncode):
        def fake(cmd, **kw):
            self.assertEqual(cmd[2:], ["fetch", "planet-history"])
            return subprocess.CompletedProcess(cmd, returncode)
        return mock.patch.object(run.subprocess, "run", side_effect=fake)

    def test_no_weekly_region_only_refreshes_the_history_file(self):
        for code in (0, 1):
            self.logs.clear()
            with self.fetch(code), mock.patch.object(bh, "weekly") as counted, \
                    mock.patch.object(run, "history") as hist, mock.patch.object(run, "publish") as pub:
                run.weekly(push=False)
            counted.assert_not_called()
            hist.assert_not_called()
            pub.assert_not_called()
            self.assertTrue(any("no region is weekly" in m for m in self.logs), self.logs)
            self.assertEqual(any("fetch planet-history failed" in m for m in self.logs), code == 1)
            self.assertFalse(self.lock.exists())

    def test_weekly_regions_count_merge_and_publish_without_push(self):
        weekly = {**BREMEN, "id": "bremen-weekly", "cadence": "weekly"}
        merged = []
        with self.fetch(1), mock.patch.object(run, "regions", return_value=[BREMEN, weekly]), \
                mock.patch.object(bh, "weekly", return_value=utc("2026-10-07T00:00:00Z")) as counted, \
                mock.patch.object(bh, "merge", side_effect=lambda r: merged.append((r.id, self.lock.exists()))), \
                mock.patch.object(run, "history") as hist, mock.patch.object(run, "publish") as pub:
            run.weekly(push=False)
        counted.assert_called_once_with(["bremen-weekly"])
        self.assertEqual(merged, [("bremen-weekly", True)])  # under the pipeline lock
        hist.assert_called_once_with()
        pub.assert_called_once_with(message="data weekly 2026-10-07", push=False)
        self.assertFalse(self.lock.exists())

    def test_a_weekly_region_without_any_history_file_fails(self):
        shutil.rmtree(self.tmp / "planet")
        (self.tmp / "planet").mkdir()
        weekly = {**BREMEN, "id": "bremen-weekly", "cadence": "weekly"}
        with self.fetch(1), mock.patch.object(run, "regions", return_value=[weekly]), \
                self.assertRaises(RuntimeError):
            run.weekly(push=False)


class PublishTest(unittest.TestCase):
    def test_no_push_commits_with_the_message(self):
        calls = []

        def git(*args, check=True):
            calls.append(args)
            return subprocess.CompletedProcess(args, 1 if args[0] == "diff" else 0, "", "")
        with mock.patch.object(run, "git", side_effect=git), mock.patch.object(run, "log"):
            self.assertTrue(run.publish(message="data weekly 2026-10-07", push=False))
        self.assertIn(("commit", "-m", "data weekly 2026-10-07", "--", "docs/data"), calls)
        self.assertFalse(any(c[0] == "push" for c in calls))


if __name__ == "__main__":
    unittest.main()
