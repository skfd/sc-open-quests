## Release 1: the world day, designed (2026-11-16, late evening; owner: "lets push towards first release")

Release 1 publishes a count of every place in the world for every day from 2026-11-01, each day every quest
(the rule in "Don't"). The pieces, in the order they are built. Nothing below is built unless it says so.

**Where a day runs.** Inside the planet store's daily run (`tools/stream/planet_store_day.py`), between `update`
and `loc advance`: there the node file still holds D-1 and both generations' tile indexes exist (`compact` keeps
only the newest generation readable, so the day must be read before it). The store and the world state move
together; the store never runs ahead of the state.

**Step 1, the seed: built, being checked.** `world_cells.py storecut` reads each plan file's padded box from the
store (`tilestore read`, ring 0, stamped with the store's day) into `cut/`, so `notes`, `count --state` and `report`
run unchanged. `tools/stream/store_lock.py` holds the store while it is read (HOLD; the daily run takes no day
while it exists, and keeps RUNNING while it works). The reader's blocks are bounded by size too (a blob must stay
under 32 MiB; byte-identical output on the clip's rectangles). Checks, in order: `tools/stream/storecheck_cities.py`
(the 32 European cities read from the store against the same day's clip, row for row), then two world files at
full size (f0, the most nodes; f19, the widest box: time and peak memory), then the seed at 11-01 against the
published 11-01 snapshots.

**Step 2, tier 1 for the world.** `world_state.apply` as it ran on 11-09..11-14, but with the store's node file
read-only (a `DenseLocations` that never saves: the store's `loc advance` moves the file). The diff read in Python
was two thirds of a day's 8-14 min; it is read once for both tiers.

**Step 3, tier 2 for the world.** `tier2.cover` as on Europe (the delta form: the same rectangles recounted on D-1
at D-1's clock and on D at D's, only the recount's own changes applied), with four changes for the planet:
- the cover in one global grid of 50 m cells, vectorised, not per city: `near_idx` loops over every city's box per
  point, which is 2,244 boxes for each of millions of changed nodes;
- changed ways' old refs, and changed relations' member ways, from the store's generation D-1 (a new `tilestore`
  lookup by way id through the way pair index), so no way index of our own. `NO_WAY_INDEX` (today's refs at
  yesterday's places) was measured equal on Europe's five days, but it has no refs for a **deleted** way, whose
  key then also misses the old-row lookup: its area-quest rows would stay. The lookup at D-1 covers both. Ways
  holding a changed node are left out (the same measurement; a tier-1 row of an untouched way can stay up to about
  1 m from its true point, which moves no count unless it crosses a cell edge);
- the rectangles split at cell edges, each a city with its cell's time zone and no country codes (gated by
  position, as every cell is); map data by `tilestore read --gen D-1` and the newest generation, ring 300 m.
**Checked (22:00):** after `update --prune-pairs` the generation before reads byte for byte as before the update
(the clip store, diff 5175), so both dates are readable until `compact`.
**Measured (`.scratch/manyrects/probe.py`, the clip store, random 150 m rectangles in inner London, 300 m ring,
area pass on, while the store's catch-up ran):** 100 rectangles: engine 6 s (pass 4.7); 1,000: 17 s (pass 14.4,
5.9M nodes read); 10,000: 157 s (pass 148, 57.9M nodes read over 9.7M in the PBF). So about 14 ms a rectangle
city on top of the map data, linear from 1,000 to 10,000 at the same data; whether it grows with the run's total
data is not measured (grouping by plan file bounds that). The store's read cost 97 s for 10,000 cities against
12 s for 1,000 over the same tiles: it opened each city's boundary file. A city's box is now read inline
(`"box"` in the cities file; `tier2.write_cities` writes it): 1.8 s, the same bytes. Still unknown: how many
rectangles a planet day makes.

**Step 4, notes and ageing at the clock.** Ageing is the state's dates against the clock (step 3 of the stream,
exact on Europe). Notes are not handled yet: `apply` has no notes clip, so a row keeps the seed's hidden flag until
its element is edited, and the note quest itself is not counted. Each day: notes opened and closed between D-1 and
D (the daily notes dump) set and clear the hidden flag on rows at the note's exact position, and the note quests
are counted from the dump at the clock.

**Step 5, counts per place from the state.** The seed's snapshots come from the engine; a day's must come from the
state. **The engine assigns places, not a second test in Python:** a test on dumped positions already disagreed on
Dublin's boundary (1 cm rounding), and a million polygons would multiply that. So the state dump carries each
row's places as the engine found them (`--dump-state` extended, or a sidecar), decided **before** the seed runs,
since a seed without them is a second planet count. A day's rows (tier 1 and the two rectangle recounts) come with
their places the same way; per-place counts move with the day's changed rows and the rows whose date comes. Also
the aged split and the three resurvey settings, as the engine's snapshots carry them.

**Step 6, the checks every day.** The gate is like for like: Europe's 32 cities from the world state against
today's engine on the Europe clip of the same instant (11-02 to 11-16 are pinned; 11-01 is cut from the history
file at 11-01T00:00Z while it is on disk, step 7). A day that misses the 0.1% bar stops the run, as the store's own
check does. The 147 published city snapshots are reported beside it, not gated: 11-01 and 11-02 are v64.0, and
Canada's and Germany's extracts are not at 00:00Z (the 11-08 report's Regina -0.42% was that).

**Step 7, catch up and publish.** The store cut again at 2026-11-01T00:00Z from a new history file (and, from the
same file, the Europe polygon at 11-01T00:00Z for step 6's day one) and held there (HOLD) until steps 2-6 exist, then store and state together, one day at a time, to today; then daily. Publishing:
place data on the R2 subdomain (DESIGN, "Place statistics for the whole world"), its DNS step the owner's.

**The world publishes the default resurvey setting only (the owner, 2026-11-17).** The engine dates settled
matches and area quests at the default setting only, so the 0.5 and 2 counts would drift from the seed; the site
shows the default. The world's counts and its daily gate are the default setting's; city snapshots keep all three.

**Before release 1, two rules.** Steps 2-6 are built and held against a clip-sized world-mode store first
(`.scratch/tiles/store-rsw`, the Europe clip with cells as cities), where every day has a whole count to compare
row for row; only then the planet. A StreetComplete release before release 1 means a reseed at the store's day
(the state is one quests file's).

### What tier 2 must recount, from the code (2026-11-17, overnight; fork E of the release-1 build)

Tier 2 marked a changed closed way's or multipolygon's whole box; on planet day 5172 the largest was 2.7M km2, and a
25 km2 cap lost 69% of tier 2's own cells on the Europe day. The 40 area quests (`engine/src/main/kotlin/ported/`,
paths below under `quests/`) were read for what OTHER elements can change whether an element is a quest, and how
far that reaches. Only three things read a polygon's inside for other elements; everything else is the element's
own quest at its own quest point, or happens on vertices and segments the outline marking already covers.

| quest (file) | what else decides it | reach | how the cover catches it |
|---|---|---|---|
| AddIsAmenityIndoor (`amenity_indoor/AddIsAmenityIndoor.kt`) | a building (`building and building != roof`) holding the node | the building's inside | **container**: a changed building's whole box; the changed node marks itself |
| AddLevel, AddLevelThing (`level/AddLevel.kt`, `AddLevelThing.kt`, `LevelUtils.kt`) | a mall or station polygon (`shop ~ mall\|department_store`, `aeroway = terminal`, `railway = station`, `amenity = bus_station`, `public_transport = station`) holding the node; elements with `level` inside it make it multi-level | the polygon's inside | **container**: its whole box; a changed `level` element: R_CONTAINED (100 m) around it |
| AddHousenumber step 5 (`address/AddHousenumber.kt`) | an addressed area that is no building (`nonBuildingAreasWithAddressFilter`), or any area way with an address node on its outline (`areasWithAddressesOnOutline`), holding the building's centre | the area's inside | **container**: its whole box. The outline case needs to know the vertices' tags: from the diff for changed nodes, or from an address-node index (`address_nodes`, not built) |
| AddHousenumber steps 1, 4 | address nodes on the building's outline or inside it | the building's inside, for the building's own quest | the building's quest point (centroid); a changed address node: R_CONTAINED around it, for the building holding it |
| AddHousenumber step 2 | a relation that is no multipolygon, with an address, holding the building | membership | **new**: such relations' member ways (lines and centroids) |
| AddHousenumber, AddIsAmenityIndoor step 3 | the map data's bbox: a building not completely inside it is no quest | the recount's ring | the recount's own limit (300 m ring), not a changed element |
| AddChargingStationSocket (`socket/AddChargingStationSocket.kt`) | `man_made = charge_point` nodes inside the station way | the station's inside, for its own quest | its quest point; a changed charge point: R_CONTAINED around it |
| AddAddressStreet (`address/AddAddressStreet.kt`) | `associatedStreet`/`street` relations holding the address; `addr:interpolation` ways' vertices | membership; vertices | the relation's member ways and **new: its member nodes**; interpolation ways by their segments |
| AddSummitCross, AddSummitRegister (`summit/SummitMarkingsUtil.kt`) | `sac_scale` hiking paths and **`route = hiking` relations** within 10 m of the peak | 10 m of the line | changed paths by their segments; **new: hiking routes' member ways** (tier2.WANTED_REL left them out: a real gap) |
| ferry quests, AddMaxWeight (`ferry/*.kt`, `FerryUtils.kt`, `max_weight/AddMaxWeight.kt`) | `route = ferry` relations: the relation is the quest, its member ways are not | membership | the relation's member ways and their quest points |
| AddMaxHeight (`max_height/AddMaxHeight.kt`, `MaxHeightUtils.kt`) | bridges (and `building = roof`, overhead pipelines) crossing a road, road and railway vertices | the crossing: `intersects` is outlines crossing (`util/math/ElementGeometryMath.kt`), not an inside | segments |
| AddEntrance, AddEntranceReference (`building_entrance*/`) | building outline vertices, incoming and private footways' vertices | vertices | segments |
| AddKerbHeight, AddTactilePavingKerb (`osm/kerb/KerbUtil.kt`) | footway vertices, `barrier = kerb` ways' vertices, crossing ends | vertices | segments |
| AddCrossing, AddBarrierOnPath, AddBarrierOnRoad (`osm/WaysCrossingUtils.kt`, `DetectWayBarrierIntersectionUtil.kt`) | shared vertices and their neighbours' places | vertices and the next segment | segments |
| AddCrossing\*, AddRailwayCrossingBarrier, AddTactilePavingCrosswalk, AddTrafficSignals\*, AddStileType, AddStepCountStile, AddBollardType, AddBarrierOpening, AddMaxHeight's nodes | the vertex sets of included or excluded ways | vertices | segments |
| AddOneway (`oneway/AddOneway.kt`) | roads meeting the way's end vertices | vertices | segments |
| AddForestLeafType (`leaf_detail/AddForestLeafType.kt`) | its own area (under 1 ha) | itself | its quest point (centroid) |
| AddRoofShape, AddCycleway | the country at its own centre | itself | its quest point |
| AddBicycleIncline | its own length (under 200 m) | itself | its segments |
| AddAmenityCover, CheckExistence | nothing (getFeature of the element) | itself | itself |

**The rule, in `tools/stream/world_tier2.py`** (`container_kind`, `contained_kind`, `wanted_relation`):
- a changed closed way's ring (new at D, old at D-1) or a changed multipolygon is marked **whole** if its tags make it
  a container (above), or its box is at most `SMALL_BOX_KM2` (0.25 km2: cheap, and a planet diff's deletions carry no
  tags, so a deleted building is still boxed); otherwise by its outline and its **quest points** (the half-length
  point and the polygon centroid, as SC places a way's or area's quest), which every changed line now gets;
- the old ring's tags come from `old_tags(kind, id)`; without it the new tags stand in (logged as unknown);
- a changed node that a container reads (an address, a `level`, a charge point) marks `R_CONTAINED` (100 m) around
  its old and new place, for the container's quest point; so does a deleted node no changed way held (its tags are
  gone, and such deletions are mostly points of interest);
- relations: multipolygons (member lines, boxed only as containers), street relations (member ways and nodes),
  ferry routes, **hiking routes**, **addressed relations that are no multipolygon**;
- `CAP_KM2` (5,000 km2) is only a logged safety net: no container comes near it.
- **The merge changed too** (`merge_rects_overlap`): tier2.merge_rects counted two padded boxes' sum, so a long strip
  grew one 50 m run at a time across a polygon's whole inside (a 7 km outline became its 52 km2 box). The gain now
  counts what the two padded boxes share, with 0.1 km2 of slack (a rectangle city costs the engine about 14 ms):
  the same outline is 5 rectangles, 8.6 km2.

**Not exact yet, and what makes it exact:**
- **Old tags.** A planet diff's deletion has no tags and no refs, and a modification only its new tags. A big way
  or multipolygon that stops being a container (a 2 km2 campus losing its address, a station polygon deleted) is
  marked by its outline only. Fix: `tilestore ways` returning each way's tags at D-1 (the payload has them; a small
  Rust change), passed as `old_tags`; the same for relations through the relation store.
- **Addresses on an area's outline.** Without an index of address nodes, only addresses changed that day are seen.
  Fix: a sorted array of every address node id, built once from the store and moved by the diffs (`address_nodes`).
- **Containers wider than R_CONTAINED.** A changed address or `level` node inside a building or mall whose quest
  point is more than about 100 m away (plus a cell's padding) is missed. Fix: look the containers up (the store's
  tiles at the node), or measure how often it happens on a real day before choosing a radius.
- **A multipolygon's old members** are not known (only its new ones, by `member_refs`); its old rows cover its own
  quest.
- **A changed ring of a container multipolygon.** An untagged closed way is usually a multipolygon's member; when
  only the way changes, the relation is not in the diff, so a big building or mall multipolygon's changed outer ring
  is marked by its outline. Fix: the relations holding a changed way, with their tags (a reverse lookup in the
  relation store, Rust).

**Measured (2026-11-17, night).**
- **Europe day, diff 5175, europe-west's three cities, tier2.cover against the world cover on the same inputs**
  (`WORLD_TIER2_EUROPE=1`, log `logs/world-tier2-europe-rule.log`): of tier 2's 103,785 cells, 7,401 are justified
  by the rule (not from a box, or from a box the rule marks) and **0 of them lie outside the rule's rectangles**.
  96,384 came only from boxes the rule leaves to their outline; 81,470 of those fall outside its rectangles: 80,181
  from one `place = island` multipolygon (no area quest reads an island's inside), 1,277 from untagged closed ways
  (multipolygon member rings: safe unless their relation is a container, the gap above), 15 from
  `landuse = greenfield`.
- **Planet day 5172**, world plan, the 11-08 seed's rows, the node file read only (`.scratch/world-tier2/5172-rule/`,
  log `logs/world-tier2-5172-rule.log`), against fork A's run with the 25 km2 cap:

| | fork A (cap 25 km2) | the rule |
|---|---|---|
| marked cells | 10.0M | 5.31M |
| rectangles | 52,128 | 128,544 |
| km2 per date | 217,299 | 101,651 |
| rectangle km2: median, 90th, 99th percentile, largest | 0.19, -, 50, 1,207 | 0.49, 1.8, 4.9, 52.5 |

  626,044 closed boxes: 610,982 small and marked whole, 141 marked whole as containers (115 addressed areas, 18
  buildings, 6 malls or stations, 2 areas with an address on the outline), 14,921 by outline (their boxes 6.4M km2
  together; 5,850 of them with old tags unknown, 11,701 ways with outline addresses unknown); 9 over the safety cap,
  none a container, the largest 2.7M km2. Relations marked: 14,386 multipolygons, 330 hiking routes, 128 streets (2,659
  member nodes), 1 ferry, 1 addressed; 1,436 wanted relations had no member geometry (the store lookup gives it).
  Contained nodes: 17,455 addresses, 1,865 `level`, 80 charge points, and **390,467 deleted nodes no changed way
  held**, which mark 965k of the 5.3M cells: most are vertices of deleted ways, whose refs a planet diff does not
  carry, so with old refs from `tilestore ways` (generation D-1) they drop out. Time: read the diff 123 s, old rows
  63 s, cover 146 s, rectangles 44 s, the engine's files 177 s.
  **The trade:** half the area, but 2.5 times the rectangles, since outlines no longer swallow their boxes; at about
  14 ms a rectangle city that is about 30 min of engine per date against 12, on top of half the map data. The slack
  (`MERGE_SLACK_M2`, 0.1 km2) is the knob: it also sets how wide a non-container polygon may be before its inside is
  no longer filled (about 2 km at 0.1 km2).

### The world day, rehearsed on the Europe clip (2026-11-17)

`tools/stream/world_day.py` (prepare before the store's update, finish after it; `run` for a rehearsal; `check`
against a whole count) and `tools/stream/world_europe_r1.py` (the driver; out dir `.scratch/r1/eu/` of the worktree
it ran in). The Europe clip of 11-09 as a world plan: 16 files, 57 cells, 15,875 places as parts plus the 32 cities'
own outlines (`osm-<city>`); a clip store cut at 11-09 and moved by the planet's day diffs 5172 on (polygon mode);
a sparse node index; the seed counted from the store (`storecut`, `count --state` with parts, 947 s at 8 GB a file):
50,273,232 rows, 16,682 place sets. Each day D is held against a whole count of the same plan from a fresh store cut
of D's Europe clip, with the seed's notes clips on both sides.

**Day 0 (the seed through the stream's own counting): exact.** 0 of 36,795,912 (element, quest) groups differ; 0 of
631,304 counts per place and cell (note quests by the engine included); all cells' open quests 29,983,203 both.

**Days 11-10 to 11-13, streamed:**

| day | groups differing (of 36.8M) | at the default setting | 0.5 / 2 settings only | outside the clip's polygon | the 32 cities' counts differing (of 5,306) | all cells open, whole / stream |
|---|---|---|---|---|---|---|
| 11-10 | 1,093 | 15 | 831 | 247 | 1 (by 1) | 29,989,003 / 29,989,161 |
| 11-11 | 2,390 | 45 | 1,754 | 591 | 3 (by 1-2) | 29,993,706 / 29,994,157 |
| 11-12 | 3,551 | 66 | 2,579 | 906 | 7 (by 1) | 29,999,555 / 30,000,246 |
| 11-13 | 4,489 | 83 | 3,118 | 1,288 | 7 (by 1) | 30,005,680 / 30,006,664 |

Rows are compared at the clock: a date the stream kept that has come counts as the open, aged match the whole count
writes (the same count). By cause:
- **Outside the clip's polygon** (1.6-7.5 km out): the moved store keeps edge ways a fresh extract of the clip drops,
  as the planet store's daily check found. Not the stream; it is also most of the all-cells difference.
- **The 0.5 and 2 settings only:** quests the seed did not date at those settings come open there (CheckExistence and
  other quests the match cache settles: `Engine.offerInZone` dates only `!isSure` matches; area quests are dated at
  the default only). The default setting, which the site shows, is not touched. Fix in the engine (date settled
  matches too, area quests at all three settings) or publish the default only.
- **At the default setting**, growing by about 20 a day:
  - most are a quest point moved by under a metre on an untouched way whose node moved (tier 1's known limit; no
    count changes unless it crosses a place's edge);
  - AddRoofShape of building multipolygons whose member way changed while the relation is not in the diff: the cover
    marks the outline, not the relation's quest point (Göteborg -1 from day one);
  - AddMaxHeight of roads under a changed bridge whose quest point lies outside the bridge's rectangles: the recount
    takes elements by centre, so a road crossing a rectangle is not recounted (Praha -2, Moscow -1);
  - a few recount-vs-whole disagreements on touched keys inside rectangles (AddMaxHeight again).

**Time per day** (the clip's share of the planet diff: about 42k nodes, 12.6k ways): read the planet diff 150-190 s,
old ways 1-4 s, store update 45-60 s, cover 2-3 s, rectangles 2-3 s (2,700-3,000 rectangles, 1,600-1,900 km2),
engine files 15-21 s, tier 1 215-245 s (16 engine runs, one per plan file), tier 2 reads 19 s, tier 2 engine
240-260 s, delta 31-34 s, notes 165-185 s, counts and note quests 200-285 s (16 engine runs): 20-23 minutes.

**What blocks the planet:**
1. **Loading parts per engine run.** Tier 1 and the note quests run once per plan file (all of a world's parts in one
   run do not fit: Europe alone has 502,597 part entries, and 8 GB ran out); a note-quest run is 120 s of which the
   pass is 0.2 s, the rest loading the file's 63k outlines. At 128 planet files that is hours a day. Needed: the
   engine kept running with its parts loaded, or the note quests as state rows with their places (the engine writes
   them at the seed; a day recounts only the cells whose notes changed).
2. **Notes' hidden flags over every row**: 165-185 s for 50M rows in one Python thread; the planet's 2 billion need
   the rows near changed notes found by position, or the files in parallel.
3. **The two cover gaps above** (a relation's quest point when a member way changed; roads crossing a rectangle):
   both need the elements whose geometry meets the marked cells, from the store, added to the cover.
4. **A rectangle city's parts index** spanned every part's whole box (a country: 512 x 512 cells per rectangle) and
   ran out of heap at 8 GB on 28,703 rectangles; now clipped to the city (engine `PolygonIndex(clip=)`, same answers).
   The planet's 128,544 rectangles still need their runs grouped (per plan file) and measured.

### Tier 2's two cover gaps closed (2026-11-17, afternoon; fork P3 of the release-1 build)

The rehearsal's default-setting residues (above) came from what the day's diff does not show. Built:
- **`tilestore context`** gains `--rel-geometry` (each asked relation's member ways from its relation store blob),
  `--vertex-ways` (every way an asked node is a vertex of, with its geometry, from the node's tile) and `--crossing`
  (the ways with a tag key whose segments cross given segments, with their geometry, from the tiles the segments
  cross). Exact against the 11-12 clip: 300 relations' member ways, 799 of 799 vertex ways, 0 of 203 crossings missed.
- **`store_context.DayContext`** asks them at D-1 (before the update) and at D (after it): the relations holding a
  changed way (their member lines marked, a container boxed, any other by the box rule) and their old rows; the
  untouched ways a moved node is a vertex of (their quest points at D-1 and D); the roads crossing a changed
  `over_road` way (AddMaxHeight's `bridgeFilter`) and the bridges crossing a changed road, each crossing a box from the
  road's quest point to the crossing (`crossing_box`), so one rectangle city holds the road's quest and the bridge (an
  area's map data is the ways with a node in its padded box).
- **`world_day` now asks the store context** (G's day never did, so F's container boxes never reached its cover).
- `_quest_points` weighs longitude at the line's own latitude (a fixed 0.63 put a 15.7 km road's half-length point at
  55.6 degrees 700 m off).

**The rehearsal again** (`.scratch/p3/rerun.py` in fork P3's worktree: G's 11-09 seed counts, a fresh clip store and
node index, each day checked against G's own whole count; 12 GB heap), default-setting groups different:

| day | G | P3 | the 32 cities' own counts different (G, P3) |
|---|---|---|---|
| 11-10 | 15 | 3 | 1, 1 |
| 11-11 | 45 | 4 | 3, 1 |
| 11-12 | 66 | 9 | 7, 4 |
| 11-13 | 83 | 9 | 7, 4 |

Every "different" from a moved node and the Praha and Moscow bridges are gone; the residue no longer grows. Left
(11-13), each traced:
- **5 groups, relations changed by their tags alone** (2213778, 2213779 Salzburg and 3252407 Göteborg on 11-08,
  `building:levels` added; 5328319 London, 3458546 München on 11-12): the rehearsal's `clip_keep` keeps a relation
  only with a kept member, so a tags-only change is dropped before the cover. A rehearsal artifact: the planet runs
  without `clip_keep`. Fix if the rehearsal is rerun: keep the diff's relations the D-1 store holds.
- **1, w1577774915 AddHousenumber**: the order effect traced on 11-14 (DESIGN, "The one tier-2 row left, traced").
- **3, not traced: r13409862 AddRoofShape and AddBuildingLevels** (a TUM building multipolygon whose members were
  replaced on 11-12) and **w684910576 AddMaxHeight** (a 15.7 km Moscow trunk road changed on 11-11). Both lie inside a
  rectangle on their day, the store's copies are right (the relation's new member way; the road's nine crossing
  footway and road bridges, each within 10 m of its box), the engine's map data rule includes them (a way with a node
  in the box comes with all its nodes), and yet both recounts lack the quest the whole count has. Needs an engine
  reproduction on that day's read (`days/<D>/t2/new.osm.pbf`).

**Planet day 5172's cover** (answers only inside Europe, from a clip store cut at 11-07; outside it the cover falls back
as before): the rule 128,039 rectangles, 101,595 km2; with F's answers 128,260, 101,887; with P3's too 128,796,
102,475 km2 (+0.6%). Inside Europe P3 added 486 holding relations (7,947 member lines), 3,266 moved-node ways and
1,024 road-under-a-bridge boxes. The planet store holds every element, so the planet adds these everywhere: not
measured; about 1.8% of 5172's changed ways lie in the clip, so a plain scale-up would be tens of thousands of boxes
and lines, mostly small. A day's store questions took about 2.5 min in the rehearsal (D-1 15 s, D 115-135 s).

### Tier 2 per plan file, measured on the planet (2026-11-17, evening; blocker 4)

`world_day.rect_rows` recounts the rectangles group by group instead of in one engine run. A group is one plan
file's rectangle cities, since their cells share the file's parts. A file whose padded area passes
`WORLD_T2_GROUP_KM2` (default no cap) is cut further. Each group is read from the store on its own, and
`WORLD_T2_WORKERS` engines run at a time (default 1). The dumps are ingested in group order, D-1's before D's, so
the place-set numbering does not depend on which engine ends first.

**Exact:** on the rehearsal's 11-13 (clip store generation 4, the day's own cities and parts), 16 groups give the same
5,668,905 rows as the one run, with 0 different (`.scratch/rectgroups/exact.py`). Grouping took 145 s at 4 workers,
the one run 157 s.

**End to end:** the rehearsal's day 11-10 through `world_day.run` with grouping (16 groups, 4 workers, both
reads), from the same 11-09 seed, against the ungrouped run of that day: every state row and all 628,364 counts per
place and quest equal (`.scratch/rectgroups/e2e.py`). Tier 2's engine time there: 245 s.

**The planet, one date** (`.scratch/rectgroups/measure.py all --workers 4 --heap 8`): planet day 5172's rectangles
under the big-polygon rule (128,544 in 127 files, 101,651 km2, 289,864 km2 padded by the 300 m ring), read from
the planet store's generation 15 (11-17) with the planet parts cache (1,069,679 outlines, 5.8 GB, built in 870 s).

| | |
|---|---|
| wall time, 4 engines at a time | 1,220 s |
| reads, one at a time beside the engines | 643 s in all; 7,961 MB of map data |
| engine time summed | 4,684 s (passes 3,603 s, the rest startup: about 20 s an engine) |
| peak heap of the largest group | 6.7 GB (f11, 2,441 rectangles, 287 MB of map data) |
| the most rectangles in one group | f116, 10,286, north Norway: 36 MB of map data, 168 s with others running, 82 s alone |

So **tier 2 on a planet day is about 40 minutes for both dates at 4 workers**, and 8 GB heaps fit with no cap. The
engine's cost follows map data and rectangle count, not area: f116 is 10% of the padded area and 0.5% of the map
data. Not measured: 6 or 8 workers (the engines already use every thread each, so 4 to 1,220 s is close to the
summed time over 4), or the cover's extra P3 boxes the planet would add outside Europe.

### The world day on the planet (2026-11-18; release 1, step 4)

`tools/stream/planet_store_day.py` moves the planet store and the world state (`.scratch/planet/world-1101`, the
seed at 11-01) together; the store never moves alone. A day D, the store, its node file and the world at D-1:

1. **D-1 kept.** Every plan file's `world.bin` hard-linked into the day's `before/` (no bytes copied). Every write
   the day makes to a world file replaces it (`replace_in_file`, `write_rows`), and `notes_day._hidden_file`, which
   sets flags in place, first copies a file another name holds; so `before/` keeps D-1's rows until the day is done.
   `world-keys.npy` is not linked (`np.save` writes into the file); a restore derives it from the rows.
2. **prepare**, then the prepared day saved (`world_day.save_day`, without the node file's memmap) and read back.
   The update's `--prune-pairs` takes D-1's way pairs away, so after it `prepare` cannot run again: the saved day is
   what makes the rest of the day repeatable.
3. **update** (`tilestore update --world --prune-pairs`).
4. **finish**, the node file still at D-1. A finish that begins again first puts the world back from `before/`.
5. **The gate** (`tools/stream/world_gate.py`): the 32 European cities' own outlines (`osm-<city>`) from the world's
   counts at D against the engine on the Europe clip of D, the same quests file and the world's own notes dump
   (clipped once per region into `W/gate-notes/`: the daily run deletes its older clips). The bar: 0.1% of open
   quests over the 32 and in each city. On the 11-01 oracle it reproduces the seed's gate exactly (21 of 32 equal,
   +9 of 19,239,746).
6. **The store's own day** as before (loc advance and check, subcmp and why, compact, punch), then D's Europe clip
   unpinned and the day's work deleted, its `day.json` and `gate.json` kept in `W/days/<D>/`. Every clip of a day the
   world has not reached is pinned on sight.

**Two ends that are not a STOP (2026-11-23).** Both end the run cleanly ("planet store run ended"), write no
STOPPED and need nobody. (a) **No day without the disk for it:** before a new day, not a resumed one, the loop reads
the free space of the store's disk and takes no day under 115 GiB (`DAY_NEEDS_GB` 75, what a day draws at its low,
plus `DISK_FLOOR_GB` 40, the floor `update`, `loc advance` and `compact` refuse under); it logs `day <D> not taken:
...` and the next run asks again. A day failed in its middle for want of disk on 11-16 and 11-21. A resumed day's
steps keep their own checks. (b) **A gate region short of its heap** ("Engine heap", `minHeapGb`): after the
60-minute wait `run.MemoryBusy` passes through `guarded` to `days`, which logs `not now: ...` and ends the run. The
store and the world are at D, `finished` is written and the node file is at D-1, which is the state `one_day`
resumes from at the gate; the regions already counted keep their `done`.

**Notes.** The world's clips hold every note's history up to their dump's `until`. A day past it cuts the newest dump
into every plan file again; the old union clip stays as that day's D-1 side of the hidden flags
(`hidden_files(prev_table=)`), since a note the newer dump lacks (hidden by a moderator) was open at D-1 and its rows
must be unhidden at D.

**Two costs moved for the planet.** Tier 2's delta compared recounts with a Python tuple per row (`groups`); a planet
date is about 34M rows. It now compares each (element, quest) group's fingerprint (row count and two 64-bit hash
sums), the same candidates as before on random cases, 6 s for 34M rows. Tier 1's and the note quests' engine runs
(one per plan file, 128) go `WORLD_T2_WORKERS` at a time, ingested in file order so the place-set numbering does
not change.
