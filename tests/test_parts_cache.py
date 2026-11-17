"""placesets.parts_cache: a world's parts cache is used only while its stamp matches the world's places.json."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "stream"))
import placesets as P  # noqa: E402


class PartsCacheTest(unittest.TestCase):
    def test_current_stale_and_missing(self):
        with tempfile.TemporaryDirectory() as t:
            w = Path(t)
            self.assertIsNone(P.parts_cache(w))  # no cache
            (w / "places.json").write_text("{}", encoding="utf-8")
            (w / P.PARTS_CACHE).write_bytes(b"OQPC")
            self.assertIsNone(P.parts_cache(w))  # no sidecar
            side = w / (P.PARTS_CACHE + ".json")
            side.write_text(json.dumps({"stamp": P.places_stamp(w)}), encoding="utf-8")
            self.assertEqual(P.parts_cache(w), w / P.PARTS_CACHE)
            # places rebuilt after the cache: stale
            (w / "places.json").write_text('{"a": 1}', encoding="utf-8")
            st = (w / "places.json").stat()
            os.utime(w / "places.json", ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
            self.assertIsNone(P.parts_cache(w))


if __name__ == "__main__":
    unittest.main()
