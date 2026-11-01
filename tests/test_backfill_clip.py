"""backfill_history: regions counted from an osm-extracts clip read the clip's history cut and share each
month's slice. Run: python -m unittest"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import run  # noqa: E402
import backfill_history as bh  # noqa: E402

REGIONS = [{"id": "eu-a", "timeZone": "Europe/Berlin", "extract": "eu", "poly": "config/eu-a.poly"},
           {"id": "eu-b", "timeZone": "Europe/London", "extract": "eu", "poly": "config/eu-b.poly"},
           {"id": "berlin", "timeZone": "Europe/Berlin", "poly": "config/berlin.poly"}]


class ClipRegionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        store = Path(self.tmp.name) / "store"
        (store / "eu").mkdir(parents=True)
        (store / "eu" / "clip.json").write_text("{}")
        self.patches = [mock.patch.object(run, "regions", return_value=REGIONS),
                        mock.patch.object(run, "OSM_DATA_DIR", store),
                        mock.patch.object(run, "ARCHIVE_DIR", Path(self.tmp.name) / "archive"),
                        mock.patch.object(bh, "BACKFILL", Path(self.tmp.name) / "backfill"),
                        mock.patch.object(bh, "PLANET", "history-261029")]
        for p in self.patches:
            p.start()
        self.store = store

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_a_clip_region_reads_the_clips_history_cut(self):
        a, b, berlin = bh.Region("eu-a"), bh.Region("eu-b"), bh.Region("berlin")
        self.assertTrue(a.on_clip)
        self.assertEqual(a.history, self.store / "eu" / "eu-history-261029.osh.pbf")
        self.assertEqual(a.history_meta, self.store / "eu" / "eu-history-261029.meta.json")  # osm-extracts' name
        self.assertEqual(a.history, b.history)
        self.assertEqual(a.slices, b.slices)
        self.assertFalse(berlin.on_clip)
        self.assertEqual(berlin.history, self.store / "berlin-history" / "berlin-history-261029.osh.pbf")
        self.assertEqual(berlin.slices, berlin.backfill)

    def test_clip_regions_share_each_slice_and_delete_it_once(self):
        regs = [bh.Region("eu-a"), bh.Region("eu-b")]
        cuts, counted, deleted = [], [], []

        def slice_at(r, t):
            pbf = mock.MagicMock()
            pbf.unlink.side_effect = lambda: deleted.append(t.date().isoformat())
            if not cuts or cuts[-1] != t:
                cuts.append(t)
            return pbf, Path("meta.json")

        def count(r, pbf, meta, out):
            counted.append(r.id)
            return Path("x.json")

        with mock.patch.object(bh, "slice_at", side_effect=slice_at), mock.patch.object(bh, "count", side_effect=count):
            bh.months(regs, "2017-01", "2019-01", 12, keep=False)
        self.assertEqual(len(cuts), 3)
        self.assertEqual(counted, ["eu-a", "eu-b"] * 3)
        self.assertEqual(deleted, ["2017-01-01", "2018-01-01", "2019-01-01"])

    def test_clip_does_not_cut_a_clip_region(self):
        with self.assertRaises(SystemExit) as e:
            bh.clip([bh.Region("eu-a")])
        self.assertIn("osm_extracts.py recut eu", str(e.exception))


if __name__ == "__main__":
    unittest.main()
