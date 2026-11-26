"""tools/overture_switch.py: the old world's days joined into the new one, old against new at the seed day, and the
cutover's refusals. Run: python -m pytest tests/test_overture_switch.py"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import overture_switch as osw  # noqa: E402


def counts(d: Path, parts: dict[str, int]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    names = list(parts)
    (d / "counts.json").write_text(json.dumps({"clock": "x", "measures": ["open"], "quests": ["Q"], "parts": names}),
                                   encoding="utf-8")
    part = np.array([i for i, n in enumerate(names) for _ in range(2)], dtype=np.uint32)
    m = np.array([[parts[n] // 2] if k == 0 else [parts[n] - parts[n] // 2] for n in names for k in range(2)],
                 dtype=np.int64)
    np.savez(d / "counts.npz", part=part, quest=np.zeros(len(part), dtype=np.uint16), m=m)


class Switch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old, self.new = Path(self.tmp.name) / "old", Path(self.tmp.name) / "new"

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_old_days_before_the_seed_are_linked_in_and_nothing_from_the_seed_day_on(self):
        for day in ("2026-11-01", "2026-11-02", "2026-11-03"):
            counts(self.old / "counts" / day, {"a": 1})
            (self.old / "days" / day).mkdir(parents=True)
            (self.old / "days" / day / "gate.json").write_text('{"ok": true}', encoding="utf-8")
        (self.old / "counts" / "2026-11-01" / "gate1101.json").write_text('{"ok": true}', encoding="utf-8")
        counts(self.new / "counts" / "2026-11-03", {"a": 5})   # the seed's own day stays the new world's
        self.assertEqual(2, osw.join_days(self.old, self.new, "2026-11-03"))
        self.assertTrue((self.new / "counts/2026-11-01/gate1101.json").exists())
        self.assertTrue((self.new / "days/2026-11-02/gate.json").exists())
        self.assertFalse((self.new / "days/2026-11-03").exists())
        self.assertEqual({"a": 5}, osw.open_by_part(self.new / "counts/2026-11-03"))
        self.assertEqual(2, osw.join_days(self.old, self.new, "2026-11-03"))   # again: nothing breaks
        self.assertTrue(osw.gate_ok(self.new, "2026-11-01"))

    def test_old_against_new_names_the_cities_that_differ_and_the_places_that_moved(self):
        counts(self.old / "counts/2026-11-30", {"osm-berlin": 100, "osm-paris": 50, "p1": 1000, "p2": 40, "gone": 7})
        counts(self.new / "counts/2026-11-30", {"osm-berlin": 100, "osm-paris": 52, "p1": 1300, "p2": 41, "fresh": 3})
        c = osw.compare(self.old, self.new, "2026-11-30")
        self.assertEqual({"osm-paris": 2}, c["cities differing"])
        self.assertEqual((2, 1, 1, 1), (c["places in both"], c["only old (ended)"], c["only new"],
                                        c["places moving over 1%"]))
        self.assertIn("p1", c["largest moves"])

    def test_the_plan_check_compares_files_cells_and_boxes(self):
        a = {"files": [{"id": "f0", "bbox": [0, 0, 1, 1], "cells": [{"id": "f0c0", "rect": [0, 0, 1, 1], "parts": 3}]}]}
        b = json.loads(json.dumps(a))
        b["files"][0]["cells"][0]["parts"] = 9   # the places differ: fine
        self.assertEqual(osw.cells_of(a), osw.cells_of(b))
        b["files"][0]["cells"][0]["rect"] = [0, 0, 1, 2]
        self.assertNotEqual(osw.cells_of(a), osw.cells_of(b))

    def test_the_pinned_release_has_nothing_to_switch_to(self):
        with self.assertRaises(SystemExit):
            osw.prepare(osw.place_ids.pinned())

    def test_cutover_and_adopt_wait_for_the_step_before(self):
        with self.assertRaises(SystemExit) as e:
            osw.cutover("2099-01-01.0")
        self.assertIn("prepare", str(e.exception))
        with self.assertRaises(SystemExit) as e:
            osw.adopt("2099-01-01.0")
        self.assertIn("cutover", str(e.exception))
