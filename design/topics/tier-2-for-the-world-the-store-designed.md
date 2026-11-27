## Tier 2 for the world: the store, designed (2026-11-14, afternoon; owner: design it, build later)

What a world day's tier 2 reads, as `tier2_step` does it for europe-west:
1. **The ground the day touched** (`tier2.cover`): every changed node's old and new place, every changed way's old
   and new segments, and **the ways whose nodes moved without a version of their own**. The old places come from
   the node store before the day (the world has it now: `planet.loc`, kept in place, so the old place is read
   before `save()`); the ways need **way refs and a node-to-way index** (`WayStore`, `ways.npz`). Europe-west's is
   3.7 GB for 21.4M ways and 168M refs (22 bytes a ref: refs, a reverse index of refs, the way of each); the planet
   has about 1.1 billion ways and of the order of 12 billion refs, so the same layout is **about 280 GB**: this is
   most of the "about 300 GB" first estimated.
2. **The map data of the rectangles with their ring, at D and at D-1** (`tier2.map_data`, today the whole day clip).
   The ring matters: 300 m reproduces a whole count but for a few AddHousenumber, 1,500 m agrees on those but reads
   seven times the nodes and brings 3 of its own ("Tested", above).

The design, smallest first:
- **(a) Try without the way index.** A way whose node moved changes only in the segments at that node, and the
  node's old and new places are already in the cover; the rest of the way is unchanged. The cover could take, for a
  moved node, a box of its two places and the ring, and no way index at all. What is lost: a long segment (over the
  ring) whose far end did not move, and the way's own centre (the position of its rows), which moves with it.
  **Measure first (no disk):** europe-west's five days in the delta form with the cover's way lookup turned off,
  against t2a's 1 difference in 1.39M. If close, the 280 GB goes away.
- **(b) If a way index is needed: compact it.** Refs delta-coded per way (2-3 bytes a ref), the reverse index kept
  only for nodes of ways that carry an area quest's interest (buildings, highways, barriers...): an estimate of
  40-80 GB, to measure on europe-west.
- **(c) The map data: a tile store, not two planets.** z14 tiles of the planet as small PBFs, each with every
  element that lies in it and every way that crosses it (complete ways, so a tile is valid map data alone), about
  the planet PBF's 85 GB plus 10-20% for the duplicated ways. A day rewrites the tiles its diff touches into a new
  generation and keeps the previous generation of only those tiles until the next day: D is the newest generation,
  D-1 is the newest generation but one of each tile, at a cost of a day's changed tiles (a few percent). A recount
  reads the tiles under its rectangles and ring and joins them (sorted merge, duplicates dropped). **Measure on
  europe-west:** the store's size against the clip's, the time to cut it, a day's update, and the read of a day's
  rectangles, and the recount on the tiles' data against the clip's (they must give the same rows).
- **Disk:** (c) about 100 GB and (a) none, against about 130 GB free while `planet.loc` (115 GB) and the stream's
  rows (48 GB) are kept, and the 12-07 planet job's 170 GB. So nothing big is built before 12-07; after it, with
  `planet.loc` rebuilt from the new file, (c) fits only if the 11-08 seed's own rows (48 GB) are given up.
- **Disk, revised (11-14, 14:05; owner: "we cleared some disc space and plan to clear 100 gb more in a month"):**
  343 GB free with `planet.loc` (115 GB) and the stream's rows on disk. A 100 GB tile store would leave about
  240 GB, above the 12-07 job's 170 GB even with `planet.loc` kept; with the further 100 GB in December, both stores
  fit beside the 12-07 reseed. The disk no longer forbids (c); the measurements on europe-west come first.
**Caught up to 11-14 (14:08):** six days (5171..5176), 7.8-13.7 min each (the files 300-505 s of it), no way unplaced on
any day. Each day drops 0.57-0.71M tier-1 rows of touched elements and adds 0.84-1.01M: the state grows by about
0.3M rows a day (0.015%), which the 12-07 count must confirm (new mapping opening quests, or rows a dropped key
should have taken). On europe-west's elements, 11-10..11-13 show only tier 1's known limits, and 11-13 is the same
row for row as europe-west's tier-1 stream and the four-file test.

**Measurement (a): the cover without the way index (11-14, 14:06-14:50; `tools/stream/europe-t2n.sh`,
`OPENQUESTS_NO_WAY_INDEX=1`, state `.scratch/stream/europe-west/t2n/`).** europe-west's five days as t2a, but a
changed way's old geometry taken as today's refs at yesterday's places, and no lookup of the ways holding a changed
node. **Tier 2 identical to t2a on every day** (0/0, 0/0, 0/0, 1/0, 1/0: the same `w1577774915 AddHousenumber`),
the rectangles a little smaller (14.5-297.8 km2 against 15.1-298.0). The cost is in tier 1's positions only: rows of
untouched ways whose node moved and whose quest point now lies outside every rectangle keep the old position,
by 11-13 12 matches and 33 waiting rows, all within 1.2 m (t2a: 0). No open set changes. **So the world's tier 2
needs no way index** (the 280 GB of the estimate): only the node store it has, a small store of the member ways of
the relations the cover follows (multipolygons, streets, ferry routes; not yet sized), and the map data store (c).

