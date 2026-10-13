"""clip_notes: planet notes dump -> bbox clip as JSONL. Run: python -m unittest"""
import bz2
import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import clip_notes  # noqa: E402

POLY = """box
1
   -80.0   43.0
   -79.0   43.0
   -79.0   44.0
   -80.0   44.0
   -80.0   43.0
END
!1
   -79.6   43.4
   -79.4   43.4
   -79.4   43.6
   -79.6   43.4
END
END
"""

# Two bz2 streams back to back, as in the real (pbzip2-style) dump; the split falls inside a note.
DUMP_A = """<?xml version="1.0" encoding="UTF-8"?>
<osm-notes>
<note id="3" lat="43.5000000" lon="-79.5000000" created_at="2020-01-01T00:00:00Z" closed_at="2020-02-01T00:00:00Z">
  <comment action="opened" timestamp="2020-01-01T00:00:00Z" uid="10" user="a">Fish &amp; chips &lt;here&gt; "café"</comment>
  <comment action="closed" timestamp="2020-02-01T00:00:00Z" uid="11" user="b"/>
</note>
<note id="1" lat="10.0" lon="-79.5" created_at="2019-01-01T00:00:00Z">
  <comment action="opened" timestamp="2026-09-30T23:59:59Z" uid="12" user="c">outside, but the newest comment</comment>
</note>
<note id="2" lat="43.0" lon="-79.0" created_at="2021-05-05T05:05:05Z">
  <comment action="opened" timestamp="2021-05-05T05:05:05Z">anonymous
second line
  third</comment>
  <comment action="commented" timestamp="2021-06-01T00:00:00Z" uid="13" user="d"></comment>
"""
DUMP_B = """  <comment action="reopened" timestamp="2021-07-01T00:00:00Z" uid="14" user="e"/>
</note>
<note id="4" lat="44.0000001" lon="-79.5" created_at="2022-01-01T00:00:00Z">
  <comment action="opened" timestamp="2022-01-01T00:00:00Z" uid="15" user="f">just north</comment>
</note>
</osm-notes>
"""

EXPECTED = [
    '{"schema":1,"source":"planet-notes-261011.osn.bz2","sha256":"SHA","until":"2026-09-30T23:59:59Z",'
    '"bbox":[-80.0,43.0,-79.0,44.0],"poly":"box.poly","notes":2}',
    '{"id":2,"lat":"43.0","lon":"-79.0","created":"2021-05-05T05:05:05Z","comments":['
    '{"action":"opened","timestamp":"2021-05-05T05:05:05Z","text":"anonymous\\nsecond line\\n  third"},'
    '{"action":"commented","timestamp":"2021-06-01T00:00:00Z","uid":13,"text":""},'
    '{"action":"reopened","timestamp":"2021-07-01T00:00:00Z","uid":14,"text":""}]}',
    '{"id":3,"lat":"43.5000000","lon":"-79.5000000","created":"2020-01-01T00:00:00Z","comments":['
    '{"action":"opened","timestamp":"2020-01-01T00:00:00Z","uid":10,"text":"Fish & chips <here> \\"café\\""},'
    '{"action":"closed","timestamp":"2020-02-01T00:00:00Z","uid":11,"text":""}]}',
]


class ClipNotesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dump = self.tmp / "planet-notes-261011.osn.bz2"
        self.dump.write_bytes(bz2.compress(DUMP_A.encode("utf-8")) + bz2.compress(DUMP_B.encode("utf-8")))
        self.poly = self.tmp / "box.poly"
        self.poly.write_text(POLY, encoding="utf-8")
        self.out = self.tmp / "out" / "clip.jsonl"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_output_exactly(self):
        clip_notes.main([str(self.dump), "--poly", str(self.poly), "--out", str(self.out)])
        sha = hashlib.sha256(self.dump.read_bytes()).hexdigest()
        want = "\n".join(EXPECTED).replace('"SHA"', f'"{sha}"') + "\n"
        self.assertEqual(self.out.read_bytes().decode("utf-8"), want)
        self.assertEqual([p.name for p in self.out.parent.iterdir()], ["clip.jsonl"])

    def test_small_blocks_give_the_same_output(self):
        clip_notes.main([str(self.dump), "--poly", str(self.poly), "--out", str(self.out)])
        whole = self.out.read_bytes()
        saved = clip_notes.BLOCK_SIZE
        try:
            for size in (1, 50, 300):
                clip_notes.BLOCK_SIZE = size
                clip_notes.main([str(self.dump), "--poly", str(self.poly), "--out", str(self.out)])
                self.assertEqual(self.out.read_bytes(), whole, size)
        finally:
            clip_notes.BLOCK_SIZE = saved

    def test_poly_bbox_ignores_holes(self):
        self.assertEqual(clip_notes.poly_bbox(self.poly), (-80.0, 43.0, -79.0, 44.0))

    def test_truncated_dump_fails(self):
        self.dump.write_bytes(bz2.compress(DUMP_A.encode("utf-8"))[:-20])
        with self.assertRaises(EOFError):
            clip_notes.main([str(self.dump), "--poly", str(self.poly), "--out", str(self.out)])
        self.assertFalse(self.out.exists())

    def test_unexpected_attribute_order_fails(self):
        self.dump.write_bytes(bz2.compress(DUMP_A.replace('id="1" lat="10.0"', 'lat="10.0" id="1"').encode("utf-8")
                                           + DUMP_B.encode("utf-8")))
        with self.assertRaises(ValueError):
            clip_notes.main([str(self.dump), "--poly", str(self.poly), "--out", str(self.out)])


if __name__ == "__main__":
    unittest.main()
