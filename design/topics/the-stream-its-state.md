## The stream: its state (2026-11-13)

The owner (2026-11-13, midday): "were building current world processing as an etalone for data and performance.
big hopes that streaming version will be faster." So the full count is the reference twice over: for the
numbers (the stream must reproduce it) and for the cost (the stream must beat it). Steps 1-5 above compared two
evaluations; nothing held a state and carried it forward. This adds that.

**The reference's cost, from `logs/planet-places.log` (11-13):** plan 1 min, slice from the history file 74 min,
notes 5 min, cut into 128 files 262 min, count 124 s a file on one engine (about 4.4 h; two engines never fit
beside what else holds memory). About 10.5 h of machine time for one instant of the world, 60% of it slice and
cut. Tier 1 of the stream did a planet day in about 7 min (step 5).

**What the state is.** Per (element, quest): the quest's position, the bits of `matchVariants` (open now, aged,
at 0.5, at 2), whether an open note hides it, and for a quest not open now at the default resurvey setting but
open from some day on, that day. Notes are a layer of their own: every match is kept, flagged when hidden, and
the checks leave notes out.

**Engine `--dump-state <file.bin>`** (`StateDump.kt`): 24-byte little-endian records written as the pass goes
(key i64 = id*4+type, lat/lon i32 at 1e-7, quest u16, flags u8, kind u8, due i32 in minutes since the epoch),
plus `<file>.json` naming the quests in index order (the order differs between runs with and without notes).
A main-pass age quest not open now is asked at 40 years ahead; if open then, the first whole day after asOf it
opens is found by halving (about 14 evaluations). Without the option nothing changes (86 engine tests pass).
Checked on step 1's 11-09 versions (europe-west): the open, unhidden records equal `--dump-matches` exactly
(1,350); counted again with `--today 2028-06-01`, all 37 quests dated by then are open and none dated later;
at `2034-03-01` all 208. The only quests opening that the dates did not foresee were the area quests
CheckExistence and AddCycleway (42): **area quests are not dated yet** (AreaPass asks a whole map data at once,
so halving per element does not fit; to do before the world seed if the Europe test shows their ageing).
Quests that only `newer` tests open, and the dates at the 0.5 and 2 settings, are not dated either.

**`world_cells.py count --state`:** every file of a kept cut again with `--dump-state` to
`files/<f>/state.bin`, beside the count (`out-state/`, `state-done.json`), so a recount never touches the
count's results. For the world seed from the 11-08 cut kept by chain4.sh.

**`tools/stream/stream.py`:** the state of a region in memory as one sorted table (`rows.npy`); `apply` takes
one day diff: the last version of every node and way in it (a day diff is sorted by type and id), node places
from the seed clip's sparse index plus an overlay of the diff's nodes, the tagged ones into a small PBF (way
nodes as synthetic nodes), the engine over that with the area pass off, and every tier-1 row of a touched
element replaced. Ageing has no event: a row waiting for its date is open from its date on. `check` holds the
state against a whole count's dump of the same instant, by tier. Measured on diff 5171 (11-08 to 11-09, the
whole planet's): reading the diff 124 s in Python, the small PBF 28 s (222,496 tagged ways placed in the
Europe clip, 209,608 outside it), the engine over europe-west's touched elements 2.4 s, the state 10 s.

**Known gaps, each visible in `check`:** a way whose nodes moved but which has no version keeps its old
position; relations are not recounted (48,899 relation versions that day); tier 2 keeps the seed's rows (the
patch recount of "The stream, tier 2" is not wired in); area quests do not age.

**The Europe test (started 11-13, 13:07):** `tools/stream/europe-test.sh`, log `logs/stream-europe.log`, state
in `.scratch/stream/europe-west/`. After the world count ends: the Europe clips 11-08 to 11-13 counted whole for
europe-west's cities with `--dump-state` (one engine, about 2 min each), the 11-08 one as the seed, then the day
diffs 5171-5175 applied one at a time, each followed by a check against that day's count. The clips of those
days are pinned in `~/Code/.osm-data/europe/pins.json` (unpin when done). Result: below.

