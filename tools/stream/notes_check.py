"""notes_day against the engine (DESIGN, "Release 1: the world day", step 4). A region's newest extract counted by the
engine with notes, parts and --dump-state at two clocks (--today D1 and D2, same extract and notes clip), then:
  full:        run 2's rows with HIDDEN cleared, recomputed at D2, equal run 2's flags on every row;
  incremental: run 1's rows carried from D1 to D2 (only positions whose open notes changed), equal run 2's flags on
               every row the two runs share (same record but for HIDDEN);
  quests:      the note quests at D2 counted by the engine over no elements, equal run 2's per city and part.
  python tools/stream/notes_check.py [region] [D1] [D2] [engine-bin-dir]
Runs and results go to .scratch/notes-day/<region>-<build|alt>/. Engines at -Xmx8g."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

WT = Path(__file__).resolve().parents[2]  # the repository
sys.path.insert(0, str(WT))
sys.path.insert(0, str(WT / "tools/stream"))
import run  # noqa: E402
import notes_day as N  # noqa: E402
from placesets import REC  # noqa: E402

HERE = WT / ".scratch/notes-day"
rid = sys.argv[1] if len(sys.argv) > 1 else "bremen"
D1 = sys.argv[2] if len(sys.argv) > 2 else "2026-09-01T00:00:00Z"
D2 = sys.argv[3] if len(sys.argv) > 3 else "2026-11-15T00:00:00Z"
ENGINE = Path(sys.argv[4]) if len(sys.argv) > 4 else WT / "engine/build/install/sc-open-quests-engine/bin"
BAT = ENGINE / "sc-open-quests-engine.bat"
region = next(r for r in run.read_json(run.REGIONS_CONFIG)["regions"] if r["id"] == rid)
pbf = run.latest_extract(region)[0]
cities = run.region_cities(region)
clip = run.notes_clip(region)
tag = "build" if len(sys.argv) <= 4 else "alt"
quests = sorted((WT / "data/quests").glob("v*.json"))[-1]


def env(tz):
    return dict(os.environ, JAVA_HOME=r"C:\Program Files\Android\Android Studio\jbr",
                JAVA_OPTS=f"-Duser.timezone={tz} -Duser.language=en -Duser.country=CA -Xmx8g")


def count(clock, d):
    if (d / "state.bin.json").exists():
        return
    d.mkdir(parents=True, exist_ok=True)
    cmd = [str(BAT), "count", "--pbf", str(pbf), "--quests", str(quests), "--cities", str(cities), "--out", str(d / "out"),
           "--notes", str(clip), "--today", clock, "--dump-state", str(d / "state.bin"), "--parts", str(WT / "config/parts")]
    with open(d / "log.txt", "w", encoding="utf-8") as f:
        subprocess.run(cmd, cwd=WT, env=env(region["timeZone"]), stdout=f, stderr=subprocess.STDOUT, check=True)


out = HERE / f"{rid}-{tag}"
r1, r2 = out / "d1", out / "d2"
count(D1, r1)
count(D2, r2)
a = np.fromfile(r1 / "state.bin", dtype=REC)
b = np.fromfile(r2 / "state.bin", dtype=REC)
bad = 0

# full recompute at D2
c = b.copy()
c["flags"] &= ~np.uint8(N.HIDDEN)
st = N.hidden_step(c, clip, D2)
diff = c["flags"] != b["flags"]
print(f"full: {len(b):,} rows, {int((b['flags'] & N.HIDDEN > 0).sum()):,} hidden by the engine; {st}; "
      f"{int(diff.sum())} differ")
for r in b[diff][:10]:
    print("   ", r, "engine hidden" if r["flags"] & N.HIDDEN else "engine not hidden")
bad += int(diff.sum())

# incremental D1 -> D2 on the rows both runs have
st = N.hidden_step(a, clip, D2, prev_clock=D1)
def ident(x):
    y = x.copy()
    y["flags"] &= ~np.uint8(N.HIDDEN)
    return y.view(np.void)
ia, ib = ident(a), ident(b)
both_a, both_b = np.isin(ia, ib), np.isin(ib, ia)
sa, sb = np.sort(a[both_a].view(np.void)), None
# align shared rows by their identity
oa = np.argsort(ia[both_a], kind="stable")
ob = np.argsort(ib[both_b], kind="stable")
fa, fb = a[both_a][oa], b[both_b][ob]
same_len = len(fa) == len(fb)
d_inc = (fa["flags"] != fb["flags"]) if same_len else None
n_inc = int(d_inc.sum()) if same_len else -1
print(f"incremental: {st}; {len(fa):,} shared rows; hidden at D1 {int((a['flags'] & 64 > 0).sum()) if False else ''}"
      f"{n_inc} differ" + ("" if same_len else f" (shared rows not paired: {len(fa)} against {len(fb)})"))
if same_len and n_inc:
    for x, y in list(zip(fa[d_inc], fb[d_inc]))[:10]:
        print("   ", x, y)
bad += abs(n_inc)

# note quests at D2 by the engine over no elements
got = N.note_quests(cities, clip, D2, out / "quests", parts=WT / "config/parts", engine=BAT, zone=region["timeZone"])
want = N.snapshot_notes(next((r2 / "out" / "snapshots").glob("*.json")))
eq = got == want
print(f"quests: cities {want['cities']}; {len(want['parts'])} parts with note quests; "
      f"{'EQUAL' if eq else 'DIFFER: ' + json.dumps({'got': got, 'want': want})[:800]}")
bad += 0 if eq else 1
print("notes_day check: " + ("all equal" if not bad else f"{bad} differences"))
sys.exit(1 if bad else 0)
