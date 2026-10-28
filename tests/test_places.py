"""places.py: the name layer's ids, parents and files. Run: python -m unittest"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import places  # noqa: E402


def row(gers, name, subtype, cc, anc, parent=None, osm=(), en=None, bbox=(0, 0, 1, 1)):
    """anc: (gers, subtype) root first, without the place itself."""
    chain = list(anc) + [(gers, subtype)]
    return {"gers": gers, "name": name, "en": en, "subtype": subtype, "country": cc,
            "parent": parent if parent is not None else (anc[-1][0] if anc else None),
            "anc": [a for a, _ in chain], "anc_st": [s for _, s in chain], "osm": list(osm),
            "xmin": bbox[0], "ymin": bbox[1], "xmax": bbox[2], "ymax": bbox[3]}


C = ("aaaaaaaa-0000-0000-0000-000000000001", "country")
R = ("bbbbbbbb-0000-0000-0000-000000000002", "region")
K = ("cccccccc-0000-0000-0000-000000000003", "county")
L = ("dddddddd-0000-0000-0000-000000000004", "locality")  # no area: not a place


def world():
    return [
        row("eeeeeeee-0000-0000-0000-000000000005", "Annex", "neighborhood", "XX", [C, R, K, L], parent=L[0]),
        row(K[0], "Metro", "county", "XX", [C, R], osm=["r42@3"], en="Metro"),
        row(R[0], "Province", "region", "XX", [C], en="The Province"),
        row(C[0], "Land", "country", "XX", [], en="Country", bbox=(-1.23456, 2, 3, 4)),
        row("ffffffff-0000-0000-0000-000000000006", "Isle", "locality", "XX", [C]),
    ]


class PlaceIdTest(unittest.TestCase):
    def test_first_twelve_hex_digits(self):
        self.assertEqual("087cbb33e54d", places.place_id("087cbb33-e54d-4a5b-9c1d-000000000000"))

    def test_shared_place_id_fails(self):
        rows = world() + [row("eeeeeeee-0000-9999-0000-000000000007", "Twin", "locality", "XX", [C])]
        with self.assertRaises(SystemExit):
            places.assign(rows)


class BuildTest(unittest.TestCase):
    def setUp(self):
        rows = world()
        places.assign(rows)
        counted, self.report = places.match_cities(rows, [
            {"id": "metro", "name": "Metro", "relation": 42, "countryCodes": ["XX", "XX-P"]}])
        self.index, self.files, self.stats = places.build(rows, counted)

    def test_region_file_parents_first_and_skip_arealess_ancestors(self):
        f = self.files["xx/bbbbbbbb0000.json"]
        self.assertEqual("bbbbbbbb0000", f["region"])
        ids = [p[0] for p in f["places"]]
        self.assertEqual(["bbbbbbbb0000", "cccccccc0000", "eeeeeeee0000"], ids)
        self.assertEqual([-1, 0, 1], [p[3] for p in f["places"]])
        self.assertEqual("The Province", f["places"][0][8])
        self.assertIsNone(f["places"][1][8], "en equal to the name is null")
        self.assertEqual("metro", f["places"][1][9])

    def test_places_outside_regions_go_to_underscore_under_the_country(self):
        f = self.files["xx/_.json"]
        self.assertEqual([["aaaaaaaa0000", "Land", 0, -1, -1.2346, 2, 3, 4, "Country", None],
                          ["ffffffff0000", "Isle", 5, 0, 0, 0, 1, 1, None, None]], f["places"])

    def test_index(self):
        (c,) = self.index
        self.assertEqual(("aaaaaaaa0000", "Land", "XX", [-1.2346, 2, 3, 4]), (c["id"], c["name"], c["cc"], c["bbox"]))
        self.assertEqual([("_", None, "xx/_.json", 2), ("bbbbbbbb0000", "Province", "xx/bbbbbbbb0000.json", 3)],
                         [(r["id"], r["name"], r["file"], r["n"]) for r in c["regions"]])
        self.assertEqual(0, self.stats["orphans"])

    def test_city_matched_by_relation(self):
        self.assertEqual(["metro: cccccccc0000 county 'Metro' by relation"], self.report)


if __name__ == "__main__":
    unittest.main()
