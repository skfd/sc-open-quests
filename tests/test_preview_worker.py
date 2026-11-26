"""The share-preview Worker (cloudflare/src/site.js): its own tests, which are node's, and its numbers
against a published site. Skipped where node is not on PATH."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "node is not on PATH")
class PreviewWorkerTest(unittest.TestCase):
    def node(self, *args: str) -> str:
        r = subprocess.run([NODE, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=100)
        self.assertEqual(0, r.returncode, (r.stdout + r.stderr)[-3000:])
        return r.stdout

    def test_the_workers_own_tests_pass(self):
        self.node("--test", "cloudflare/test/preview.test.mjs")

    def test_every_fixture_city_says_cities_jsons_number(self):
        # the same script holds the real site to it: node cloudflare/test/parity.mjs
        out = self.node("cloudflare/test/parity.mjs", "tests/fixtures")
        self.assertRegex(out, r"(\d+) of \1 links say")

    def test_the_page_carries_the_tags_the_worker_rewrites(self):
        head = (ROOT / "docs" / "index.html").read_text(encoding="utf-8").split("</head>")[0]
        for tag in ('<meta property="og:title"', '<meta property="og:description"', '<meta property="og:image"',
                    '<meta name="twitter:card"'):
            self.assertEqual(1, head.count(tag), tag)
        self.assertNotIn('property="og:url"', head)   # every view shares this file (the comment there)
        self.assertTrue((ROOT / "docs" / "img" / "share-card.png").exists())


if __name__ == "__main__":
    unittest.main()
