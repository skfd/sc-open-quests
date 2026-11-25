import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import world_publish as wp  # noqa: E402

MEASURES = ["open", "nodes", "ways", "relations", "agedOnly", "open05", "aged05", "open2", "aged2"]
QUESTS = ["OsmNoteQuestType", "AddBench", "AddLit"]
C, R, A, B, X = "aa0000000001", "bb0000000002", "cc0000000003", "cd0000000004", "dd0000000005"
E = "ee0000000006"


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), encoding="utf-8", newline="\n")


def name_layer(root: Path) -> Path:
    places = root / "places"
    write_json(places / "index.json", {"schema": 1, "overture": "test", "countries": [
        {"id": C, "cc": "DE", "en": "Testland", "bbox": [0, 0, 1, 1],
         "regions": [{"id": R, "name": "Region", "file": "de/r.json", "n": 3}]},
        {"id": None, "cc": "PS", "en": "Headless", "bbox": [0, 0, 1, 1],
         "regions": [{"id": "_", "name": "-", "file": "ps/_.json", "n": 1}]}]})
    write_json(places / "ps" / "_.json", {"schema": 1, "region": "_", "places": [
        [E, "Village", 5, -1, 0, 0, 1, 1, None, None]]})
    # rows: [id, name, st, parentIdx, xmin, ymin, xmax, ymax, en, counted]; A under the region, B under A
    write_json(places / "de" / "r.json", {"schema": 1, "region": R, "places": [
        [R, "Region", 2, -1, 0, 0, 1, 1, None, None],
        [A, "Town", 5, 0, 0, 0, 1, 1, None, None],
        [B, "Quarter", 8, 1, 0, 0, 1, 1, None, None]]})
    return places


def world_day(world: Path, day: str, rows: dict, compressed: bool, gate: str = "days", parts=None) -> None:
    """rows: (part, quest) -> (open, aged); X is counted but not in the name layer, `city:` a cell"""
    parts = parts or [C, R, A, B, X, E, "city:f0", "osm-town"]
    d = world / "counts" / day
    write_json(d / "counts.json", {"clock": day + "T00:00:00Z", "measures": MEASURES, "quests": QUESTS,
                                   "parts": parts})
    keys = sorted(rows)
    m = np.zeros((len(keys), 9), np.int64)
    for i, k in enumerate(keys):
        m[i, 0], m[i, 4] = rows[k]
        m[i, 1] = 99  # nodes: not published
    part = np.array([parts.index(p) for p, _ in keys], np.uint32)
    quest = np.array([QUESTS.index(q) for _, q in keys], np.uint16)
    (np.savez_compressed if compressed else np.savez)(d / "counts.npz", part=part, quest=quest, m=m)
    if gate == "seed":
        write_json(d / "gate1101.json", {"x": {}})
    elif gate == "days":
        write_json(world / "days" / day / "gate.json", {"day": day, "ok": True})
    elif gate == "failed":
        write_json(world / "days" / day / "gate.json", {"day": day, "ok": False})


DAYS = {
    "2026-10-30": {(A, "AddBench"): (5, 1), (B, "AddBench"): (2, 0), (C, "AddLit"): (7, 0),
                   ("city:f0", "AddBench"): (9, 9), (X, "AddBench"): (3, 0)},
    "2026-10-31": {(A, "AddBench"): (5, 1), (B, "AddBench"): (1, 0), (C, "AddLit"): (7, 0), (A, "AddLit"): (0, 0)},
    "2026-11-01": {(A, "AddBench"): (4, 2), (C, "AddLit"): (7, 0), (A, "OsmNoteQuestType"): (1, 0)},
    "2026-11-02": {(A, "AddBench"): (4, 2), (B, "AddBench"): (6, 0), (C, "AddLit"): (8, 1), (E, "AddLit"): (2, 0)},
    "2026-11-03": {(A, "AddBench"): (0, 0)},
}


