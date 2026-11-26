"""world_day: the delta form on the world's WREC files, and a rectangle city's pseudo part mapped to its cell."""
import json
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "stream"))
import placesets as P  # noqa: E402
import world_day as WD  # noqa: E402
import world_state as WS  # noqa: E402


def rec(key, quest, lat=10.0, lon=10.0, flags=1, kind=0, due=0, place=0):
    r = np.zeros(1, P.WREC)
    r["key"], r["quest"], r["lat"], r["lon"] = key, quest, int(lat * 1e7), int(lon * 1e7)
    r["flags"], r["kind"], r["due"], r["place"] = flags, kind, due, place
    return r


class DeltaTest(unittest.TestCase):
    def world(self, d: Path, rows_by_file):
        files = []
        for k, (fid, rows) in enumerate(rows_by_file.items()):
            (d / "files" / fid).mkdir(parents=True)
            r = np.sort(np.concatenate(rows) if rows else np.zeros(0, P.WREC), order=WS.ORDER)
            WS.write_rows(d / "files" / fid / WS.WORLD_BIN, r)
            files.append({"id": fid, "rect": [k * 20.0, 0.0, k * 20.0 + 20.0, 20.0]})
        (d / "plan.json").write_text(json.dumps({"files": files}))
        return files

    def rows(self, d, fid):
        return np.fromfile(d / "files" / fid / WS.WORLD_BIN, P.WREC)

    def test_delta_forms(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            files = self.world(d, {"a": [rec(4, 1), rec(8, 1), rec(12, 1)], "b": [rec(16, 1, lat=25)]})
            # 4: unchanged by the recount; 8: removed; 12: changed (moved), held; 20: added; 24: changed, not held
            old = np.concatenate([rec(4, 1), rec(8, 1), rec(12, 1), rec(24, 1)])
            new = np.concatenate([rec(4, 1), rec(12, 1, lat=11), rec(20, 1, lat=26), rec(24, 1, lat=12)])
            added = defaultdict(set)
            st = WD.delta_w(d, old, new, files, added)
            a, b = self.rows(d, "a"), self.rows(d, "b")
            self.assertEqual(sorted(a["key"].tolist()), [4, 12])
            self.assertEqual(int(a[a["key"] == 12]["lat"][0]), int(11e7))
            self.assertEqual(sorted(b["key"].tolist()), [16, 20])  # 20 routed by its position to file b
            self.assertEqual(st["changed, the state lacked it (kept out)"], 1)
            self.assertEqual(st["removed"], 1)
            self.assertIn(20 * 1024 + 1, added["b"])

    def test_place_change_alone_is_applied(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            files = self.world(d, {"a": [rec(4, 1, place=1)]})
            st = WD.delta_w(d, rec(4, 1, place=1), rec(4, 1, place=2), files, defaultdict(set))
            self.assertEqual(int(self.rows(d, "a")["place"][0]), 2)
            self.assertEqual(st["changed"], 1)


class RectToCellTest(unittest.TestCase):
    def test_pseudo_part(self):
        with tempfile.TemporaryDirectory() as t:
            sets = P.PlaceSets(Path(t) / "place-sets.json")
            s1 = sets.intern(["city:f0c1-3", "abc"])
            s2 = sets.intern(["abc"])
            want = sets.intern(["city:f0c1", "abc"])
            rows = np.concatenate([rec(4, 1, place=s1), rec(8, 1, place=s2), rec(12, 1, place=0)])
            out = WD.rect_to_cell(rows, sets)
            self.assertEqual(out["place"].tolist(), [want, s2, 0])

    def test_rect_groups(self):
        def city(cid, s, w, n, e):
            return {"id": cid, "box": [s, w, n, e]}
        with tempfile.TemporaryDirectory() as t:
            cs = [city("f10c0-0", 50, 10, 50.01, 10.01), city("f2c3-0", 50, 10, 50.01, 10.01),
                  city("f2c3-1", 50, 11, 50.01, 11.01), city("f2c4-0", 50, 12, 50.01, 12.01)]
            src = Path(t) / "cities.json"
            src.write_text(json.dumps({"cities": cs}))
            # per plan file, in plan-file order (f2 before f10), each file's cities in their order
            gs = WD.rect_groups(src, Path(t) / "g")
            self.assertEqual([g for g, _ in gs], ["f2", "f10"])
            got = [[c["id"] for c in json.loads(p.read_text())["cities"]] for _, p in gs]
            self.assertEqual(got, [["f2c3-0", "f2c3-1", "f2c4-0"], ["f10c0-0"]])
            # a rectangle of about 1.1 x 0.7 km padded by 300 m is about 1.7 x 1.3 km: two fit under 5 km2, not three
            a = WD.padded_km2([50, 10, 50.01, 10.01])
            self.assertAlmostEqual(a, (1.1132 + 0.6) * (0.7155 + 0.6), delta=0.01)
            gs = WD.rect_groups(src, Path(t) / "h", cap_km2=5)
            self.assertEqual([g for g, _ in gs], ["f2-0", "f2-1", "f10"])
            got = [[c["id"] for c in json.loads(p.read_text())["cities"]] for _, p in gs]
            self.assertEqual(got, [["f2c3-0", "f2c3-1"], ["f2c4-0"], ["f10c0-0"]])


def poly(w, s, e, n):
    return f"box\n1\n   {w}   {s}\n   {e}   {s}\n   {e}   {n}\n   {w}   {n}\n   {w}   {s}\nEND\nEND\n"


NOTES_DUMP = """<?xml version="1.0" encoding="UTF-8"?>
<osm-notes>
<note id="1" lat="43.5" lon="-79.5" created_at="2020-01-01T00:00:00Z">
  <comment action="opened" timestamp="2020-01-01T00:00:00Z" uid="10" user="a">in file a and region west</comment>
</note>
<note id="2" lat="43.5" lon="-78.5" created_at="2021-01-01T00:00:00Z">
  <comment action="opened" timestamp="2021-01-01T00:00:00Z">in file b and region east</comment>
  <comment action="closed" timestamp="2026-11-20T00:00:00Z" uid="11" user="b"/>
</note>
<note id="3" lat="45.5" lon="-78.5" created_at="2022-01-01T00:00:00Z">
  <comment action="opened" timestamp="2022-01-01T00:00:00Z" uid="12" user="c">in region east's box only</comment>
</note>
</osm-notes>
"""


class RefreshNotesTest(unittest.TestCase):
    """the gate's notes clips cut in the refresh's own pass over the dump: the bytes world_gate would cut"""

    def setUp(self):
        import bz2
        from unittest import mock
        import world_gate as WG
        self.WG = WG
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        t = Path(self.t.name)
        (t / "notes").mkdir()
        self.dump = t / "notes" / "planet-notes-261125.osn.bz2"
        self.dump.write_bytes(bz2.compress(NOTES_DUMP.encode("utf-8")))
        for rid, box in (("west", (-80, 43, -79, 44)), ("east", (-79, 43, -78, 44))):
            (t / f"{rid}.poly").write_text(poly(*box), encoding="utf-8", newline="\n")
        self.regions = [{"id": "west", "poly": str(t / "west.poly")}, {"id": "east", "poly": str(t / "east.poly")}]
        boxes = {"west": [], "east": [[-79.0, 45.0, -78.0, 46.0]]}
        for target, name, value in ((WG.run, "note_boxes", lambda r: boxes[r["id"]]), (WG.run, "OSM_DATA_DIR", t)):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)

    def world(self, name):
        w = Path(self.t.name) / name
        files = []
        for fid, box in (("a", (-80, 43, -79, 44)), ("b", (-79, 43, -78, 44))):
            d = w / "files" / fid
            d.mkdir(parents=True)
            (d / "bbox.poly").write_text(poly(*box), encoding="utf-8", newline="\n")
            (d / "notes.jsonl").write_text('{"source": "planet-notes-261101.osn.bz2", "until": "2026-11-01T00:00:00Z"}\n',
                                           encoding="utf-8", newline="\n")
            files.append({"id": fid})
        (w / "plan.json").write_text(json.dumps({"files": files}), encoding="utf-8")
        (w / "gate-notes").mkdir()
        (w / "gate-notes" / "gone.jsonl").write_text('{"source": "planet-notes-261101.osn.bz2"}\n', encoding="utf-8")
        return w

    def tree(self, w):
        return {p.relative_to(w).as_posix(): p.read_bytes() for p in sorted(w.rglob("*")) if p.is_file()}

    def test_the_gates_clips_from_the_refresh_are_the_gates_own(self):
        from unittest import mock
        WG = self.WG
        said = []
        w1, w2 = self.world("with"), self.world("without")
        WD.refresh_notes(w1, self.dump, said.append, WG.gate_clips(w1, self.regions))
        WD.refresh_notes(w2, self.dump, said.append)                    # as before: the gate cuts its own
        self.assertEqual(sorted(p.name for p in (w1 / "gate-notes").iterdir()), ["east.jsonl", "west.jsonl"])
        self.assertEqual(list((w2 / "gate-notes").iterdir()), [])       # the old clips gone, either way
        with mock.patch.object(WG.subprocess, "run", side_effect=AssertionError("the dump read a second time")):
            got = WG.gate_notes(w1, self.regions, said.append)
        self.assertEqual(sorted(got), ["east", "west"])
        WG.gate_notes(w2, self.regions, said.append)
        a, b = self.tree(w1), self.tree(w2)
        self.assertEqual(sorted(a), sorted(b))
        self.assertEqual(sorted(a), ["files/a/bbox.poly", "files/a/notes.jsonl", "files/b/bbox.poly",
                                     "files/b/notes.jsonl", "gate-notes/east.jsonl", "gate-notes/west.jsonl",
                                     "notes-all.jsonl", "plan.json"])
        for name in a:
            self.assertEqual(a[name], b[name], name)
        east = (w1 / "gate-notes" / "east.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(l)["id"] for l in east[1:]], [2, 3])   # the poly's note and the box's
        self.assertEqual(json.loads(east[0])["source"], self.dump.name)
        # a clip of another dump than the world's (a refresh that stopped half way) is cut again by the gate
        (w1 / "gate-notes" / "west.jsonl").write_text('{"source": "planet-notes-261101.osn.bz2"}\n', encoding="utf-8")
        WG.gate_notes(w1, self.regions, said.append)
        self.assertEqual((w1 / "gate-notes" / "west.jsonl").read_bytes(), b["gate-notes/west.jsonl"])


if __name__ == "__main__":
    unittest.main()
