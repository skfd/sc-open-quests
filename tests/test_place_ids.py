"""place_ids.py and rename_places.py: our own ids, and the one rename to them. Run: python -m unittest"""
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import place_ids  # noqa: E402
import rename_places as rp  # noqa: E402

GERS = ["087cbb33-e54d-4a5b-9c1d-000000000001", "187cbb33-e54d-4a5b-9c1d-000000000002",
        "287cbb33-e54d-4a5b-9c1d-000000000003"]
ROWS = [(GERS[0], "r11@3", "Berlin", "region", "DE"), (GERS[1], "w12@1", "Mitte\tOst", "macrohood", "DE"),
        (GERS[2], None, "Nowhere", "locality", "XX")]


class Mint(unittest.TestCase):
    def test_ids_are_the_guids_first_digits_and_every_rule_holds(self):
        reg = place_ids.mint(ROWS, "2026-10-21.0")
        self.assertEqual(3, len(reg.places))
        self.assertEqual([], reg.check())
        p = reg.places[reg.id_of(GERS[0])]
        self.assertEqual(p.id, uuid.UUID(p.guid).hex[:12])
        self.assertEqual(("r11", "2026-10-21.0", "live"), (p.osm, p.since, p.state))

    def test_a_new_id_is_never_an_old_one_or_taken(self):
        clash = uuid.UUID("087cbb33e54d4a5b8c1d000000000000")  # the first 12 digits are the first place's old id
        ok = [uuid.UUID(int=n << 80 | 0x4000 << 64 | 0x8000 << 48) for n in (1, 2, 3)]
        given = iter([clash, ok[0], ok[0], ok[1], ok[2]])
        reg = place_ids.mint(ROWS, "r", guid=lambda: next(given))
        self.assertEqual({g.hex[:12] for g in ok}, set(reg.places))

    def test_an_unknown_gers_id_stops(self):
        with self.assertRaises(SystemExit):
            place_ids.mint(ROWS, "r").id_of("ffffffff-0000-4000-8000-000000000000")


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "registry.tsv.gz"

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip(self):
        reg = place_ids.mint(ROWS, "r")
        a, b = sorted(reg.places)[:2]
        reg.places[a].state, reg.places[a].successors = "ended", (b,)
        reg.save(self.path)
        back = place_ids.load(self.path)
        self.assertEqual(reg.places, back.places)
        self.assertNotIn(reg.places[a].gers, back.by_gers)

    def test_save_refuses_to_lose_or_renumber_a_place(self):
        place_ids.mint(ROWS, "r").save(self.path)
        with self.assertRaises(SystemExit):
            place_ids.mint(ROWS, "r").save(self.path)
        fewer = place_ids.load(self.path)
        fewer.places.popitem()
        with self.assertRaises(SystemExit):
            fewer.save(self.path)

    def test_mint_command_refuses_a_second_time(self):
        place_ids.mint(ROWS, "r").save(self.path)
        with self.assertRaises(SystemExit):
            place_ids.main(["--registry", str(self.path), "mint", "--src", self.tmp.name])


