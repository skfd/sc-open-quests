## The planet cut, designed (2026-11-15, afternoon; owner: "Yes, planet cut"). Not built.

The cut above holds a file in memory (12 GiB for the clip, 41 GiB for Germany, about 720 GiB on that line for the
planet). This is the design of a cut that does not. It is rare work (once, and again when the tile rule or the kept
relations change at a repin), so hours are acceptable; exactness and fitting this machine are what it must have.

**Disk decides the order of work, so it comes first.** Free on C: today 263 GB, with the history file (170.7 GB) on
it and the 12-07 job wanting about 170 GB.
| piece | size | basis |
|---|---|---|
| node places by id (the stream's `planet.loc` in another build) | 108 GB | 8 bytes an id, ids to about 13.5 billion; `planet.loc` was 107 GiB |
| spill: every way with its nodes' places, by bucket | 110-135 GB | **a guess**: about the tiles' size at one copy a ref; to be measured as bytes a ref on Germany |
| member ways of kept relations, whole | about 15 GB | a guess from the relation store's 0.13 times the PBF |
| the store: tiles at z14 | 97-136 GB | 1.14 times the PBF as the city clip, 1.60 as Germany |
| relation store, way-tiles index | 11 GB, 19 GB | "Measurement (c)" |

The spill goes as its buckets are cut, so the peak is about the node file, the member ways and the larger of spill
and store with its indexes: **about 290-310 GB. The whole cut does not fit on C: today**, and less so beside the
12-07 job. It waits on the 2 TB drive (or on room made here). What fits now: the design's proof at clip and country
size (no planet resources), and one timing of the node file and the way pass (108 GB, deleted after).

**Which day.** The file on disk is the history of 2026-11-02, so a cut from it is the store of 11-02. A current store
is that plus every day's update since (the update is not built in Rust), or a cut of the 12-07 file. A planet
snapshot instead of the history file is a download of about 85 GB, the owner's call (only `osm-extracts` downloads
into the shared store).

**Tile zoom: fixed z14, as built.** "Smaller tiles" (adaptive, a split of dense tiles) is designed above and not in
Rust; the 124 GB estimate assumed it. The cut below does not depend on the zoom: its buckets are coarser cells.

**Why not the world files of the monthly count, cut one by one with today's binary.** An extract keeps a way that has
a node in its region; the tile rule keeps a way whose *segment* crosses the tile. A long segment (a ferry, a power
line) can cross a tile of a file it has no node in, so tiles would be wrong anywhere such a segment passes, not only
at the files' edges. The streaming cut is exact by construction.

**The cut: three streaming passes over a file sorted by type then id, then the buckets one by one.**
A *bucket* is a coarse cell (z8 proposed: 64 by 64 tiles); spill files are per z6 cell (at most 4,096, opened as
needed), each holding its z8 buckets' records.
- **Pass 0, relations** (the end of the file; the blobs are found by seeking). The kept relations (tagged, not
  ignored by the app) stay in memory whole: ids, versions, members, roles, tags. Two sorted id sets come out: every
  member way and every member node of a kept relation.
- **Pass 1, nodes.** Each node's place goes into the node file at its id. Each **tagged node** goes to its home
  bucket's spill (id, place, version, timestamp, tags) and, the same record, into one **tagged-node file** in id
  order with a sparse index in memory; a bit per id in memory says "tagged" (1.7 GB). Each **member node of a kept
  relation** (pass 0's set) goes to its home bucket's spill too, tagged or not (a tile stores its kept relations'
  member nodes even when no way holds them: the bug the Python update's check found), and its tile is kept in memory
  for pass 2's end.
- **Pass 2, ways**, in id order, decoded on all threads. For each way: its nodes' places from the node file (ids in
  a way lie close in the file: the access osmium's dense index relies on); its tiles by segment (`tiles.rs`, as
  now); its line of the way-tiles index, written as it goes. The way with its nodes' places, version, timestamp and
  tags goes to the spill of every bucket it crosses (1.001 buckets a way at z8, measured below). For each of its
  nodes that is tagged and at home in another bucket, a **need** (bucket, node id) is written: a tile gives version,
  timestamp and tags to every tagged node among its ways' nodes, far ones too. A **member way** of a kept relation
  is also written whole into the member-way file (id order, offsets in memory) and its tiles kept in memory.
- **After pass 2.** The needs, sorted by node id, are merged with the tagged-node file and those records appended
  to the needing buckets' spills. Each kept relation gets its tiles (its member nodes' tiles from pass 1, its member
  ways' tiles from pass 2) and is appended to those buckets' spills; its line of the relation-tiles index is
  written; its **relation store blob** is built from the member-way file (member ways whole with their nodes'
  places, wherever on the planet they lie) and written in relation id order.
- **The buckets.** Each z6 spill file is read and its z8 buckets cut in memory by today's code (the tile pairs, the
  payloads), several at once, their tiles appended to the pack; the spill file is then deleted. The index is sorted
  by key at the end (the pack's order does not matter to a reader). A bucket's ways crossing into other buckets
  bring their far nodes along in the spill record, so a bucket needs nothing from its neighbours.

Untagged nodes on no way and in no kept relation reach no spill and no tile, as now.

**Measured for it today** (the stores already cut, `idx-0000.npy` and `wtiles-0000.npy`):
| | europe clip (32 city boxes) | Germany |
|---|---|---|
| largest tile | 1.87 MB | 1.49 MB |
| largest z8 bucket, store bytes | 120 MiB | 383 MiB |
| largest z6 cell, store bytes | 170 MiB | 3,404 MiB |
| way copies a way at z14 / z10 / z8 / z6 | 1.057 / 1.004 / 1.001 / 1.000 | 1.085 / 1.005 / 1.001 / 1.000 |

The in-memory cut took about 4.3 times its store in memory (41 GiB for Germany's 9.5 GB), so a z8 bucket of 400 MiB
is about 2 GiB while it is cut, and a z6 file is never held whole. Germany is densely mapped; the planet's densest
z8 bucket is not known.

**Memory, by design:** the kept relations (pass 0), the tagged bit (1.7 GB), the member ways' tiles and offsets, the
spill writers' buffers, and the buckets being cut. The node file is read through the OS cache: 108 GB against 87.6 GB
of RAM, so not all of it stays cached. Node rows, 32 bits in the spike, go away (places are found by id); way and
relation rows are per bucket.

**What is not known, and how each is settled.**
1. **Is it exact at bucket borders?** *The streaming cut against the in-memory cut* by `storecmp.py`, on the clip
   and on Germany, with the bucket zoom a parameter: at z8, and at z11 or z12, where ways crossing buckets are
   common and every border rule above (far tagged nodes, member nodes, relations over several buckets) is worked
   hard. No planet resources. **This is the first thing to build.**
2. **The way pass against a node file larger than RAM.** One timing: pass 1 and pass 2 over the history file's
   current objects, the node file written, ways resolved and their tiles computed, nothing spilled. 108 GB, deleted
   after. Proposed threshold, the owner's to change: the two passes within 4 hours pass; over 12 hours fail and the
   node store is redesigned (places in id-sorted runs in memory, or the planet cut in two halves). No time is
   projected before that run.
3. **The spill's size.** Bytes a ref, from Germany's spill in step 1.
4. **Reading the history file at a date.** New code with its own oracle: `berlin-history` (on disk) filtered to a day
   by the Rust reader against `osmium time-filter` of the same file in the Docker image, object for object
   (`pbfcmp.py`). Only needed if the cut reads the history file itself; a snapshot or an `osmium time-filter` of the
   planet (hours, 85 GB more) avoids it.
5. **At planet size, exactness:** the planet store's tiles inside the europe clip of the same day equal that clip's
   store, away from the clip's edge.

### The streaming cut, built and proven below planet size (11-15, 15:00-16:10; owner: "Yes, build it now")

The owner's answers first: the cut's source is **the history file, read at a date by Rust** (to be proven on
`berlin-history` against `osmium time-filter`); the 108 GB timing runs **on C: after this proof**, the file deleted
after.

`tilestore scut --pbf X.osm.pbf --out S --day D [--z 14] [--bucket-z 8] [--keep-spill]` (`tilestore/src/stream.rs`;
the tile rule moved to `pairs.rs`, shared with the in-memory `cut`). It is the design above, with these differences,
each one named:
- **The node places are in memory**, sorted by id as the file gives them, found by binary search (16 bytes a node).
  The planet's file by id is not built: on a clip or a country a file by id would be nearly as large as the
  planet's (NTFS allocates a sparse file in 64 KB units, and a region's nodes are spread over the whole id range).
  So the one part of the design this proof does not exercise is the node file; the 108 GB timing does.
- **It reads a snapshot**, not the history file.
- The tagged-node file's index holds every tagged node (id, offset, length), not a sparse one; the relations of
  pass 0 are all held, kept or not. Both are memory to trim for the planet, not rules.
- A spill file is read whole and its buckets cut side by side; spill files go one after another.

**Exact, with the border rules worked hard** (`storecmp.py`, generation 0 against generation 0):
| input | bucket zoom | buckets | needs | against | tiles | relation blobs | pair indexes |
|---|---|---|---|---|---|---|---|
| europe clip 11-12 | z8 | 253 | 39,742 | the **Python** store | 59,026, 0 different | 438,232, 0 different | both equal |
| europe clip 11-12 | z12 | 8,561 | 735,132 | the **Python** store | 59,026, 0 different | 438,232, 0 different | both equal |
| Germany 11-07 | z8 | 167 | 112,219 | the Rust in-memory `cut` (itself equal to Python on the clip only) | 190,006, 0 different | 628,034, 0 different | both equal |

The pack and relation files are the same size to the byte as the Python store's. **The comparison can fail on a
border rule:** with the needs dropped on purpose (`TILESTORE_TEST_NO_NEEDS=1`) at z12, 38,141 of 59,026 tiles differ,
in exactly the tagged nodes' columns. The in-memory `cut`, refactored onto `pairs.rs`, was run again: equal to the
Python store.

**Cost, clip (one run each, 24 threads, other work on the machine):**
| | in-memory `cut` | `scut` z8 | `scut` z12 |
|---|---|---|---|
| wall | 35.7 s, 57.5 s (two runs) | 240.0 s | 239.0 s |
| peak working set | 12.2-12.3 GiB | **5.2 GiB** | 5.5 GiB |
| blob index | | 2.7 s | 1.3 s |
| pass 0, relations | | 0.9 s | 1.3 s |
| pass 1, nodes | | 34.9 s | 24.1 s |
| pass 2, ways | | 65.6 s | 59.9 s |
| needs and relations | | 2.7 s | 13.4 s |
| relation store | | 25.6 s | 22.1 s |
| buckets | | 107.1 s | 116.7 s |

**Cost, Germany (4.88 GB), one run:** 629.5 s and **33.4 GiB peak** against the in-memory cut's 128.7 s and
41.3 GiB: blob index 12.5 s, pass 0 1.5 s, pass 1 55.9 s, pass 2 132.3 s, needs and relations 3.5 s, relation store
34.5 s, **buckets 388.9 s**. The memory is not what the design promised. **The likely reason**, not
measured (the wrapper reports the peak, not when it came): Germany's largest spill file (one z6 cell) is 9.7 GB
uncompressed and is read whole, then its z8 buckets are cut side by side, after the node places (7 GB here) are
freed. If so the peak no longer grows with the file but is set by the densest z6 cell. For the planet: spill files
per z7 or z8 cell, or fewer buckets at once; the first act of that fix is the working set logged at each phase.
**Bounded memory is designed, not yet shown.** Not done here; done in "The bucket phase in bounded memory" below.

**A planet-only unknown, added: the antimeridian.** Neither input holds a way with nodes on both sides of 180
degrees. `segment_tiles` (here and in `tiles.py`, the same rule) walks every column between the two ends' x, so such
a way would be copied into a whole row of tiles, 16,384 at z14, and spilled to every bucket of that row. It stays a
superset of what the engine asks (a way by a node in the padded box), so not wrong, but large; how many such ways the
planet has is not counted. To settle before the planet cut: count them, and split such a segment at 180 degrees.
The engine carries its own caveat for cells at the antimeridian (HANDOFF: run the canary file first on 12-07).

Four to seven times slower than the in-memory cut on the clip and under half its memory; five times slower on
Germany and four fifths of its memory. The time is not tuned: each
pass decodes on all threads but spills, writes its indexes and reads the member-way file on one; the bucket phase
reads and unpacks each spill file on one thread. Of the clip's 5.2 GiB, about 2 GiB is the node places, which the
planet keeps on disk.

**The spill is larger than guessed: 12.8 bytes a ref written** (clip: 2.00 GiB for 168.2M refs, 6.04 GiB before
compression; Germany: 6.89 GiB for 602.3M refs, 12.3 bytes a ref). The planet's refs were estimated at 14.5 billion (above, from the europe clip's 1.32 refs a node), so about
**185 GB as it is coded now**, not the 110-135 GB in the table above: the peak on disk is then about 310-330 GB, and
the conclusion stands, more firmly: it does not fit on C: today. The coding is plain (whole ids and places, zstd
level 1 over rows); refs and places as steps from the one before, as the tiles code them, should bring it near the
tiles' own size. Not done: disk on the 2 TB drive is not the constraint.

