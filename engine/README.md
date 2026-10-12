# engine

Counts open StreetComplete quests per city from an OSM PBF extract by running StreetComplete's own
element filter and geometry code on a plain JVM. Status: all 138 filter quests of SC v63.4 and 48 of its
51 custom quests (see "Custom quests" and "Area quests" below), 48 Ontario cities, one pass over the
Ontario extract plus an area pass for the quests that need surroundings. Output format: [DATA-FORMAT.md](../DATA-FORMAT.md).

## Licence

`src/main/kotlin/sc/` is StreetComplete source, **GPL-3.0** (licence text copied alongside). Linking it
makes the engine a GPL-3.0 derivative; the repository is GPL-3.0. The SC files carry no per-file headers
upstream; they are copied byte-for-byte except for the one patch below (see the sha256 list in
`SC-VERSION.txt`).

## Build, run, test

```powershell
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'   # JDK 21
cd engine; ./gradlew.bat installDist; cd ..

# from the repo root; paths are relative to the working directory
engine/build/install/sc-open-quests-engine/bin/sc-open-quests-engine.bat count `
    --pbf C:\Users\kk\Code\.osm-data\ontario\ontario-2026-10-10.osm.pbf `
    --quests data/quests/v63.4.json --cities config/cities.json --out docs/data `
    --source-meta C:\Users\kk\Code\.osm-data\ontario\ontario-2026-10-10.meta.json
