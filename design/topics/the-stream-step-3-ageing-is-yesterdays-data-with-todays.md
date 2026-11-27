## The stream, step 3: ageing is yesterday's data with today's clock (2026-11-10, night)

Plan step 3 of "The stream: probed, and the plan". A quarter of the measured flips had no edit behind them.
`.scratch/due/due.py` (gitignored; `RESULT.txt`). No engine change: `--today` moves the clock.

**The test.** The 11-08 clip of europe-west counted again with the clock at 11-09T00:00Z, same notes clip,
every match dumped, against the two full counts of `.scratch/diff-flips/`.
- **On elements the diff did not touch it opens exactly the 342 quests the full counts show opening, and
  closes the one they show closing by a note.** 339 are agedOnly (CheckShopExistence most of them); the
  other 3 opens and the close are the day's note flips: the notes clip holds each note's dates, so the
  moved clock replays the notes too.
- **One measured flip is not predicted:** AddIsAmenityIndoor on node 302134936 closing, the neighbour flip,
  which tier 2's patch recount has.
- **9 more quests were due on elements the diff then touched; 1 of them is open on 11-09.** The edit's
  re-evaluation decides those, not the clock.
- So on this day the three parts explain every flip: the element's own edit (tier 1), the ground an edit
  touched (tier 2), and the clock with the notes clip.

**The due-date table, sized.** The same clip without notes (the engine refuses a clock past the notes
dump's end), clock moved on, against a no-notes count at 11-08 (4,626,985 matches):

| clock moved by | quests opened | closed |
|---|---|---|
| 2 days | 728 | 0 |
| 7 days | 1,595 | 0 |
| 30 days | 4,122 | 0 |
| 365 days | 64,992 | 0 |
| to the year 2100 | 971,545 | 0 |

- **The clock only opens.** No quest closed at any later clock, so a due date is one date per (quest,
  element): the first day it matches. That holds for these three cities and v64.1's quests.
- **About 970,000 quests wait for their date**, a fifth again of the 4.6M open ones: AddWayLit 191k,
  AddPathSurface 145k, AddRoadSurface 135k, CheckExistence 131k, CheckShopExistence 75k. A year brings
  65,000 of them (CheckShopExistence 23k, AddOpeningHours 13k, CheckExistence 12k); a day 140 to 360, by the horizon averaged over.
- **What was not built:** the table itself. These runs find a due date only to the nearest clock tried;
  an engine output "first day this matches" does not exist. An edit to an element replaces its due
  dates, as it replaces its open quests.

**Next:** step 5, the store (open quests, due dates, node locations, "what lies in this box", "which ways
hold this node") and one planet day's cost through it.
