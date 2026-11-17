"""tools/stream/notes_day.py: open notes at a clock, SC's 6-decimal truncation from a stored position, HIDDEN by day."""
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "stream"))
import notes_day as N  # noqa: E402
from placesets import REC  # noqa: E402


def e7(x: float) -> int:
    """StateDump.e7, as the engine computes it"""
    r = int(np.floor(x * 1e7 + 0.5))  # Kotlin roundToInt: half up
    t = int(x * 10.0 ** 6)
    lo, hi = (t * 10, t * 10 + 9) if t > 0 or (t == 0 and x >= 0) else (t * 10 - 9, t * 10)
    return min(max(r, lo), hi)


def rows_at(points):
    r = np.zeros(len(points), dtype=REC)
    r["key"] = np.arange(len(points)) * 4
    r["lat"] = [e7(a) for a, _ in points]
    r["lon"] = [e7(b) for _, b in points]
    return r


def note(lat, lon, created, *comments):
    return (lat, lon, N.ms(created), [(N.ms(t), a) for t, a in comments])


class Truncation(unittest.TestCase):
    def test_stored_value_keeps_sc_truncation(self):
        rnd = random.Random(7)
        xs = [rnd.uniform(-180, 180) for _ in range(20000)]
        # positions just below and on 1e-6 steps, where plain rounding loses the truncation
        xs += [k * 1e-6 - d for k in (-5, -1, 0, 1, 7, 52123457) for d in (0, 1e-9, 4e-8, 4.9e-8, -1e-9)]
        r = rows_at([(x, -x) for x in xs])
        k = N.row_keys(r)
        want = N.key([int(x * 1e6) for x in xs], [int(-x * 1e6) for x in xs])
        self.assertTrue((k == want).all())

    def test_plain_rounding_would_not(self):
        x = 52.1234569999  # rounds to ...4570, truncates to ...456
        self.assertEqual(int(x * 1e6), 52123456)
        self.assertEqual(round(x * 1e7) // 10, 52123457)
        self.assertEqual(e7(x) // 10, 52123456)

    def test_note_string(self):
        self.assertEqual(N.trunc6("53.0268032"), 53026803)
        self.assertEqual(N.trunc6("-0.0000005"), 0)
        self.assertEqual(N.trunc6("-12.3456789"), -12345678)


class OpenAt(unittest.TestCase):
    def test_status_actions(self):
        ns = [note("1", "1", "2026-01-01T00:00:00Z", ("2026-01-01T00:00:00Z", "opened")),
              note("2", "2", "2026-01-01T00:00:00Z", ("2026-01-01T00:00:00Z", "opened"), ("2026-02-01T00:00:00Z", "closed")),
              note("3", "3", "2026-01-01T00:00:00Z", ("2026-01-01T00:00:00Z", "opened"), ("2026-02-01T00:00:00Z", "closed"),
                   ("2026-03-01T00:00:00Z", "reopened")),
              note("4", "4", "2026-01-01T00:00:00Z", ("2026-01-01T00:00:00Z", "opened"), ("2026-02-01T00:00:00Z", "hidden")),
              note("5", "5", "2026-04-01T00:00:00Z", ("2026-04-01T00:00:00Z", "opened")),
              note("6", "6", "2026-01-01T00:00:00Z", ("2026-01-02T00:00:00Z", "commented")),
              note("7", "7", "2026-01-01T00:00:00Z")]
        ids = lambda t: [n[0] for n in N.open_at(ns, N.ms(t))]
        # 6 has no status action, only a comment: open from that comment on, as the engine has it; 7 has no comment
        self.assertEqual(ids("2026-01-01T12:00:00Z"), ["1", "2", "3", "4"])
        self.assertEqual(ids("2026-01-15T00:00:00Z"), ["1", "2", "3", "4", "6"])
        self.assertEqual(ids("2026-02-15T00:00:00Z"), ["1", "6"])
        self.assertEqual(ids("2026-03-15T00:00:00Z"), ["1", "3", "6"])
        self.assertEqual(ids("2026-02-01T00:00:00Z"), ["1", "6"])  # a comment at the clock counts


class Hidden(unittest.TestCase):
    def test_incremental_equals_full(self):
        rnd = random.Random(3)
        spots = [(round(rnd.uniform(52, 53), 7), round(rnd.uniform(13, 14), 7)) for _ in range(50)]
        rows = rows_at([spots[rnd.randrange(50)] for _ in range(2000)] + [(52.5, 13.5)] * 5)
        ns = []
        for i, (a, b) in enumerate(spots[:40]):
            cs = [("2026-01-01T00:00:00Z", "opened")]
            if i % 3 == 0:
                cs.append(("2026-02-10T00:00:00Z", "closed"))
            created = "2026-01-01T00:00:00Z" if i % 4 else "2026-02-05T00:00:00Z"
            ns.append(note(f"{a:.7f}", f"{b:.7f}", created, *[(max(t, created), x) for t, x in cs]))
        with tempfile.TemporaryDirectory() as d:
            clip = Path(d) / "c.jsonl"
            clip.write_text("\n".join([json.dumps({"schema": 1})] + [json.dumps({
                "id": 1, "lat": lat, "lon": lon,
                "created": _iso(created), "comments": [{"action": a, "timestamp": _iso(t)} for t, a in cs]})
                for lat, lon, created, cs in ns]) + "\n", encoding="utf-8")
            d1, d2 = "2026-02-01T00:00:00Z", "2026-02-20T00:00:00Z"
            a = rows.copy()
            N.hidden_step(a, clip, d1)
            full = rows.copy()
            N.hidden_step(full, clip, d2)
            st = N.hidden_step(a, clip, d2, prev_clock=d1)
            self.assertTrue((a["flags"] == full["flags"]).all())
            self.assertGreater(st["flagsChanged"], 0)
            self.assertLess(st["rowsTouched"], len(rows))
            # a fresh row (a recount without notes) is set even where no note changed
            b = full.copy()
            b["flags"][:] = 0
            fresh = np.zeros(len(b), bool)
            fresh[:100] = True
            N.hidden_step(b, clip, d2, prev_clock=d2, fresh=fresh)
            self.assertTrue((b["flags"][:100] == full["flags"][:100]).all())


def _iso(ms):
    import datetime as dt
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    unittest.main()
