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


if __name__ == "__main__":
    unittest.main()