class WorldCase(unittest.TestCase):
    """a small world of four gated days and a failed fifth, and a name layer for it"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.places = name_layer(root)
        self.world = root / "world"
        for i, (day, rows) in enumerate(DAYS.items()):
            gate = "seed" if i == 0 else ("failed" if day == "2026-11-03" else "days")
            world_day(self.world, day, rows, compressed=bool(i % 2), gate=gate)
        self.out, self.work = root / "out", root / "work"

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, through=None, out=None, work=None):
        return wp.build(self.world, out or self.out, work or self.work, self.places, "2026-10-30", through)

    def read(self, path, out=None):
        return json.loads(((out or self.out) / path).read_text(encoding="utf-8"))

    def tree(self, out=None):
        out = out or self.out
        return {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*.json")}


class WorldPublishTest(WorldCase):
    def test_layout_and_values(self):
        latest = self.build()
        self.assertEqual(latest["date"], "2026-11-02")  # 11-03's gate failed
        self.assertEqual((latest["first"], latest["back"]), ("2026-10-30", "2026-10-30"))
        self.assertEqual((latest["place"], latest["children"], latest["schema"]), ("place/", "children/", 2))
        self.assertNotIn("dates", latest)
        place = self.read("place/cc/cc0000000003.json")
        self.assertEqual((place["subtype"], place["first"]), ("locality", "2026-10-30"))
        self.assertNotIn("from", place)
        self.assertEqual(place["quests"]["AddBench"], [[0, 5, 1], [2, 4, 2]])
        self.assertEqual(place["quests"]["OsmNoteQuestType"], [[2, 1, 0], [3, 0, 0]])
        self.assertNotIn("AddLit", place["quests"])  # (0, 0) rows are not published
        self.assertFalse((self.out / "place/dd").exists())  # not in the name layer
        self.assertEqual(len(list((self.out / "place").glob("*/*.json"))), 5)
        # a country with no Overture id is addressed by its code, as the page's countryId does
        ps = self.read("children/ps/ps.json")
        self.assertEqual((ps["quests"], ps["places"]), (["AddLit"], {E: {"0": [2, 0, 0, 0]}}))
        # B's parent is A: A's children file holds B on the date and on `back` (here the first day)
        ca = self.read("children/cc/cc0000000003.json")
        self.assertEqual((ca["quests"], ca["places"]), (["AddBench"], {B: {"0": [6, 0, 2, 0]}}))
        world = self.read("children/world.json")
        self.assertEqual(world["places"][C], {"0": [8, 1, 7, 0]})
        self.assertEqual(self.read("children/aa/aa0000000001.json")["places"], {R: {}})
        self.assertEqual(wp.verify(self.world, self.out, self.work, self.places, sample=10), 0)

    def cities(self):
        ask = {"enabledInCountries": {"type": "AllCountries"}, "support": "full"}
        return wp.Cities([{"id": "town", "name": "Town", "countryCodes": ["DE"]}], {"town": [B, "ab0000000009"]},
                         [{"name": "AddBench", **ask}, {"name": "AddLit", **ask, "defaultDisabled": True},
                          {"name": "OsmNoteQuestType", **ask, "enabledInCountries": {"type": "NoCountriesExcept", "codes": ["CA"]}}])

    def town(self):
        """the same world with the town counted"""
        days = [{"AddBench": (5, 1), "AddLit": (4, 0)}, {"AddBench": (5, 1), "OsmNoteQuestType": (9, 0)},
                {"AddBench": (3, 0)}, {"AddLit": (2, 2)}]
        for i, ((day, rows), mine) in enumerate(zip(DAYS.items(), days)):
            world_day(self.world, day, {**rows, **{("osm-town", q): v for q, v in mine.items()}}, bool(i % 2),
                      gate="seed" if i == 0 else "days")
        return wp.build(self.world, self.out, self.work, self.places, "2026-10-30", None, self.cities())

    def test_cities(self):
        self.build()   # without them first, as the cache and the manifest were on 2026-11-25
        before = self.tree()
        latest = self.town()
        self.assertEqual((latest["city"], latest["cityParts"]), ("city/", "city-parts/"))
        town = self.read("city/town.json")
        self.assertEqual((town["id"], town["name"], town["first"]), ("town", "Town", "2026-10-30"))
        self.assertEqual(town["quests"], {"OsmNoteQuestType": [[1, 9, 0], [2, 0, 0]], "AddBench": [[0, 5, 1], [2, 3, 0], [3, 0, 0]],
                                          "AddLit": [[0, 4, 0], [1, 0, 0], [3, 2, 2]]})
        self.assertEqual(self.read("city-trends.json")["open"], {"town": [5, 5, 3, 0]})   # AddLit is off by default
        self.assertEqual(self.read("cities.json")["open"], {"town": 0})
        q = self.read("city-quests.json")
        self.assertEqual({q["quests"][int(i)]: v for i, v in q["places"]["town"].items()},
                         {"AddBench": [0, 0, 5, 1], "AddLit": [2, 2, 4, 0]})
        parts = self.read("city-parts/town.json")
        self.assertEqual((parts["noFile"], parts["places"]["ab0000000009"]), (["ab0000000009"], {}))
        self.assertEqual(parts["places"][B], {"0": [6, 0, 2, 0]})
        after = self.tree()
        self.assertEqual({k: v for k, v in after.items() if k in before and k != "latest.json"},
                         {k: v for k, v in before.items() if k != "latest.json"})   # the places' files stay as they were
        self.assertEqual(wp.verify(self.world, self.out, self.work, self.places, sample=10, cities=self.cities()), 0)

    def test_a_wrong_city_file_fails_the_check(self):
        self.town()
        f = self.out / "city" / "town.json"
        f.write_text(f.read_text(encoding="utf-8").replace("[0,5,1]", "[0,6,1]"), encoding="utf-8")
        self.assertEqual(wp.verify(self.world, self.out, self.work, self.places, sample=10, cities=self.cities()), 1)

    def test_a_city_the_world_does_not_count_stops_the_build(self):
        cities = self.cities()
        cities.keys["gone"] = wp.city_key("gone")
        with self.assertRaisesRegex(SystemExit, "gone"):
            wp.build(self.world, self.out, self.work, self.places, "2026-10-30", None, cities)

    def test_incremental_equals_whole(self):
        self.build(through="2026-11-01")
        self.build()
        root = Path(self.tmp.name)
        self.build(out=root / "out2", work=root / "work2")
        self.assertEqual(self.tree(), self.tree(root / "out2"))

    def test_a_newer_file_clipped_reads_as_the_older_day(self):
        # what the layout rests on: a place file built through D+1 and read with D's latest.json equals D's
        old = self.build(through="2026-11-01")
        def seen(p):   # a quest the file leaves out is 0, as the page reads it
            return {d: {q: v for q, v in row.items() if v != (0, 0)}
                    for d, row in wp.read_place(self.out, old, p).items()}
        before = {p: seen(p) for p in (C, R, A, B, E)}
        self.assertTrue(any(row for row in before[A].values()))
        self.build()
        for p, want in before.items():
            self.assertEqual(seen(p), want, p)

    def test_back_is_28_days_before(self):
        old = wp.WINDOW_DAYS
        wp.WINDOW_DAYS = 1
        try:
            latest = self.build()
        finally:
            wp.WINDOW_DAYS = old
        self.assertEqual(latest["back"], "2026-11-01")
        self.assertEqual(self.read("children/cc/cc0000000003.json")["places"], {B: {"0": [6, 0, 0, 0]}})
        ra = self.read("children/bb/bb0000000002.json")
        self.assertEqual(ra["quests"], ["OsmNoteQuestType", "AddBench"])  # the world's order
        self.assertEqual(ra["places"][A], {"0": [0, 0, 1, 0], "1": [4, 2, 4, 2]})
        self.assertEqual(wp.verify(self.world, self.out, self.work, self.places, sample=10), 0)

    def test_a_place_counted_later_says_from(self):
        world = Path(self.tmp.name) / "world2"
        for i, (day, rows) in enumerate(DAYS.items()):
            parts = [C, R, A, B, X, "city:f0", "osm-town"] + ([E] if day >= "2026-11-02" else [])
            world_day(world, day, {k: v for k, v in rows.items() if k[0] in parts}, compressed=False,
                      gate="seed" if i == 0 else "days", parts=parts)
        latest = wp.build(world, self.out, self.work, self.places, "2026-10-30", "2026-11-02")
        e = self.read("place/ee/ee0000000006.json")
        self.assertEqual((e["from"], e["quests"]), (3, {"AddLit": [[3, 2, 0]]}))
        self.assertEqual(list(wp.read_place(self.out, latest, E)), ["2026-11-02"])
        self.assertEqual(wp.verify(world, self.out, self.work, self.places, sample=10), 0)

    def test_only_changed_files_are_written_and_planned(self):
        self.build(through="2026-11-01")
        todo, gone, local, _ = wp.plan(self.out, self.work)
        self.assertEqual((len(todo), gone), (len(local["p"]) + len(local["c"]), []))  # an empty bucket: all
        wp.save_manifest(self.work / "bucket.json", local)   # as if uploaded
        self.build(through="2026-11-01")                      # the same day again: nothing
        self.assertEqual(wp.plan(self.out, self.work)[:2], ([], []))
        before = self.tree()
        stamps = {p: (self.out / p).stat().st_mtime_ns for p in before}
        self.build()                                          # a new day: exactly the files whose bytes differ
        after = self.tree()
        differ = {p for p in after if p != "latest.json" and before.get(p) != after[p]}
        todo, gone, _, _ = wp.plan(self.out, self.work)
        self.assertEqual({wp.rel(*x) for x in todo}, differ)
        self.assertEqual(gone, [])
        self.assertTrue(differ and len(differ) < len(after) - 1)   # some, not all
        for p in set(before) - differ - {"latest.json"}:
            self.assertEqual((self.out / p).stat().st_mtime_ns, stamps[p], p)   # not rewritten
        self.assertNotEqual(self.read("latest.json")["v"], json.loads(before["latest.json"])["v"])

    def test_a_place_no_longer_built_is_removed_and_planned_as_gone(self):
        self.build()
        wp.save_manifest(self.work / "bucket.json", wp.load_manifest(self.work / "local.json"))
        idx = json.loads((self.places / "index.json").read_text(encoding="utf-8"))
        idx["countries"] = idx["countries"][:1]   # the headless country leaves the name layer, and E with it
        write_json(self.places / "index.json", idx)
        self.build()
        self.assertFalse((self.out / "place/ee/ee0000000006.json").exists())
        self.assertFalse((self.out / "children/ps/ps.json").exists())
        self.assertEqual(wp.plan(self.out, self.work)[1], [("c", "ps"), ("p", E)])

    def test_decode(self):
        self.assertEqual(wp.decode([[1, 3, 1], [3, 0, 0]], 5), ([0, 3, 3, 0, 0], [0, 1, 1, 0, 0]))
        self.assertEqual(wp.decode([[1, 3, 1], [3, 0, 0]], 3), ([0, 3, 3], [0, 1, 1]))  # the clip


class UploadTest(WorldCase):
    """upload with rclone and the spend breaker stubbed: what runs, in which order, and what the manifest keeps"""

    def setUp(self):
        super().setUp()
        import cloud_publish
        import spend_breaker
        self.sb, self.cp = spend_breaker, cloud_publish
        self.saved = (spend_breaker.gate, wp.subprocess.run, wp.MAX_UPLOAD, wp.DAY_CAP, wp.BATCH,
                      cloud_publish.read_env, cloud_publish.rclone_env)
        cloud_publish.read_env = lambda *a, **k: {}
        cloud_publish.rclone_env = lambda env: {}
        self.asked = []
        spend_breaker.gate = lambda planned_class_a=0, strict=False, **k: self.asked.append((planned_class_a, strict))
        self.ran, self.fail_at = [], None

        def run(cmd, **k):
            files = []
            if "--files-from" in cmd:
                files = Path(cmd[cmd.index("--files-from") + 1]).read_text(encoding="utf-8").split()
            self.ran.append((cmd[1], files, cmd))
            rc = 1 if self.fail_at == len(self.ran) else 0
            return type("R", (), {"returncode": rc, "stderr": "boom" if rc else "", "stdout": ""})()
        wp.subprocess.run = run
        self.build()

    def tearDown(self):
        (self.sb.gate, wp.subprocess.run, wp.MAX_UPLOAD, wp.DAY_CAP, wp.BATCH,
         self.cp.read_env, self.cp.rclone_env) = self.saved
        super().tearDown()

    def all_files(self):
        return sorted(p for p in self.tree() if p != "latest.json")

    def test_uploads_in_batches_and_latest_json_last(self):
        wp.BATCH = 4
        self.assertEqual(wp.upload(self.out, self.work), 0)
        copies = [r for r in self.ran if r[0] == "copy"]
        self.assertEqual(sorted(f for r in copies for f in r[1]), self.all_files())
        self.assertTrue(all(len(r[1]) <= 4 for r in copies) and len(copies) > 1)
        self.assertEqual(self.ran[-1][0], "copyto")
        self.assertIn("--no-check-dest", copies[0][2])
        self.assertIn(f"Cache-Control: {wp.CACHE_FILE}", copies[0][2])
        self.assertEqual(self.asked, [(len(self.all_files()) + 1, True)])
        bucket = wp.load_manifest(self.work / "bucket.json")
        self.assertEqual(bucket["v"], self.read("latest.json")["v"])
        self.ran.clear()
        self.assertEqual(wp.plan(self.out, self.work)[:2], ([], []))

    def test_a_failed_batch_keeps_the_ones_before_it(self):
        wp.BATCH = 4
        self.fail_at = 2
        self.assertEqual(wp.upload(self.out, self.work), 1)
        self.assertEqual([r[0] for r in self.ran], ["copy", "copy"])   # no latest.json
        left = {wp.rel(*x) for x in wp.plan(self.out, self.work)[0]}
        self.assertEqual(left, set(self.all_files()) - set(self.ran[0][1]))
        self.assertIsNone(wp.load_manifest(self.work / "bucket.json").get("v"))

    def test_trial_uploads_a_few_and_not_latest_json(self):
        self.assertEqual(wp.upload(self.out, self.work, trial=4), 0)
        self.assertEqual([r[0] for r in self.ran], ["copy"])
        self.assertEqual(len(self.ran[0][1]), 4)
        self.assertTrue(any(f.startswith("place/") for f in self.ran[0][1]))
        self.assertTrue(any(f.startswith("children/") for f in self.ran[0][1]))

    def test_past_day_cap_needs_full(self):
        wp.DAY_CAP = 3
        self.assertEqual(wp.upload(self.out, self.work), 1)
        self.assertEqual((self.ran, self.asked), ([], []))
        self.assertEqual(wp.upload(self.out, self.work, full=True), 0)

    def test_past_max_upload_refused_even_with_full(self):
        wp.MAX_UPLOAD = 3
        self.assertEqual(wp.upload(self.out, self.work, full=True), 1)
        self.assertEqual((self.ran, self.asked), ([], []))

    def test_tripped_breaker_stops_upload(self):
        def gate(planned_class_a=0, strict=False, **k):
            raise self.sb.Tripped("test trip")
        self.sb.gate = gate
        self.assertEqual(wp.upload(self.out, self.work), 1)
        self.assertEqual(self.ran, [])

    def test_gone_files_are_deleted_before_latest_json(self):
        self.assertEqual(wp.upload(self.out, self.work), 0)
        idx = json.loads((self.places / "index.json").read_text(encoding="utf-8"))
        idx["countries"] = idx["countries"][:1]
        write_json(self.places / "index.json", idx)
        self.build()
        self.ran.clear()
        self.assertEqual(wp.upload(self.out, self.work), 0)
        kinds = [r[0] for r in self.ran]
        self.assertEqual(kinds.count("deletefile"), 2)
        self.assertEqual(kinds[-1], "copyto")
        self.assertEqual(wp.plan(self.out, self.work)[:2], ([], []))


if __name__ == "__main__":
    unittest.main()