class Rename(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.world, self.archive, self.parts = root / "world", root / "archive", root / "parts"
        self.reg = place_ids.mint(ROWS, "r")
        self.pairs = {place_ids.old_id(p.gers): p.id for p in self.reg.places.values()}
        self.o = [place_ids.old_id(g) for g in GERS]
        self.n = [self.pairs[x] for x in self.o]
        self.put(self.parts / "berlin.json", '{"schema": 1, "parts": [\n  {"id": "%s", "gers": "%s"}\n]}\n' % (self.o[1], GERS[1]))
        self.put(self.archive / "berlin/snapshots/2026-11-01.json",
                 json.dumps({"cities": {"berlin": {"parts": {self.o[1]: {"AddBench": 2}}, "partsAged": {self.o[1]: {}}}}}))
        self.put(self.world / "places.json", json.dumps({"places": [
            {"id": x, "gers": g, "parent": GERS[0], "geometry": f"geo/{x[:2]}/{x}.geojson"} for x, g in zip(self.o, GERS)]}))
        self.put(self.world / "files/f0/parts/f0c0.json", json.dumps({"parts": [{"id": self.o[0], "geometry": f"g/{self.o[0]}.geojson"}]}))
        self.put(self.world / "counts/2026-11-01/counts.json",
                 json.dumps({"quests": ["AddBench"], "parts": [self.o[2], "city:f0c0", "osm-berlin", self.o[0]]}))
        self.put(self.world / "place-sets.json", json.dumps({"parts": [self.o[0], "city:f0c0", self.o[1]], "sets": [[], [0, 1]]}))
        self.put(self.world / "parts.cache.json", json.dumps({"stamp": rp.stamp_of(self.world / "places.json"), "built": "x"}))

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def run_all(self, apply):
        return rp.run(["config", "archive", "world"], apply, self.pairs, self.world, self.archive, self.parts)

    def test_every_store_is_renamed_and_nothing_else(self):
        self.run_all(True)
        self.assertEqual(self.n[1], json.loads((self.parts / "berlin.json").read_text())["parts"][0]["id"])
        self.assertEqual(GERS[1], json.loads((self.parts / "berlin.json").read_text())["parts"][0]["gers"])
        city = json.loads((self.archive / "berlin/snapshots/2026-11-01.json").read_text())["cities"]["berlin"]
        self.assertEqual({self.n[1]: {"AddBench": 2}}, city["parts"])
        self.assertEqual({self.n[1]: {}}, city["partsAged"])
        ps = json.loads((self.world / "places.json").read_text())["places"]
        self.assertEqual(self.n, [p["id"] for p in ps])
        self.assertEqual(f"geo/{self.o[0][:2]}/{self.o[0]}.geojson", ps[0]["geometry"])  # an outline's path stays
        counts = json.loads((self.world / "counts/2026-11-01/counts.json").read_text())["parts"]
        self.assertEqual([self.n[2], "city:f0c0", "osm-berlin", self.n[0]], counts)     # the order stays
        sets = json.loads((self.world / "place-sets.json").read_text())
        self.assertEqual(([self.n[0], "city:f0c0", self.n[1]], [[], [0, 1]]), (sets["parts"], sets["sets"]))

    def test_the_outline_cache_stays_current(self):
        self.run_all(True)
        side = json.loads((self.world / "parts.cache.json").read_text())
        self.assertEqual(rp.stamp_of(self.world / "places.json"), side["stamp"])

    def test_a_stale_outline_cache_stays_stale(self):
        self.put(self.world / "parts.cache.json", json.dumps({"stamp": {"size": 1}}))
        self.run_all(True)
        self.assertEqual({"size": 1}, json.loads((self.world / "parts.cache.json").read_text())["stamp"])

    def test_plan_writes_nothing_and_a_second_apply_is_a_no_op(self):
        before = (self.world / "place-sets.json").read_text()
        self.assertEqual((1, 1), self.run_all(False)["config"])
        self.assertEqual(before, (self.world / "place-sets.json").read_text())
        self.run_all(True)
        self.assertEqual({"config": (0, 0), "archive": (0, 0), "world": (0, 0)}, self.run_all(True))

    def test_an_unknown_or_mixed_id_stops_before_anything_is_written(self):
        for bad in ("ffffffffffff", self.n[0]):
            f = self.world / "place-sets.json"
            self.put(f, json.dumps({"parts": [self.o[0], bad], "sets": [[]]}))
            before = (self.world / "places.json").read_text()
            with self.assertRaises(SystemExit):
                self.run_all(True)
            self.assertEqual(before, (self.world / "places.json").read_text())

    def test_check_finds_an_old_id_left_behind(self):
        self.assertNotEqual(0, rp.check(self.pairs, self.world, self.archive, self.parts))
        self.run_all(True)
        self.assertEqual(0, rp.check(self.pairs, self.world, self.archive, self.parts))
        self.put(self.world / "report.json", json.dumps({"places": [self.o[0]]}))
        self.assertEqual(1, rp.check(self.pairs, self.world, self.archive, self.parts))

    def test_apply_refuses_beside_a_run_an_open_day_or_a_stop(self):
        cut = Path(self.tmp.name) / "cut"
        cut.mkdir()
        was, rp.PLANET_CUT = rp.PLANET_CUT, cut
        days, rp.WORLD_DAYS = rp.WORLD_DAYS, cut / "world-days"
        locks, rp.LOCKS = rp.LOCKS, [cut / "daily.lock"]
        try:
            with self.assertRaises(SystemExit):   # no HOLD
                rp.refuse_beside_the_loop()
            (cut / "HOLD").write_text("x")
            rp.refuse_beside_the_loop()
            (cut / "world-days" / "2026-11-24").mkdir(parents=True)
            with self.assertRaises(SystemExit):
                rp.refuse_beside_the_loop()
            (cut / "world-days" / "2026-11-24").rmdir()
            for name in ("STOPPED", "RUNNING", "daily.lock"):
                (cut / name).write_text("x")
                with self.assertRaises(SystemExit):
                    rp.refuse_beside_the_loop()
                (cut / name).unlink()
        finally:
            rp.PLANET_CUT, rp.WORLD_DAYS, rp.LOCKS = was, days, locks

    def test_a_hard_linked_copy_keeps_the_old_text(self):
        import os
        link = self.world / "checkpoint.json"
        os.link(self.world / "place-sets.json", link)
        self.run_all(True)
        self.assertIn(self.o[0], link.read_text())


if __name__ == "__main__":
    unittest.main()
