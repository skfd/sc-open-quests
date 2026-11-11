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


class EnglishTest(unittest.TestCase):
    def test_overture_english_only_no_home_made_romanisation(self):
        self.assertEqual(places.english({"name": "Москва", "en": "Moscow"}), "Moscow")
        self.assertIsNone(places.english({"name": "Тверь", "en": None}))
        self.assertIsNone(places.english({"name": "Paris", "en": "Paris"}))


C = ("aaaaaaaa-0000-0000-0000-000000000001", "country")
R = ("bbbbbbbb-0000-0000-0000-000000000002", "region")
K = ("cccccccc-0000-0000-0000-000000000003", "county")
L = ("dddddddd-0000-0000-0000-000000000004", "locality")  # no area: not a place


def world():
    return [
        row("eeeeeeee-0000-0000-0000-000000000005", "Annex", "neighborhood", "ZZ", [C, R, K, L], parent=L[0]),
        row(K[0], "Metro", "county", "ZZ", [C, R], osm=["r42@3"], en="Metro"),
        row(R[0], "Province", "region", "ZZ", [C], en="The Province"),
        row(C[0], "Land", "country", "ZZ", [], en="Country", bbox=(-1.23456, 2, 3, 4)),
        row("ffffffff-0000-0000-0000-000000000006", "Isle", "locality", "ZZ", [C]),
    ]


class PlaceIdTest(unittest.TestCase):
    def test_first_twelve_hex_digits(self):
        self.assertEqual("087cbb33e54d", places.place_id("087cbb33-e54d-4a5b-9c1d-000000000000"))

    def test_shared_place_id_fails(self):
        rows = world() + [row("eeeeeeee-0000-9999-0000-000000000007", "Twin", "locality", "ZZ", [C])]
        with self.assertRaises(SystemExit):
            places.assign(rows)


class BuildTest(unittest.TestCase):
    def setUp(self):
        rows = world()
        places.assign(rows)
        counted, self.report = places.match_cities(rows, [
            {"id": "metro", "name": "Metro", "relation": 42, "countryCodes": ["ZZ", "ZZ-P"]}])
        self.index, self.files, self.stats = places.build(rows, counted)

    def test_region_file_parents_first_and_skip_arealess_ancestors(self):
        f = self.files["zz/bbbbbbbb0000.json"]
        self.assertEqual("bbbbbbbb0000", f["region"])
        ids = [p[0] for p in f["places"]]
        self.assertEqual(["bbbbbbbb0000", "cccccccc0000", "eeeeeeee0000"], ids)
        self.assertEqual([-1, 0, 1], [p[3] for p in f["places"]])
        self.assertEqual("The Province", f["places"][0][8])
        self.assertIsNone(f["places"][1][8], "en equal to the name is null")
        self.assertEqual("metro", f["places"][1][9])

    def test_places_outside_regions_go_to_underscore_under_the_country(self):
        f = self.files["zz/_.json"]
        self.assertEqual([["aaaaaaaa0000", "Land", 0, -1, -1.2346, 2, 3, 4, "Country", None],
                          ["ffffffff0000", "Isle", 5, 0, 0, 0, 1, 1, None, None]], f["places"])

    def test_index(self):
        (c,) = self.index
        self.assertEqual(("aaaaaaaa0000", "Land", "ZZ", [-1.2346, 2, 3, 4]), (c["id"], c["name"], c["cc"], c["bbox"]))
        self.assertEqual([("_", None, "zz/_.json", 2), ("bbbbbbbb0000", "Province", "zz/bbbbbbbb0000.json", 3)],
                         [(r["id"], r["name"], r["file"], r["n"]) for r in c["regions"]])
        self.assertEqual(0, self.stats["orphans"])

    def test_city_matched_by_relation(self):
        self.assertEqual(["metro: cccccccc0000 county 'Metro' by relation"], self.report)


def g(n):
    return f"{n:08x}-0000-0000-0000-000000000000"


class CountriesTest(unittest.TestCase):
    """Filing by StreetComplete's countries (DESIGN.md, "Countries in the place index")."""

    def setUp(self):
        ua, cr, sim = (g(1), "country"), (g(2), "region"), (g(3), "locality")
        ru, mos = (g(4), "country"), (g(5), "region")
        us, pr, sj = (g(6), "country"), (g(7), "dependency"), (g(8), "region")
        xg, gaza = (g(9), "country"), (g(10), "locality")
        rows = [
            row(ua[0], "Ukraine", "country", "UA", []),
            row(cr[0], "Crimea", "region", "UA", [ua]),
            row(sim[0], "Simferopol", "locality", "UA", [ua, cr]),
            row(g(11), "Donetsk", "locality", "UA", [ua]),
            row(ru[0], "Russia", "country", "RU", []),
            row(mos[0], "Moscow", "region", "RU", [ru]),
            row(us[0], "United States", "country", "US", []),
            row(pr[0], "Puerto Rico", "dependency", "PR", []),
            row(sj[0], "San Juan", "region", "PR", [pr]),
            row(xg[0], "Gaza Strip", "country", "XG", []),
            row(gaza[0], "Gaza", "locality", "XG", [xg]),
            row(g(12), "Uotsuri-jima", "locality", "XD", []),
        ]
        sc = {ua[0]: ["UA"], cr[0]: ["UA-43", "RU"], sim[0]: ["UA-43", "RU"], g(11): ["UA"], ru[0]: ["RU"],
              mos[0]: ["RU"], us[0]: ["US"], pr[0]: ["PR", "US"], sj[0]: ["PR", "US"], xg[0]: ["PS"],
              gaza[0]: ["PS"], g(12): []}
        for r in rows:
            r["sc"] = sc[r["gers"]]
        self.by = {r["name"]: r for r in rows}
        places.assign(rows)
        self.index, self.files, _ = places.build([r for r in rows if r["files"]], {})

    def ids(self, path):
        return [p[1] for p in self.files[path]["places"]]

    def test_crimea_under_both_inside_its_region(self):
        self.assertEqual(["RU", "UA"], self.by["Simferopol"]["cs"])
        self.assertEqual(["Crimea", "Simferopol"], self.ids("ua/000000020000.json"))
        self.assertEqual(["Crimea", "Simferopol"], self.ids("ru/000000020000.json"))
        self.assertEqual(["UA"], self.by["Donetsk"]["cs"], "SC says UA alone")

    def test_a_dependency_nests_under_its_sovereign(self):
        self.assertEqual(["Puerto Rico", "San Juan"], self.ids("us/000000070000.json"))
        us = next(c for c in self.index if c["cc"] == "US")
        self.assertEqual("United States", us["name"])
        self.assertIn("Puerto Rico", [r["name"] for r in us["regions"]])
        self.assertEqual(["Puerto Rico"], self.ids("pr/_.json"))
        self.assertEqual(["San Juan"], self.ids("pr/000000080000.json"), "at home, regions keep their files")

    def test_placeholders_are_no_country(self):
        ccs = [c["cc"] for c in self.index]
        self.assertNotIn("XG", ccs)
        self.assertNotIn("XD", ccs)
        self.assertEqual(["Gaza Strip", "Gaza"], self.ids("ps/000000090000.json"))
        ps = next(c for c in self.index if c["cc"] == "PS")
        self.assertIsNone(ps["id"], "no Overture division stands for PS; the site names it")

    def test_no_country_is_left_out(self):
        self.assertEqual([], self.by["Uotsuri-jima"]["files"])


if __name__ == "__main__":
    unittest.main()