**Next:** (1) the history file read at a date, with its oracle on `berlin-history` (done, below); (2) the node file by id and the
108 GB timing of passes 1 and 2 on the planet's history file; (3) the passes' single threads, if that timing says
they matter. The update in Rust waits behind these or runs beside them: it does not depend on the planet cut.

### The history file read at a date (11-15, 16:00-17:00; owner: "The next step toward the planet timing is the history-file reader")

`tilestore at --pbf X.osh.pbf --at T [--out Y.osm.pbf] [--stamp S]` writes a history file as it was at T as a
snapshot PBF (with no `--out` it only reads and counts); `tilestore scut ... --at T` cuts a history file as it was at
T (`tilestore/src/history.rs`; `Blobs::each_at` in `stream.rs`; `clip::metas` and `parse_into` in `clip.rs`).

**The rule is osmium's**, version by version (`osmium time-filter FILE T`): a version counts if it is visible, its
timestamp is at or before T, and the next version of the same object in the file, if there is one, is after T. A
deletion at or before T therefore removes the object. The rule needs only a version and the one after it, so each
block is decided alone on all threads, but for its last version: that one is held until the next block's first
version is seen (`Stitch`, in the file's order; at a pass's end the blob after the range is looked at). Only the
versions that count are copied out of a block (tags, refs, members); the others cost their id and timestamp.

**Exact against `osmium time-filter`** (osmium 1.18 in the Docker image `name-ru-repair-osmium`;
`berlin-history-261005.osh.pbf`, 413 MB, 23,735,962 versions; `tools/stream/tilecheck/atcheck.sh`, which compares
with `pbfcmp.py`: type, id, version, timestamp, place, tags, refs, members and roles):
| date | why this date | objects | different |
|---|---|---|---|
| 2019-01-01T00:00:00Z | an old round date | 5,969,070 | 0 |
| 2026-10-01T00:00:00Z | near the file's end | 9,305,598 | 0 |
| 2025-08-05T10:30:16Z | the second of a node's version 2 | 8,793,653 | 0 |
| 2010-08-18T11:50:20Z | the second of node 21508760's version 8 | 945,689 | 0 |
| 2010-08-18T11:50:19Z | the second before it | 945,689 | 0 |
| 2008-11-06T01:22:11Z | way 12618300 is given twice (below) | 393,648 | 0 |
| 2008-05-31T11:36:29Z | relation 15190 is given twice | 227,937 | 0 |

**The checks can fail.** The Rust file of 11:50:20 against osmium's of 11:50:19: 1 object different, node 21508760
(version 8 against 7). The border rule has unit tests (`cargo test`: every way of cutting one object's versions
into blocks, empty blocks among them, a deletion at a block's start, 3,000 random files cut at random, each held
against the rule applied to the whole file); with `<=` made `<` at the border, two of the three fail. Berlin's
file has 2,988 blocks, so the borders are also worked by the real file.

**Through the cut:** `scut --at 2026-10-01T00:00:00Z --bucket-z 12` on the history file against `scut` and the
in-memory `cut` of osmium's snapshot of that date (`storecmp.py`): 1,719 tiles, 15,739 relation blobs, both pair
indexes, **0 different** both times. The passes start in the middle of the file (ways at blob 2,215, relations at
2,916). What this does not hold: a tile keeps no version for an untagged node, so only the PBF comparison above
checks those.

**Timestamps that run backwards: in the data, and the rule then gives an object twice.** Berlin's file has 28
versions older than the version before them (2008 edits), and for each a window of one or two seconds in which
osmium's rule counts two versions of the object (`tools/stream/tilecheck/oshdates.py` lists them). osmium writes
both; so does `at` (it reports `notIncreasing: 1` at those two dates, 0 at the others). **`scut --at` refuses such
a date:** the reader counts, per kind and across blocks, the objects whose id is not above the one before, and the
cut stops when a pass reports any (run at both dates: it stops, on the doubled way and on the doubled relation; at
2026-10-01 it cuts as before). The cut's own asserts would not have caught the way: a way given twice passed
silently before this check (run, and found by review). The stop comes at the end of the pass that meets the
object, which on the planet is hours in. All 28 of Berlin's windows lie between 2008-05-03 and 2008-11-06. **The
planet's are not counted.** `backwards` counts the whole file whatever the date and will not be zero on the planet;
`notIncreasing` is the figure for the date, and `tilestore at` with no `--out` gives it for the cost of one read.

**Speed, and a finding about the allocator.** The first build read Berlin's file in 25-35 s, on one thread in
10.6 s: nine relation blocks (hundreds of versions of relations with thousands of members) took 10-13 s each to
decode on 24 threads at once and 5.5 s together on one. The cause was taken to be large allocations queueing on the
Windows heap, and the fix bears it out: with `mimalloc` as the crate's allocator, **1.44 s to read and decide the
file (three runs, 1.43-1.45), about 19 million versions a second; 1.8-4.5 s with the PBF written** (the 4.5 s
while other work ran). osmium's time-filter took about 20 s through Docker. One file, one size, in the OS cache:
**nothing about the planet's 170 GB is projected from it.** The allocator changed every command, so the clip was
cut again, one run each, other work on the machine: in-memory `cut` 24.7 s (35.7 and 57.5 s before), `scut` z8
133.9 s (240 s before), both still equal to `store-rs` (`storecmp.py`, 59,026 tiles, 438,232 blobs).

**What a history file costs the cut:** every version is decoded (Berlin: 23.7M versions for 9.3M objects at
2026-10-01, 2.6 a kept object), and each pass reads its part of the file: 170.7 GB for the planet against a
snapshot's 85 GB. Not measured at that size.

