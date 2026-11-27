## The stream, step 5: a planet node store, and one planet day through tier 1 (2026-11-10, night)

Plan step 5 of "The stream: probed, and the plan": the world's cost. Of the store's five parts one was
built and used (node locations), one was measured on real data (the open-quest state), three are sized
by arithmetic (due dates, "which ways hold this node", "what lies in this box"). Then 11-08's 1,415 minute
files went through tier 1 for the whole planet. `.scratch/store/` (gitignored; `store.py`, `day.py`,
`state_size.py`, `count_nodes.py`, `planet.sh`, `RESULT.txt`, `events-world.tsv`). One engine change,
opt-in: `-Dopenquests.areaPass=false` skips the area pass (snapshots never set it).

**The node location store: built, 107 GiB, 35 minutes.**
- **What it is:** pyosmium's `dense_file_array` (4.3.1, natively on Windows, no Docker): one memory-mapped
  file, 8 bytes for every node id, absent ids empty. `planet.loc` has 14,361,507,332 slots and is
  106.8 GiB (114.8 GB).
- **Built from `history-261102.osh.pbf` (159 GiB) in 2,072 s:** the node pass 1,455 s (every version read,
  the last one wins, a deleted node reads as absent), then a way pass of 617 s that the store does not need
  (it fetched the versions before the day, below). About six cores busy, 2 GB of memory. The six day diffs
  to 11-08T00Z went in at 32 to 39 s each.
- **Checked against the clips:** every 50th node of the 11-08 Europe clip, 2,556,447 of them, is at the same
  place in the store; after the day's replay, every 50th node of the 11-09 clip, 2,556,762, likewise. None
  missing, none elsewhere. So the history file, the day diffs and the minute files all land where
  osm-extracts' own clip does.
- **The planet has 10,988,329,357 live nodes** at the end of 11-08 (the slots that hold a place, 76.5% of
  them; counted from the file in 288 s, after the fourth trap below was mended). The "10-11 billion" used
  for the count's hours was an estimate; it holds.
- **Two things the pilot found** (the Europe history cut, 7.4 GiB): with the location handler in the same
  chain the ways took twelve times as long (400 s against 32 s), so nodes and ways are two readers; and a
  dense file is as large for a region as for the planet (the pilot's was 107 GiB too), so a region's store
  would be the sparse kind.

**The day: how.** The minute files in order. For each file: every node version first (the old place read,
the new one written), then each way version placed from the store as it is at that minute, then that
file's node deletions. Every tagged, visible version becomes its own element in a synthetic PBF, as in
step 1, a way's nodes beside it as one synthetic node per (node, place). The version before the day of
every touched element (from the same pass over the history file, then the six diffs: 80,025 tagged nodes
and 236,781 tagged ways) goes into a second file, counted with the clock at 11-08; the day's versions with
the clock at 11-09. The engine sees the world as one "city" without country codes, so each quest is gated at
its position; UTC, no notes, the area pass off.

| stage | wall | |
|---|---|---|
| the 1,415 minute files parsed: 4,727,281 versions | 115 to 126 s | Python, one thread |
| 3,931,249 node versions into the store, a read and a write each | 243 to 251 s | 62 µs each |
| 747,133 way versions; the 454,782 tagged and visible ones placed with 6.2M lookups | 28 s | 4.5 µs a lookup |
| **the day, two runs** | **386 and 405 s** | 447 s CPU, 3.1 GB of private memory; the slowest minute file 5.1 s (57,203 versions) |
| the engine over the day's 611,840 versions | 10.9 s | 109 s CPU, 1.8 GB |
| the engine over the 316,806 versions before the day | 8.0 s | 80 s CPU |
| those prior ways placed: 3.5M lookups in a store not yet in memory | 73 s | 21 µs a lookup |

- **A planet day through tier 1 is about seven minutes on one thread and twenty seconds of engine.** A
  minute of the world's edits takes a quarter of a second on average and five seconds at worst.
- **The node step is the wrapper, not the disk.** Reading an absent slot through pyosmium raises a Python
  exception: 74 µs against 11 µs for a present one (a million of each), and three quarters of the node
  versions are new nodes, so about 225 of the 243 s. The undo of all 3,931,249 writes took 24 s. Without the
  exception the day would be about three minutes (arithmetic, not run).
- Of the node versions 3,025,623 made a node, 399,080 moved one, 425,947 deleted one and 80,599 changed
  only tags.

**Result: the world's tier-1 events of one day.**
- **350,162 events: 240,991 quests opened and 109,171 closed, on 231,524 elements, from 27,580
  changesets.** 4,610,980 nodes and ways had a version that day; they held 363,278 open tier-1 quests
  before it and 495,098 after. Net flips 336,574; 13,588 events went there and back within the day.
- **Every minute has events:** 194 in the median minute, 4,299 in the busiest.
- **By editor (opened / closed):** iD 112,185 / 37,939, JOSM 91,232 / 29,656, StreetComplete 12,478 /
  22,499, Rapid 9,726 / 1,945, StreetComplete_ee 3,759 / 5,606, Vespucci 2,663 / 1,522, osm-revert 176 /
  2,826, atp2osm 0 / 2,133. StreetComplete and its fork close 28,105 of the 109,171, a quarter.
- **By quest (opened / closed):** AddBuildingType 74,969 / 21,170, AddBuildingLevels 22,625 / 3,466,
  AddWayLit 19,027 / 6,476, AddRoadSurface 16,901 / 10,173, AddPathSurface 12,344 / 5,324. Closed more
  than opened: AddMaxSpeed 6,426 / 7,710, AddSidewalk 5,313 / 6,464, AddOpeningHours 2,709 / 5,323,
  CheckShopExistence 33 / 6,280.

**Checks.**
- **europe-west is exact.** The same two files counted with step 1's cities file and notes clip give 660
  events, the same 660 as step 1, each in the same minute, changeset, quest and element. The state before
  the day, from the store's prior versions, equals the 11-08 dump on every touched element (218 of them
  hold a quest), and the state after equals the 11-09 dump. So places taken from the store at the minute
  and prior versions taken from the history file reproduce what step 1 took from the two clips and the dump.
