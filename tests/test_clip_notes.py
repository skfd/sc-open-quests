"""clip_notes: planet notes dump -> poly clips as JSONL, one pass for many. Run: python -m unittest"""
import bz2
import hashlib
import json
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


def poly(name: str, *sections: tuple[str, list[tuple[float, float]]]) -> str:
    body = "".join(f"{sec}\n" + "".join(f"   {x}   {y}\n" for x, y in pts) + "END\n" for sec, pts in sections)
    return f"{name}\n{body}END\n"


def dump_of(points: dict[int, tuple[float, float]]) -> bytes:
    notes = "".join(f'<note id="{i}" lat="{lat}" lon="{lon}" created_at="2020-01-01T00:00:00Z">\n'
                    f'  <comment action="opened" timestamp="2020-01-01T00:00:00Z" uid="1" user="u">n{i}</comment>\n'
                    f'</note>\n' for i, (lon, lat) in sorted(points.items()))
    return bz2.compress(f'<?xml version="1.0" encoding="UTF-8"?>\n<osm-notes>\n{notes}</osm-notes>\n'.encode())


class PolygonClipTest(unittest.TestCase):
    """The real polygon test, boxes, several clips in one pass, and the antimeridian."""

    # an L: the box (0,0)-(4,4) without its north-east quarter (2,2)-(4,4), with a hole (0.5,0.5)-(1.5,1.5)
    L = poly("ell", ("1", [(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4), (0, 0)]),
             ("!hole", [(0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5), (0.5, 0.5)]))
    POINTS = {1: (1, 3), 2: (3, 3), 3: (1, 1), 4: (3, 1), 5: (0.5, 1), 6: (5, 5), 7: (3, 4), 8: (-1, 1)}

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dump = self.tmp / "planet-notes-261024.osn.bz2"
        self.dump.write_bytes(dump_of(self.POINTS))
        (self.tmp / "ell.poly").write_text(self.L, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def read(self, out: Path) -> tuple[dict, list[int]]:
        lines = out.read_text(encoding="utf-8").splitlines()
        return json.loads(lines[0]), [json.loads(ln)["id"] for ln in lines[1:]]

    def test_inside_the_polygon_not_its_bbox(self):
        out = self.tmp / "ell.jsonl"
        clip_notes.main([str(self.dump), "--poly", str(self.tmp / "ell.poly"), "--out", str(out)])
        head, ids = self.read(out)
        # 2 (the missing quarter) and 3 (inside the hole) are in the bbox but out; 5 is on the hole's edge
        self.assertEqual(ids, [1, 4, 5])
        self.assertEqual(head["bbox"], [0.0, 0.0, 4.0, 4.0])
        self.assertEqual(head["notes"], 3)
        self.assertNotIn("boxes", head)

    def test_boxes_keep_notes_outside_the_poly(self):
        cfg = self.tmp / "clips.json"
        out = self.tmp / "ell.jsonl"
        cfg.write_text(json.dumps({"clips": [{"poly": str(self.tmp / "ell.poly"), "out": str(out),
                                              "boxes": [[2.5, 2.5, 3.5, 4.0], [-2, 0.9, -0.5, 1.1]]}]}), encoding="utf-8")
        clip_notes.main([str(self.dump), "--config", str(cfg)])
        head, ids = self.read(out)
        self.assertEqual(ids, [1, 2, 4, 5, 7, 8])
        self.assertEqual(head["boxes"], [[2.5, 2.5, 3.5, 4.0], [-2.0, 0.9, -0.5, 1.1]])

    def test_one_pass_equals_one_run_each(self):
        (self.tmp / "ne.poly").write_text(poly("ne", ("1", [(2, 2), (6, 2), (6, 6), (2, 6), (2, 2)])),
                                          encoding="utf-8")
        alone = {}
        for name in ("ell", "ne"):
            out = self.tmp / "alone" / f"{name}.jsonl"
            clip_notes.main([str(self.dump), "--poly", str(self.tmp / f"{name}.poly"), "--out", str(out)])
            alone[name] = out.read_bytes()
        clip_notes.main([str(self.dump), "--poly", str(self.tmp / "ell.poly"), "--out", str(self.tmp / "both" / "ell.jsonl"),
                         "--poly", str(self.tmp / "ne.poly"), "--out", str(self.tmp / "both" / "ne.jsonl")])
        for name in ("ell", "ne"):
            self.assertEqual((self.tmp / "both" / f"{name}.jsonl").read_bytes(), alone[name], name)
        # 4 (3,1) is in ell only; 2, 6 and 7 in ne only (7 sits on ell's bbox, not on ell)
        self.assertEqual(self.read(self.tmp / "both" / "ne.jsonl")[1], [2, 6, 7])
        self.assertEqual(self.read(self.tmp / "both" / "ell.jsonl")[1], [1, 4, 5])

    def test_a_poly_or_out_without_its_pair_fails(self):
        with self.assertRaises(SystemExit):
            clip_notes.main([str(self.dump), "--poly", str(self.tmp / "ell.poly")])

    def test_antimeridian_either_way_it_is_written(self):
        points = {1: (179.5, -17), 2: (-179.5, -17), 3: (-179.5, -30), 4: (170, -17), 5: (0, -17), 6: (-176, -16)}
        self.dump.write_bytes(dump_of(points))
        jumping = [(175, -20), (-175, -20), (-175, -15), (175, -15), (175, -20)]
        unwrapped = [(175, -20), (185, -20), (185, -15), (175, -15), (175, -20)]
        for name, pts in (("jumping", jumping), ("unwrapped", unwrapped)):
            p = self.tmp / f"{name}.poly"
            p.write_text(poly(name, ("1", pts)), encoding="utf-8")
            out = self.tmp / f"{name}.jsonl"
            clip_notes.main([str(self.dump), "--poly", str(p), "--out", str(out)])
            head, ids = self.read(out)
            self.assertEqual(ids, [1, 2, 6], name)
            self.assertEqual(head["bbox"], [175.0, -20.0, 185.0, -15.0], name)

    def test_a_ring_around_the_pole(self):
        self.dump.write_bytes(dump_of({1: (10, 85), 2: (-170, 89), 3: (10, 75)}))
        p = self.tmp / "arctic.poly"
        p.write_text(poly("arctic", ("1", [(-180, 80), (-90, 80), (0, 80), (90, 80), (180, 80)])), encoding="utf-8")
        out = self.tmp / "arctic.jsonl"
        clip_notes.main([str(self.dump), "--poly", str(p), "--out", str(out)])
        self.assertEqual(self.read(out)[1], [1, 2])


if __name__ == "__main__":
    unittest.main()
