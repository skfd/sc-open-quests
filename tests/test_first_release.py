"""tools/sc_first_release.py and the file it wrote."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sc_first_release as fr  # noqa: E402


def registry_names() -> set[str]:
    return {q["name"] for q in json.loads(fr.newest_registry().read_text(encoding="utf-8"))["quests"]}


class FirstReleaseTest(unittest.TestCase):
    def test_quest_names(self):
        kotlin = "listOf(1 to AddRoadName(), 2 to AddLanes(), 3 to AddHelper(x), CheckExistence(get()))"
        self.assertEqual(fr.quest_names(kotlin, {"AddRoadName", "AddLanes", "CheckExistence", "Other"}),
                         {"AddRoadName", "AddLanes", "CheckExistence"})
        self.assertEqual(fr.quest_names("new AddRoadName(o), AddLanes.class", {"AddRoadName", "AddLanes"}),
                         {"AddRoadName", "AddLanes"})

    def test_first_tag_is_the_oldest(self):
        first = fr.first_tags([("v1", {"A"}), ("v2", {"A", "B"}), ("v3", {"B"})])
        self.assertEqual(first, {"A": "v1", "B": "v2"})

    def test_a_successor_counts_from_its_predecessor(self):
        first = {"AddCrossingType": "v1", "AddCrossingMarkings": "v9"}
        got = fr.first_releases(["AddCrossingMarkings"], first, {"v1": "2017-08-16", "v9": "2024-03-01"})
        self.assertEqual(got, {"AddCrossingMarkings": {"version": "v1", "date": "2017-08-16"}})

    def test_a_quest_in_no_tag_stops_it(self):
        with self.assertRaises(SystemExit):
            fr.first_releases(["AddNothing"], {}, {})


class FileTest(unittest.TestCase):
    def test_it_covers_the_newest_registry(self):
        """Fails after a repin that adds a quest, until tools/sc_first_release.py runs (REPIN.md, step 5):
        a quest missing from the file would count for all of history."""
        quests = json.loads(fr.OUT.read_text(encoding="utf-8"))["quests"]
        self.assertEqual(registry_names() - set(quests), set())

    def test_predecessors_are_old_names(self):
        names = registry_names()
        self.assertEqual(set(fr.PREDECESSOR.values()) & names, set())
        self.assertEqual(set(fr.PREDECESSOR) - names, set())


if __name__ == "__main__":
    unittest.main()
