"""run.py regions: a region's extract is separate from its id. Run: python -m unittest"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run  # noqa: E402

EAST = {"id": "canada-east", "timeZone": "America/Toronto", "extract": "canada",
        "url": "https://download.geofabrik.de/north-america/canada-latest.osm.pbf"}
WEST = {"id": "canada-west", "timeZone": "America/Vancouver", "extract": "canada",
        "url": "https://download.geofabrik.de/north-america/canada-latest.osm.pbf"}


class RegionExtractTest(unittest.TestCase):
    def test_todays_regions_fetch_their_id_once_each(self):
        regs = run.regions()
        self.assertEqual(run.extract_fetches(regs), [(r["id"], None) for r in regs])
        self.assertEqual([run.region_extract(r) for r in regs], [r["id"] for r in regs])

    def test_regions_sharing_an_extract_fetch_it_once(self):
        regs = [{"id": "ontario"}, EAST, WEST, {"id": "berlin"}]
        self.assertEqual(run.extract_fetches(regs), [("ontario", None), ("canada", EAST["url"]), ("berlin", None)])

    def test_regions_disagreeing_on_the_url_fail(self):
        with self.assertRaises(ValueError):
            run.extract_fetches([EAST, {**WEST, "url": "https://example.org/other.osm.pbf"}])

    def test_download_passes_url_only_when_given(self):
        calls = []
        with mock.patch.object(run, "regions", return_value=[{"id": "ontario"}, EAST, WEST]), \
                mock.patch.object(run.subprocess, "run", side_effect=lambda cmd, **kw: calls.append(cmd[2:])):
            run.download()
        self.assertEqual(calls, [["fetch", "ontario"], ["fetch", "canada", "--url", EAST["url"]], ["fetch", "notes"]])


class StoreFolderTest(unittest.TestCase):
    def setUp(self):
        self.store = Path(tempfile.mkdtemp())
        d = self.store / "canada"
        d.mkdir()
        for day in ("2026-10-20", "2026-10-21"):
            (d / f"canada-{day}.osm.pbf").write_bytes(b"")
            (d / f"canada-{day}.meta.json").write_text(json.dumps({"sha256": day}), encoding="utf-8")
        (d / "canada-latest.osm.pbf").write_bytes(b"")
        (d / "latest.json").write_text(json.dumps({"file": "canada-2026-10-21.osm.pbf"}), encoding="utf-8")
        self.patch = mock.patch.object(run, "OSM_DATA_DIR", self.store)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.store)

    def test_both_regions_read_the_shared_folder(self):
        for r in (EAST, WEST):
            self.assertEqual(run.latest_extract(r)[0], self.store / "canada" / "canada-2026-10-21.osm.pbf")
            self.assertEqual([p.name for p, _ in run.dated_extracts(r)],
                             ["canada-2026-10-20.osm.pbf", "canada-2026-10-21.osm.pbf"])

    def test_without_extract_key_the_id_is_the_folder(self):
        with self.assertRaises(FileNotFoundError):
            run.latest_extract({"id": "canada-east"})
        self.assertEqual(len(run.dated_extracts({"id": "canada"})), 2)


class NotesClipTest(unittest.TestCase):
    """run.notes_clip: the first region to need a clip of a dump makes every missing one in one pass."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "store" / "notes").mkdir(parents=True)
        (self.tmp / "store" / "notes" / "latest.json").write_text(
            json.dumps({"file": "planet-notes-261024.osn.bz2"}), encoding="utf-8")
        self.notes = self.tmp / "notes"
        self.notes.mkdir()
        self.regs = [{"id": "ontario", "poly": "config/ontario.poly"},
                     {"id": "new-brunswick", "poly": "config/new-brunswick.poly"},
                     {"id": "brunswick", "poly": "config/new-brunswick.poly"}]
        self.patches = [mock.patch.object(run, "OSM_DATA_DIR", self.tmp / "store"),
                        mock.patch.object(run, "NOTES_DIR", self.notes),
                        mock.patch.object(run, "regions", return_value=self.regs),
                        mock.patch.object(run, "note_boxes", return_value=[[0, 0, 1, 1]])]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        shutil.rmtree(self.tmp)

    def fake_clip(self, cmd, **kw):
        cfg = json.loads(Path(cmd[cmd.index("--config") + 1]).read_text(encoding="utf-8"))
        self.calls.append([Path(c["out"]).name for c in cfg["clips"]])
        for c in cfg["clips"]:
            Path(c["out"]).write_text("{}\n", encoding="utf-8")

    def test_one_pass_for_all_missing_clips(self):
        (self.notes / "planet-notes-261024-ontario.jsonl").write_text("{}\n", encoding="utf-8")
        (self.notes / "planet-notes-261023-new-brunswick.jsonl").write_text("{}\n", encoding="utf-8")
        self.calls = []
        with mock.patch.object(run.subprocess, "run", side_effect=self.fake_clip):
            clip = run.notes_clip(self.regs[2])
            for r in self.regs:
                run.notes_clip(r)
        self.assertEqual(clip.name, "planet-notes-261024-brunswick.jsonl")
        self.assertEqual(self.calls, [["planet-notes-261024-brunswick.jsonl", "planet-notes-261024-new-brunswick.jsonl"]])
        # the config is gone, and the old dump's clip went with its own region only
        self.assertEqual(sorted(p.name for p in self.notes.iterdir()),
                         ["planet-notes-261024-brunswick.jsonl", "planet-notes-261024-new-brunswick.jsonl",
                          "planet-notes-261024-ontario.jsonl"])

    def test_no_dump_no_clip(self):
        (self.tmp / "store" / "notes" / "latest.json").unlink()
        self.assertIsNone(run.notes_clip(self.regs[0]))


class NoteBoxesTest(unittest.TestCase):
    def test_every_city_bbox_is_inside_its_padded_box(self):
        cities = run.read_json(run.CITIES_CONFIG)["cities"]
        for r in run.regions():
            boxes = run.note_boxes(r)
            mine = [c for c in cities if c["region"] == r["id"]]
            self.assertEqual(len(boxes), len(mine))
            for c, (w, s, e, n) in zip(mine, boxes):
                b = run.read_json(run.ROOT / c["boundary"])["bounds"]
                self.assertTrue(w < b["minlon"] and s < b["minlat"] and e > b["maxlon"] and n > b["maxlat"], c["id"])
                self.assertAlmostEqual(b["minlat"] - s, 1000 / 111_320, places=6)


if __name__ == "__main__":
    unittest.main()
