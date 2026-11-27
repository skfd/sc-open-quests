## The whole world: measured and proposed (2026-11-06)

The owner asked what it takes to count all of it, hosting and hardware open. Nothing built. Scripts in
`.scratch/world-spike/` (gitignored); both runs on this machine (12 cores, 24 threads, 88 GB).

- **The engine's cost is flat per node, in town or country.** v64.1, 24 threads:

  | area | nodes | pass | s per million nodes |
  |---|---|---|---|
  | the 147 cities, area pass, Paris and Toulouse left out | 259M | | 5.4 |
  | Estonia as one area | 13.6M | 76.5 s | 5.6 |
  | Czechia as 15 grid cells, each a "city" | 97.5M | 522 s | 5.4 |

- **Czechia as one area ran out of heap** (41 GB, `MutableMapDataWithGeometry`, while building the map
  data). The same file as 15 cells ran with no engine change, the largest cell 17M nodes in 72 s. So the
  world is cut into cells. The cells' sum was 11.2M open, every quest. An element's centre lies in one
  cell, so nothing is counted twice.
- **The planet is 15 to 17 hours on this machine.** 10 to 11 billion nodes, a density estimate (100-110k
  nodes per MB of pbf, and a planet now larger than the 85 GB noted above), at 5.4 s per million. About 1.5
  billion open quests of every kind, 0.12 to 0.16 a node; the app's default quests are about a third of that.
- **Outliers are single quests, not places.** Paris's AddAddressStreet took 582 s (Praha, the same size,
  28 s in all), a quarter of a day's engine time; Toulouse 47 s; London's AddHousenumber 176 s. A fast twin
  is due for the first, and cities not yet counted will hold more of these.

**The proposal: count the planet once, not cities one by one.**
1. Cut the planet into about 1,000 cells of at most 15M nodes, each with a ring of map data around it.
   The engine's node index (16 bytes a node) cannot hold the planet, so this comes first. `osmium
   extract` holds about 4 GB per output, so the cut goes in stages: continent, country, cell. Unmeasured:
   the daily cost of keeping cells current, guessed at 1 to 3 hours. That holds only for cells re-cut in
   stages from a planet updated by diffs: a clip's own daily fetch takes 2-3 minutes, 40 hours for 1,000.
2. Each element counts in the one cell that owns its position, and into every place around it. Every place
   has real numbers, roll-ups are true sums, no request or bar is needed, and "does land outside cities
   count" answers itself. The name layer has no polygons, so these 1.08M come from Overture's division
   areas; fetching them from OSM one relation at a time is not an option. That undoes the owner's "counting
   on OSM geometry" (2026-10-24) and is the owner's to accept. Two engine prerequisites follow: no
   planet-wide node index, and a spatial index over a million polygons, not the grid over city boxes.
3. Country gating and time zone come from the position, not the city (one zone per run today).
4. **The test before anything else:** cell counts against today's whole-city counts for the 147 cities.
   The unit changes from "the whole city" (the owner's choice, 2026-10-12), so the difference is the
   owner's to accept.
5. Publish to R2, the site staying where it is with `DATA` pointing there. Per-place history about 15 KB
   gzipped at most, so about 16 GB for the world. Rewriting a million objects daily costs about $140 a month
   in writes, so a day's numbers go in the 4,202 region shards and per-place history is written monthly.
6. History since 2017 is run once: 118 months at about 6.5 billion nodes on average, about 7 weeks on this
   machine, if months are sliced from per-cell history cuts, not from the 159 GB file each time.

**What it needs.** Hetzner, 2026-11-06, excl. VAT, no minimum term: AX102 (16 cores, 128 GB, 2x 1.92 TB) EUR 259
a month + 129 setup; AX162 (48 cores, 128-512 GB) EUR 614 + 304. Speed on either is unmeasured; a guess of
1.5-2x and 3-4x this machine gives 8-11 and 4-6 hours a planet. R2 about $5 a month and egress free. It
needs a custom domain and Linux for the pipeline (no Docker Desktop, no Task Scheduler). This machine could
do a weekly world for nothing: the planet (85+ GB) and its cells (about 90) fit in the 247 GB free. The 2017
history does not: its per-cell cuts add about 160 more.

**The owner's answers (2026-11-06, evening):**
- **Cells are accepted if every city's total stays within 0.1%** of its whole-city count; the per-quest
  differences are listed for the owner.
- **Overture's boundaries for every place.** This replaces "counting on OSM geometry" (2026-10-24).
- **Only this machine, for now.** No server; work out what it takes.

**Neighbourhoods in a world count, as asked.** The same rule as today's parts, and Wandrer's shape: a quest
has one position, and it counts once in every polygon holding that position, from country down to
microhood. Places overlap, leave gaps, and children need not add up to a parent. A part no longer needs a
counted city around it, so `add_parts.py`'s step 1 and its "inside the city" check go. The filter stays: only
divisions whose own source is OSM, the owner's rule of 2026-10-24 (costs Germany 4,130 of 4,717 microhoods,
few neighbourhoods). A division with no polygon, 3.6M of the 4.7M, keeps its name and has no number. Parts
cost about 4% of a pass today (Ontario 216 s against 208 s, 790 parts).

**Only this machine: measured the same evening.**
- **CPU is the limit, not memory.** Czechia's five columns, two engines at once at 20 GB heap each: 520 s
  of wall clock, against 522 s for one engine. One engine fills the 24 threads; running more buys nothing.
  (Not so: measured again with equal work on 2026-11-07, below, two engines at once are 1.38 times faster.)
  A 31M-node area needs under 24 GB.
- **`osmium extract` holds 4.2 GB per output:** five outputs 21 GB, and 15 were killed by docker's 43 GB.
  Five outputs of Czechia took 121 s for 951 MB, 7.9 MB/s, so a stage over the planet is about 3 hours.
- **So the planet needs only a coarse cut.** The engine does the fine cutting itself, as in the Czechia
  grid: a file of 100M+ nodes with its cells as "cities". Two stages of 9 outputs give about 80 files of
  about 130M nodes. No 1,000 cell files.
- **A weekly world is about 24 hours:** 2 for the current planet, 6 to cut, 15-17 to count. That is 14% of
  the week, beside the daily run of the 147 cities, which stays as it is. A daily world does not fit.
- **Disk, 260 GB free:** peak about 210 GB (planet 90, first stage 90, one continent's files up to 30), if
  each file is deleted once used. The monthly rewrite needs 170 GB at another time, so the two must not
  overlap. `data/backfill/` (20 GB) can go. Tight but enough.
- **History without per-cell cuts:** each date goes through the whole chain, about 16 hours on average, so
  10 yearly points in about a week, 40 quarterly in a month, all 118 months in 3 to 4 months beside the weekly
  run. No extra disk. Fill coarse first, as Europe did.
- **Not known:** whether a 16-hour run holds speed on a laptop chip (these runs were 10 minutes), and the
  time of a planet slice from the current history file.
- **Hosting stays a separate cost:** weekly data for a million places cannot go through git. R2 at this
  size is about $1-2 a month, and needs a domain.