**Measurement (c): the z14 tile store (11-14, 17:00-; `tools/stream/tiles.py`, `tools/stream/tilestore.py`, tests
`tests/test_tiles.py`, `tests/test_tilestore_update.py`; work in `.scratch/tiles/`).**

*The tile rule.* What a tile holds, chosen from how the engine reads an area (AreaPass.kt): it takes a way when any of
its nodes lies in the padded box, then all that way's nodes; tagged nodes in the box; tagged relations (not the
ignored kinds) with such a way or node as member, their geometry built from **all** member ways, which the main pass
reads off the whole file; and it orders its map data by id hash, so the order the store hands things over in cannot
matter. So a tile holds: every tagged node located in it; every way with a segment that crosses it (a superset of
"a node in it": a long segment can carry a way's quest point across a small rectangle), complete, all its nodes
wherever they lie; every kept relation with a member node in it or a member way crossing it. Apart from the tiles,
the **relation store**: per kept relation, its member ways whole with their nodes' places.

*Proved first with a filter extract, no store* (`tiles.py extract`: the clip's objects that the tiles under the
rectangles and the 300 m ring would hold, written as one PBF). t2n's 103 rectangles of 11-13 (dublin-0 12 x 7 km, the
rest small) sit under 331 tiles; the extract is 8.76M objects, 105 MiB against the 1.75 GB clip; the recount on it is
**row for row the recount on the whole clip** (1,116,244 rows, 0 different), and on 11-12 the same (1,114,046). The
engine took 22 s on it against 35 s on the clip. Without the relation store's ways (7% fewer nodes) also 0 different
on this day: it stays, for multipolygons reaching beyond the ring.

*The store.* One pack file per generation (`pack-GGGG.bin`, tile payloads end to end) and a whole index per generation
(`idx-GGGG.npy`: key, pack, offset, length): no file per tile (the planet would be tens of millions of small files).
A payload is the tile's columns (ids and places delta-coded, versions, timestamps, tags as `k\0v\0` bytes), each
byte-shuffled, zstd level 3 over the whole. Untagged nodes keep only id and place (the store gives them version 1, no
timestamp): the recount does not see the difference (below). The relation store likewise (`rel-GGGG.bin`,
`relidx-GGGG.npy`), and two pair indexes, every way's and kept relation's tiles by id (`wtiles`, `rtiles`), for a
day's update to find a changed object's old tiles.