**Next:** the node file by id and the 108 GB timing of passes 1 and 2 on `history-261102.osh.pbf` at a date (the
owner allowed it on C: after this proof; the file deleted after). Before or with it: the working set logged at each
phase. Then the spill-file memory fix. (Both done, the two sections below.)

### Passes 1 and 2 on the planet, the node places in a file by id: 53 minutes (11-15, 17:26-18:23; owner: "go ahead")

`tilestore ptime --pbf history-261102.osh.pbf --at 2026-11-02T00:00:00Z --nodes .scratch/planet-time/planet.loc`
(`tilestore/src/ptime.rs`; log `logs/planet-ptime.log`, figures `.scratch/planet-time/planet.loc.json`). It is the
planet cut's unknown 2: the history file read at a date, every node's place written at 8 bytes an id, the file then
mapped and every way's nodes found in it and its tiles computed (`keys_of_way`, z14). Nothing is spilled, no tagged
node or member way is written, no store. The node file: latitude plus 2^31 and longitude, little-endian, eight zero
bytes for "no node"; written in id order in runs, a seek where ids are more than 4,096 apart. Deleted at the end.

**One run, 24 threads, another session's engine runs on the machine at the same time:**
| phase | seconds | working set | private bytes | what |
|---|---|---|---|---|
| blob index | 284.1 | 0.22 GiB | 0.26 GiB | 2,406,776 blobs, one header read each, on one thread |
| pass 1, nodes | 630.0 | 0.32 GiB (peak 0.60) | 0.63 GiB | 16,706,092,276 versions read, 10,975,350,797 nodes at the date (298,913,371 tagged); node file 106.84 GiB (114.7 GB), 49,267 seeks |
| node file to disk | 2.0 | | | `sync_all` |
| pass 2, ways | 2,554.4 | 65.11 GiB (peak 65.64) | 0.95 GiB | 2,479,548,086 versions read, 1,229,012,042 ways, 13,078,570,851 refs, 1,393,086,909 (way, tile) pairs |
| **in all** | **3,470 (57.8 min)** | | | passes 1 and 2: **3,184 s, 53 min** |

**Against the threshold (both passes within 4 hours pass, over 12 hours fail): passed, by more than four times.**
The node file by id works on this machine with the file (107 GiB) larger than what the OS can keep of it: pass 2's
working set is the mapped file's pages in memory, 65 GiB; the program's own memory stayed under 1 GiB in both
passes. **The seconds are an upper bound:** the engine session ran f0 counts from 17:23 to about 18:15 (up to 24
threads and 30 GB each) and then two test suites, and around 18:10 no memory was free, which takes cache from the
node file exactly while pass 2 reads it. Alone the run would be faster by an amount nobody measured.
Pass 2 took four times pass 1 for a seventh of the versions. Whether it waited on the disk or on the
processors was not measured (no CPU time or disk figures were taken), so what a faster disk or more memory would
change is not known.

**What this run does not include**, so it is not the planet cut's time: pass 0 (the relations, and with them
the relation blocks' memory, which on Berlin was where the allocator hurt); the spill (every way written with its
places, about 13 bytes a ref, on one thread as coded); the tagged-node and member-way files; the needs; the buckets
(on Germany the largest share: 389 of 630 s). The blob index is 4.7 minutes on its own and would be read once.

**Settled by it, for 2026-11-02:**
- **No object is given twice at this date** among nodes and ways (`notIncreasing` 0 in both passes), though the file
  has 61 node versions and 610 way versions older than the one before. Relations were not read.
- **Every ref has a node:** 0 of 13.08 billion refs without a place (the file is the planet, so this is the
  node file and the lookup agreeing with the data, at full size).
- **The antimeridian: no way has two nodes in a row more than 180 degrees of longitude apart.** So the segment
  rule's whole-row case does not arise from a way stepping across 180 degrees. One way does have 16,384 tiles, a
  whole row at z14; which way was not looked up (a line of latitude drawn round the globe with nodes less than 180
  degrees apart would give exactly that; not verified).
- **Refs: 13.08 billion, not the 14.5 billion estimated,** so the spill as coded is about 167 GB, not 185 GB
  (12.8 bytes a ref). The way-tiles index has 1.393 billion pairs, 1.134 a way (the clip: 1.057, Germany: 1.085).
- **Node ids reach 14.34 billion,** so the node file is 114.7 GB; the table in "The planet cut, designed" said 108.

**Not proven at this size:** the tiles themselves. The counts were held against `scut --at` on Berlin only (the
same nodes, ways, refs and pairs through a sparse node file); the planet's 1.39 billion pairs have nothing to be
held against until a planet store exists (unknown 5).

**Next:** the spill-file memory fix (done, the next section), then the spill's coding and the passes' single threads; the whole cut
still waits on disk (node file 115 GB, spill about 167 GB, store 97-136 GB with its indexes).

### The bucket phase in bounded memory (11-15, 19:10-20:00; owner: "go on")

Germany's 33.4 GiB peak had a likely cause, not a measured one. Now measured, then fixed (`tilestore/src/stream.rs`).

**The cause, measured.** `scut` logs the working set and private bytes after every phase (`ptime::memory`), and
samples the working set every 50 ms through the bucket phase (the process's own peak cannot be reset, and the
passes may have set it). Germany, the old arrangement (`--file-z 6 --cut-gib 0`: a spill file a z6 cell, one file at
a time, its buckets side by side): **11.3 GiB at most through the passes, 31.3 GiB in the bucket phase**, the
largest spill file 9.07 GiB of records. So the peak was the densest z6 cell, as supposed.

**The fix, three parts.**
- **A spill file a bucket** (`--file-z`, default the bucket zoom; it was two zooms coarser). Germany: 167 files
  instead of 22; the clip at bucket zoom 12: 8,561 files.
- **The spill's buffers are capped together** at 1 GiB (each still goes out at 4 MiB): with a file a bucket there
  are thousands of buffers, and without the cap their sum is not bounded. Past the cap every buffer is written.
- **Spill files are cut in groups under a budget** (`--cut-gib`, default 2: GiB of records, before compression):
  as many files as fit, one at least, cut side by side; their tiles written in order; then the next group.
Before the phase, what the passes held is dropped (the relations, the member and tagged-node tables), not only the
node places.

**Exact: every run below equals its oracle** (`storecmp.py`: tiles, relation blobs, both pair indexes; Germany
against `store-rs-germany`, 190,006 tiles and 628,034 blobs; the clip against `store-rs`, 59,026 and 438,232).
Fifteen runs in all, 0 different in each: five settings before the sampler was added, the six of the table below
(the 8 GiB budget ran only there), and four after the spill's appends were counted and its buffers freed (below).

**Memory and time, the second set of runs, the machine otherwise idle (pass 2 took 61-62 s in all four Germany
runs):**
| input | spill files | budget | groups | largest group, records | working set in the bucket phase | bucket phase | whole cut | process peak |
|---|---|---|---|---|---|---|---|---|
| Germany | z6 cells (old) | one file | 22 | 9.07 GiB | **31.3 GiB** | 76.5 s | 175.6 s | 31.3 GiB |
| Germany | a bucket | 2 GiB | 11 | 1.98 GiB | **7.8 GiB** | 62.7 s | 161.0 s | 11.4 GiB |
| Germany | a bucket | 0.5 GiB | 37 | 1.17 GiB | 6.7 GiB | 93.9 s | 192.0 s | 11.4 GiB |
| Germany | a bucket | 8 GiB | 3 | 7.60 GiB | 25.7 GiB | 48.2 s | 146.3 s | 25.7 GiB |
| clip, bucket z8 | a bucket | 2 GiB | 4 | 1.95 GiB | 7.6 GiB | 14.2 s | 54.3 s | 7.6 GiB |
| clip, bucket z12 | a bucket | 2 GiB | 4 | 2.00 GiB | 5.4 GiB | 18.8 s | 82.1 s | 7.8 GiB |

- **The bucket phase's memory now follows the budget, not the file.** The three large points lie near 1.5 GiB plus
  3.2 GiB for each GiB of records cut at once (31.3 for 9.07, 25.7 for 7.60, 7.8 for 1.98); the small one is above
  that line (6.7 for 1.17). It moves between runs: the default gave Germany 7.8 and then 8.3 GiB, the clip at z8
  7.6 and then 7.9.
- **Its floor is the largest single bucket.** At a 0.5 GiB budget the largest group is still 1.17 GiB: Germany's
  densest z8 bucket alone, which no budget splits. The planet's densest z8 bucket is not known; if it is too large,
  a finer bucket zoom is the lever (the clip is exact at z12).
- **Germany's process peak is now the passes', 11.4 GiB,** of which about 7 GiB is the node places held in memory
  here. The planet keeps those in the file by id (`ptime`), so this figure does not carry over either way.
- **Time is not worse at the default on Germany, with its 167 files:** the bucket phase 62.7 s against 76.5 s, the
  cut 161.0 s against 175.6 s. A smaller budget costs time (93.9 s at 0.5 GiB), a larger one buys a little (48.2 s
  at 8 GiB) for 18 GiB more. **Many files do cost time,** next paragraph.
- The spill is slightly smaller with a file a bucket on Germany (6.71 GiB, 11.96 bytes a ref, against 6.89 and
  12.28) and slightly larger on the clip at z12 (13.30 bytes a ref against 12.79): frames are smaller.

