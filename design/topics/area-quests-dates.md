## Area quests' dates (2026-11-13, night)

The last tier-2 gap the delta form left: area quests opening by age (CheckExistence, AddCycleway, the traffic-signal
sound and vibration quests...), about 20 a day on europe-west, 98 of the 99 differences on 11-13. The main pass
dates a waiting quest by asking the element at 40 years ahead and halving (about 14 evaluations of one element);
an area quest asks a whole map data at once, and London's AddCycleway is about 2.8 s a run, so halving whole cities
does not fit. The design (advisor-checked):
- **A horizon, not 40 years:** an age area quest runs once more at asOf + `AREA_DUE_DAYS` (64,
  `-Dopenquests.areaDueDays`; [Run.AHEAD]), in city mode with `--dump-state` only. Its results not open now are the
  candidates. Dates beyond the horizon are not looked for: the sidecar's `areaDueDays` says how far the state's
  area dates reach, and the stream must reseed before then (it reseeds with each StreetComplete release anyway,
  and the second world reference is the 12-07 planet).
- **The day on a small map data:** the candidates of one z16 tile share a map data of that tile with a 300 m ring
  (the ring the tier-2 recounts found to reproduce a whole city), built from the city's records as the tile mode
  builds its tiles. On it the SC port (not its fast twin, whose shared searches belong to the whole city) is asked
  at asOf and at the horizon: an element the small data does not give at the horizon, or gives already now, stays
  undated (counted). The rest are halved together, one run per distinct middle day: 6 levels for 64 days.
- **Rows:** a DUE row at the default setting (the 0.5 and 2 settings are not dated for area quests), hidden flag as
  for a match. The candidate list carries the city, so an element in two cities is dated in each, as it is counted.
- **Not checked by the design:** a quest that opens and closes again within the horizon (the halving assumes it
  stays open, as the main pass does).

`AreaDatesTest`: four benches (CheckExistence, six years since `check_date`, the edit recent), at asOf 2026-12-01:
one open now, two within the horizon, one after. Two dates written; for each, a whole count the day before has it
closed and one on the day has it open. `tools/stream/europe-area.sh` (log `logs/stream-area.log`) waits for the
world seed, installs the engine, runs every engine test, counts the 11-08 clip again with the dates, holds them
against the whole counts with `.scratch/stream/areacheck.py`, and streams the five days from that seed
(`.scratch/stream/europe-west/t2a/`). The baseline from the old seed: 108 area quests open on untouched ground over
11-09..11-13 (CheckExistence 72, AddCycleway 20, the signal quests 8, and 8 that neighbours opened: AddEntrance,
AddBarrierOnRoad, AddBarrierOpening, AddChargingStationSocket); none dated.

**The result on europe-west (11-14, 03:07-03:11).** Every engine test passes with the dates in. The 11-08 recount
with `--dump-state` dated **1,462 candidates, 1,462 dated, 0 undated** (the small map data agreed with the whole
city every time), the dating adding about 5 s in all to a 71 s engine pass (London: 1,305 candidates in 581 tiles,
5,190 runs, 3.2 s). Its dump is the old 11-08 dump plus exactly those 1,462 DUE rows, nothing else changed
(`.scratch/stream/seedsame.py`). Against the whole counts of 11-09..11-13 (`areacheck.py`): of the 108 area quests
opening on untouched ground, **100 dated on the day, 0 on another day**, 8 without a date, all quests a neighbour
opens (AddEntrance 3, AddBarrierOnRoad, AddBarrierOpening, AddChargingStationSocket, AddKerbHeight,
AddTactilePavingKerb), which ageing cannot date; and **no date up to 11-13 without such an opening**. The dates on
untouched ground reach only seed + 64 days; inside the recount rectangles the delta form rolls the horizon on (the
recount at today's clock dates up to today + 64, the one at yesterday's clock up to yesterday + 64, and the delta
applies the difference; both recounts print their "area dates" lines in `t2a/work/t2/`).

**The five days streamed from the dated seed (`t2a/`, the delta form, 11-14 03:11-03:51).** Tier 1 exact in every
field on all five days, as before. Tier 2 differences after each day, against the delta form without area dates
(`t2d/`):

| day | t2d (no area dates) | t2a (area dates) |
|---|---|---|
| 11-09 | 0 / 8 | 0 / 0 |
| 11-10 | 0 / 30 | 0 / 0 |
| 11-11 | 0 / 55 | 0 / 0 |
| 11-12 | 1 / 72 | 1 / 0 |
| 11-13 | 1 / 98 | 1 / 0 |

(only in the state / only in the count, of about 1.39M open tier-2 quests). The one row left is
`w1577774915 AddHousenumber`, which a diff touched on 11-12: that day's recount counts it and the whole count does
not (the control line: recount against whole inside its rectangles, the same family as the 36 AddHousenumber the
whole count has and the recount lacks on 11-12), and the delta applied the recount's word. So every ageing gap is
closed and what is left is a recount's own disagreement with the whole count; the Dublin boundary ways the 11-13
recount still counts stay out, as in t2d. A day costs 6.5-10 min here (reading the planet diff about 2 min, the
two tier-2 recounts 1.5-4 min, the engine's area runs 2-10 s of that).
