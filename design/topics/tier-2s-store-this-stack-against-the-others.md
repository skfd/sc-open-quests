## Tier 2's store: this stack against the others (2026-11-14, late evening; owner: "i need to see reasons why this specific stack and not other")

*What the store must do*, from the measurements above: hand the engine, for each day's rectangles and their ring, the
map data the app would download, **at D and at D-1**: every way with a node there, complete with all its nodes **by
id** (SC tells shared nodes, kerbs and crossings by node identity), tagged nodes, kept relations with all their member
ways; kept current from the daily planet diff; on this Windows machine, beside `planet.loc` (115 GB), the stream's
state (about 100 GB) and the monthly planet job's 170 GB, in 340 GB free now (100 GB more in December); a day's work
in minutes, no server to run.

| option | D and D-1 | disk for the planet | a day's cost | fit | verdict |
|---|---|---|---|---|---|
| **Overpass API, own instance with attic** | yes, natively (`[date:]`) | **about 708 GB** as cloned with attic (dev.overpass-api.de/clone/2026-11-10, summed 11-14; 455 GB without attic, 360 GB without meta too); 400 GB was 2023 data | thousands of bbox queries with recursion (`way(bbox);>;` and relation members), each 0.1-1 s; minutely or daily updates built in | Linux service (Docker/WSL here); XML/JSON out, so a converter or a new engine reader | the closest fit in function; ruled out by disk (it alone exceeds what is free beside the 12-07 job) and by running a server, **until the owner chose (11-14) a USB4 NVMe drive for it**: whether it becomes tier 2's store is open |
| **OSMExpress (osmx)** | no: current only (D-1 needs a second copy or reversing the diff) | about 600 GB (2020 planet; ~10x the PBF), twice for D-1 | `osmx extract --bbox` per rectangle; `osmx-update` from replication | C++ CLI, Linux/macOS first | **ruled out by disk**: 10x the PBF |
| **GeoDesk (GOL)** | no: rebuild daily (about 20 min, 200 GB temp); updates promised with 2.0, not confirmed shipped | under 100 GB, twice for D-1 | a bbox query is fast (Java, would sit in the engine's JVM) | Java library: the best fit of language | **ruled out by model**: it stores features with coordinates, not the untagged way nodes' ids SC needs, and no daily update yet; worth a look again if updates ship |
| **PostGIS + osm2pgsql (slim, append)** | no | about 1 TB with the slim tables | `--append` daily; SQL per box | Postgres server | ruled out by disk and by the element model (geometries, not OSM elements back) |
| **osmium on a planet PBF kept current** | yes: keep yesterday's file | 170 GB (two planets) | apply the day diff to the planet (read and write 85 GB), then one extract pass per day for D and one for D-1 over all rectangles (complete ways, "smart" relations); of the order of an hour or two a day | osmium-tool not installed here (pyosmium is, much slower); no new format | **the credible fallback**: no new code, exact by construction (the clips are made this way), but 170 GB and the planet rewritten daily |
| **the tile store (this design)** | yes: the previous generation's index (one day's write) | about 124 GB (adaptive split at 256 KB: 1.33x the PBF plus the relation store) | rewrites only the changed tiles (a tenth of the bytes in a city-centre clip, less on the planet's average); reads only the rectangles' tiles (2 s here) | ours to build and keep; Windows-native | **chosen**: least disk of the options that give D-1, the smallest daily work, and exact on two days already |

*Why Kotlin for the tile store, and not Python, C++ or Rust.*
- **Python, as the prototype is:** exact but slow: the cut is about 30 min for a 1.75 GB clip (the planet is about 50
  times that: a day or more), a day's update about 9 min on the clip, and 31-41 s of each 34-45 s read is pyosmium
  writing a PBF for the engine. Per-object loops (tags, ways' refs) are the cost, not the design.
- **Kotlin, beside the engine:** the engine already decodes PBF blobs in parallel (this clip's 128M nodes in 6.7 s)
  with the protobuf classes on its classpath, which also write PBF; a store in the engine's own build can be **read
  by the engine directly**, so the join's PBF write disappears, and the cut, the update and the read share its
  tests, its `--today` clock and its state format. One language for the hot path, one build, Windows-native.
- **C++ (libosmium) or Rust:** as fast or faster, and libosmium has the PBF and diff machinery ready; but a third
  toolchain on this machine, and the engine (JVM) would still need its own reader of the store or a PBF handed over,
  which is the cost Kotlin removes. Worth it only if the Kotlin cut proves too slow on the planet (to measure: the
  cut of one world file first).
- **What stays in Python:** the stream's orchestration (`stream.py`, `world_state.py`), the checks, and the
  prototype itself as the oracle: an adaptive store built in Kotlin must equal the z14 store's tiles where unsplit and
  the z16 store's where split, payload for payload.

*Open, whichever stack:* the way-tiles index (19 GB as plain pairs, rewritten whole each day in the prototype: a key
per way, or an overlay of a day's changes), compaction (packs die slowly), and a first world-file measurement of the
Kotlin cut before the planet.

Sources: Overpass attic size (wiki.openstreetmap.org, User:Mmd/Overpass API/Performance Project 2016/Full Attic DB
Setup; osm.hpi.de/overpass/full_installation.html), OSMExpress (github.com/protomaps/OSMExpress, README and
docs/MANUAL.md), GeoDesk (community.openstreetmap.org, "Just released: GeoDesk 2.0"; wiki.openstreetmap.org/wiki/GeoDesk).
