"""run.py inputs (the world's daily inputs) and tools/site_quests.py: no network, no docker."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import run  # noqa: E402
import site_quests  # noqa: E402


class InputsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lock = Path(self.tmp.name) / "inputs.lock"
        self.fetched, self.backed, self.slept, self.site_fails = [], [], [], False
        self.codes = {}      # name -> the exit codes its fetches end with, the last one repeated
        for name, value in [("INPUTS_LOCK", self.lock), ("log", lambda m: None), ("check_release", lambda: None),
                            ("site", self.site),
                            ("backup_archive", lambda only=None: self.backed.append(only) or True)]:
            p = mock.patch.object(run, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(run.subprocess, "run", self.fetch)
        p.start()
        self.addCleanup(p.stop)

    def site(self, card=False):
        self.assertTrue(card)   # inputs' site, at 11:15, is the one that may redraw the share card
        self.assertFalse(self.lock.exists())
        self.assertEqual(self.backed, ["facts", "world"])
        if self.site_fails:
            raise RuntimeError("site: the deploy failed")

    def fetch(self, cmd, check=False, **kw):
        name = cmd[-1]
        self.assertEqual(cmd[-2], "fetch")
        self.assertTrue(self.lock.exists())
        self.fetched.append(name)
        codes = self.codes.get(name, [0])
        return subprocess.CompletedProcess(cmd, codes.pop(0) if len(codes) > 1 else codes[0])

    def test_fetches_then_backs_up_and_lets_go_of_the_lock(self):
        run.inputs(self.slept.append)
        self.assertEqual(self.fetched, ["europe", "notes"])
        self.assertEqual(self.backed, ["facts", "world"])
        self.assertEqual(self.slept, [])
        self.assertFalse(self.lock.exists())

    def test_a_fetch_is_tried_again(self):
        self.codes["europe"] = [1, 0]
        run.inputs(self.slept.append)
        self.assertEqual(self.fetched, ["europe", "europe", "notes"])
        self.assertEqual(self.slept, [run.INPUTS_WAIT_S])

    def test_a_dead_fetch_stops_nothing_else_and_fails_the_run(self):
        self.codes["europe"] = [1]
        with self.assertRaisesRegex(RuntimeError, "fetch europe failed"):
            run.inputs(self.slept.append)
        self.assertEqual(self.fetched, ["europe"] * run.INPUTS_TRIES + ["notes"])
        self.assertEqual(self.backed, ["facts", "world"])
        self.assertFalse(self.lock.exists())

    def test_a_release_check_that_fails_fails_nothing(self):
        with mock.patch.object(run, "check_release", side_effect=RuntimeError("gh")):
            run.inputs(self.slept.append)

    def test_a_failed_publish_fails_the_run(self):
        self.site_fails = True
        with self.assertRaisesRegex(RuntimeError, "site failed"):
            run.inputs(self.slept.append)

    def test_a_second_run_beside_a_live_one_does_nothing(self):
        self.lock.write_text(str(os.getpid()), encoding="utf-8")
        run.inputs(self.slept.append)
        self.assertEqual(self.fetched, [])
        self.assertTrue(self.lock.exists())

    def test_a_dead_runs_lock_is_taken_over(self):
        self.lock.write_text("not a pid", encoding="utf-8")
        run.inputs(self.slept.append)
        self.assertEqual(self.fetched, ["europe", "notes"])


class SiteQuestsTest(unittest.TestCase):
    def test_enabled_in_is_the_engines_rule(self):
        e = site_quests.enabled_in
        self.assertTrue(e({"type": "AllCountries"}, ["CA"]))
        self.assertFalse(e({"type": "AllCountriesExcept", "codes": ["CA-QC"]}, ["CA", "CA-QC"]))
        self.assertTrue(e({"type": "AllCountriesExcept", "codes": ["CA-QC"]}, ["CA", "CA-ON"]))
        self.assertTrue(e({"type": "NoCountriesExcept", "codes": ["DE"]}, ["DE", "DE-BE"]))
        self.assertFalse(e({"type": "NoCountriesExcept", "codes": ["DE"]}, ["CA"]))
        with self.assertRaises(ValueError):
            e({"type": "Other"}, ["CA"])

    def test_status(self):
        q = {"support": "supported", "enabledInCountries": {"type": "NoCountriesExcept", "codes": ["DE"]}}
        self.assertEqual(site_quests.status(q, {"countryCodes": ["DE"]}), "counted")
        self.assertEqual(site_quests.status(q, {"countryCodes": ["CA"]}), "not-in-region")
        self.assertEqual(site_quests.status({**q, "support": "unsupported"}, {"countryCodes": ["DE"]}), "unsupported")

    def test_the_published_file_is_what_build_writes(self):
        doc = site_quests.document(site_quests.base(), run.read_json(run.CITIES_CONFIG)["cities"])
        self.assertEqual((run.DATA_DIR / "quests.json").read_text(encoding="utf-8"), run.quests_json(doc))

    def test_a_newer_list_in_the_archive_is_used_and_a_same_version_one_is_not(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(run, "log", lambda m: None):
            archive = Path(d)
            mine = site_quests.base()
            for region, version in [("a", mine["scVersion"]), ("b", "999.0")]:
                (archive / region).mkdir()
                run.write_json(archive / region / "quests.json",
                               {"scVersion": version, "scCommit": region, "quests": [
                                   {"name": "AddX", "status": {"toronto": "counted"}}]})
            got = site_quests.base(archive=archive)
            self.assertEqual((got["scVersion"], got["quests"]), ("999.0", [{"name": "AddX"}]))
            (archive / "b" / "quests.json").unlink()
            self.assertEqual(site_quests.base(archive=archive), mine)


if __name__ == "__main__":
    unittest.main()