**What a file a bucket costs the passes: the appends.** Every record is spilled on one thread, and each buffer
that goes out is compressed, its file opened, appended to and closed. Counted (`spill:` in the log), one run each:
| input | spill files | appends | all buffers at once | compressing and writing | pass 2 | needs and relations |
|---|---|---|---|---|---|---|
| clip, bucket z8, a file a bucket | 253 | 1,771 | 0 | 14.0 s | 17.1 s | 1.2 s |
| clip, bucket z12, a file a z10 cell (old) | 1,411 | 2,929 | 0 | 15.2 s | 16.9 s | 4.4 s |
| clip, bucket z12, a file a bucket | 8,561 | 23,725 | 4 times | 31.6 s | 31.1 s | 11.9 s |
| Germany, bucket z8, a file a bucket | 167 | 4,856 | 0 | 44.0 s | 60.4 s | 1.7 s |

At bucket zoom 12 a file a bucket adds 16.4 s of writing for 20,796 more appends of the same 6.34 GiB: about
0.8 ms an append beyond the compression, and it makes pass 2 nearly twice as long (31.1 s against 16.9 s). Where
appends are few the time is the compression itself, on that one thread: 2.3 to 2.4 s for each GiB of records (clip
z8 and Germany). **The planet's count of buckets and of appends is not known, and no planet time is taken from
this.** If the appends matter there: a spill file a coarser cell again (`--file-z`), which the group budget now
makes safe only while a file fits the budget; or files kept open; or the spill compressed off the pass's thread.
The 1 GiB cap on the buffers together was reached only at z12 (4 times); when it is, the buffers themselves are
now freed, not only emptied (an emptied buffer keeps what it grew to, so the cap bounded bytes waiting, not memory).

**The earlier figures, for the record:** 33.4 GiB and 629.5 s for Germany were before `mimalloc`; the old
arrangement with it is 31.3 GiB and 175.6 s, so most of the time lost then was the allocator, not the cut.

**Still in memory through the passes, and not bounded for the planet** (designed as "memory to trim", unchanged):
the relations of pass 0, all of them, kept or not; the tagged-node index, 20 bytes a tagged node in a 24-byte
tuple, so about 7 GB for the planet's 298.9 million; the tagged bit (1.8 GB at 14.34 billion ids); the member
ways' positions and tiles. Germany holds 12.7 GiB of private bytes after pass 2 with the places in memory; what the
planet holds with the places in a file has not been run.

**Not done:** the passes joined to the node file (`scut` still keeps places in memory; `ptime` has the file but no
spill); the spill written on one thread; the spill's coding (12-13 bytes a ref); the antimeridian's whole-row way.

**Next:** `scut` with the node file by id (`--nodes F.loc`), held against today's `scut` on the clip and Germany
through a sparse file; then the tagged-node index and the relations trimmed. After that the planet cut needs only
disk: node file 115 GB, spill about 167 GB as coded, store 97-136 GB with its indexes.

### The node file inside the cut, two tables trimmed, and a disk incident (11-15, 20:15-21:45; owner: "keep building")

**`scut --nodes F.loc [--sparse]`: the node places in the file by id, not in memory** (`tilestore/src/nodefile.rs`,
shared with `ptime`; `Places` in `stream.rs` is now memory or file). Pass 1 writes the file, pass 2 reads it
through a mapping, and it is deleted when pass 2 ends (the member-way file and the spill carry the places on).
**Exact where it was run** (`storecmp.py`, 0 different): Berlin's history at 2026-10-01 against the same cut with
the places in memory (1,719 tiles), the clip at bucket zoom 8 and at 12 against `store-rs` (59,026 tiles, 438,232
blobs). `ptime` on Berlin, moved onto the shared module, gives its counts again. **Germany was not run to the end**
(the incident below). A region's file is sparse and its timing means nothing for the planet: the clip's pass 1
took 155.8 s and 183.3 s against 6-9 s in memory, pass 2 49.3 s and 64.2 s against 17-31 s.

**Two tables trimmed, exact on the clip (z8, z12) and Germany against their oracles, the places in memory:**
- **No index of the tagged-node file.** The needs and the file are both in id order, so the needs are served by one
  read of the file. The index was 24 bytes a tagged node: about 7 GB for the planet's 298.9 million.
- **Relations that are not kept are let go as they are read** (in the block's own thread), not held to the end.
  Private bytes after pass 0: Germany 1.70 GiB (2.97 before), the clip 1.59 GiB (1.83).
- Germany's process peak: 10.5 GiB (11.4 before), still the node places in memory. With them in the file the clip's
  passes hold 4.6 to 6.1 GiB of private bytes; what the planet's hold has not been run. Still held through the
  passes: the kept relations, the tagged bit (1.8 GB at planet size), the member ways' tables, the needs.

**The incident: C: full at about 21:13, and about 216 GB not given back since.** Two separate things.
1. *A region's sparse node file is large.* NTFS allocates a sparse file in 64 KB units and a region's nodes are
   spread over the whole id range: Berlin's file (7.9M nodes) takes 22.9 GB of disk, and Germany's (442.6M nodes)
   took everything that was free and stopped the run with "not enough space on the disk". **Guard, built and seen
   to work:** the writer reads the free space of its disk every 256 blocks and under 40 GiB deletes its file and
   stops. Do not run a country through `--nodes --sparse`. The planet's own file is 115 GB, not sparse.
2. *A node file the program deleted itself did not give its space back.* Reproduced on Berlin: the same file
   deleted with `rm` after the program ended frees its 22.9 GB at once (free space 42.4 GB to 65.3 GB); deleted by
   the program (unmapped, then removed while its handle was still open) the name goes and 20.4 GB stays taken, with
   the process gone and 20 s later still. The four files deleted that way on the way to the incident (Berlin twice,
   the clip twice) and two tests after it account for the missing space: C: had 258 GB free at 21:00 and has 43 GB
   now, with nothing of that size on the disk. **The cause is not known.** Seen at 22:20 from the owner's elevated prompt: shadow
   copies hold 11.8 GB (ruled out); `fsutil volume diskfree C:` gives 42.5 GB free, 38.2 GB "Total Reserved" and
   about 178 GB allocated to nothing listed; no tilestore process is left. The reserve suggests sparse files still
   held in the kernel (a restart would clear that), not shown. Which difference from `rm` after the exit matters
   is not established either. Taking 54 GB of
   memory for a moment, until 2.5 GB was available, freed nothing (and grew the pagefile by 17 GB for a minute;
   the owner was using the machine). The planet's node file at 18:23, not sparse, deleted the same way, did come
   back within minutes. What is known to work is deleting after the handle is closed. **Changed, not yet shown to
   help:** the file is cut to length 0 before it is removed (the guard's path too); the one test of it ran into the
   40 GiB floor instead. Finding or freeing the space needs an elevated prompt (`vssadmin list shadowstorage`,
   `fsutil volume diskfree C:`, `chkdsk C:` read-only) or a restart, which are the owner's.

**Closed 11-15, 23:20.** The held files were in `C:\$Extend\$Deleted` (176.4 GiB on disk, the owner's WinDirStat):
deleted by name and still referenced by Windows, no process of ours left. A restart released them (283 GB free
after it). **The cut-to-nothing delete is shown to work,** one run on Berlin: 291.5 GB free before, 291.0 GB after
the program deleted its 22.9 GB file, 291.0 GB 20 s later; the same run left 20.4 GB taken before the change. What
held the files is not known; cutting the file first makes it not matter.

**Next, as written before the restart (its first item is done):** show the cut-to-nothing delete frees the space (Berlin, 23 GB, watch free space
before and after); then the spill's appends and coding. The planet cut itself waits on the 2 TB drive.

### The spill off the pass's thread, and its ways' refs coded (11-15 23:40 to 11-16 00:15; owner: work through the night)

Two changes to `tilestore/src/stream.rs`, each run against the oracles on its own (`.scratch/history/spill.sh`: the
clip at bucket zoom 8 and 12 against `store-rs`, Germany against `store-rs-germany`, the places in memory;
`storecmp.py`, 0 different in every run). The baseline was taken the same night on the unchanged program, after the
restart, the inputs read once first; what else the machine was doing was not looked at. One run each.

**1. Six workers compress and append the spill.** The pass's thread only fills the buffers; a full one is handed
to a worker over a bounded queue (8 buffers a worker), which compresses it and appends it as one write. A file
always goes to the same worker, so its frames are whole and in order. A worker whose write fails stops the run.

**2. A way's refs are coded.** The record keeps its head (id, version, timestamp, count); then the refs, their
latitudes and their longitudes, each run as differences in zigzag varints (a ref with no node: the old marker, in
the same run); then the tags. It was 16 bytes a ref. Node and relation records are unchanged. With
`TILESTORE_TEST_WAY_CODING` set every way is read back from its record in pass 2 and compared: 21,380,964 ways on
the clip (both zooms) and 71,518,636 on Germany, all as they went in.

| input | | pass 2 | whole cut | spill written | bytes a ref | appends |
|---|---|---|---|---|---|---|
| clip, bucket z8 | before | 21.3 s | 59.2 s | 1.99 GiB | 12.69 | 1,771 |
| | workers | 8.6 s | 41.7 s | 1.99 GiB | 12.69 | 1,771 |
| | workers, refs coded | 7.7 s | 42.4 s | 1.65 GiB | 10.53 | 1,407 |
| clip, bucket z12 | before | 31.8 s | 79.5 s | 2.08 GiB | 13.30 | 23,725 |
| | workers | 17.4 s | 59.6 s | 2.08 GiB | 13.30 | 23,725 |
| | workers, refs coded | 15.1 s | 59.4 s | 1.73 GiB | 11.07 | 19,941 |
| Germany | before | 73.8 s | 175.5 s | 6.71 GiB | 11.96 | 4,856 |
| | workers | 31.7 s | 129.9 s | 6.71 GiB | 11.96 | 4,856 |
| | workers, refs coded | 27.3 s | 121.9 s | 5.49 GiB | 9.79 | 3,526 |

- **Pass 2 is less than half as long** (Germany 73.8 s to 27.3 s). The workers together still work 54 to 85 s on
  Germany; the pass waits for them 0.2 to 1.4 s at bucket zoom 8. At zoom 12 it waits 12 to 15 s: when the 1 GiB
  cap sends every buffer out at once (3 or 4 times), thousands of small buffers queue up.
- **The spill is 17 to 18 % smaller, not half.** Refs were only half of it before compression. Germany, before
  compression: 18.42 GiB, of which way records 15.77 (the refs 9.03, at 16 bytes each of 606.0M spilled), node
  records 2.52, relation records 0.12. Coded, the way records are 10.59 GiB, so the refs are 3.85 GiB, 6.8 bytes
  each, and the whole 13.23 GiB. What is left is mostly tags and record heads, which this does not touch.
- **For the planet: about 137 GB of spill instead of about 167 GB,** if it shrinks as Germany's did (13.08 billion
  refs at 9.79 bytes would be 128 GB; neither is measured).
- **The cut budget still counts the old bytes.** A file's size is its records' bytes as they were before the
  coding (`way_units`), so `--cut-gib 2` cuts the same ways at once as before and the bucket phase's memory is
  where it was: Germany 7.40 GiB (7.81 before), the clip 7.07 and 5.21 (7.26 and 4.87). The log's "GiB raw" and
  `spillRawBytes` in `meta.json` are the real bytes; `largestSpillFileRawBytes`, `largestCutGroupRawBytes`,
  `cutBudgetBytes` and the `buckets:` line are the old ones.

**Not done:** the tags and heads in the spill (most of what is left; a higher zstd level on the workers is the
cheap thing to try); the passes' own single thread (the records are still handed to the spill one by one); the
antimeridian's whole-row way. **Next:** the planet cut needs only disk (node file 115 GB, spill about 137 GB,
store 97-136 GB with its indexes), so it waits on the 2 TB drive.

### Germany through a node file that is not sparse, and the spill's compression level (11-16, 00:35-00:55; owner: "keep building")

**Germany, the node places in a file by id as the planet's will be, equals its oracle** (`.scratch/history/gnode.sh`:
`scut --nodes F.loc`, no `--sparse`; `storecmp.py` against `store-rs-germany`, 0 different, 190,006 tiles and
628,034 blobs). This was the run the disk incident stopped. One run.
- **The file:** 106.97 GiB long (highest id 14,357,382,709), 553,711 seeks, 110.1 GiB less free while it stood. It
  was deleted by the program when pass 2 ended and **its space came back**: 288.7 GiB free before the run, 276.5
  GiB with the finished store (8 GiB) still there, 285.4 GiB after the store was removed. The 3.3 GiB between
  first and last is the disk's own drift, not the delete: the Berlin test run again at 01:02 with readings around
  it (314,621 and 314,620 MiB free in the 45 s before, 314,620 MiB after the program deleted its file, 314,617 MiB
  30 s later) lost nothing, and between 00:59 and 01:01, with no run of ours going, free space rose by about 22 GiB
  (285 GiB to 307 GiB: another session deleted 23 GB of stale files from the shared OSM store, commit f3f18ecd).
