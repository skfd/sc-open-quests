"""overture_release.py: a release taken into the registry by proposals an operator judges. Run: python -m pytest"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import place_ids  # noqa: E402
import overture_release as orl  # noqa: E402

OLD, NEW = "2026-10-21.0", "2026-12-16.0"


def g(n: int) -> str:
    return f"{n:08x}-0000-4000-8000-{n:012x}"


# gers, osm, name, subtype, country, parent, (x0, y0, x1, y1)
BOX = (10.0, 50.0, 10.01, 50.01)
FAR = (100.0, -40.0, 100.01, -39.99)
OLD_ROWS = [
    (g(1), "r1", "Alpha", "locality", "DE", None, (9.9, 49.9, 10.2, 50.2)),       # kept, renamed
    (g(2), "r2", "Bravo", "neighborhood", "DE", g(1), BOX),                      # lost; same OSM object, same name
    (g(3), "r3", "Charlie", "microhood", "DE", g(1), (11.0, 51.0, 11.01, 51.01)),  # lost; same OSM, subtype changed
    (g(4), "w4", "Delta", "neighborhood", "DE", g(1), (12.0, 52.0, 12.01, 52.01)),  # lost; a new Delta 0.7 km away
    (g(5), "r50", "Echo", "neighborhood", "DE", g(1), (13.0, 53.0, 13.01, 53.01)),  # lost; contested with Foxtrot
    (g(6), "r50", "Foxtrot", "neighborhood", "DE", g(1), (13.0, 53.0, 13.01, 53.01)),
    (g(7), "r7", "Hotel", "neighborhood", "DE", None, (9.95, 49.95, 10.15, 50.15)),  # lost; overlaps Alpha
    (g(8), "r8", "India", "microhood", "DE", g(1), (14.0, 54.0, 14.001, 54.001)),  # lost; only its parent lives on
    (g(9), "r9", "Juliet", "locality", "XX", None, FAR),                          # lost; nothing
    (g(10), "r10", "Lima", "locality", "DE", None, (15.0, 55.0, 15.01, 55.01)),     # ended in the registry, back now
    (g(11), "r11", "Mike", "neighborhood", "XX", g(9), (120.0, -30.0, 120.01, -29.99)),  # lost; its parent Juliet too
    (g(12), "r12", "November", "microhood", "DE", g(1), (17.0, 57.0, 17.01, 57.01)),  # lost; same OSM, far outline
]
NEW_ROWS = [
    (g(1), "r1", "Alpha Stadt", "locality", "DE", None, (9.9, 49.9, 10.2, 50.2)),
    (g(102), "r2", "Bravo", "neighborhood", "DE", g(1), BOX),
    (g(103), "r3", "Charlie", "neighborhood", "DE", g(1), (11.0, 51.0, 11.01, 51.01)),
    (g(104), "w99", "Delta", "neighborhood", "DE", g(1), (12.005, 52.005, 12.015, 52.015)),
    (g(105), "r50", "Echo-Foxtrot", "neighborhood", "DE", g(1), (13.0, 53.0, 13.01, 53.01)),
    (g(110), "r110", "Kilo \"K\"", "locality", "DE", None, (16.0, 56.0, 16.01, 56.01)),   # new
    (g(10), "r10", "Lima", "locality", "DE", None, (15.0, 55.0, 15.01, 55.01)),
    (g(112), "r12", "November", "neighborhood", "DE", g(1), (17.5, 57.5, 17.6, 57.6)),
]


def write_places(path: Path, rows) -> None:
    import duckdb
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("CREATE TABLE t (gers VARCHAR, osm VARCHAR, name VARCHAR, subtype VARCHAR, country VARCHAR, parent VARCHAR, "
                "x0 DOUBLE, y0 DOUBLE, x1 DOUBLE, y1 DOUBLE, lx DOUBLE, ly DOUBLE)")
    con.executemany("INSERT INTO t VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(gers, osm, name, st, cc, par, *b, (b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
                     for gers, osm, name, st, cc, par, b in rows])
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT parquet)")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.root, self.registry, self.former = t / "releases", t / "registry.tsv.gz", t / "former-names.tsv"
        write_places(self.root / OLD / "places.parquet", OLD_ROWS)
        write_places(self.root / NEW / "places.parquet", NEW_ROWS)
        reg = place_ids.mint([(r[0], r[1], r[2], r[3], r[4]) for r in OLD_ROWS], OLD)
        lima = reg.places[reg.id_of(g(10))]
        del reg.by_gers[g(10)]
        lima.state = "ended"
        reg.save(self.registry)
        self.reg = place_ids.load(self.registry)
        self.id = {p.gers: p.id for p in self.reg.places.values()}
        self.registry_bytes = self.registry.read_bytes()

    def tearDown(self):
        self.tmp.cleanup()

    def propose(self):
        orl.propose(NEW, OLD, self.registry, self.root)
        return {r["key"]: r for r in orl.read_rows(self.root / NEW / "proposals.tsv")}


class Release(Base):
    def test_each_kind_of_change_gets_its_class_and_proposal(self):
        rows = self.propose()
        cls = {k: (r["class"], r["proposal"]) for k, r in rows.items()}
        i = self.id
        self.assertEqual(("same-osm", f"same {g(102)}"), cls[i[g(2)]])
        self.assertEqual(("same-osm-changed", f"same {g(103)}"), cls[i[g(3)]])
        self.assertEqual(("same-name-near", f"same {g(104)}"), cls[i[g(4)]])
        self.assertEqual(("contested", f"same {g(105)}"), cls[i[g(5)]])
        self.assertEqual(("contested", f"same {g(105)}"), cls[i[g(6)]])
        self.assertEqual("overlap", cls[i[g(7)]][0])
        self.assertIn(i[g(1)], cls[i[g(7)]][1])
        self.assertEqual(("ended-parent", f"ended {i[g(1)]}"), cls[i[g(8)]])
        self.assertEqual(("ended-none", "ended"), cls[i[g(9)]])
        self.assertEqual(("ended-none", "ended"), cls[i[g(11)]], "a lost parent is no successor")
        self.assertEqual(("back", "revive"), cls[i[g(10)]])
        self.assertEqual(("new", "new"), cls[g(110)])
        self.assertNotIn(i[g(1)], rows)   # kept: no row
        self.assertEqual(("same-osm-far", f"same {g(112)}"), cls[i[g(12)]])
        self.assertEqual(12, len(rows))   # ten lost, one back, one new
        self.assertTrue((self.root / NEW / "report.md").exists())

    def test_contested_rows_are_never_accepted_in_bulk_and_bad_verdicts_stop(self):
        self.propose()
        with self.assertRaises(SystemExit):
            orl.accept(NEW, ["contested"], self.root)
        with self.assertRaises(SystemExit):
            orl.judge(NEW, self.id[g(9)], "revive", root=self.root)
        with self.assertRaises(SystemExit):
            orl.judge(NEW, g(110), "same " + g(1), root=self.root)

    def test_apply_needs_every_row_judged_and_then_keeps_every_id(self):
        self.propose()
        orl.accept(NEW, [c for c in orl.CLASSES if c != "contested"], self.root)
        with self.assertRaises(SystemExit):
            orl.apply(NEW, self.registry, self.former, self.root)
        orl.judge(NEW, self.id[g(5)], f"same {g(105)}", root=self.root)
        orl.judge(NEW, self.id[g(6)], f"ended {self.id[g(5)]}", root=self.root)
        s = orl.apply(NEW, self.registry, self.former, self.root)
        self.assertEqual(self.registry_bytes, self.registry.read_bytes(), "the live registry is never written")
        out = place_ids.load(self.root / NEW / "registry.tsv.gz")
        self.assertEqual([], out.check())
        for pid, p in self.reg.places.items():
            self.assertEqual(p.guid, out.places[pid].guid)
        self.assertEqual({r[0] for r in NEW_ROWS}, {p.gers for p in out.places.values() if p.state == "live"})
        i = self.id
        self.assertEqual((g(102), "live"), (out.places[i[g(2)]].gers, out.places[i[g(2)]].state))
        self.assertEqual(("neighborhood", g(103)), (out.places[i[g(3)]].subtype, out.places[i[g(3)]].gers))
        self.assertEqual(("ended", (i[g(5)],)), (out.places[i[g(6)]].state, out.places[i[g(6)]].successors))
        self.assertEqual(("ended", (i[g(1)],)), (out.places[i[g(8)]].state, out.places[i[g(8)]].successors))
        self.assertEqual(("live", ()), (out.places[i[g(10)]].state, out.places[i[g(10)]].successors))
        self.assertEqual("Alpha Stadt", out.places[i[g(1)]].name)
        kilo = out.places[out.id_of(g(110))]
        self.assertEqual((NEW, "r110", "Kilo \"K\""), (kilo.since, kilo.osm, kilo.name))
        former = (self.root / NEW / "former-names.tsv").read_text(encoding="utf-8").splitlines()
        self.assertIn(f"{i[g(1)]}\tAlpha\t{NEW}", former)
        self.assertEqual((1, 5, 5, 1), (s["minted"], s["same"], s["ended"], s["revived"]))

        # again, after the operator turns Bravo's same down: Kilo keeps the id it was given, Bravo's new GERS id gets one
        orl.judge(NEW, i[g(2)], "ended", root=self.root)
        s2 = orl.apply(NEW, self.registry, self.former, self.root)
        again = place_ids.load(self.root / NEW / "registry.tsv.gz")
        self.assertEqual(kilo.id, again.id_of(g(110)))
        self.assertEqual("ended", again.places[i[g(2)]].state)
        self.assertEqual(NEW, again.places[again.id_of(g(102))].since)
        self.assertEqual(1, s2["minted after a same proposal was turned down"])

    def test_propose_keeps_verdicts_already_given(self):
        self.propose()
        orl.accept(NEW, ["new"], self.root)
        with self.assertRaises(SystemExit):
            orl.propose(NEW, OLD, self.registry, self.root)


if __name__ == "__main__":
    unittest.main()


class Judges(Base):
    """the algorithm's clear cases, then the Fable judge (a fake runner here), then what is left for the operator"""

    def test_the_algorithm_decides_only_the_clear_classes(self):
        self.propose()
        self.assertEqual(4, orl.auto(NEW, self.root))   # Bravo, Charlie, Lima back, Kilo new
        rows = {r["key"]: r for r in orl.read_rows(self.root / NEW / "proposals.tsv")}
        decided = {k for k, r in rows.items() if r["verdict"]}
        i = self.id
        self.assertEqual({i[g(2)], i[g(3)], i[g(10)], g(110)}, decided)
        self.assertTrue(all(rows[k]["judged"].startswith("algorithm") for k in decided))

    def test_fable_verdicts_stand_only_when_every_run_agrees_with_high_confidence(self):
        self.propose()
        orl.auto(NEW, self.root)
        i = self.id
        answers = {
            i[g(4)]: [("same " + g(104), "high")] * 2,                               # agreed: taken
            i[g(12)]: [("same " + g(112), "high")] * 2,                              # agreed: taken
            i[g(7)]: [("ended " + i[g(1)], "low")] * 2,                              # unsure: operator
            i[g(8)]: [("ended " + i[g(1)], "high"), ("ended", "high")],              # disagree: operator
            i[g(9)]: [("ended", "high")] * 2,                                        # agreed: taken
            i[g(11)]: [("same " + g(1), "high")] * 2,                                # not a new GERS id: operator
            i[g(5)]: [("same " + g(105), "high")] * 2,                               # both take g(105): operator
            i[g(6)]: [("same " + g(105), "high")] * 2,
        }
        calls = []

        def runner(prompt):
            run = sum(1 for c in calls if c == prompt)
            calls.append(prompt)
            keys = [line.split(" | ")[0] for line in prompt.splitlines() if " | " in line and not line.startswith("Rows")]
            return {"verdicts": [{"key": k, "verdict": answers[k][run][0], "confidence": answers[k][run][1],
                                  "reason": "test"} for k in keys if k in answers], "_cost": 0.5}

        t = orl.agent(NEW, OLD, self.root, self.registry, runs=2, batch=3, workers=2, runner=runner)
        rows = {r["key"]: r for r in orl.read_rows(self.root / NEW / "proposals.tsv")}
        taken = {k for k, r in rows.items() if r["judged"].startswith(("judge", "fable")) and "by rule" not in r["judged"]}
        self.assertEqual({i[g(4)], i[g(12)], i[g(9)]}, taken)
        operator = {k for k, r in rows.items() if not r["verdict"]}
        self.assertEqual({i[g(11)], i[g(5)], i[g(6)]}, operator, "doubts about the same place only")
        # every answer ended the place: only the successor was in doubt, settled by rule (owner, 2026-11-26)
        self.assertEqual("ended " + i[g(1)], rows[i[g(8)]]["verdict"])   # the high answer of the two
        self.assertEqual("ended " + i[g(1)], rows[i[g(7)]]["verdict"])             # its proposal names the parent
        self.assertIn("successor chosen by rule", rows[i[g(7)]]["judged"])
        self.assertIn("not a new GERS id", rows[i[g(11)]]["judged"])
        self.assertIn("two rows take", rows[i[g(5)]]["judged"])
        self.assertEqual((3, 3), (t["judged"], t["operator"]))
        ex = (self.root / NEW / "exceptions.md").read_text(encoding="utf-8")
        self.assertIn("3 rows for the operator", ex)
        # a second run judges nothing again: the operator's rows wait for the operator
        self.assertEqual({"judged": 0, "operator": 0}, orl.agent(NEW, OLD, self.root, self.registry, runner=runner))

    def test_a_failed_run_leaves_its_rows_for_the_next_run(self):
        self.propose()
        orl.auto(NEW, self.root)

        def runner(prompt):
            raise RuntimeError("no network")

        t = orl.agent(NEW, OLD, self.root, self.registry, runs=1, runner=runner)
        self.assertEqual(0, t["judged"])
        rows = orl.read_rows(self.root / NEW / "proposals.tsv")
        left = [r for r in rows if not r["verdict"]]
        self.assertTrue(left and all(r["judged"] == "" for r in left), "left for the next run, not for the operator")
        self.assertEqual(len(left), t["retry"])

    def test_look_shows_a_rows_context(self):
        self.propose()
        text = orl.look(NEW, self.id[g(7)], OLD, self.root, self.registry)
        self.assertIn("Hotel", text)
        self.assertIn("Alpha Stadt", text)   # what overlaps it in the release
        self.assertIn(f"our {self.id[g(1)]}", text)