- **The world's StreetComplete changesets:** 7,228 name a tier-1 quest and have a node or way version in
  the stream; the stream shows that quest closing in 7,101, 98.2%. The 127 others were not traced (step 1
  traced its six: the quest was not open before, or the app showed a date quest earlier than the default
  interval). 4,045 more name an area quest or an overlay.
- **Nothing else checks the world's numbers:** no full count of the planet exists for either day.

**Four traps.**
- **A node deleted in the same minute.** 15 way versions named a node that the same minute file deletes:
  a file lists nodes before ways, and in time the way version came first. With a file's deletions applied
  after its ways, no version is left unplaced (the figures above are from that run).
- **A box from -180 to 180.** The country lookup wraps an east edge of 180 to -180 and takes the world for
  a sliver on the antimeridian, so every country-limited quest was gated wrongly (AddAcceptsCash off in
  London). The test's world ends at 179.9999999. A world cell must not span every longitude; the cap on a
  cell's sides (cells' list, item 1) covers it.
- **The engine wants every ported quest in its quests file,** so "tier 1 only" is the switch above, not a
  shorter file.
- **A deletion in a day diff carries the node's last place,** and the location handler stored it: 4,482,349
  nodes deleted between 11-02 and 11-07 still held a place (found at review, after the run). No way names
  a deleted node, so no event moves and the clip checks could not see it; only the node count was too high.
  They were emptied by hand and `store.py` now empties them with each diff. The history file's own
  deletions carry no place (419,657 deleted nodes of the Europe cut checked: none in the store), and the
  replay writes the empty slot itself.

**The state, sized on real data, not built.** The 11-09 dump of europe-west, 4,624,345 matches on
2,371,321 elements (`state_size.py`):

| layout | bytes a match | zlib |
|---|---|---|
| the text dump | 95.1 | |
| fixed records (quest, type, id, place) | 18.0 | 6.1 |
| by element: id deltas, one place per element, its quest list | 6.2 | 4.1 |
| the same without places | 2.1 | 0.5 |

Germany as cells is the only whole country counted: 76,065,341 open quests on 442,630,768 nodes, 0.172 a
node. The planet's 10.99 billion nodes at that rate are **1.9 billion open quests, about 12 GB by element**
(the guess had been 15 to 30 GB). Whether the world is tagged like Germany is not known. Due dates add about
a fifth as many entries (971,545 waiting against 4.6M open in europe-west), each with a date: 2 to 3 GB.

**The other two lookups, estimates only.**
- **"Which ways hold this node":** the 11-09 Europe clip has 21,368,006 ways with 168,134,144 node
  references on 127.8M nodes, 1.32 a node; that is cities, and the planet's ratio was not measured. At that
  ratio the planet has about 14.5 billion pairs: 116 GB at 8 bytes each, perhaps half sorted and
  delta-coded. Its load is the 399,080 moved nodes a day.
- **"What lies in this box":** the elements themselves with their tags, by tile; that is the planet as
  files, about 90 GB (HARDWARE.md), plus an index, kept current. Nothing measured.
- With the node store that is roughly 300 GB kept current by the minute: what an Overpass instance already
  is (250 to 300 GB, HARDWARE.md).

**What this shows.** Tier 1 for the whole world, 70% of the matches and 72% of the flips of the measured
day, costs minutes a day, one 107 GiB file and no new engine command. The full count is 6.5 hours of a chain
that has not yet run once.

**What it does not show.**
- **The state itself.** The state before the day came from prior versions out of the history file, a
  ten-minute pass, not from a table of open quests. A live stream is seeded by a full count of the world.
- **Tier 2,** 30% of the matches: it needs the two lookups above, or a recount of the ground touched.
- **Relations** (48,899 versions) were again not replayed. A way whose node moved without a new version
  keeps its events; only its place moves.
- **Places, notes, time zones, ageing:** which place holds each event, the notes that hide quests, a zone
  per position and the due-date table were not part of the run. One clock for the whole day.
- **Other days:** one day, a Sunday.

**The disk.** `planet.loc` was deleted after the run; `planet.sh` rebuilds it in 40 minutes from the
history file in the store. With it C: had 120 GiB free, and the planet job of 2026-12-07 needs about 170.

**Next, the owner's call.** Both ways forward wait for the first count of the whole world: it seeds the
stream's state and is the oracle for it. That count waits for the cells' list (item 1, no giant boxes).
After it, tier 1 can follow the minute diffs at minutes a day while tier 2 is recounted weekly or on the
ground touched; whether tier 2's store is built here or is an Overpass instance is the open strategic
question.