**The Europe test: the result (11-13, 16:35 to 17:04, after the world count ended).**
- **`--dump-state` changes nothing else, and costs nothing visible.** Days 08 and 09 held against the old
  engine's `--dump-matches` of the same clips: 4,623,562 and 4,624,345 open unhidden matches, equal both ways
  (0 only new, 0 only old). Each whole clip counted in 55.6 to 57.9 s (the old engine's count of 11-09: 89.6 s,
  under other load), due searches included. Main's engine was rebuilt after this (`installDist`).
- **The seed:** 5,472,907 rows from the 11-08 count, 706,179 of them waiting for a date; 6.1 s.
- **A day through `apply`: 171 to 256 s,** of which reading the planet's day diff in Python 106 to 164 s (the
  same for any region), the small PBF 24 to 32 s, the engine 1.7 to 2.2 s, the state 31 to 58 s (growing with
  the node overlay, 492 MB after five days).
- **Tier 1 is exact for nodes and ways, five days running, ageing included.** Every difference is a relation:

| day | tier 1, state | full count | only in the state | only in the count | tier 2 (seed's rows), only state / only count | of the count's, on touched elements |
|---|---|---|---|---|---|---|
| 11-09 | 3,239,807 | 3,239,807 | 0 | 0 | 34 / 324 | 316 |
| 11-10 | 3,240,633 | 3,240,634 | 0 | 1 relation | 178 / 956 | 922 |
| 11-11 | 3,241,307 | 3,241,308 | 0 | 1 relation | 212 / 1,380 | 1,321 |
| 11-12 | 3,242,161 | 3,242,160 | 2 relations | 1 relation | 272 / 2,040 | 1,960 |
| 11-13 | 3,242,868 | 3,242,867 | 2 relations | 1 relation | 434 / 3,146 | 3,038 |

  The relations: r21949748 (AddBuildingType) opened on 11-10 and the state lacks it; r5328319
  (AddOpeningHours) and r21447069 (AddBuildingLevels) closed on 11-12 and the state still has them. No way
  missed a place, no moved node changed a way's quest, no due date was missed or early.
- **Tier 2, kept from the seed, drifts by about 700 differences a day** (3,580 of 1.39M after five days, 0.26%).
  96 to 98% of the count's extra quests are on elements the diff touched (an edited building gets
  AddRoofShape and AddHousenumber, an area quest, so tier 1's recount does not reach them); the rest (8 to 108)
  are on untouched elements: neighbours and area quests ageing.
- **So the next gaps, by size:** tier 2 (the patch recount of "The stream, tier 2", which needs the map data
  around each touched element: a day clip here, a store in the world), then relations (one a day or so here;
  48,899 to 55,199 relation versions a planet day), then area quests' due dates. The world seed is a whole
  recount of chain4's cut: chain4's 128 files took 4.4 h of engine (15,853 s summed), 8.9 h on the clock
  with the daily window and waits for memory.

**Every row checked, and dates for the 0.5 and 2 settings (11-13, evening).** `check` compared only the open
set; it now holds every tier-1 row too (position, variant bits, dates; the note flag apart, since `apply`'s
runs have no notes clip). On the first run's 11-13 that showed the default setting exact in every bit, but
the 0.5 and 2 settings drifting (838 matches the count had and the state lacked, 173 rows with other bits:
they had no dates), and untouched ways whose nodes moved off by a median 0.3 m (774 rows, 90% under 3.2 m,
max 30 m; that position is what a place counts by). So `--dump-state` now dates each setting (a DUE row's
flags carry `M_NOW`, `M_05` or `M_2`; a dump with no bit there means the default). Main's engine with it:
still equal to the old engine's dumps on 11-08 and 11-09, snapshot unchanged with the option off (only the
commit and run time differ); the pass 57 to 65 s against 52 to 54 s (about 12% more, so about 5 h of engine
for the world seed); the seed 6.83M rows, 2.06M of them dates (0.71M before). Rerun of the five days: no
variant bit differs on any day; tier 1 is left with the relations and the moved-node positions.