*Cut from the europe clip of 11-12* (the 32 city boxes europe-west's stream reads from; `tilestore.py cut`, from `tiles.py geom` + `attrs`): **59,026 tiles, 1.86 GiB, against
the clip's 1.63 GiB** (1.14x), plus the relation store 218 MiB (438,232 kept relations, 1.76M member ways): 1.27x the
clip in all. Copies: 175.6M node copies of 127.9M nodes (orphan untagged nodes dropped), 22.6M way copies of 21.4M
ways (1.06x), 0.57M relation copies. Tile sizes: median 5 KB, 90% under 89 KB, 99% under 450 KB, largest 1.9 MB (47
over 1 MB, 60 MB in all). Prototype times, Python: node places 8 s (pyosmium's C++ index), way refs 342 s, tags and
versions 930 s, the cut itself 451 s (tile pairs 192 s, payloads 77 s, relation store 41 s).

*Read through the store, D-1 (11-12):* the 331 tiles under the rectangles joined into one PBF (`tilestore.py read`:
duplicates dropped, every kept relation's member ways from the relation store), recounted: **1,114,046 rows, 0
different** from the recount on the clip. The join took 33.5 s: reading and decoding the tiles 2.3 s (92 MB of
payloads, 9 MB of relation blobs), merging 1.3 s, writing the PBF through pyosmium 29.9 s. The write is the
prototype's cost, not the store's: a PBF writer in the engine, or the engine reading the store, removes it.

*A day's update* (`tilestore.py update`: diff 5175, 11-12 to 11-13, the node store before the day being 11-12's node
places, as `planet.loc` read before `save()` is for the world). The tiles a day changes are rebuilt from a working set:
the old payloads of every tile it reaches, the old relation-store blobs of the relations it reaches, the diff over them,
and the tile rule run again; only the reached tiles are written, into a new pack and a new index. A tile is reached
through the old and new tiles of each changed node (its own place), each changed way and each way holding a changed node
(found in that node's old home tile, which holds every way with a node there: **no node-to-way index**), and each changed
relation (an unchanged relation's tiles change only where a moved member way came or went, already reached; one the
app ignores is in no tile). A reached tile that comes out the same keeps its old entry. Result: 59,279 nodes, 16,176
ways and 1,657 relations of the diff reach the store, plus 2,459 ways holding a moved node; **2,902 tiles reached of
59,026, 2,893 written (302 of them new, at the clip's edge), 461 MB: 4.9% of the tiles, 23% of the pack's 2.0 GB**
(with the region the later runs use, "Smaller tiles": 2,591 written, none new, the same 461 MB);
993 relation blobs (2.4 MB). Reached through a changed node's home 1,796 tiles (328 MB as they were), through a moved
way 2,036 (332 MB), through a changed relation 663 (82 MB); the sets overlap. 532 s in Python (diff 165 s, finding
49 s, reaching 126 s, the rule 156 s, writing 35 s). Two earlier runs, before a reached tile that came out the same
was kept and before relations were narrowed, wrote 5,664 tiles and 814 MB, half of them unchanged.
- **Held against a fresh cut of 11-13:** the 331 tiles under the rectangles byte for byte the same; of all 59,373 tiles,
  58,610 the same and every one of the 755 others (408 different, 302 only in the update, 45 only in the cut) touches
  the clip polygon's edge or lies outside it: the planet diff carries what the polygon clip leaves out. No tile wholly
  inside differs. The relation store: 438,327 of 438,360 blobs the same, 32 of the rest at the edge, and one a
  relation of relations created that day (no member ways, an empty blob in the cut, never reached by the update). The
  day's way and relation tile indexes: their 4,856 and 33 differing objects all touch the edge.
- **The bug the check found:** a rebuilt tile lost a relation held there only by an untagged member node no way holds
  (a site's label): the cut saw the node in the whole clip, the tile did not store it. A tile now stores its kept
  relations' member nodes (`tests/test_tilestore_update.py` has the case).
- **D through the updated store:** the 331 tiles joined and recounted at 11-13: **1,116,244 rows, 0 different** from
  the recount on the clip; D-1 through generation 0 again 0 different. Each read 34-45 s, of which the tiles 2.2 s.
- To rerun: `tools/stream/tilecheck/chain-z.sh 14` (both cuts, the update, every check) or `day12.sh` there (two
  days from generation 0). They read `.scratch/tiles/geom-*/` (from `tiles.py geom` and `attrs`) and the frozen t2n
  recount in `.scratch/tiles/ref/`.

*What it says for the world.*
- **Correctness: exact on two days.** The tile rule, the store and the update reproduce the clip's recount exactly, D
  and D-1, and the updated store equals a fresh cut away from the clip's edge on 11-13 and on 11-14 (the second day
  reading the first's indexes: "Smaller tiles", "A second day").
- **Size:** tiles 1.14x the PBF, relation store 0.13x: about 108 GB beside the planet's 85 GB PBF. The index is small
  (1.4 MB a generation here; tens of millions of tiles for the planet, about 1 GB a generation). The way-tiles index is
  not: 362 MB here (16 bytes a pair, 22.6M pairs, 18% of the pack), about 19 GB for the planet as plain pairs, and the
  prototype writes it whole each day. It only serves a changed way's old tiles; a key per way (its first tile; the rest
  from that tile's complete copy) is 12 bytes a way, or none at all if a changed way is always found through its
  nodes' old home tiles (a deleted way whose nodes all stay is the case that needs it), and a day's changes belong in
  an overlay, not a rewrite.
- **The day's write: 23% of the bytes for 4.4% of the tiles** (2,591). The tiles a day changes are the dense ones (city
  centres: up to 1.9 MB a z14 tile), and any edit rewrites its whole tile. So a generation's pack is about 0.46 GB a
  day on a 2 GB store, and keeping D-1 costs that much; packs whose tiles are all superseded by D-1 can be deleted, the
  few live tiles of the rest copied forward. This clip is 32 European city boxes padded by 2 km (Lisbon, Barcelona,
  Toulouse, Milan, Zurich, Salzburg, Munich, Paris, Prague, Antwerp, London at 3,071 km2, Amsterdam, ...): all
  urban, denser and more edited than the planet on average, so the world's share should be lower, but it is not
  measured. **Smaller tiles where data is dense** (a z15/z16 split of any tile over a few hundred KB, the index then
  keyed by quadtree cell) would cut the rewrite of point edits roughly in proportion; long ways and relations cover
  the same ground at any zoom. To measure before building.
- **Speed is the prototype's limit, not the design's.** In Python the cut is about 30 min with the passes, the update
  about 9 min a day on this clip (the planet diff's reading alone 2-3 min), the read 34-45 s, 31-41 s of it pyosmium
  writing the PBF. A world store needs the cut, the update and the read in compiled code (the engine's parallel blob
  reader did this clip's 128M nodes in 6.7 s), and the engine reading the joined tiles directly instead of a PBF.
