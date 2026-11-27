## The tile store in Rust: the cut, a spike (2026-11-15, early afternoon; owner: "I want to consider a rust version. Third tool chain is not a problem for us, since agent handles technical side")

*Why Rust is on the table.* "Why Kotlin for the tile store" above gave three reasons against C++ or Rust: a third
toolchain, and the engine needing its own reader of the store or a PBF handed over. The owner set the first aside. The
second is smaller than it read: the 30 s of each read was pyosmium writing the PBF, not the handing over; native code
should write that file in seconds (not measured: no Rust reader exists yet). What Rust offers is the planet cut and
its memory, where the Kotlin plan's risk was. What it costs: the tile rule lives a third time (AreaPass.kt, `tiles.py`,
now `tilestore/`), with `ignore_relation` to keep in step at a repin.

*What was built* (`tilestore/`, a cargo crate; Rust 1.100 stable-msvc installed with rustup through winget, Visual
Studio 2022's linker; crates `osmpbf` 0.3.8 to read, `rayon`, `zstd`). `tilestore cut --pbf X.osm.pbf --out S --day D
[--z 14]` reads the clip itself (no `tiles.py geom`/`attrs` step) and writes the prototype's store layout, generation
0: `pack-0000.bin`, `idx-0000.npy`, `wtiles`/`rtiles`, `rel-0000.bin`, `relidx-0000.npy`, `store.json`. So the Python
`read` and checks work on a Rust-cut store unchanged (run); the Python `update` should too, since the files are the
same, but it was not run on one. The tile maths follows `tiles.py` operation for
operation (no fused multiply-add, no reciprocal). Everything is held in memory.

*Exactness: the same store, byte for byte in its payloads* (`tools/stream/tilecheck/storecmp.py --a
.scratch/tiles/store --b .scratch/tiles/store-rs`, generation 0 of each; europe clip of 11-12):
| part | Python | Rust | different |
|---|---|---|---|
| tiles (decompressed payloads) | 59,026 | 59,026 | 0 |
| relation store blobs | 438,232 | 438,232 | 0 |
| way-tiles pairs | 22,600,881 | 22,600,881 | 0 |
| relation-tiles pairs | 570,738 | 570,738 | 0 |
| copies: nodes / ways / relations | 175,614,649 / 22,600,881 / 570,738 | the same | 0 |

The pack files are also the same size to the byte (1,995,590,460 and 229,049,083), compressed. The checker was first
shown able to fail: the Python store against itself is equal, against the 11-13 store 2,227 tiles differ. No
last-digit difference between numpy's and Rust's tan, cos and log moved any of 127.9M nodes across a tile edge. **End
to end:** the Python `read` of the 331 tiles under t2n's rectangles from the Rust store, recounted by the engine at
11-12: **1,114,046 rows, 0 different** from `ref/old`.

*Speed: 35.7 s against about 32 min, one run, 24 threads.*
| step | Python prototype | Rust |
|---|---|---|
| read the clip (places, refs, members, tags, versions) | 1,309 s (`geom` 379 s, `attrs` 930 s) | 15.0 s |
| every node's tile, the refs as node rows | (in the cut) | 1.8 s |
| way tiles | (in the cut) | 0.4 s |
| tile pairs | (in the cut) | 3.4 s |
| payloads, packed and written | 122 s | 9.8 s |
| pair indexes | (in the cut) | 0.3 s |
| relation store | 68 s | 5.1 s |
| **the whole cut** | **about 1,920 s** (1,309 + 613) | **35.7 s** |

About 50 times (49 to 54: the Python cut was 451 s in one run, 613 s in another), **24 threads against one**: it
measures the prototype's per-object Python loops, not Rust against Kotlin. The only Kotlin figure on record is the
engine decoding this clip's 128M nodes in 6.7 s; Rust's 15.0 s read is more work (ways, relations, tags, versions
too), so the two do not compare. No Kotlin cut exists to hold beside this one. The Python update of a day (532-623 s) and its read
(34-55 s, of which the PBF write 30-50 s: 50.2 s in this run) are untouched.

*Memory: 12.2 GiB peak working set for a 1.64 GB clip, and that is what does not carry to the planet.* The planet's
PBF is about 52 times this clip: the same in-memory cut would want over 600 GB, and node rows and tile keys are 32
bits here (11 billion nodes do not fit). The time scales to about half an hour if it stayed linear, which it cannot
in this form. **A planet cut is a different program:** node places from a file on disk (as `planet.loc`, 107 GiB),
tags streamed in a second pass rather than held, the pairs sorted in runs on disk, the planet cut by region. Not
designed, not built, not measured: the reason Rust was preferred is still unproven.

*A country, not city boxes: Germany (the 11-07 extract, 4.88 GB), the same binary, timing and memory only (no Python
store of it to hold it against):* **128.7 s, 41.3 GiB peak.** 442.6M nodes, 71.5M ways, 915,665 relations (628,034
kept); 190,006 tiles; read 47.6 s, places 7.9 s, way tiles 2.0 s, tile pairs 15.6 s, payloads 44.7 s, pair indexes
1.6 s, relation store 9.2 s. Per GB of PBF: 26 s and 8.5 GiB (the clip: 22 s and 7.4 GiB), so time and memory go
with the file's size; the planet (85 GB) on that line is about 37 min and about 720 GiB. **The store is larger than
the city clip said: tiles 7.28 GiB, 1.60 times the PBF** (the clip: 1.14), because nodes are copied 1.60 times
(707.9M copies of 442.6M nodes; the clip 1.37) while ways are copied 1.08 times: outside city boxes ways are long
and cross tiles, and each tile keeps all of a crossing way's nodes. With the relation store (425 MiB) and the
way-tiles index (1.24 GB as plain pairs) the directory is 9.5 GB, 1.96 times the PBF. If the planet is like Germany
rather than like the clip, its tiles are about 136 GB, not the 97 GB behind "about 124 GB" above. One country, not
checked for exactness.

*Not shown:* the planet cut (above); a day's update in Rust; a read to PBF in Rust (the "few seconds" handoff; the
`osmpbf` crate only reads, so the writer is ours to choose or write); adaptive tiles (z14 only here, `--z` up to 16).
**Next, in this order:** the read (331 tiles to a PBF the engine takes, timed against Overpass's 40 s and Python's
34-55 s), then the update, then the planet cut's design with one world file measured.

### The read in Rust (11-15, 14:10-14:25; owner: "Yes, the read")

`tilestore read --store S [--gen -1] --cities C.json [--base DIR] [--ring 300] --out Y.osm.pbf [--stamp T]`
(`tilestore/src/read.rs`, `pbf.rs`): the tiles under the cities' boxes and ring (the same keys as `tiles.py
tiles_of`), decoded on all threads, one copy of each id kept, every kept relation's member ways from the relation
store, written as a PBF the engine takes. The `osmpbf` crate only reads, so the writer is ours (`pbf.rs`, about 250
lines, the protobuf encoded by hand): a header with `osmosis_replication_timestamp` and `Sort.Type_then_ID`, blocks
of 8,000 of one kind, dense nodes with version and timestamp, zlib blobs made on all threads.

*Exact, three ways* (t2n's 103 rectangles, 331 tiles):
| check | result |
|---|---|
| the Rust PBF against the Python `read`'s PBF of the same store, object for object (`tools/stream/tilecheck/pbfcmp.py`: type, id, version, timestamp, place, tags in order, refs, members and roles, the header's stamp) | 8,269,618 objects (6,847,049 nodes, 1,406,926 ways, 15,643 relations), **0 different** |
| the engine's recount of it at 11-12 against `ref/old` | 1,114,046 rows, **0 different** |
| generation 1 of the **Python** store (11-12 cut, updated by diff 5175: two packs, two relation packs) read by Rust at 11-13, recounted against `ref` | 1,116,244 rows, **0 different** |

`pbfcmp.py` fails as it should on the 11-12 file against the 11-13 one.

*Speed: about 1 s a date, against 34-55 s in Python and about 40 s from Overpass.*
| | tiles read and decoded | merge | PBF written | in all |
|---|---|---|---|---|
| Python (`tilestore.py read`) | 2.2-2.6 s | 1.3-1.9 s | 30-50 s (pyosmium) | 34-55 s |
| Rust, generation 0, three runs | 0.26-0.27 s | 0.13-0.14 s | 0.57-0.60 s | **0.97-1.00 s** |
| Rust, generation 1 of the Python store | 0.58 s | 0.15 s | 0.57 s | 1.30 s |
| Overpass, this machine (above) | | | | about 40 s (30 s selection) |

So the "few seconds" handoff holds, with room: writing the 80 MB PBF takes 0.6 s, and the engine reads it as it
reads any clip (13.6-14.7 s for the recount, the JVM's start included). **Reading a date costs about 15 s, almost
all of it the engine; both dates about 30 s, against about 80 s of Overpass plus the engine. That compares reads
only:** Overpass's figure is from a store that keeps itself current, while the tile store's day also needs its
update (9-10 min in Python on the clip, not built in Rust) and a planet cut that does not exist. A reader of the
tile format inside the engine would save the 0.6 s write and part of the engine's own decoding (its node and way
passes are 1.9 s and 2.9 s here, decoding and matching together, not split): a few seconds at most, not measured,
not worth building now.

*What the figure does not show.* The files were in the OS cache (the store was written minutes before): a cold read
is 101 MB in 331 tile reads and 15,643 relation blob reads, not measured; the only hint is generation 1's tile
phase, 0.58 s against 0.26 s, on packs read less recently. Everything is held in memory: **849 MiB peak** for these
8.3M objects (sampled every 20 ms). This run's rate is 8M objects a second; what a world day's read costs is not
projected from it (one run, one size, cached files, and its 0.4-2.1 billion objects per date would have to be read
region by region). **A known limit of the writer:** blocks are cut by count (8,000) and not by size; the format
wants a blob under 32 MiB uncompressed, which 8,000 very large relations could pass. Not met here, not guarded.

**Next:** the update in Rust (first the Python `update` on a Rust-cut store, then `storecmp.py --ga 1 --gb 1`),
then the planet cut's design.
