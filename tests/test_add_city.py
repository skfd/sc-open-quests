"""add_city: city ids from names in any script. Run: python -m unittest"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import add_city  # noqa: E402


class SlugTest(unittest.TestCase):
    def test_ascii_names_keep_their_slug(self):
        self.assertEqual("toronto", add_city.slug("Toronto", 324211))
        self.assertEqual("north-vancouver-district", add_city.slug("North Vancouver (District)", 1))
        self.assertEqual("st-catharines", add_city.slug("St. Catharines", 1))

    def test_accents_are_transliterated(self):
        self.assertEqual("quebec", add_city.slug("Québec", 1))
        self.assertEqual("montreal", add_city.slug("Montréal", 1))
        self.assertEqual("koln", add_city.slug("Köln", 1))
        self.assertEqual("sao-paulo", add_city.slug("São Paulo", 1))
        self.assertEqual("lodz", add_city.slug("Łódź", 1))  # ł does not decompose
        self.assertEqual("munster", add_city.slug("Münster", 1))
        self.assertEqual("gross-gerau", add_city.slug("Groß-Gerau", 1))
        self.assertEqual("aarhus", add_city.slug("Aarhus", 1))
        self.assertEqual("tromso", add_city.slug("Tromsø", 1))
        self.assertEqual("l-ile-perrot", add_city.slug("L'Île-Perrot", 1))

    def test_other_scripts_get_the_relation_id(self):
        self.assertEqual("r2555133", add_city.slug("Москва", 2555133))
        self.assertEqual("r1543125", add_city.slug("東京都", 1543125))
        self.assertEqual("r123", add_city.slug("القاهرة", 123))
        # a mixed name is not cut down to its Latin part
        self.assertEqual("r9", add_city.slug("Zürich 苏黎世", 9))
        self.assertEqual("r5", add_city.slug("---", 5))


class ChooseIdTest(unittest.TestCase):
    cities = [{"id": "springfield", "relation": 100}, {"id": "quebec-city", "relation": 200}]

    def test_new_relation_gets_its_slug(self):
        self.assertEqual("montreal", add_city.choose_id("Montréal", 300, None, self.cities))

    def test_a_slug_held_by_another_relation_falls_back_to_the_relation_id(self):
        self.assertEqual("r101", add_city.choose_id("Springfield", 101, None, self.cities))

    def test_readding_a_relation_keeps_its_id(self):
        self.assertEqual("quebec-city", add_city.choose_id("Québec", 200, None, self.cities))
        self.assertEqual("springfield", add_city.choose_id("Springfield", 100, None, self.cities))

    def test_a_given_id_wins_and_must_be_a_slug(self):
        self.assertEqual("moscow", add_city.choose_id("Москва", 2555133, "moscow", self.cities))
        for bad in ("", "Moscow", "moscow-", "моск"):
            with self.assertRaises(SystemExit):
                add_city.choose_id("Москва", 2555133, bad, self.cities)


if __name__ == "__main__":
    unittest.main()
