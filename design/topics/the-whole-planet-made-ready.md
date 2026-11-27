## The whole planet, made ready (2026-11-10)

The owner asked whether the first count of the whole planet could run now. Not as things stood: the planner
made giant boxes, the engine's `nodegrid` read a whole file into memory, the cut was one osmium pass, and
nothing could hold 1.9 billion matches for a check. All of that is done; the chain is
`.scratch/planet/chain.sh` (gitignored), log `logs/planet-count.log`.

**The date is 2026-11-08T00:00Z, so the count checks something.** It is the stream's measured day (step 5)
and the instant of the 32 European cities' published snapshots (their clip is at day diff 5170):
- **The planet at that instant:** the history file's own end (11-02T00Z, diff 5164) through `osmium
  time-filter`, piped into `osmium apply-changes` with day diffs 5165 to 5170, one container, no 90 GB file
  between (`.scratch/planet/slice.sh`). The output header carries the replication timestamp and sequence
  and `sorting=Type_then_ID`, without which the engine refuses the file (the trap of 2026-11-02; checked on
  the Bremen history cut).
- **Oracle 1, the stream:** the engine's new `--dump-ids <file>` dumps only the listed elements' matches.
  The list is the 316,806 elements step 5 replayed (their versions before the day,
  `.scratch/store/priors-index.tsv`), so the world count's matches on them can be held against the
  stream's state before the day (`matches-world-priors.tsv`). A dump of everything would be about 180 GB.
  Expected differences: the count hides quests at open notes and runs each cell's own zone; the stream had
  neither.
- **Oracle 2, the cities:** every counted city is a part of the plan, and `world_cells.py report --archive
  2026-11-08` holds each against its published snapshot of that day, with that snapshot's asOf. Europe's
  are the same data at the same instant, so the owner's 0.1% bar applies; Canada's and Germany's come
  from Geofabrik extracts of other hours.

**No giant boxes.** SC's `LatLonRaster(mapData.boundingBox, 0.0005)` (AddHousenumber, AddIsAmenityIndoor)
is sized by a cell's box:
- **The planner caps a cell at 10 degrees a side** (`CAP_DEG`): a cell over its node limit is split at the
  median as before, one under it but too large in the middle of its long side. 10 by 10 degrees with the
  ring is 400M raster squares.
- **The engine refuses a box over 500M squares by name,** before it builds the map data ("area: f0c0's box
  spans ... cut it smaller"; `-Dopenquests.maxRasterSlots` for tests), instead of dying in a full
  collection.
- **Tried and dropped: cutting the map data's box down to its data.** On Germany's f0c0 it moved
  AddHousenumber by +3 (ways 173233535, 547235965, 681584868, near Brüggen). SC's `isInPolygon` counts a
  point outside a polygon as inside when it lies on the latitude of one of the polygon's vertices and west
  of it: address node (51.2583502, 6.1902655) lies 12 m west of building 173233535, on its first vertex's
  latitude, and closes its quest. Whether such a point is even tested depends on which raster squares the
  building's box reads, and so on where the box starts. The app's own box is its download, so counts follow
  the box SC would have; it cannot be moved to save memory.
- **On the globe:** a cell's east edge stays at 179.9999999 (SC's country lookup reads 180 as -180; a node
  at exactly 180 is in no cell), boxes are clamped to ±90 and ±180, and the 1 km ring's width in longitude
  is taken at 85 degrees at most, in the planner and in the engine's padded boxes (at a pole it divided by
  zero; in 1e-7 degrees a box past 214 degrees overflowed an Int). No counted city is affected. A cell with
  no nodes takes the time zone at its centre; timezonefinder gives open sea an Etc/GMT zone.

**A planet-sized plan.**
- `kd` passes each part its own squares instead of scanning the whole grid at every split, and the zones
  are looked up once per square. The planet's grid is 0.1 degree squares.
- **Regions, files, cells:** regions of at most 8 files' worth of nodes, each cut into files of at most
  130M nodes, each into cells of at most 15M. A region's box is the union of its files' padded boxes, so
  each file is whole when it is cut from its region with the same `smart` strategy.
- **The cut in two stages:** `osmium extract` holds 4.2 GB per output, so a pass has at most 8. The planet
  gives the regions (a pass per 8), each region its files, and the region is deleted once they are out.
  Every output is written as `.part` and renamed, so a rerun skips what is whole.
- **`nodegrid` streams** the file's blobs through a bounded pool (`streamPbfBlobs`); `readPbf` keeps a
  whole file in memory, 90 GB for the planet.
- **`count`:** waits out the daily update's window before starting a file (`backfill_history.QUIET`: two
  engines of 30 GB and the daily run's do not fit), `--delete-cut` deletes a file once counted,
  `--dump-ids` as above, `--only` for a canary (the file with the most cells, open sea and the
  antimeridian, alone first).

**The rehearsal: Germany re-planned** (`.scratch/world-de2/`, the same cut files and notes clip as the
prototype of 11-09):
- 46 cells against 34. f0, whose stray nodes stretched it to longitude -20, now has 18 cells, the largest
  8.20 by 7.40 degrees; 5 cells hold no nodes. The four files are the same as before, box for box.
- **Every counted city equal to the prototype's cells,** each within 0.002% of its whole-city count (the
  same three AddHousenumber -1). Four files in 893 s with two engines (1,007 s on 11-09).
- The total is 76,063,895 against 76,065,341, all from the gate: the prototype typed `DE` for every cell,
  and cells are gated by position since item 11, so the slices of the Netherlands, Denmark, Czechia and
  France inside Germany's files lose AddHousenumber (-1,501, off in those countries) and
  AddFireHydrantDiameter (-290); AddAcceptsCash rises by 174.

**The rehearsal of the new paths: the 11-08 Europe clip** (`.scratch/planet/rehearse/`, files of at most 12M
nodes so that there are two regions; three outputs a pass beside the running slice, `WORLD_CELLS_MAX_OUTPUTS`):
- **The streamed `nodegrid`** gives Germany's grid of 11-09 byte for byte (442,630,768 nodes, 24 s, 8 GB heap).
- **Plan and cut:** 2 regions of 8 files, 38 cells (4 with no nodes, the largest 9.30 by 9.50 degrees). The
  regions in one pass of 192 s, their 16 files in six passes; 811 s in all. Every file accepted by the engine;
  16 files in 488 s with two engines.
- **Oracle 2: every one of the 32 cities within 0.004% of its published count of 11-08** (`report --archive
  2026-11-08`, each at asOf 2026-11-08T00:00Z); 22 exactly equal, the other 10 within 4 matches (Bratislava's
  AddCycleway +4 is the border gate, as on 11-09).
- **Oracle 1, as the world run will use it:** `.scratch/planet/oracle.py rehearse` holds the cells' dump of the
  listed elements against europe-west's full dump of 11-08 (`.scratch/diff-flips/`), inside London, Dublin and
  Lisboa: 676 matches, 676 equal. `oracle.py world` on the same cells against the stream's state before the day:
  all 11,021 tier-1 matches the Europe cells hold on listed elements are in the stream's state, none only in the
  cells, agedOnly equal on all. (The other 352,257 of the stream's are not covered by this rehearsal.)

**The chain, with what it costs** (estimates from earlier measurements, none yet on the planet):

| step | estimate | disk |
|---|---|---|
| the slice, 11-08T00Z | 2 to 3 h | +about 90 GB |
| `nodegrid` at 0.1 degrees | 15 min | |
| plan, notes | 15 min | |
| the cut: 16 regions in two passes, then their files | 9 to 12 h (the rehearsal's 8-9 MB/s) | +about the planet's size, then the planet deleted |
| the canary file alone, then the rest with two engines | about 6.5 h (Germany's 443M nodes took 893 s) | the files kept until both checks pass |

The slice wrote about 8 MB/s, about 3.3 hours. The planet may be 100 to 110 GB (100-110k nodes a MB), so the
peak is the planet and its regions together, about 210 GB: the cut stops unless the planet's size and 40 GB
are free. C: had 227 GB free. The files are
kept until both checks pass (no `--delete-cut` yet), about 95 GB. The planet job of 2026-12-07 needs about 170 GB, so
nothing of this may be left by then.
