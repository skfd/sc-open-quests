## Smaller tiles for the tile store (2026-11-14, evening; owner: "measure smaller tiles first")

A day rewrote 23% of the z14 store's bytes in 4.9% of its tiles (above): any edit rewrites its whole tile, and the
tiles a day touches are the dense city-centre ones. Measured here: uniform z15 and z16 stores, and an adaptive split
(a z14 tile over a threshold held as its 16 z16 children) estimated from the z14 and z16 stores. Same clip, same day.

*Made for it.* The zoom is a setting (`OPENQUESTS_TILE_Z`; a store records its own and refuses another), tests pass at
z14, z15 and z16. The update's region (the prototype's stand-in for a world with no edge: the planet diff's changes
outside the clip stay out) is now the tiles the store holds plus the tiles under the clip polygon's parts; the earlier
z14 runs took the store's tiles grown by one, which at z16 is too little ground and left out tiles a moved node's way
newly crossed, and a first polygon-only region left out the far nodes of ways the clip holds whole. With it, z14's day
writes 2,591 tiles (461 MB), none new at the edge. Scripts: `tools/stream/tilecheck/chain-z.sh Z [update-only]`
(logs `logs/tiles-z14.log`, `tiles-z15b.log`, `tiles-z16.log`), the table by `tools/stream/tilecheck/adaptive.py
.scratch/tiles .scratch/tiles/ref/cities.json`. The z15 and z16 runs predate the two relation-index fixes of "A second
day" (which change only the way and relation tile indexes, not a tile); those fixes are checked at z15 and z16 by the
small test only. The adaptive rows are an estimate from the two uniform stores; no adaptive store is built.

*Exact at every zoom.* D through each updated store recounts **1,116,244 rows, 0 different**; the tiles under the
rectangles (331 at z14, 1,004 at z15, 3,367 at z16) are byte for byte the fresh 11-13 cut's; every other differing
tile touches the polygon's edge, except 3 at z15 and 7 at z16 wholly inside, and every node those miss is absent from
the 11-12 clip: two ways in Vilnius (v3, v4) drawn into the city box on the day reuse old nodes from outside it, which
the diff does not carry (they did not change) and the clip's node store never had. `planet.loc` has every node, so a
world store cannot meet this.

| layout | tiles | GB | written a day | MB | share of bytes | tiles read | MB read |
|---|---:|---:|---:|---:|---:|---:|---:|
| z14 | 59,026 | 2.00 | 2,591 | 461 | 23.1% | 331 | 92 |
| z15 | 167,105 | 2.66 | 4,475 | 285 | 10.7% | 1,004 | 83 |
| z16 | 496,719 | 4.06 | 8,169 | 198 | 4.9% | 3,367 | 89 |
| z14, z16 over 64 KB | 167,872 | 2.92 | 5,908 | 194 | 6.6% | 2,782 | 86 |
| z14, z16 over 128 KB | 121,048 | 2.64 | 4,807 | 205 | 7.8% | 2,408 | 84 |
| z14, z16 over 256 KB | 83,918 | 2.33 | 3,927 | 250 | 10.7% | 1,510 | 82 |
| z14, z16 over 512 KB | 65,277 | 2.11 | 3,151 | 338 | 16.0% | 716 | 86 |

(Tiles only; the relation store, 0.22 GB, is the same at every zoom. "Read" is the day's 103 rectangles and their ring,
dominated by dublin-0's 12 x 7 km. Updates took 6-9 min each in Python at every zoom.)

*What it says.*
- **Size grows with the zoom** because a way is held whole in every tile it crosses: z15 +33%, z16 +103%. The daily
  write falls faster than the size grows: z15 halves it, z16 cuts it to a fifth (in MB: 461, 285, 198).
- **The adaptive split takes the best of both**: z16 children only for z14 tiles over 128 KB is z15's size (+32%) with
  z16's write (205 MB, 7.8%); over 256 KB is +17% for half z14's write (250 MB). The index stays small (84-121k
  entries here against z16's 497k; the planet at uniform z16 would be hundreds of millions of index entries).
- **The read does not care**: 82-92 MB at every layout for these rectangles; more, smaller tiles (up to 3,367) cost
  index lookups, not bytes.
- **For the world**, with the split at 256 KB: tiles about 1.33x the planet PBF (1.14 x 1.165), with the relation store
  about 124 GB beside the PBF's 85 GB; a day's write up to a tenth of it in a clip that is all city centre, less on the
  planet's average ground (not measured). Keeping D-1 costs one day's write.
- **The key for an adaptive store**: a quadtree cell (zoom, x, y); a box asks for the cells under it at z14, and a z14
  cell that is split answers with its z16 children. The cut decides the split from the z14 payload size; a day may
  leave a tile across the threshold, which only costs a later re-split (the content is the same either way).

*A second day (11-14, 21:00-21:50; `tools/stream/tilecheck/day12.sh`, log `logs/tiles-day12.log`).* The z14 store from
generation 0 through diff 5175 and then 5176 (the second update reading the first's way and relation tile indexes,
the node store before it being 11-13's), each held against a fresh cut of that day's clip (`store13/`, `store14/`):
**no tile, relation blob, way-tiles or relation-tiles entry wholly inside the polygon differs on either day**, and D of
day one recounts 0 different. Day two reached 2,438 tiles and wrote 2,426 (477 MB, 24% again; 572 s). The edge's
differences grow with the days (799 tiles against 408), as they must where the planet diff keeps adding what the clip
leaves out. The first try at day two found two gaps, both fixed and in the small test: (1) a reached relation's tile
index was rebuilt from the working set alone, which lacks a far member node or way, so relations placed by far member
nodes lost entries (5 interior; their tiles were right); now a reached relation keeps its entries outside the day's
reach. (2) A changed relation's new member nodes were neither reached nor in the working set (an untagged node no tile
held); now they are, placed from the node store.

*Packs die slowly.* After day two, 1,873 of day one's 2,591 tiles are still live (221 of its 461 MB; only 718 were
rewritten again), and 54,727 of the cut's 59,026 (1.30 of 2.00 GB). A day's edits land mostly on other tiles than the
day before's, so a pack is not dropped whole after a day or two: dead bytes build up (0.94 GB of the 2.93 GB of packs
after two days) and a compaction copies the live tiles of a mostly dead pack forward. Keeping D-1 is still one day's
write; the dead space beside it is what compaction bounds, at the cost of copying.
