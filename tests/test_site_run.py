"""run.py site: when the site is deployed, and what a run that can't do it leaves behind. No network."""
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import run  # noqa: E402
import world_publish  # noqa: E402

NOW = datetime(2026, 11, 25, 20, 20, tzinfo=timezone.utc)
STATE = {"day": "2026-11-24", "docs": "t1", "at": (NOW - timedelta(hours=2)).isoformat()}


class DueTest(unittest.TestCase):
    def test_due(self):
        self.assertIn("no deploy", run.site_due({}, "2026-11-24", "t1", NOW))
        self.assertIsNone(run.site_due(STATE, "2026-11-24", "t1", NOW))
        self.assertIn("2026-11-25", run.site_due(STATE, "2026-11-25", "t1", NOW))
        self.assertIsNone(run.site_due(STATE, "2026-11-24", "t2", NOW))
        self.assertIn("docs/", run.site_due(STATE, "2026-11-24", "t2", NOW + timedelta(hours=19)))


class SiteTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.calls, self.logged, self.cloud_ok, self.branch, self.memory = [], [], True, "main", (50.0, 40.0, 64.0)
        (self.tmp / "data").mkdir()
        run.write_json(self.tmp / "data" / "cities.json", {"asOfDate": "2026-11-24"})

        def git(*args, check=True):
            return subprocess.CompletedProcess(args, 0, self.branch if "--abbrev-ref" in args else "t1", "")

        def step(name, value=None):
            return lambda *a, **k: self.calls.append(name) or value
        for name, value in [("SITE_STATE", self.tmp / "state.json"), ("LOCK_PATH", self.tmp / "pipeline.lock"),
                            ("LOCK_DIR", self.tmp), ("DATA_DIR", self.tmp / "data"), ("git", git),
                            ("log", self.logged.append), ("history", step("history")), ("publish", step("publish")),
                            ("publish_cloud", lambda: self.calls.append("cloud") or self.cloud_ok),
                            ("memory_status", lambda: self.memory)]:
            p = mock.patch.object(run, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(world_publish, "gated_days", lambda w: ["2026-11-23", "2026-11-24"])
        p.start()
        self.addCleanup(p.stop)

    def test_a_new_day_goes_up_once(self):
        run.site()
        self.assertEqual(self.calls, ["history", "publish", "cloud"])
        self.assertEqual(run.read_json(run.SITE_STATE)["day"], "2026-11-24")
        self.assertFalse(run.LOCK_PATH.exists())
        run.site()
        self.assertEqual(len(self.calls), 3)

    def test_a_failed_deploy_is_tried_again(self):
        self.cloud_ok = False
        with self.assertRaisesRegex(RuntimeError, "deploy failed"):
            run.site()
        self.assertFalse(run.SITE_STATE.exists())
        self.cloud_ok = True
        run.site()
        self.assertTrue(run.SITE_STATE.exists())

    def test_left_to_the_next_run(self):
        self.memory = (1.0, 5.0, 64.0)
        run.site()
        self.memory = (50.0, 40.0, 64.0)
        run.LOCK_PATH.write_text("4321", encoding="utf-8")
        with mock.patch.object(run, "pid_alive", return_value=True):
            run.site()
        self.assertEqual(self.calls, [])
        self.assertIn("commit left", self.logged[0])
        self.assertIn("another run", self.logged[1])

    def test_only_from_main(self):
        self.branch = "wip"
        with self.assertRaisesRegex(RuntimeError, "wip"):
            run.site()
        self.assertEqual(self.calls, [])

    def test_no_push_is_no_deploy(self):
        run.site(push=False)
        self.assertEqual(self.calls, ["history", "publish"])
        self.assertFalse(run.SITE_STATE.exists())


class PushTest(unittest.TestCase):
    def test_unchanged_data_still_pushes_main(self):
        calls = []

        def git(*args, check=True):
            calls.append(args[0])
            return subprocess.CompletedProcess(args, 0, "", "")
        with mock.patch.object(run, "git", git), mock.patch.object(run, "log"):
            self.assertFalse(run.publish())
            self.assertIn("push", calls)
            calls.clear()
            self.assertFalse(run.publish(push=False))
            self.assertNotIn("push", calls)


if __name__ == "__main__":
    unittest.main()