**Untouched tier-2 differences, by quest:** on 11-13, 100 of the 108 the count has and the state lacks are
area quests opening by age (CheckExistence 72, AddCycleway 20, AddTrafficSignalsSound and -Vibration 8);
8, and 15 the other way, are neighbours (AddHousenumber, crossings). So area-quest dates are about 20 a day
here, tier 1's own changes about 1,000: the first world seed goes without them (the stream reseeds with each
StreetComplete release anyway), recorded as a known gap.

**Tier 2 in `apply`: built and run on the five days (11-13, evening).** `stream.py apply --tier2-clip`,
`tools/stream/tier2.py`, `tools/stream/europe-t2.sh` (state in `.scratch/stream/europe-west/t2/`, log
`logs/stream-t2.log`). After tier 1's small PBF, the ground the diff touched (as "The stream, tier 2", plus
the old position of every row of a touched element) becomes rectangles of 50 m cells with a 300 m ring; the
rectangles are counted as cities on the day's clip (`map_data`, the one place a world store would answer);
inside each rectangle and its own city every row (all quests, tier 1 too) is replaced by the recount's
(splice). The parents of a changed node come from a way store of the seed clip (`stream.py ways`: 21.4M
ways, 168M refs, 3.7 GB, 7 min) plus the diffs' ways since.

| day | rectangles, km2 | nodes the area runs read | tier 1 differences | tier 2 differences (inside a rectangle / outside all) | control, inside the day's rectangles |
|---|---|---|---|---|---|
| 11-09 | 81, 15 | 0.95M | 0 | 8 (0 / 8) | equal (42,399 and 17,332) |
| 11-10 | 82, 22 | 1.18M | 0 | 30 (1 / 29) | equal |
| 11-11 | 104, 111 | 2.05M | 0 | 55 (1 / 54) | equal |
| 11-12 | 189, 140 | 3.62M | 0 | 98 (38 / 60) | tier 2: 36 AddHousenumber the recount lacks, 1 extra |
| 11-13 | 104, 298 | 3.71M | 11 (2 ways) | 130 (60 / 70) | tier 1 and 2: 2 Dublin ways the recount has (19 rows) |

- **Against tier 2 kept from the seed (3,580 differences on 11-13), 130.** Tier 1 is exact in every field on
  four days (positions of ways whose nodes moved, and the three relations, now right).
- **Outside every rectangle: area quests ageing** (CheckExistence, AddCycleway, the traffic-signal sound and
  vibration quests), 8 to 70: the area-quest dates the dump lacks.
- **Inside: the recount's own disagreements, brought in by the splice.** 11-12: 36 AddHousenumber the whole
  count has and the recount lacks (AddHousenumber depends on the order of the map data, engine/README.md); they
  stay on 11-13. 11-13: ways 71455532 and 168339841 lie on Dublin's boundary; the recount counts them, the whole
  count has no row for them at all. The engine's own point test puts both positions inside Dublin (checked with
  its arithmetic), so the cause is elsewhere: not traced. The delta form (the recount's own flips) would keep
  both out; the splice was the first choice because it needs only the new day's data.
- **Cost a day: 5 to 7 min** (300 to 432 s): reading the planet's diff in Python 110 to 156 s, the small PBF
  27 to 35 s, the cover 38 to 80 s, the engine over the whole clip for the rectangles 23 to 36 s (its area runs
  0.9 to 8 s; the whole count's area pass for these cities is about 25 s), the splice and state 30 to 60 s. The
  engine still reads the whole clip for its main pass; with a store, the rectangles' map data (1 to 4M nodes a
  day here, against 14.8M in London alone) is all it needs.

**Tier 2 in the delta form (11-13, night; the owner held the world seed for this).** The splice brought the
recount's own disagreements with a whole count into the state. Two probes, before building anything, asked
whether the delta form would keep them out: it does only if the old-day recount of the same rectangles has the
same disagreement.
- **The 36 AddHousenumber of 11-12:** 11-12's rectangles recounted on the 11-11 clip lack all 36 too (the whole
  11-11 count has them). So the recount's change between the days does not touch them, and the delta leaves the
  state's rows alone.
