## The stream, step 1: a day of minute diffs replayed, exact (2026-11-10, just past midnight)

The owner: "do it now". Plan step 1 and 2 above. `.scratch/stream-replay/` (gitignored; `fetch.py`,
`replay.py`, `RESULT.txt`, `events.tsv`; 120 MB of minute files). No engine change.

**How.** The 1,415 minute files of 2026-11-08 (sequences 7363129 to 7364543, found from the feed's state
files; 3.93M node, 747k way and 49k relation versions) read in order. Every node and way version inside the
three city boxes, 3,304 of them on 3,078 elements, became its own element in a synthetic PBF (a new id per
version, a way's nodes beside it), which the unchanged engine counted with `--dump-matches` in 2.7 s. Each
version's match set, in stream order, against the element's state before (the 11-08 dump) gives the events,
each with its minute and changeset. Tier 1 only, the 153 quests decided from the element alone.

**Result: the stream reproduces the day.**
- **606 net flips, the same 606 the two full counts show on touched elements; none extra, none missing.**
  No element ends the day in a state other than the 11-09 dump's. These are one fact, not two: net events
  per element add up to the final state less the state before. It proves that evaluating an element alone
  is exact and that the minute stream ends where the 11-09 clip does. It cannot see a wrong event in between
  or a wrong changeset; only the StreetComplete check below tests those.
- **The other 335 measured tier-1 flips have no event, as expected:** 331 opened by ageing, 4 by the two notes.
- **660 events from 113 changesets, in 82 of the 1,415 minutes.** 27 quests went there and back within the
  day (54 events), which a daily diff cannot see. One changeset made 100.
- **A changeset is not one unit of input:** of the 178 changesets with a version in the boxes, 27 span more
  than one minute file, at most 4. The minute file is what is applied; the changeset is what an event is
  credited to.
- **By editor (opened / closed):** iD 215 / 22, StreetComplete 46 / 111, JOSM 114 / 26, Every Door 17 / 73,
  StreetComplete_ee 11 / 8. Mappers with other editors open quests; StreetComplete and Every Door close them.
- **The changeset feed as a second check:** 69 StreetComplete changesets name a tier-1 quest and touch an
  element in the boxes; the stream shows that quest closing in 63. The other six were traced, and in none was
  the quest open before and left open after. Four touch only elements that match no quest in any version
  (AddBusStopShelter, AddSidewalk, AddParkingType, AddParkingAccess: in the boxes, outside the city polygons,
  or hidden; not told apart). Two are date quests on a counted element where the engine did not have the
  quest open yet (AddOpeningHours on node 11119491490, CheckShopExistence on node 2681302751 and way
  42527973): the mapper's app showed it earlier than the default resurvey interval the counts use.

**What the replay did not have to do, and a live stream must:**
- **Hold the state.** The before-state came from the 11-08 dump, and a way's node positions from the stream
  or the two clips (the day's last position, not the one at that minute). A stream needs the open-quest set
  and a node location store of its own.
- **Find the elements without the boxes' help at world scale:** here 3,304 of 4.7M versions were in the boxes;
  for the world all are, about 55 a second on average.
- **The clock.** Every version was evaluated at 11-09T00:00Z, not at its minute.
- **The day's edges.** The range is cut where the feed's state files say, not at 00:00:00Z, so up to a minute
  at each end can differ from the day diff. It moved nothing that day.
- **Relations** (49k versions) were not replayed; none flipped that day in these cities.
- **Tier 2,** ageing and notes, as planned.

**Next:** tier 2 (step 4) before due dates (step 3): the neighbourhood test decides whether this route beats
the others, and it is where the store is decided; due dates are low risk. What this cost at world scale is
still unmeasured: exact is not yet efficient. One more day or region of this replay costs about 10 minutes if wanted.
