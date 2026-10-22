"""run.py check-release: the pure parts (no network, no gh)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run  # noqa: E402

RELEASES = [
    {"version": "v63.3", "date": "2026-07-28"},
    {"version": "v63.4", "date": "2026-07-28"},
    {"version": "v64.0", "date": "2026-10-19"},
]


class ReleaseCheckTest(unittest.TestCase):
    def test_version_tuple(self):
        self.assertEqual(run.version_tuple("v64.0"), (64, 0))
        self.assertEqual(run.version_tuple("63.4"), (63, 4))
        self.assertEqual(run.version_tuple("v63.10.json"), (63, 10))
        self.assertEqual(run.version_tuple("notes.json"), ())
        self.assertLess(run.version_tuple("v63.4"), run.version_tuple("v64.0"))
        self.assertLess(run.version_tuple("v63.4"), run.version_tuple("v63.10"))

    def test_newer_release(self):
        self.assertEqual(run.newer_release("v63.4", RELEASES)["version"], "v64.0")
        self.assertIsNone(run.newer_release("v64.0", RELEASES))
        self.assertIsNone(run.newer_release("v64.1", RELEASES))
        # the newest of several newer ones
        more = RELEASES + [{"version": "v64.1", "date": "2026-11-01"}]
        self.assertEqual(run.newer_release("v63.4", more)["version"], "v64.1")

    def test_pinned_sc_tag(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "SC-VERSION.txt"
            p.write_text("# header\ntag=v64.0\ncommit=abc\n", encoding="utf-8")
            self.assertEqual(run.pinned_sc_tag(p), "v64.0")
        self.assertRegex(run.pinned_sc_tag(), r"^v\d+\.\d+$")  # the repo's own file

    def test_issue_title(self):
        self.assertEqual(run.repin_issue_title("v64.0"), "Repin to StreetComplete v64.0")


if __name__ == "__main__":
    unittest.main()
