## The stream, tier 2: only the ground a day's diff touched, recounted (2026-11-10, night)

Plan step 4 of "The stream: probed, and the plan": the 40 area quests, which read their surroundings. The
test is daily, not per minute: mark the ground the day's diff touched, recount only there, compare with the
two full counts of `.scratch/diff-flips/`. `.scratch/tier2/patch.py` (gitignored; `plan`, `count`,
`compare`; a `RESULT.txt` per ring in `r100/`, `r300/`, `r1000/`). One engine change, opt-in:
`-Dopenquests.areaPaddingM=<metres>` sets the ring around a city's box (default 1 km, snapshots unchanged).

**How.** europe-west, 11-08 to 11-09, planet day diff 5171.
- **The ground touched**, as cells of 50 m in each city's own flat grid, then one more cell all round:
  a changed node's old and new place; every segment of a changed way, old and new, and a closed way's whole
  bounding box; for a way that is not in the diff but holds a changed node (a moved node does not re-version
  its ways; found by reading every way of both clips), the segments next to that node and the way's own
  quest position; a changed multipolygon's bounding box. Changed `route`, `public_transport` and
  `restriction` relations (165) were left out. Ferry routes would have been covered; the summit quests
  read hiking routes and have no match in these cities; the other quests were not checked one by one.
- **Rectangles.** The cells are merged greedily: two rectangles become their bounding box when that box with
  its ring is no larger than the two with theirs. Each rectangle is a "city" for the unchanged engine (its
  parent's country codes and time zone, the same quests file and notes clip), counted on both clips.
- **Three comparisons**, inside the real city polygons. *Control:* the patch count against the full count of
  the same day, inside the rectangles; any difference there has nothing to do with the diff. (The city
  test is even-odd over the boundary's rings; it puts all 178,000 patch matches the full counts also have
  inside their city.) *Splice:* the
  old state with the rectangles' matches replaced by the new day's patch count. *Delta:* the patch counts'
  own flips (new less old) applied to the old state.

**Result.**

| ring | rectangles | control, each day | splice | delta | London: nodes read, area runs |
|---|---|---|---|---|---|
| 100 m | 90 | 1 match the patches lack (of 14,775) | 1 wrong | exact | 2.1%, 0.5 s |
| 300 m | 81 | equal, all 17,055 and 17,337 | exact | exact | 5.3%, 2 to 5 s |
| 1 km | 48 | 1 match the patches have extra (of 56,575) | 1 wrong | exact | 22.7%, 12 to 14 s |

The whole of London is 14.8M nodes and 26.7 s of area runs. "Exact" leaves out the aged flips, as planned.
- **All 350 flips an edit caused lie inside a rectangle, and the delta reproduces them at every ring:** 316
  opened, 34 closed. The other 8 of the 358 measured tier-2 flips are CheckExistence opening by ageing, on
  untouched ground: step 3's. (At 1 km one of the 8 falls inside a rectangle and the delta has it too.)
- **The patches are 1.1% of the tier-2 state** (14,775 of 1,387,420 matches at 100 m) and 12 km2 of London's
  1,595. Two changed ways are three quarters of London's 2,805 touched cells: a `landuse=residential` outline
  (way 23298277, 1,249 cells) and Harrow Lodge Park (way 23051299, 894), each covered by its whole box.
- **The two control differences**, the same on both days, so the delta cancels them and the splice does not:
  at 100 m the patches lack AddMaxHeight on way 437671407 in Lisbon, which the 300 m run finds (not traced;
  a bridge further than 100 m from the rectangle is the likely cause). At 1 km a patch gives AddHousenumber
  for way 1176630809 in London where the whole city does not (not traced; AddHousenumber depends on the order
  of the map data, engine/README.md). So a local count is not always the whole-city count, at any ring.
- **Splice or delta is a design choice of the store.** The delta needs the old evaluation of the same
  ground but never brings a patch's disagreement into the state; the splice needs only the new one and did
  bring it in, once in 15,000 matches.

**What this does not show.**
- **A radius.** One of the 358 flips was on a neighbour (20 m). The day settles that the method works, not
  how wide the cover or the ring must be.
- **A speed-up.** The engine still read the whole clip for each run (37 to 69 s a pass); and the plan step
  read every way of both clips to find the parents of changed nodes, 10 minutes a clip in Python. A store
  must answer both "what lies in this box" and "which ways hold this node" without a scan.
- **The stream form.** Per day, not per minute or changeset.
- **Other days:** an import, a rural region, a day on which a route relation matters.

**Next:** the same over the stored week and the four Europe regions if a radius is wanted (the plan step's
way scan is the slow part); due dates (step 3); then step 5, the store and one planet day's cost.