- **Memory:** private bytes 4.0 GiB after pass 1 and after pass 2 (11.0 and 7.7 with the places in memory). The
  working set reached 34.8 GiB in pass 2: the mapped file's pages, which the system can take back, counted as the
  process's. The bucket phase's working set 7.69 GiB, as without the file.
- **Time, which says little for the planet** (a country's nodes are a thin scatter over the whole id range, the
  planet's fill it): pass 1 63.5 s (12.7 s in memory), pass 2 123.6 s (27.3 s), the cut 269.1 s (121.9 s).

**A higher zstd level on the spill buys little: level 1 stays.** `TILESTORE_SPILL_LEVEL` (a test switch; unset is
level 1). Germany, the places in memory, each equal to the oracle, one run each (`level.sh`):
| level | spill written | bytes a ref | the workers together | the pass waited | pass 2 | whole cut |
|---|---|---|---|---|---|---|
| 1 | 5.49 GiB | 9.79 | 45.3 s | 0.2 s | 25.9 s | 122.6 s |
| 3 | 5.25 GiB | 9.35 | 94.4 s | 1.2 s | 29.5 s | 119.4 s |
| 6 | 5.00 GiB | 8.91 | 259.2 s | 13.7 s | 43.9 s | 138.3 s |

Level 3 is 4 % smaller for twice the workers' time, level 6 is 9 % smaller for nearly six times and holds the pass
up. For the planet that would be about 6 or 12 GB of about 137. If the spill has to be smaller, it is the tags'
and heads' own coding that is left, not the level.

**A free-space floor on the spill and the pack too (11-16, 00:53-01:00).** The node file's floor (40 GiB free on
its disk) now holds for every large writer of the cut (`nodefile::under_floor`). The spill looks at its disk every
64 appends, and under the floor ends its workers, deletes the spill and stops the run. The bucket phase looks
before each group of spill files, and under the floor stops and says the store is not whole (what is written is
left). **Seen for the spill:** with `TILESTORE_TEST_FLOOR_GIB=100000` the clip's run stopped at its first append
("the spill is deleted and the run stopped: 285.0 GiB free on its disk, under the floor of 100000 GiB", exit 101)
and no spill was left. **What a stop of the spill leaves:** the rest of the `work` folder (the tagged-node file, the member-way
file) and, with `--nodes`, the node file itself, 115 GB on the planet: nothing on that path deletes it. Both are
removed by hand, which frees the space at once. **Not seen: the bucket phase's stop** (the spill's comes first under any floor that would
show it). The clip (z8, z12) and Germany equal their oracles with it built (`spill4.out`).

### The planet cut, run: 1 h 42 min, and the clip of the same instant agrees (11-16, 01:47-03:30; owner: "Yes, run the cut")

Room made first (the scratch cleared, C: 544 GB free), so it ran on C: without the 2 TB drive.
`.scratch/planet-cut/run.sh` (hidden, log `logs/planet-cut.log`): `scut --pbf history-261102.osh.pbf --at
2026-11-02T00:00:00Z --day 2026-11-02 --nodes planet.loc --out store`, defaults (z14 tiles, bucket z8, 2 GiB
budget), the node file not sparse, binary main at 4b1003b4 copied out of `target/` and smoke-tested first (Germany
through a node file, equal to `store-rs-germany`). Nothing else of ours ran but two `du`/`find` size scans of the store in the bucket phase. One run.

| step | time | what it did |
|---|---|---|
| blob index | 266.4 s | |
| pass 0, relations | 34.8 s | 15,052,718 read, 12,514,868 kept; 45,720,197 member ways, 11,116,833 member nodes |
| pass 1, nodes | 780.5 s | 10,975,350,797 nodes, 298,913,371 tagged; node file 106.84 GiB, highest id 14,339,779,110 |
| pass 2, ways | 2,258.5 s | 1,229,012,042 ways, 13.08 billion refs, 1.393 billion (way, tile) pairs, 12.6 million needs |
| needs and relations | 95.7 s | |
| relation store | 558.1 s | 12,514,868 relations, 57,658,655 member ways, 12.6 GiB |
| buckets | 2,141.6 s | 178 groups of spill files, the largest 2.56 GiB of records |
| **all** | **6,135.7 s** | **32,110,824 tiles, the pack 232.55 GiB** |

- **Against `ptime` (11-15):** pass 1 630 s then, 780 s now with the spill; pass 2 2,554 s then on a busy machine,
  2,258 s now with the spill. The same counts of nodes, ways, refs and pairs.
- **The history reader:** 19.25 billion versions over the three passes, 12.22 billion at the date; 850 older than
  the one before (backwards timestamps), none of which gave an object twice (the cut would have stopped).
- **The spill:** 28,329 files, 211.80 GiB of records, **90.16 GiB written, 7.40 bytes a ref** (Germany 9.79; the
  guess was 137 GB). 1,108,345 appends; every buffer was full at once 148 times, and **the pass waited 807 s for the
  six workers**, a third of pass 2: more workers, or a coarser `--file-z`, is the lever if the cut must be faster.
- **The store is larger than designed: 268 GiB on disk (about 288 GB).** The pack 232.55 GiB, the relation store 12.6 GiB, the
  way-tiles index 20.8 GiB, the rest about 1.6 GiB. The design's 97-136 GB for the tiles (1.14 to 1.60 times the
  PBF) was low: the planet's pack is about 2.7 times its 85 GB PBF, against Germany's 1.60 and the clip's 1.14, from
  long ways copied into every tile they cross outside cities. "Smaller tiles" would not shrink this; fewer copies
  of a long way would.
- **Memory:** private bytes at most 11.6 GiB (pass 2); the working set reached 69.9 GiB in pass 2, the mapped node
  file's pages; the bucket phase at most 22.3 GiB (the planet's densest bucket fits the default budget).
- **Disk** (`df -BM`, MiB): 544,259 free at the start (531.5 GiB), **the lowest reading 249,948 (244.1 GiB)**, every
  5 minutes, at 03:27 near the bucket phase's end: about 287 GiB (309 GB) at the peak, inside the design's 290-310 GB.
  276.8 GiB free at the end with the store; the node file and `work` were deleted by the program and their space
  came back.

