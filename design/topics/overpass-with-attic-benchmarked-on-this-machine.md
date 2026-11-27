## Overpass with attic, benchmarked on this machine (2026-11-14 night; owner: "benchmark overpass on this pc before committing")

*Decided before it (owner, 11-14, 22:30-23:00):* tier 2's world store is to be an own Overpass instance with attic, on an
external SSD; what reads it is **Python** (the queries, beside `stream.py`) **plus osmium** (Overpass answers XML or JSON,
the engine reads only PBF with versions, timestamps and `osmosis_replication_timestamp`). The comparison above (Overpass
"ruled out by disk") is superseded by that decision: the disk is to be bought. Kotlin's reasons there were the tile
store's cut, update and direct read, none of which exists with Overpass; a StAX XML reader in the engine stays the option
if conversion ever costs time.

*Method* (`tools/stream/overpass/bench.sh`, `opbench.py`; logs `logs/opbench-rehearse.log`, `logs/opbench-full.log`;
results `.scratch/overpass/{rehearse,full}/summary.json`). Docker `wiktorn/overpass-api:v0.7.62.11`, the db in a named
volume (ext4 in Docker's VHDX on the internal NVMe). A history file cannot seed attic (the Overpass wiki: unsupported, an
`.osh` fed to `update_database` leaves the db unusable), so: the europe clip of 11-12 (1.64 GB, stamp 11-12T00:00Z) piped
as XML into `update_database --keep-attic` (lz4), then planet day diff 5175 by `update_from_dir --keep-attic`, as
production applies diffs. One query per date for t2n's 103 rectangles of 11-13 (412 km2; Dublin's one is 249 km2), each
box padded 300 m as the engine pads, mirroring `tiles.py select()`: nodes in the boxes; ways by those nodes and ways
crossing; relations with a member node or crossing way, and all their member ways; every node of those ways; `out meta`.
XML to PBF by `osmium sort` with the stamp; recount as `tiles.py recount`; compared with `.scratch/tiles/ref/`.

*Exactness: all three stages 0 rows different, every row, not only inside the boxes.*
| stage | query | against | rows | different |
|---|---|---|---|---|
| 1 | after the load, current | ref/old (11-12) | 1,114,046 | 0 |
| 2 | after 5175, current | ref (11-13) | 1,116,244 | 0 |
| 3 | after 5175, `[date:"2026-11-12T00:00:00Z"]` | ref/old (11-12) | 1,114,046 | 0 |

Two effects could have shown as differences without being Overpass's fault, and did not here: the clip's edge (the
planet diff brings edited ways whose nodes lie outside the clip, so boxes near its edge could lose geometry) and
midnight (`[date:]` selects by element timestamp, ref/old was cut by replication sequence, so an element stamped just
before 11-12T00:00Z but in diff 5175 would show at that date in Overpass only). On the planet db the first goes away;
the second remains possible at every day's boundary and is to be named before any such row is called a bug.