```

- Writes `docs/data/snapshots/<asOfDate>.json` and `docs/data/quests.json`. Exit code 1 on any error.
- `--source-meta`: the extract's metadata. Both the osm-extracts `<file>.meta.json` (`sha256`) and the
  toronto-streets-osm `meta.json` (`pbf_sha256`) work. The engine hashes the PBF while reading it and
  fails if the meta describes a different file. Without it, `source.url`/`lastModified` are null.
- `--today <instant or date>`: evaluate age filters at this time instead of the extract's
  `osmosis_replication_timestamp` (tests and what-ifs; a bare date means noon in the cities' zone).
  `asOf`/`asOfDate` follow it; `extractTimestamp` keeps the header's.
- `--dump-matches <tsv> --dump-quests A,B`: every counted match of those quests with id, version,
  timestamp, city, quest position and agedOnly, for cross-checks.
- `--dump-elements <jsonl> --dump-city <id>` and `--area-unit city`: input for the oracle, see
  "Custom quests" and "Area quests".
- `engine/measure.ps1 count ...` runs the installed engine from the repo root and reports wall time and
  peak working set.
- `./gradlew.bat test` (from `engine/`): unit tests; a check that recounting the newest stored extract reproduces its committed snapshot; and the spike regression on the 2026-07-16 extract (skipped since that extract was pruned from the shared store).
  `-Ppbf=<file>` points it elsewhere; it is skipped if the file is missing. One country-gating test reads
  SC's `boundaries.ser` from the SC checkout (`-PscBoundaries=<file>`), skipped if absent.

Extracts live in the shared store `~/Code/.osm-data/ontario/` (managed by `~/Code/osm-extracts`). Open the
dated file, not `ontario-latest.osm.pbf`. The store keeps 14 days of extracts, plus the newest two and pinned ones.

## How a count is made

1. **Quests**: every `kind: "filter"` entry of the registry dump (`tools/sc-harness`), parsed with SC's
   `toElementFilterExpression()`; plus the 12 custom quests ported in `openquests/custom/` and the 36
   generated into `ported/` (see below). AddHousenumber, AddCycleway, AddRoofShape (they need SC's country
   metadata) and the note quest are `unsupported` and not counted.
   At start-up the engine checks that no filter or per-element port matches an untagged element, then
   skips untagged elements in the main pass; the area pass sees them.
2. **Clock**: SC's age filters (`older today -N`, `< today`) read the wall clock. The `clock` patch
   makes that clock settable; the engine sets it to the extract's replication timestamp. Dates are
   computed in the JVM's default zone, pinned to `America/Toronto` by the launcher
   (`-Duser.timezone`); the engine refuses to run if a city's `timeZone` differs.
3. **agedOnly**: each match of a `usesAge` quest is re-evaluated on the same thread with the clock at
   1900-01-01, where every `older today -N` and `x < today` test is false. Matches that disappear are
   `agedOnly`. Besides `older`, this catches four date-tag comparisons with today: `opening_date < today`
   (MarkCompletedBuildingConstruction, MarkCompletedHighwayConstruction) and `smoothness:date < today -4
   years` (AddRoadSmoothness, AddPathSmoothness). All of them reopen without an edit.
4. **Country gating** per city from `countryCodes` (`["CA","CA-ON"]`), as SC's `CountryBoundariesImpl.
   isInAny`: `NoCountriesExcept(codes)` is on if a code equals one of the city's ids,
   `AllCountriesExcept(codes)` if none does. SC's countryboundaries data gives an Ontario position the
   ids `CA-ON` and `CA` (checked by a test against SC's `boundaries.ser` for 47 of the 48 cities), so
   a quest listing only `CA-ON` is on and one excluding `CA` is off. 11 filter quests are off in every
   city. SC also skips a quest type when the download bbox does not intersect its countries; that is
   redundant for cities wholly inside CA-ON.
5. **Quest position** from SC's own `ElementGeometryCreator` (vendored): a node is its position; a way
   with fewer than 2 distinct positions or a missing node has no geometry (no quest); a closed way that
   `isArea()` (SC's `IS_AREA_EXPRESSION`) gets the polygon centroid, any other way the point at half its
   length; a `type=multipolygon` relation gets the centroid of its first outer ring after SC joins the
   member ways into rings; any other relation gets the half-length point of its first joined polyline.
   Relation geometry uses member **ways** only, skipping missing ones (`allowIncomplete = true`, as in
   `MapDataControllerImpl`); node and sub-relation members are ignored, as in SC.
6. **Cities**: bbox prefilter, then even-odd point-in-polygon on the boundary from `config/cities.json`
   (Overpass `out geom` relation). An element whose bounding box misses every city's is skipped before its
   geometry is built (its centroid or midpoint cannot be inside). A quest counts in a city if its position
   is inside the city polygon and the quest is enabled there.
7. **Denominators**: `taggedNodes` and `taggedWays` are tagged elements whose quest position is in the
   city. `highwayKm` sums the length of ways tagged `highway` = motorway, trunk, primary, secondary,
   tertiary, unclassified, residential, service, living_street or one of motorway_link, trunk_link,
   primary_link, secondary_link, tertiary_link, not `area=yes`, whose position is in the city. Length is
   SC's `measuredLength()` (great circle on a sphere of radius 6371 km), summed in whole millimetres so the
   total does not depend on thread order, and written in km with 3 decimals.

Pass structure (file sorted Type_then_ID): relation blocks are read first to collect the member way ids of
tagged relations; then nodes (an id -> position index), ways (member ways of tagged relations keep their
node positions), relations. Each stage decodes blocks in parallel.

## SC patches and stubs

- **`clock`** (`util/ktx/Instant.kt`): `fun systemTimeNow(): Instant = Clock.System.now()` becomes
  `fun systemTimeNow(): Instant = systemClock.now()` plus `var systemClock: Clock = Clock.System`.
  `LocalDate.now()`, `LocalDateTime.now()`, `RelativeDate.date` and `nowAsCheckDateString()` all go through
  `systemTimeNow()`. `sync-sc.ps1` applies it by exact line match after the copy (and fails if the
  upstream line changed) and records both hashes in `SC-VERSION.txt`. The engine installs a clock that
  reads a thread-local override first (`EngineClock`), which is how agedOnly runs in the same pass.
- **Stub** `src/main/kotlin/stubs/de/westnordost/streetcomplete/ui/common/street_side_select/Side.kt`: SC
  declares `enum class Side { LEFT, RIGHT }` in a Compose UI file; the vendored `osm/Sides.kt` imports it.
- osmfeatures (`Feature`, `GeometryType`) is the real library, `de.westnordost:osmfeatures:8.0.0`, which
  publishes an `osmfeatures-jvm` variant (an earlier version of this README wrongly said it had none and
  stubbed `GeometryType`). The opening-hours parser is `de.westnordost:osm-opening-hours:0.4.0`, as in SC.

Everything else under `src/main/kotlin/sc/` is byte-identical to SC v63.4. To move to a new SC tag:
`./sync-sc.ps1 -ScPath <checkout> -Tag vX`, regenerate `data/quests/vX.json` with `tools/sc-harness`, build.

## Custom quests

SC's 51 custom quests (`OsmElementQuestType` but not `OsmFilterQuestType`) live in `androidMain` next to
their Android forms, so they cannot be vendored. For those whose `getApplicableElements()` looks at one
element at a time, the filter strings and `isApplicableTo()` are **transcribed** into
`src/main/kotlin/openquests/custom/<Name>.kt` (one object per quest, implementing `CustomQuest`), calling the
vendored `commonMain` helpers they use (`osm/Places.kt`, `osm/sidewalk/*`, `osm/opening_hours/*`, ...).

- `engine/PORTED-QUESTS.txt` pins each upstream file by the sha256 of its LF text (= the git blob's text).
  `sync-sc.ps1` fails if one changed at the new tag: re-check the port, then update the hash.
- A port's `isApplicable()` is what `getApplicableElements()` keeps (some quests only take nodes there).
  Its date logic (`older`, `TagOlderThan`) goes through the patched clock, so agedOnly works as for filters.
- **Checked against SC itself**, element for element: `tools/sc-harness` `CheckCustomQuests` runs SC's
  own quest classes on SC's unit-test classpath. The engine writes its input with
  `--dump-elements <file.jsonl> --dump-city <id>` (every tagged element whose quest position is in the
  city); run both with the same "today" (`--today <now>` for the engine, since the oracle reads the wall
  clock) and diff the oracle's TSV with `--dump-matches` for that city. Ontario 2026-10-11, Toronto,
  1,601,992 tagged elements: **55,271 quests, identical sets** for all twelve.
- Ported (v63.4): AddSidewalk, AddOpeningHours, AddPostboxCollectionTimes, AddRecyclingContainerMaterials,
  CheckShopType, AddClothingBinOperator, AddOnewayAerialway, AddRoadWidth, AddMaxPhysicalHeight; and,
  with SC's feature dictionary, CheckShopExistence, CheckOpeningHoursSigned, AddPlaceName.
- **Feature dictionary** (`ScFeatures`): the app passes the registry
  `{ featureDictionary.getFeature(it) }`, osmfeatures over SC's own presets, asked with no language, so
  in the phone's locale. The engine pins the JVM locale to **en-CA** (launcher `-Duser.language=en
  -Duser.country=CA`; it refuses to run otherwise) and bundles the three preset files that locale reads
  (`presets.json`, `en.json`, `en-CA.json`; vendored by `sync-sc.ps1` into `src/main/resources/sc/`).
  The locale matters only for whether a feature has a name; a user with a French phone in Ottawa could
  see a slightly different set. Calls are serialized: osmfeatures fills its indexes lazily in HashMaps.
  The oracle uses the same dictionary over the checkout's full preset folder, also in en-CA.
  AddRoadWidth is off by default on every phone; AddMaxPhysicalHeight only on phones without AR (the dump
  records it as default-disabled because the harness mocks the AR check).
- The other custom quests need the surrounding map data: see "Area quests".

## Area quests

36 custom quests decide where they apply from the map data around an element (crossings of roads and
footways, kerbs, entrances on building outlines, ways below bridges, nodes of ferry routes...). They are
**generated**, not hand-transcribed: `engine/port_area_quests.py --sc <checkout> <Name>...` copies the
quest's androidMain file, keeps the imports, everything outside the class, every non-override member and
`getApplicableElements()` verbatim (plus `isApplicableTo()` where `getApplicableElements()` calls it), and
writes `object <Name> : AreaQuest` into SC's own package under `src/main/kotlin/ported/`, so same-package
helpers resolve unchanged. A `getFeature` constructor parameter becomes `ScFeatures`. Four androidMain helper
files (FerryUtils, LevelUtils, SummitMarkingsUtil, MaxHeightUtils) are copied whole. Every file is pinned in
`PORTED-QUESTS.txt` (helpers as `helper:<File>`); on a new SC tag, rerun the script for whatever
`sync-sc.ps1` reports as changed, build, and recheck with the oracle. `ported/AreaQuests.kt` lists them.

`AreaPass` runs after the main pass and does what `OsmQuestController.createQuestsForBBox` does after a
download:

- **Unit: one z16 tile** (`DOWNLOAD_TILE_ZOOM`, about 600 x 440 m here; SC's own `TilesRect` math). The
  app's first download is one tile and later ones a few, sized by data density. The tile's map data is the
  API map call's answer for its bbox: every way with a node in the tile, with all its nodes (untagged ones
  too, with their tags, version and timestamp), the tagged nodes in it, and the tagged relations with such
  a member. Geometry is SC's `ElementGeometryCreator` (relations from the main pass's member ways).
- A result counts if it has geometry and its position is **inside the tile** (`mayCreateQuest`), so each
  quest is counted once; then in the cities whose polygon holds it, where the quest is enabled. A quest
  that returns an element twice (AddMaxHeight) gives one quest, as the app keys quests by element.
- **agedOnly**: each tile is run again with the clock at 1900; results that disappear are agedOnly.
- Tiles run in parallel: 184,811 non-empty tiles for the 48 cities, about 60 s for 33 quests (3 are off in
  every Ontario city: AddEntranceReference, AddSummitCross, AddSummitRegister).
- Edge effects of the tile unit are small: Toronto per tile vs. the whole city as one map data gave
  AddCrossing 914 vs 913 and the same AddKerbHeight, AddEntrance and AddBarrierOnPath counts.
- `--area-unit city` uses one map data per city (bbox padded by 1 km) instead, only for the dumped city:
  that is the oracle's exact input. Not for snapshots: AddMaxHeight compares every road with every bridge
  and takes many minutes on all of Toronto.

**Checked against SC itself** with `tools/sc-harness` CheckCustomQuests in city mode (same map data, SC's
own classes and geometry, `-PcheckBbox` = the engine's area bbox), Ontario 2026-10-11, all 36 quests:
Guelph 13,027, Kingston 10,245, Barrie 6,514 quests, identical sets. @@TORONTO@@

## What still differs from the app

All counted quests are marked `supported`: none of the differences below is specific to a quest.

- **Notes**: the app hides a quest whose position is exactly on an open OSM note. Notes are not modelled.
- **What the app has downloaded**: the app builds relation geometry from whatever member ways it has in its
  local database (`allowIncomplete`). The engine has every member way in the extract, so for a large
  multipolygon or route the app's position can differ, depending on download history. Members outside the
  extract (relations crossing the Ontario border) are missing for the engine as well.
- **Relations without geometry**: 1,360 tagged Ontario relations have no usable member way (node-only
  relations such as `public_transport=stop_area`, relations of sub-relations). SC gives them no geometry
  either, so they get no quest in the app; this is not an engine gap.
- **Country gating** is evaluated per city, not per element position. Exact while every city lies inside
  CA-ON.
- **Default-disabled quests** (30 filter quests) are counted like the others; the site leaves them out of
  headline totals (`defaultDisabled` in quests.json). The resurvey multiplier is the app default, 1.

## Timings and memory

Ontario 2026-10-11, 24 threads, with the area pass: main pass about 17 s, area pass about 75 s (ways
5.4 s: 4.85M ways near a city, 35.8M of their nodes; nodes 3.7 s; tiles 3.2 s; quests 61 s), process
wall about 115 s. Peak heap about 22 GB (sum of pool peaks) with `-Xmx24g`: the area pass holds the ways
and nodes near the cities on top of the main pass's node index.

Main pass alone (Ontario 2026-07-16, 967 MB):

| stage | time |
| --- | --- |
| read blobs + sha256 | 1.2–2.0 s |
| relation member scan | 0.7 s (1.03M member ways) |
| nodes (132.6M indexed, 4.6M tagged) | 6.7–9.8 s |
| ways (4.6M tagged near a city) | 7.2–7.9 s |
| relations | 1.3–2.4 s |
| **total in-process** | **17–23 s**; process wall 19–27 s |

Peak heap 10.4–10.7 GB (sum of pool peaks), peak working set 11.6–12.1 GB, then with `-Xmx16g`. Most of it is
the node index (16 bytes per node, ~2.1 GB), the blobs held in memory (~1 GB), the positions of the
0.97M member ways of tagged relations, and garbage from building SC elements in parallel. A bigger region needs a bigger heap; the 92 GB host has room.

Rerunning on the same extract gives the same bytes apart from `runSeconds` and `engineCommit` (checked
by diffing two runs).
