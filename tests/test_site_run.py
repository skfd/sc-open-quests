"""run.py site: when the site is deployed, and what a run that can't do it leaves behind. No network."""
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
import world_publish  # noqa: E402

STATE = {"docs": "t1", "config": "c1", "at": "2026-11-25T18:20:00+00:00"}


class DueTest(unittest.TestCase):
    def test_due(self):
        self.assertIn("no deploy", run.site_due({}, {"docs": "t1", "config": "c1"}))
        self.assertIsNone(run.site_due(STATE, {"docs": "t1", "config": "c1"}))
        self.assertEqual(run.site_due(STATE, {"docs": "t2", "config": "c1"}), "docs/ changed since the last deploy")
        self.assertEqual(run.site_due(STATE, {"docs": "t1", "config": "c2"}), "config/ changed since the last deploy")
        before = {"day": "2026-11-24", "docs": "t1"}   # a state from before 2026-11-26
        self.assertIn("config/", run.site_due(before, {"docs": "t1", "config": "c1"}))


class SiteTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.world_ok = True
        self.calls, self.logged, self.cloud_ok, self.branch, self.memory = [], [], True, "main", (50.0, 40.0, 64.0)
        (self.tmp / "data").mkdir()
        run.write_json(self.tmp / "data" / "cities.json", {"asOfDate": "2026-11-24"})
        self.days, self.trees = ["2026-11-23", "2026-11-24"], {"HEAD:docs": "t1", "HEAD:config": "c1"}

        def git(*args, check=True):
            return subprocess.CompletedProcess(args, 0, self.branch if "--abbrev-ref" in args else self.trees[args[-1]], "")

        def step(name, value=None):
            return lambda *a, **k: self.calls.append(name) or value
        for name, value in [("SITE_STATE", self.tmp / "state.json"), ("LOCK_PATH", self.tmp / "pipeline.lock"),
                            ("LOCK_DIR", self.tmp), ("DATA_DIR", self.tmp / "data"), ("git", git),
                            ("log", self.logged.append), ("history", step("history")), ("publish", step("publish")),
                            ("push_main", step("push")),
                            ("publish_cloud", lambda: self.calls.append("cloud") or self.cloud_ok),
                            ("publish_world", lambda: self.calls.append("world") or self.world_ok),
                            ("memory_status", lambda: self.memory)]:
            p = mock.patch.object(run, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(world_publish, "gated_days", lambda w: self.days)
        p.start()
        self.addCleanup(p.stop)

    def test_a_change_goes_up_once_and_a_new_day_is_the_place_files_alone(self):
        run.site()
        self.assertEqual(self.calls, ["world", "history", "publish", "cloud"])
        state = run.read_json(run.SITE_STATE)
        self.assertEqual((state["docs"], state["config"]), ("t1", "c1"))
        self.assertFalse(run.LOCK_PATH.exists())
        self.days = self.days + ["2026-11-25"]
        self.calls.clear()
        run.site()
        self.assertEqual(self.calls, ["world", "push"])   # it asks the bucket's manifest itself
        for folder in ("HEAD:docs", "HEAD:config"):
            self.trees[folder] += "x"
            self.calls.clear()
            run.site()
            self.assertEqual(self.calls, ["world", "history", "publish", "cloud"])

    def test_config_changed_during_the_build_is_the_next_runs(self):
        def moved(*a, **k):
            self.trees["HEAD:config"] = "c2"
        with mock.patch.object(run, "history", moved):
            run.site()
        self.assertEqual(run.read_json(run.SITE_STATE)["config"], "c1")

    def test_nothing_is_pushed_off_main(self):
        run.site()
        self.calls.clear()
        self.branch = "wip"
        run.site()
        self.assertEqual(self.calls, ["world"])

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
        self.assertEqual(self.calls, ["world"])   # the place files need no pipeline lock
        self.assertIn("commit left", self.logged[0])
        self.assertIn("another run", self.logged[1])

    def test_failed_place_files_hold_nothing_back(self):
        self.world_ok = False
        with self.assertRaisesRegex(RuntimeError, "place files"):
            run.site()
        self.assertEqual(self.calls, ["world", "history", "publish", "cloud"])
        self.assertTrue(run.SITE_STATE.exists())

    def test_only_from_main(self):
        self.branch = "wip"
        with self.assertRaisesRegex(RuntimeError, "wip"):
            run.site()
        self.assertEqual(self.calls, ["world"])

    def test_only_inputs_site_redraws_the_card(self):
        with mock.patch.object(run, "redraw_card", lambda newest: self.calls.append(f"card {newest}")):
            run.site()   # the loop's own call, and the command line
            self.assertNotIn("card 2026-11-24", self.calls)
            self.calls.clear()
            run.site(card=True)
            self.assertEqual(self.calls[:2], ["world", "card 2026-11-24"])
            self.calls.clear()
            run.site(card=True, push=False)
            self.assertNotIn("card 2026-11-24", self.calls)

    def test_no_push_is_no_deploy(self):
        run.site(push=False)
        self.assertEqual(self.calls, ["history", "publish"])
        self.assertFalse(run.SITE_STATE.exists())


PAGE = ('<meta property="og:image" content="https://street-complete-statistics.comentality.com/img/share-card.png'
        '?v={}">\n')


class CardStaleTest(unittest.TestCase):
    def test_the_day_on_the_page(self):
        self.assertEqual(run.card_day(PAGE.format("2026-11-24")), run.date(2026, 11, 24))
        for odd in ("", "2026-13-01", "24 Nov 2026", "2026-11-24x"):
            self.assertIsNone(run.card_day(PAGE.format(odd)), odd)
        self.assertIsNone(run.card_day("<html>no card</html>"))

    def test_a_later_month_of_the_world(self):
        nov24 = run.date(2026, 11, 24)
        self.assertFalse(run.card_stale(nov24, "2026-11-24"))
        self.assertFalse(run.card_stale(nov24, "2026-11-30"))   # 12-01 at 11:15: the world's day is still 11-30
        self.assertTrue(run.card_stale(nov24, "2026-12-01"))
        self.assertTrue(run.card_stale(run.date(2026, 12, 31), "2027-01-01"))
        self.assertFalse(run.card_stale(run.date(2027, 1, 1), "2026-12-31"))
        self.assertFalse(run.card_stale(None, "2026-12-01"))     # no day: the render could not write one either


class RedrawCardTest(unittest.TestCase):
    """The scripts and git mocked: nothing is drawn, nothing under docs/ changes."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.page = self.tmp / "index.html"
        self.page.write_text(PAGE.format("2026-11-24"), encoding="utf-8")
        self.drawn, self.fails, self.branch, self.dirty = "2026-12-01", None, "main", ""
        self.ran, self.gits, self.logged = [], [], []

        def git(*args, check=True):
            self.gits.append(args[0])
            out = self.branch if "--abbrev-ref" in args else self.dirty if args[0] == "status" else ""
            return subprocess.CompletedProcess(args, 0, out, "")

        def script(cmd, **kw):
            name = Path(cmd[-1]).name
            self.ran.append(name)
            if name == self.fails:
                return subprocess.CompletedProcess(cmd, 1, "", "the world loop is running")
            if name == "render_share_card.py":
                self.page.write_text(PAGE.format(self.drawn), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        for name, value in [("CARD_PAGE", self.page), ("LOOP_RUNNING", self.tmp / "RUNNING"), ("git", git),
                            ("log", self.logged.append)]:
            p = mock.patch.object(run, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(run.subprocess, "run", script)
        p.start()
        self.addCleanup(p.stop)

    def test_redrawn_and_committed_once_a_month(self):
        self.assertFalse(run.redraw_card("2026-11-30"))
        self.assertEqual(self.ran, [])
        self.assertTrue(run.redraw_card("2026-12-01"))
        self.assertEqual(self.ran, ["project_card.py", "render_share_card.py"])
        self.assertIn("commit", self.gits)
        self.assertIn("committed, 2026-12-01", self.logged[-1])

    def test_a_failure_puts_the_files_back_and_raises_nothing(self):
        self.fails = "render_share_card.py"
        self.assertFalse(run.redraw_card("2026-12-01"))
        self.assertEqual(self.gits[-1], "checkout")
        self.assertNotIn("commit", self.gits)
        self.assertIn("redraw FAILED", self.logged[-1])

    def test_a_card_drawn_for_the_same_month_is_not_committed(self):
        self.drawn = "2026-11-30"   # sc-data behind the world
        self.assertFalse(run.redraw_card("2026-12-01"))
        self.assertNotIn("commit", self.gits)
        self.assertEqual(self.gits[-1], "checkout")

    def test_not_while_the_loop_runs_off_main_or_over_edits(self):
        (self.tmp / "RUNNING").write_text("x", encoding="utf-8")
        self.assertFalse(run.redraw_card("2026-12-01"))
        (self.tmp / "RUNNING").unlink()
        self.branch = "wip"
        self.assertFalse(run.redraw_card("2026-12-01"))
        self.branch, self.dirty = "main", " M docs/index.html"
        self.assertFalse(run.redraw_card("2026-12-01"))
        self.assertEqual(self.ran, [])

    def test_a_page_without_a_day_is_left_alone(self):
        self.page.write_text("<html></html>", encoding="utf-8")
        self.assertFalse(run.redraw_card("2026-12-01"))
        self.assertEqual(self.ran, [])
        self.assertIn("not redrawn", self.logged[0])


class RedrawCardGitTest(unittest.TestCase):
    """The commit and the putting back, in a throwaway repo with real git; only the two scripts are faked."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.page = self.repo / "docs" / "index.html"
        for f in run.CARD_FILES:
            (self.repo / f).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / f).write_text("old\n", encoding="utf-8")
        self.page.write_text(PAGE.format("2026-11-24"), encoding="utf-8")
        g = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
        self.g = g
        for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "start"]):
            subprocess.run(g + args, cwd=self.repo, check=True, capture_output=True)
        self.fail_render = False
        real_run = subprocess.run

        def script(cmd, **kw):
            if cmd[0] == "git":
                return real_run(g + list(cmd[1:]), **kw)
            if Path(cmd[-1]).name == "render_share_card.py":
                (self.repo / "design" / "project-card.png").unlink()
                self.page.write_text(PAGE.format("2026-12-01"), encoding="utf-8")
                (self.repo / "docs" / "img" / "share-card.png").write_text("new\n", encoding="utf-8")
                if self.fail_render:
                    return subprocess.CompletedProcess(cmd, 1, "", "boom")
                (self.repo / "design" / "project-card.png").write_text("new\n", encoding="utf-8")
            else:
                (self.repo / "design" / "project-card.svg").write_text("new\n", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        for name, value in [("ROOT", self.repo), ("CARD_PAGE", self.page), ("LOOP_RUNNING", self.repo / "RUNNING"),
                            ("log", lambda m: None)]:
            p = mock.patch.object(run, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(run.subprocess, "run", script)
        p.start()
        self.addCleanup(p.stop)

    def git_out(self, *args):
        return subprocess.run(self.g + list(args), cwd=self.repo, check=True, capture_output=True,
                              text=True).stdout.strip()

    def test_committed_so_the_deploy_sees_docs_changed(self):
        before = self.git_out("rev-parse", "HEAD:docs")
        self.assertTrue(run.redraw_card("2026-12-01"))
        self.assertNotEqual(self.git_out("rev-parse", "HEAD:docs"), before)
        self.assertEqual(self.git_out("status", "--porcelain"), "")
        self.assertEqual(self.git_out("log", "-1", "--format=%s"), "Share card: 2026-12-01")

    def test_a_failed_render_leaves_the_checkout_as_it_was(self):
        self.fail_render = True
        head = self.git_out("rev-parse", "HEAD")
        self.assertFalse(run.redraw_card("2026-12-01"))
        self.assertEqual(self.git_out("rev-parse", "HEAD"), head)
        self.assertEqual(self.git_out("status", "--porcelain"), "")
        self.assertIn("?v=2026-11-24", self.page.read_text(encoding="utf-8"))


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