Stage 3's answer against stage 1's: 4,966,517 objects the same, 463 differ, 366 only in tag order and 97 only in the
user name (attic gives a renamed user's current name); the engine reads neither. So **one attic db answers D and D-1
exactly**. Also exact: stage 2 with relation member ways only by role outer/inner (output 997 MB against 1,125 MB: the
bulk is ways and nodes over the big boxes, not relations).

*Cost here* (internal NVMe; timings vary up to 2x between identical runs while other work runs):
- Load of the 1.64 GB clip: 1,842 s, single-threaded; db 13.7 GB (8.4x the PBF). Day diff 5175 (the whole planet's day,
  so worldwide objects too): 409 s **on a clip db**; db 18.7 GB after. Not a planet's daily cost: here most of the day's
  objects went in new, with no earlier versions; on a planet db with fourteen years of attic each change rewrites
  existing blocks and their attic. A planet db takes a daily diff in minutes (dev.overpass-api.de keeps
  up minutely); not measured on a planet-size db, nor on the external drive.
- One union query per date: 84-206 s warm, 86-113 s cold, of which most is writing 1.1 GB of XML (16k read requests,
  0.8 GB read from cold). XML to PBF (61 MB): 10-16 s. The engine on it: 21-23 s (48 s under load).
- Each rectangle alone, 103 queries: current 87 s warm / 169 s cold; dated 130 s warm / 221 s cold (median 1.07 s warm,
  1.9 s cold; timed inside the container). **Dated costs 30-50% more than current** on a db with one day of attic.
  The 65 rectangles under 1 km2 still take about 1.7 s each cold. That is selection work, not a floor (a trivial query
  takes 0.02 s): each small box still brings its relations' member ways and the far nodes of long ways. The union
  selects everything in 30 s, where the 103 alone add to 130-190 s warm (their results overlap), so a world day batches
  rectangles into union queries (per world file or region), not one query each.
- Reads from cold: 306k-361k requests, 18-20 GB, for the 103 alone; the union 16k requests. At a USB4 NVMe's latency
  (some tens of microseconds more than internal) that adds seconds, not minutes, on this 19 GB db with one day of attic;
  a 708 GB db reads more per query, which only the real clone on the real drive will show. **Carry the reads over, not
  the seconds:** the db fits in RAM, and `drop_caches` empties only the Docker VM's cache, while Windows may still cache
  the VHDX underneath, so "cold" seconds may be optimistic. Lisboa's 16 alone, cold: 14,736 requests, 870 MiB.
- **Where the union's time goes** (dated, warm; `tools/stream/overpass/split.py`, `.scratch/overpass/full/split-dated.json`):
  selection alone (`out count;`) 30 s for 4,966,980 objects; with the XML written inside the container 50 s; **piped
  straight into osmium inside the container, a stamped, sorted PBF in 36 s + 1.6 s**. The 84-206 s above (and their 2x
  spread) were the Windows bind mount taking 1.1 GB of XML: the reader must convert inside the container (or WSL) and hand
  over only the PBF (64 MB). So a date costs about 40 s here for these rectangles, both dates about 80 s.
- **In parallel** (the 103 alone, dated, warm, to /dev/null): 207 s one at a time, 71 s four at a time (2.9x), 59 s eight
  at a time (3.5x). Overpass serves concurrent queries; past four the db's reads or this machine's other load limit it.
- No answer carried a `<remark>` (Overpass reports timeouts and memory limits there with exit 0; the reader must check
  for it, since the staged runs are proven complete only by their recounts).
- **A world day, estimated, not measured.** Europe-west's tier 2 (the files of Dublin, Lisboa and London, 2.46M elements)
  asked 15-298 km2 of rectangles a day over 11-09..11-13; 11-13's 412 km2 padded gave 4.97M objects per date. The world's
  seed has 1,061M elements, 430 times as many. Scaled linearly (these are urban edit hotspots, and at world scale
  overlapping rectangles merge, so this leans high): 0.4-2.1 billion objects per date, 0.9-4.4 h per date at this
  machine's 7.5 microseconds an object on one query stream, **15 min to 1.3 h per date at four streams, 0.5-2.5 h for a
  world day's two dates**; the engine on the same data adds about 10-50 min per date (the world count ran at about 1.4
  microseconds an object). That fits a day, but tier 2 at world scale reads perhaps a fifth of the planet twice a day:
  the store's speed matters less than how much ground the cover asks for. To measure on the real db: one world file's
  rectangles as one union query.
- Against the tile store (Python prototype): its read of these rectangles was 34-45 s (31-41 s of it pyosmium writing a
  PBF); Overpass gives both dates in about 3.5-4 min with conversion. Fine for europe-west; for the world, the time goes
  with the output's size (about 10-25 MB of XML a second), which goes with the rectangles' area, not their count.

*What this cannot show:* a planet db's speed with fourteen years of attic (here one day). Tried on the public
overpass-api.de with a 0.2 km2 London box, current and dated (11-12 and 2019): 35-46 s each with two gateway errors, so
the server's load drowned any difference; stopped there. Tried again on overpass.private.coffee (full planet with attic;
a peer session's suggestion, 11-15 00:55): four Lisboa rectangles, sequential: the union and lisboa-1 dated and current
all answered 504 after 109-262 s, and a single small node query got no answer in 90 s either way; stopped after 5
requests. So no real-attic timing from public servers tonight; it waits for the clone on the drive. The **size to buy**: the current clone
(dev.overpass-api.de/clone/2026-11-10/, listing read 11-14) is **about 708 GB with attic** (attic files about 253 GB;
nodes.bin 95 GB, nodes_meta.bin 84 GB, ways.bin 80 GB), against "about 400 GB" for 2023 above. **A 2 TB drive**: 1 TB
would hold it with under 300 GB to grow and no room for a second copy during a re-clone.

Sources: wiki.openstreetmap.org, User:Mmd/Overpass_API/install/attic and Overpass_API/Installation (attic from history
files unsupported; `--keep-attic`); dev.overpass-api.de/clone/ (sizes); hub.docker.com wiktorn/overpass-api (tags).