**Exactness at planet size (the design's item 5): the planet store agrees with the clip of the same instant
wherever the clip is whole.** `tools/stream/tilecheck/subcmp.py --clip S1 --planet S2 --poly P [--inset-km 2]`
compares, by decompressed payload, every tile whose square lies at least the inset inside the clip's polygon.
The clip: `europe-2026-11-02.osm.pbf` (sequence 5164, the history file's own instant; pinned for the check and
unpinned after), cut by the same binary (`cut`, 58,314 tiles, 25.7 s), `.scratch/planet-cut/clip-1102`.

| inset | tiles inside | same | differ | only in the planet | only in the clip |
|---|---|---|---|---|---|
| 2 km | 14,001 | 13,964 | 32 | 5 | 0 |
| 0.5 km | 16,828 | 16,770 | 50 | 8 | 0 |

**Every difference is a way the planet has and the clip lacks, and nothing else:** for all 58 tiles (0.5 km; the
37 at 2 km among them), the planet's tile with those ways and the nodes only they bring taken out equals the clip's,
node, way and relation, version, tags and refs (`.scratch/planet-cut/why3.py`; on the 11-12 clip against 11-02 it
explains 4 of 5,964). Four ways: 153021227 (3 nodes, from Kent to Surrey, across London's box), 1091714367 (8
nodes, along the Kattegat coast, across Göteborg's box), 172152780 (3 nodes, the same) and 1117929203 (6 nodes).
**Every node of each lies outside the clip's polygon**, so `osmium extract` leaves them out while their segments cross the clip's tiles:
the case "Why not the world files of the monthly count" names. There the planet store is right and the clip is not.
The comparison itself: the clip against itself equal (13,996 tiles), the 11-12 clip against 11-02 not (5,960 differ).
Not compared: the relation store's blobs and the pair indexes (a clip's relations are cut at its edge). **Read:**
`tilestore read` of t2n's 331 tiles from the planet store, 3.17 s, one run, after the comparisons had read many
of the same tiles (2.38 s of it finding the tiles, not explained; the clip's store 1.07 s); tile bytes within 101
bytes of the clip's, and about 300,000 more nodes and 10,000 more ways, likely from the relation store (11.6 MB of
relation blobs against 9.0 MB: a planet relation carries its member ways whole), not shown object by object.

**Not done:** the update in Rust (a current store is this cut plus every day since, or a cut of the 12-07 file);
the engine's count on a read of the planet store; the antimeridian's whole-row way in this store. Left on disk:
`.scratch/planet-cut/store` (268 GiB), `clip-1102` (1.9 GiB), `subcmp-*.json`, `read-*.osm.pbf`, `why*.py`.

### The day's update in Rust, equal to the Python update on two days (11-16, 08:05-08:25; owner: "rebuild daily update")

`tilestore/target/release/tilestore.exe update --store S --diff N.osc.gz --before D-1.osm.pbf --day D [--polygon P]`
(`tilestore/src/update.rs`, `osc.rs`). A step-for-step port of `tilestore.py update`. That includes the choices that
look arbitrary: which copies make up the working set, and what is filtered by the store's region and what is not.
The port is held against the prototype's output, so it keeps them. New code beyond the port:
- **The diff reader:** the last version of each object in file order. A node in `<delete>`, or one without a valid
  location, counts as deleted. Coordinates are parsed to 1e-7 as libosmium parses them, with no float in between.
  Attribute values are normalised as an XML parser must, then unescaped.
- **The node places before the day:** read from the clip's PBF of the day before, not from `geom-N/nodes.idx`. Those
  were deleted in the scratch cleanup, and they came from the same PBF.
- **`store.json` last:** written to a temporary file and renamed, so a generation exists only once its files do.

**Held against the Python store's generations 1 and 2 (`.scratch/tiles/store`, made by `day12.sh`)** on a copy of
the Rust cut of 11-12 (`.scratch/tiles/store-rsu`; generation 0 was shown equal to the Python store's on 11-15):

| day | diff | Rust | Python | storecmp (tiles, relation blobs, both pair indexes) |
|---|---|---|---|---|
| 11-13 | 5175 | 42.5 s, 10.3 GiB peak | 623 s | equal: 59,026 tiles, 438,348 blobs, 22,607,707 + 570,881 pairs |
| 11-14 | 5176, on the Rust generation 1 | 38.5 s, 10.7 GiB peak | 571 s | equal: 59,026 tiles, 438,514 blobs, 22,614,482 + 571,106 pairs |

Every count the prototype records also agrees, for example changed nodes, parent ways, relations reached, tiles
reached by each cause with their bytes, tiles written, and bytes written.

Checks:
- **Negative control:** the Rust generation 2 against the Python generation 1 differs (2,426 tiles, 744 blobs,
  both pair indexes), and storecmp exits 1.
- **Synthetic day:** `tests/test_tilestore_update.py` now sends the synthetic day through the binary too, against a
  fresh Rust cut of the day after and against the Python update. It covers a deleted tagged node, a moved node, a
  new way and node, and a relation gaining a far member node.

Of the 42.5 s, 14.2 s is the diff (single-threaded XML), 6.8 s the node places, and 5.8 s the tile rule. The rest
is finding and writing the tiles.

**What a planet day would take, measured as a lower bound (`.scratch/planet-cut/reach.py`, diff 5165, 11-02 to
11-03, against the planet store's own indexes):** 180,583 tiles holding 7.71 GB of compressed payload, 3.1% of the
store's bytes. These come from three sources, which overlap:
- the new home tiles of the diff's 3.62 million nodes: 46,165 tiles
- the old tiles of its ways that had any: 84,213 tiles
- the old tiles of its relations that had any: 89,412 tiles

Missing from the bound are the old homes of changed nodes, the parent ways, and the new tiles of changed ways. The
clip's day for comparison reached 2,595 tiles and rewrote 2,591 of them, which held 0.46 GB before the day. It
peaked at 10.3 GiB. So the planet day is at least 70 times the tiles and 17 times the bytes. 5165 is a light day: 3.6 million nodes, where 5175 had 6.0 million.

**So this port cannot run on the planet store as it is. That is the next design, not built.** Four things stand
in the way:
1. **Node places before the day.** On the planet these come from a node file by id. `scut` deletes its file after
   pass 2, so it would have to be rebuilt: about 115 GB, about 18 minutes for the blob index and pass 1 (`ptime --keep` runs pass 2 as well; pass 1 alone needs a small
   subcommand). It
   would then be kept and moved forward each day by the diff's nodes. A smaller choice needs design: one tile key
   per id (4 bytes, about 57 GB). A node in a way is in its home tile, so its place can be read from there. A side
   table would hold the few nodes no tile holds.
2. **Memory.** One working set for a planet day would be roughly 80 GiB or more, an estimate scaled from the
   clip's peak, on an 87.6 GB machine. Part of the clip's 10.3 GiB does not grow with the reach: about 2 GB of node
   places and the parsed diff. But `load_pairs` alone would hold the planet's 22.3 GB of way pairs, and the new
   copy beside it. The rebuild has to go in groups of reached tiles. Each group's working set is:
   - the group's old tiles
   - one old tile of each moved way that reaches the group (a tile holds every node of its ways)
   - the relation blobs it needs
   The result must equal the single working set's, restricted to the group, and the clip can show that.
3. **The pair indexes.** The prototype rewrites them whole each day. On the planet the way pairs alone are
   22.3 GB, and each generation keeps its own copy. Read them mapped, merge the day's changes in a stream, and keep
   only the newest (an update needs only that).
4. **Disk.** Each day writes at least the bytes of its changed tiles, about 8 GB, plus a 0.77 GB index. Fourteen
   days to reach today from 11-02 come to well over 100 GB beside the 268 GiB store and the node file. That does
   not fit on C: before 12-07, and the space of tiles superseded by later generations never comes back without
   compaction (rewriting live tiles out of old packs). The alternative is to cut the 12-07 history file anew and
   update from there.

**The node store need not be extra disk.** The world stream's node store (`.scratch/store/planet.loc`, to be
rebuilt before 12-07 by `.scratch/store/planet.sh`) is an osmium `dense_file_array`: 8 bytes per node id, longitude
then latitude, an empty place at both values 2^31-1. `stream.py` `DenseLocations` moves it forward each day. That
is the same information as the cut's node file, in another byte order. So if the update reads that layout as
`--before`, one file serves both. The cost is order: the tile store's update for day D has to run after the stream
has saved day D-1 and before it saves day D.

The planet also needs a "no region" mode: `region_of` without a polygon spreads the held tiles by one, which is
right for a clip and wrong for the world. The only oracle for a planet update is a clip of the day after, compared
inside its polygon (`subcmp.py`): `europe-2026-11-03.osm.pbf` for diff 5165, pinned for that until the check is done.

### Toward the planet: world mode, the node file, pair indexes in a stream, and the rebuild in groups (11-16, 08:40-09:20)

Three of the four obstacles named above are now addressed and held against the Python store: the node places, the
pair indexes, and the memory of the tile rebuild. Memory is only partly addressed: grouping bounds the tile rebuild,
but the first working set (the carried copies) and the relation store's working set are still single. The fourth
obstacle, disk, is the owner's call. Each piece has its own commit.

- **`--world` and `--before-loc F`** (8bb2b2a0). World mode has no region, so every tile counts. The node places
  before the day come from a node file by id in osmium's `dense_file_array` layout. That is the layout the world
  stream's `planet.loc` already has, and `stream.py` `DenseLocations` keeps it current: 8 bytes per id, longitude
  then latitude as int32, both 2^31-1 when empty (checked on a file written by pyosmium). The synthetic day run
  this way equals the fresh cut, and an empty node file changes the result.
- **Pair indexes mapped and merged in a stream, and `--prune-pairs`** (e1f90086). The way and relation pairs are
  read through a mapping. The new file is the old one, less what the day drops, merged in one pass with the day's
  sorted additions, so the planet's 22.3 GB of way pairs never enter memory. `--prune-pairs` deletes the previous
  generation's pair files once the new ones are written; only the next update reads them. Both clip days are
  still equal to Python, with and without pruning.
- **`--group-z G`: the reached tiles rebuilt one cell of zoom G at a time** (02811a1b). Three phases:
  - **Finding** decodes tiles only in passing. These are the old homes of the changed nodes, one old tile of each
    moved way, and the old homes of the new versions' nodes, which together are the prototype's first working set.
    From them it keeps copies of four things: the moved ways with their nodes, the relations that a moved way or a
    changed node reaches, the needed nodes, and the changed relations' member ways that did not move. The first
    working set is built from those copies, and it finds the same new way tiles, relations and reach.
  - **Each group's working set** is the group's own old tiles plus the carried copies. That is enough because the
    tile rule puts an object in a tile only if the object was there before (its old payload has it, with every
    node of its ways) or the day moved it there. A day moves things only through moved ways, changed nodes and
    the relations they reach, and the carried copies hold all of those whole.
  - **The relation store** is rebuilt from the reached relations' old blobs and the carried copies.

  **Equal to the Python store on both clip days at group zoom 8 (72 and 86 groups), 12 (794 and 841) and 14 (2,595
  and 2,438, one tile each)**: every tile, relation blob and pair. The synthetic day runs grouped too. The equality
  rests on every copy of an object in one generation being the same, which a cut and this update keep. It is shown
  on these two days, not proved for every day.

  | day one (5175) | wall | peak working set |
  |---|---|---|
  | one working set | 37.9 s | 10.3 GiB |
  | `--group-z 8` | 38.9 s | 5.51 GiB |
  | `--group-z 10` | 45.7 s | 5.48 GiB |
  | `--group-z 12` | 73 s | not measured |
  | `--group-z 14` | 159 s | not measured |

  **Every group carries the whole diff share and the carried copies,** so a group costs a fixed amount on top of its
  tiles. That amount grows with the diff, not with the store. In world mode, where the share is the whole diff, it
  was about 0.2 s a group on the clip: diff 5175 on the Rust cut of 11-12 with `--world` took 9.7 s of rule time
  in one working set and 27.8 s in 91 groups at zoom 4. Those two runs are equal to each other: 131,000 tiles
  (71,974 of them new), every blob, both pair indexes. **Hence `--group-mib M`** (08a86e24): the tiles in zoom-8
  cell order, a group closed once its old payloads reach M MiB. Any partition gives the same store.
  - **World mode, diff 5175, 256 MiB:** 3 groups, 38.2 s, peak 8.43 GiB, equal to the single working set (10.65 GiB).
  - **Both polygon days, 64 MiB:** 7 and 8 groups, 35.0 s and 32.9 s, equal to the Python store.
  - **Synthetic day:** run with all of the planet's flags together (`--world --before-loc --group-mib 0
    --prune-pairs`).

  **For the planet, from diff 5165 against the planet store** (lower bounds, `.scratch/planet-cut/reach-5165.json`):
  - the reached tiles lie in 3,623 zoom-8 cells (666 at zoom 6, 13,865 at zoom 10), so a group per cell would add on
    the order of 12 minutes, and a 512 MiB budget makes about 15 groups
  - the diff's own relations have 13,938 blobs of 49 MB, so the relation store's working set is small beside the
    tiles

  What remains at 5.5 GiB does not depend on the groups. It is the clip's node places read from its PBF (about 2 GB;
  on the planet that is the mapped node file) and the parsed diff, which is the planet's on any store. On the planet
  the carried copies grow with the day; their size there is not measured.

**Still in the way of a planet update.**
- **The node file at the store's day.** The world stream's `.scratch/store/planet.sh` builds `planet.loc` at 11-02
  and then moves it forward to 11-08 in the same run. Bringing the 11-02 tile store forward needs the file at 11-02
  and moved one day at a time beside it. Moving it forward in Rust, by writing the diff's places, is small and not
  built.
- **Disk:** about 115 GB for the node file, and about 8 GB of pack a day without compaction. That is the owner's
  call.
- **The only oracle is the 11-03 clip** (`subcmp.py` inside its polygon, pinned), and only for a first day from
  11-02.

### The planet store's first day: 13 minutes, 20 GiB, exact against the clip of the day after (11-16, 10:41-11:16; owner: "keep building whatever needs to be built")

Built first: `tilestore loc build|advance|check` (`tilestore/src/locfile.rs`, 9f65401e, 1c136890), the node places
by id in osmium's dense_file_array layout, the layout `update --before-loc` reads and the world stream's
`planet.loc` has. `build` writes every node at a date from a history file (or a snapshot) in id order, gaps as
empty places, never sparse; `advance` writes a day's last version of each node in place (a deleted one emptied) and
refuses a diff not after the instant in `F.loc.state`; `check` holds every node of a snapshot against the file.
Test (`tests/test_tilestore_update.py`): equal to pyosmium's dense file of the synthetic day's before and after,
up to the empty tail pyosmium grows its file by; `check` fails the advanced file against the day before; the same
diff twice is refused and leaves the file untouched. `update` now refuses to start under the 40 GiB floor.

The run: `.scratch/planet-day/run.sh` (log `logs/planet-day.log`, memory every 10 s in `logs/planet-day-mem.log`
from `mem.ps1`), binary 9f65401e, nothing else of ours running.

| step | time | result |
|---|---|---|
| `loc build`, history-261102 at 11-02 | 1,037.9 s (300 s the blob index) | 10,975,350,797 nodes, highest id 14,339,779,110, 106.84 GiB, none out of order |
| `loc check` against `europe-2026-11-02` | 20.5 s | 127,715,680 nodes, 0 differ |
| `update`, diff 5165, `--world --group-mib 512`, no pruning | 791.2 s | 16 groups; 195,294 tiles reached, 194,440 written (6,333 new, 680 dropped), pack 8.03 GB; relation store 20,207 blobs, 131 MB |
| `loc advance` to 11-03 | 17.4 s | 3,592,575 nodes: 2,257,300 new, 723,284 moved, 561,299 emptied |
| `loc check` against `europe-2026-11-03` | 27.1 s | 127,743,794 nodes, 0 differ |

- **Memory:** the update's private bytes at most 20.1 GiB (the carried copies: 429,476 ways, 9,100 relations,
  6.53M nodes, and 274,188 member ways of changed relations); commit headroom never under 43 GiB. The update's
  seconds: diff 11, finding 348, reach 41, rule 238, writing 153.
- **Against the lower bound** (`reach-5165.json`: 180,583 tiles, 7.71 GB): above it, as it must be; the old homes
  of changed nodes, the parent ways and the changed ways' new tiles are what the bound left out.
- **Exactness:** `subcmp.py --gp 1` of the store against a cut of `europe-2026-11-03` (`clip-1103`, 58,386 tiles):
  at 2 km inside the polygon 13,968 of 14,005 tiles equal, 32 differ, 5 only in the planet; at 0.5 km 16,774 of
  16,832, 50 and 8. **Every one is explained** (`why.py`, the planet's tile less the ways the clip lacks equals the
  clip's) **by the same four ways as on 11-02**, ways with every node outside the polygon that osmium's extract
  drops. **Negative control:** generation 0 against the same clip differs in 1,482 tiles and 4 only in the clip at
  2 km: the day changed about 1,490 interior tiles, and generation 1 has all of them right.
- **Disk:** a day writes the pack (8.03 GB), a new tile index (0.77 GB), relation index (0.30 GB), relation blobs
  (0.13 GB) and a second copy of the pair indexes (22.8 GB, gone with `--prune-pairs`): about 9.2 GB a day kept,
  8.2 GB if older generations' indexes are let go.
- **Dead space after one day:** of pack-0000's 232.55 GiB, 188,787 tiles and 7.45 GiB (3.20%) are superseded.
  4.51 GiB of that lies in whole 64 KiB chunks no live tile touches (0.49 GiB in whole 1 MiB chunks), so punching
  holes in the gen-0 pack (sparse file, zeroed ranges) would give back about 60% of its dead bytes without a
  rewrite. Daily packs, small, can be compacted by copying their live tiles forward. Day 2 measures the overlap.

Left on disk: `.scratch/planet-day/planet.loc` (106.9 GiB, at 11-03), `clip-1103` (1.9 GiB), the store with
generations 0 and 1 and both generations' pair indexes (gen 0's kept so the day can be redone from 0).

**The second day, diff 5166 (11-16, 11:18-11:33; `.scratch/planet-day/run2.sh`, log `logs/planet-day2.log`), with
`--prune-pairs`:** 638.0 s, 14 groups, 159,722 tiles reached, 158,582 written, pack 7.10 GB; generation 1's pair
indexes deleted after generation 2's were written (generation 0's kept). Node file moved to 11-04 in 17.3 s (2.53M
new, 438k moved, 1.03M emptied), **equal to `europe-2026-11-04`** (127,760,942 nodes). **Tiles:** generation 2
against a cut of that clip at 2 km: 13,968 of 14,005 equal, 32 differ, 5 only in the planet, **all 37 explained by
the same four ways**; control, generation 1 against the same clip: 1,314 differ.

**What two days say about disk.** The live payload stays where the cut left it: 232.60 GiB after day 2 (pack 0
220.79, pack 1 5.20, pack 2 6.61) against 232.55. What grows is dead space, about one pack a day:

| pack | written | dead after day 2 |
|---|---|---|
| 0 (the cut) | 232.55 GiB | 11.76 GiB (5.1%; day 1 7.45, day 2 4.31 more); 7.28 GiB of it in whole 64 KiB chunks |
| 1 | 7.48 GiB | 2.28 GiB (30.5%) after one more day |

So a store without compaction grows by about 8.5 GB a day (pack plus the new tile and relation indexes), about 255
GB a month. Two kinds of compaction, neither built: **daily packs** copied forward (their live tiles into the
newest pack, the old pack deleted; small, since a daily pack is a few GiB and loses a third the next day), and
**the cut's pack** given back in place (marked sparse, whole dead 64 KiB ranges zeroed: about 62% of its dead bytes
after two days, without rewriting 220 GiB). Either makes older generations unreadable where their tiles were, so
only the newest generation would stay readable.

### Compaction: daily packs copied forward, the cut's pack given back in place (11-16, 11:35-11:50)

Two commands, both leaving only the newest generation readable (store.json marks the older ones `"readable":
false` before any file changes):
- **`tilestore compact --store S [--min-dead F] [--dry-run]`** (`compact.rs`, ed6f7efd): the live tiles and
  relation blobs of packs 1 .. newest-1 (those at least F dead) appended to the newest generation's pack and
  relation file, every copy read back and held against its source byte for byte, then the newest indexes
  replaced (written aside and renamed), then the copied packs and the older generations' indexes removed. The
  newest files' lengths are recorded (`packBytes`, `relFileBytes`), and a stopped run's bytes past them are cut off
  by the next. Pack 0 and rel 0 are never copied.
- **`tilestore punch --store S [--dry-run]`** (`punch.rs`, 9e79a347): pack-0000 made sparse and every whole 64
  KiB unit no live tile touches zeroed (`FSCTL_SET_ZERO_DATA`), each return checked; every live tile of pack 0
  hashed before and after, a change marks the store `damaged` and stops; generation 0's pair indexes removed
  after (a redo from the cut is no longer possible).

**On the clip** (`.scratch/tiles/compact-days.sh`: a copy of store-rsu's generation 0, day 1, compact, day 2,
compact): every generation equal to the Python store's, the day after a compaction too; the second compaction
copied pack 1's 1,873 live tiles. **Punch** on that store at generation 2: 600,965,120 bytes in 990 ranges, equal
to an independent count in Python; free space up 0.56 GiB (the pack 1.3 GB on disk, 1.9 GB long); storecmp equal
after. **Negative control** (`TILESTORE_TEST_PUNCH_LIVE=1` on a copy, one unit holding a live tile punched too):
21 live tiles changed, caught, exit 101, `damaged` set. Unit test `dead_ranges_are_whole_untouched_units`; the
synthetic test compacts after an empty second day.

**On the planet, compaction at generation 2** (`.scratch/planet-day/run3.sh`): dry run as measured (pack 1 5.20
of 7.48 GiB live), 15.6 s, 138,827 tiles and 18,601 relation blobs copied, 9.59 GiB of files removed (about 4.3
GiB net); the compacted generation 2 against `clip-1104` gives exactly what it gave before (13,968 same, 32
differ, 5 only in the planet).

**The third day, on the compacted store (11-16, 13:36-13:52; it waited for the daily run, which ended 13:36):**
diff 5167, 647.8 s, 13 groups, 153,919 tiles reached, pack 6.53 GB. Node file to 11-05 (3.73M new, 413k moved,
269k emptied), equal to `europe-2026-11-05` (127,777,322 nodes). Generation 3 against a cut of that clip at 2 km:
13,968 equal, 32 differ, 5 only in the planet, all 37 explained by the same four ways; control, generation 2:
1,489 differ. **An update on a compacted store is exact.**

**The planet punch at generation 3 (13:52-19:25, `.scratch/planet-day/run4.sh`, log `logs/planet-punch.log`):**
the dry run's 10,096,607,232 bytes in 41,404 ranges equal to the independent count (`count-dead.py`) byte for
byte, so the gate passed; the punch zeroed them, free space up 10.71 GiB, every one of 31,709,976 live tiles of
pack 0 the same (hashed before and after, 134 s each); generation 0's pair indexes (21.25 GiB) removed after.
Generation 3 against `clip-1105` after the punch: the same counts and the same differing tiles as before it.
pack-0000 is now 224 GiB on disk, 233 GiB long. **But the punch took 19,621 s, about 0.47 s a range** (on the
clip 13 ms a range): the cost per `FSCTL_SET_ZERO_DATA` call grows with the file, cause not measured (the
allocation map of a file with tens of thousands of holes is a guess). Fixed for later punches (31b7c503): only the
dead ranges that still hold space (`FSCTL_QUERY_ALLOCATED_RANGES`) are punched; the planet's dry run now finds 0
of 41,404. A day adds a few thousand new dead ranges, so a daily punch would cost tens of minutes at this rate;
weekly, or the call's cost understood first, is the open choice. C: 141 GB free after.

### Why the punch was slow: its own memory-mapped hash pass (11-16, evening; owner: "work out why the punch is slow")

The planet punch cost about 0.47 s a call. Measured with `.scratch/punch-cost/` (`zt.py`, `at.py`, `grow.py`,
`evict.py`, `unstick.py`, `mapread.py`, `flushtime.py`: Python and ctypes around the same Windows calls):
- **A fixed cost per call, on that file only.** Zeroing ranges of pack-0000 that were already holes (no data to
  free) cost 0.43-0.95 s each; at the same moment a fresh 1 GiB file and a 30 GiB test file punched in 0.04 ms.
  `FlushFileBuffers` on pack-0000 with nothing to write cost about 370 ms every time; on every other store file
  (`planet.loc` 115 GB, the newest pack, the pair index, rel-0000) 0.1 ms.
- **Not the number of extents.** pack-0000 has 85,106 extents (41,405 allocated ranges). A 30 GiB file written
  past the cache and punched to 41,664 allocated ranges kept 0.04 ms a call all the way (`grow.out`).
- **Not cached pages.** The same file read whole through the cache (30 GiB of cached clean pages): flush 0.1 ms,
  punches 0.0 ms.
- **Pages read through a memory mapping.** The same file read through a mapping, one page touched per MiB, then
  closed: flush 40 ms, each punch 21 ms. The punch's own "hash before" mapped pack-0000 and read all 217 GiB of
  its live tiles, then punched: every one of the 41,404 calls paid for those pages. Reading 80 GiB of other data
  (the history file) until they left memory brought pack-0000 back to a 0.1 ms flush and 0.0 ms calls, hours
  after the punch. A non-cached handle, a flush or a non-cached write did not.

**Fix** (the change landed in 41dacebd, another session's commit that took the uncommitted file with it): the
hashes come from 8 MiB positional reads, never a mapping. On the clip the punch phase went from 12.9 s to 0.1 s
for the same 990 ranges, storecmp equal after, the negative control still caught. Nothing else in the tile store
maps a pack (`npy.rs` maps pair indexes, `update.rs` the node file; both flush fast). **So a daily punch costs
seconds, not hours**, unless something maps a pack first; any new reader of packs must not use a mapping. Not
shown at planet size yet: the next planet punch (a day's new dead ranges) is the test.

### The planet store caught up, 11-06 to 11-16: eleven days, each exact (11-16 20:16 to 11-17 00:41)

`tools/stream/planet_store_day.py`, hidden, diffs 5168-5178 on generations 3 to 14, about 19-30 min a day.
**Every day the same result:** the node file equal to that day's Europe clip (`loc check`, exit 0); the new
generation against a cut of the clip at 2 km: 13,968 equal, 32 differ, 5 only in the planet, 0 only in the clip, all
37 explained by the same four ways the clip's extract drops. No STOPPED. With days 1-3 that is fourteen days in a row.
- **Update** 561-935 s a day; each day's pack 6.1-8.5 GiB.
- **Compaction** (`--min-dead 0.25`) copies forward every two or three days: 20-52 GiB of files removed on those days
  (the copied packs and the older generations' indexes), about 1 GiB on the others.
- **Punch** (the planet test the section above left open): 0.9-2.3 GiB of pack-0000 zeroed a day, every live tile the
  same, the punch phase itself 2.1-13.7 s; the hash passes (155-209 s each) are most of its cost. **One exception:
  generation 13 (23:41-00:13), 1,482 s**, while free space fell 21 GiB from other sessions' work (a Europe re-cut,
  planet counts, a benchmark writing a 1.9 GB log). No reader of packs uses a mapping (`grep` of `tilestore/src` and
  `tools/`), so contention is the likely cause, not proven; generation 14 was back to 13.7 s.
- **D-1 is not kept past compaction** (the release-1 plan's "not checked"): `compact` and `punch` both mark every
  older generation `"readable": false` before touching a file, `compact` removes their indexes, and the punch zeroes
  the units only D-1's tiles held. Between `update` and `compact` generation g-1 is whole (its index is still on
  disk, its packs untouched). **So a world day reads D-1 after the store's update and before its compaction**, or the
  store run takes the world day as a step between the two.