- **The two Dublin ways of 11-13 (71455532, 168339841):** 11-13's rectangles on the 11-12 clip have the same 9
  rows each, at the same position. Unchanged, so kept out.
- **The Dublin cause, traced:** the two roads are Dublin's boundary, and their centres lie 3 and 4 mm from it
  (2.6e-8 and 4.0e-8 degrees). The whole count, with all three cities or with Dublin alone, puts them outside
  (no row at all); the dump stores positions at 1e-7 degrees (about 1 cm), and at that rounded position the
  engine's even-odd test says inside. One step of 1e-7 south says outside. So `tier2.inside`, deciding on the
  dump's position, kept rows that the engine itself had not put in the city. Any recount whose own city test is
  a rectangle meets this for elements within a centimetre of a boundary; the delta keeps an existing
  disagreement out, but an edit to such an element would still bring its rows in. A full fix would hand the
  engine the real outline (the rectangle cut by the city) so the engine decides at full precision.
- **Built:** `stream.py apply --tier2-old-clip Y` (yesterday's clip): the rectangles are counted twice, on
  yesterday's clip at the state's clock and on today's, and `tier2.delta` compares the two per (element, quest)
  group of rows (a match and up to three dates). Old absent and new present: set to new. Old present and new
  absent: removed. Both present and different: set to new only if the state holds the group. Equal: untouched.
  Each case is counted, with how often the state disagreed with the old recount (the measure of drift). The delta
  never heals: the splice resynced everything inside a rectangle, earlier misses included, so the measure is the
  total of tier-2 differences each day. In a world store this means "the map data of these boxes at D-1" too,
  asked before the diff goes in. `tools/stream/europe-t2d.sh` (state `.scratch/stream/europe-west/t2d/`, log
  `logs/stream-t2d.log`); `tests/test_stream_delta.py`.

**The delta form on the five days: the result (11-13, 20:05-20:46).** Against the splice (`t2/`, same seed,
same diffs, same rectangles):

| day | tier 1, splice / delta | tier 2 differences, splice / delta | delta's inside a rectangle | seconds a day, splice / delta |
|---|---|---|---|---|
| 11-09 | 0 / 0 | 8 / 8 | 0 | 289 / 325 |
| 11-10 | 0 / 0 | 30 / 30 | 1 (CheckExistence) | 302 / 298 |
| 11-11 | 0 / 0 | 55 / 55 | 1 (CheckExistence) | 286 / 339 |
| 11-12 | 0 / 0 | 98 / 73 | 12 CheckExistence, 1 AddHousenumber the state has extra | 405 / 457 |
| 11-13 | 11 / 0 | 130 / 99 | 27 CheckExistence, 1 AddCycleway, the same extra AddHousenumber | 386 / 434 |

- **Tier 1 exact in every field on all five days**, and the 36 AddHousenumber and the two Dublin ways stay out.
- **What tier 2 has left is area quests ageing** (CheckExistence, AddCycleway, the traffic-signal sound and
  vibration quests), 98 of 99 on 11-13, plus one AddHousenumber (way 1577774915) that the 11-12 recount has and
  the whole count lacks, new that day, so the delta took it in as an addition. Inside the rectangles the delta
  keeps the ageing misses the splice resynced (1 against 27 on 11-13): it never heals, as expected. So the next
  gap by size is the area quests' dates, about 20 a day here.
- **Cost:** the second engine run adds about 35-50 s a day (tier 2 160-285 s against 100-235 s).
- **The drift counters measure the overlap with tier 1, not drift:** "added, the state had it" (449 to 1,098 a
  day) and "removed, the state lacked it" (173 to 289) are mostly tier 1's own replacements of touched elements,
  made before the delta. To read drift from them, count tier-2 quests only. Not done.
