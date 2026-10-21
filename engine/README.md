# engine

Counts open StreetComplete quests per city from an OSM PBF extract by running StreetComplete's own
element filter and geometry code on a plain JVM. Status: all 140 filter quests of SC v64.0 and all 52 of
its custom quests (see "Custom quests" and "Area quests" below), 48 Ontario cities and 4 German ones, one
pass over each extract plus an area pass for the quests that need surroundings. Moving to a new SC
release is a *repin*: [REPIN.md](../REPIN.md). Output format: [DATA-FORMAT.md](../DATA-FORMAT.md).

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
    --quests data/quests/v64.0.json --cities config/cities.json --out docs/data `
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
   `toElementFilterExpression()`; plus the 12 custom quests ported in `openquests/custom/` and the 39
   generated into `ported/` (see below; AddHousenumber, AddCycleway and AddRoofShape use SC's country
   metadata); and with `--notes`, the note quest (see "Notes").
   At start-up the engine checks that no filter or per-element port matches an untagged element, then
   skips untagged elements in the main pass; the area pass sees them.
2. **Clock**: SC's age filters (`older today -N`, `< today`) read the wall clock. The `clock` patch
   makes that clock settable; the engine sets it to the extract's replication timestamp. Dates are
   computed in the JVM's default zone, pinned to `America/Toronto` by the launcher
   (`-Duser.timezone`); the engine refuses to run if a city's `timeZone` differs. Cities in another
   zone (Berlin, Hamburg, Bremen: `Europe/Berlin`) need their own run, with
   `JAVA_OPTS=-Duser.timezone=Europe/Berlin` (the launcher puts `JAVA_OPTS` after its defaults, and the
   last `-D` wins).
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
   redundant for cities wholly inside CA-ON. A German position gets only the id `DE` (SC's data has no
   German subdivisions), so a German city's `countryCodes` should be `["DE"]`; no SC v63.4 quest lists
   a `DE-*` code.
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
- **Stubs** `resources/Res.kt` and `ui/ktx/Res.kt` (`Res.readBytesOrNull`): SC reads its
  composeResources through Compose Multiplatform. The stub reads the files the engine bundles under
  `src/main/resources/sc/` instead, so that the vendored `data/meta/CountryInfos.kt` compiles unchanged.
- osmfeatures (`Feature`, `GeometryType`) is the real library, `de.westnordost:osmfeatures:8.0.0`, which
  publishes an `osmfeatures-jvm` variant (an earlier version of this README wrongly said it had none and
  stubbed `GeometryType`). The opening-hours parser is `de.westnordost:osm-opening-hours:0.4.0`, as in SC.

Everything else under `src/main/kotlin/sc/` is byte-identical to SC v64.0 (the third patch, `nolazy`, is
described in `sync-sc.ps1`: v64 caches a date filter's threshold, which would freeze the movable clock
and the multiplier). Stubs under `src/main/kotlin/stubs/` stand in for what the vendored files reach
into but the engine never calls: Compose's `Locale`/`LocaleList` (the JVM's default locale),
`DrawableResource`, SC's generated `Res` with `readYamlOrNull` reading the bundled files,
`ApplicationConstants.MAX_OSM_TAG_VALUE_LENGTH`, `Side`. Moving to a new SC tag is a repin:
[REPIN.md](../REPIN.md).

## Custom quests

SC's 52 custom quests (`OsmElementQuestType` but not `OsmFilterQuestType`) hold their Compose form next
to their logic (in `commonMain` since v64, in `androidMain` before), so they cannot be vendored. For those whose `getApplicableElements()` looks at one
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
- Ported (v64.0): AddSidewalk, AddOpeningHours, AddPostboxCollectionTimes, AddRecyclingContainerMaterials,
  CheckShopType, AddClothingBinOperator, AddOnewayAerialway, AddRoadWidth, AddMaxPhysicalHeight; and,
  with SC's feature dictionary, CheckShopExistence, CheckOpeningHoursSigned, AddPlaceName. Since v64
  AddOpeningHours, CheckOpeningHoursSigned and AddPlaceName take relations too, and CheckShopExistence no
  longer requires a name (a nameless shop whose preset has a name counts).
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

39 custom quests decide where they apply from the map data around an element (crossings of roads and
footways, kerbs, entrances on building outlines, ways below bridges, nodes of ferry routes...). They are
**generated**, not hand-transcribed: `engine/port_area_quests.py --sc <checkout> <Name>...` copies the
quest's file, keeps the imports (minus Compose and resources), everything outside the class, every
non-override member and
`getApplicableElements()` verbatim (plus `isApplicableTo()` where `getApplicableElements()` calls it), and
writes `object <Name> : AreaQuest` into SC's own package under `src/main/kotlin/ported/`, so same-package
helpers resolve unchanged. A `getFeature` constructor parameter becomes `ScFeatures`, and a
`getCountryInfoByLocation` one becomes `ScCountryInfos` (see "Country metadata" below). Four helper
files (FerryUtils, LevelUtils, SummitMarkingsUtil, MaxHeightUtils) are copied whole. v64 added
AddChargingStationSocket (a charging station without mapped charge points), ported the same way. Every file is pinned in
`PORTED-QUESTS.txt` (helpers as `helper:<File>`); on a new SC tag, rerun the script for whatever
`sync-sc.ps1` reports as changed, build, and recheck with the oracle. `ported/AreaQuests.kt` lists them.

`AreaPass` runs after the main pass and does what `OsmQuestController.createQuestsForBBox` does after a
download:

- **Unit: one city** (since 2026-10-12). The map data is the API map call's answer for the city's
  bounding box padded by 1 km: every way with a node in it, with all its nodes (untagged ones too, with
  their tags, version and timestamp), the tagged nodes in it, and the tagged relations with such a member.
  That is the app after downloading the whole city, and exactly the oracle's input. Geometry is SC's
  `ElementGeometryCreator` (relations from the main pass's member ways).
- A result counts if it has geometry, its position is inside the padded bbox (`mayCreateQuest`) and in the
  city's polygon, and the quest is enabled there. A quest that returns an element twice (AddMaxHeight)
  gives one quest, as the app keys quests by element.
- **agedOnly**: each map data is run again with the clock at 1900; results that disappear are agedOnly.
- Cities run one after the other, the quests of a city in parallel.
- **Fast twins** (`openquests/fast/`). Three quests compare everything with everything in SC's code, which
  is fine on the app's small downloads and not on a whole city: AddMaxHeight (every road with every
  bridge; Mississauga 231 s; all cities did not finish in 30 minutes), AddIsAmenityIndoor (every node with every
  building; Ottawa 306 s) and AddHousenumber (every candidate building for every area with an address,
  and a sort that recomputes polygon areas). Each twin is a copy of SC's code with one change that only
  skips work SC's code throws away (a bounds grid where SC's own check fails on disjoint bounds; skipping
  a `removeAll` of nothing; computing a sort key once in a stable sort). AreaPass uses the twin in place
  of the port. A test ties each twin to the pinned sha256 of the SC file it copies, so a version bump
  that changes the file fails until the twin is redone. `-Dopenquests.verifyFast=true` runs the port
  next to its twin on every map data and fails on any difference.
- `--area-unit tiles` runs each z16 tile alone instead (`DOWNLOAD_TILE_ZOOM`, about 600 x 440 m here;
  SC's own `TilesRect` math), the app's smallest download; results count if inside the tile.

**Country metadata** (AddHousenumber, AddCycleway, AddRoofShape). The app hands these quests
`{ countryInfos.get(countryBoundaries, it) }`. `ScCountryInfos` is that call, built from SC's own parts:
- the region ids that SC's countryboundaries data (`boundaries.ser`, library `de.westnordost:countryboundaries:3.0.0`)
  gives for the position, smallest region first: `CA-ON`, `CA` in Ontario; only `DE` in Germany, since
  SC's data has no German subdivisions;
- SC's `CountryInfos` and `CountryInfo`, vendored unchanged. They merge the yml of each id that has one
  (`CA-ON.yml`, `CA.yml`; `DE.yml`) and then `default.yml`, each field from the first file that sets it,
  with kaml 0.104.0, as SC does. SC v63.4 has no `DE-*.yml`.

`sync-sc.ps1` bundles `boundaries.ser` and those four yml files. A position outside Ontario and Germany
(Gatineau, Michigan) reads `default.yml` only, but no quest is counted there. The values the three
quests read are:
- `roofsAreUsuallyFlat`: false (default.yml; neither CA nor DE sets it), so AddRoofShape asks for every
  building with levels;
- the cycleway-ambiguity fields: `hasAdvisoryCycleLane` is false in Ontario (default.yml) but true in
  Germany (DE.yml), where a `cycleway=lane` without `cycleway:lane` is ambiguous and gets AddCycleway;
- `countryCode` (`CA`, `DE`), which AddCycleway compares with BE/NL and AddHousenumber only uses in the
  answer.

**Checked against SC itself** with `tools/sc-harness` CheckCustomQuests in city mode (same map data, SC's
own classes and geometry, `-PcheckBbox` = the engine's area bbox), Ontario 2026-10-11, all 36 quests:
Guelph 13,027, Kingston 10,245, Barrie 6,514 quests, identical sets. For the three country-metadata quests the
oracle's registry gets the app's real `getCountryInfoByLocation`: SC's boundaries.ser and country_metadata from the
checkout, loaded the way `CountryInfos.load` does. The sets are identical again:
- Guelph 15,437 quests;
- Kingston 63,391;
- Barrie 19,422;
- Toronto 404,665: AddHousenumber 12,541, AddCycleway 26,811, AddRoofShape 365,313. Toronto (7.9M nodes, 1.07M ways): 118,170 quests,
identical sets for every quest (the oracle also lists 28 AddEntranceReference, a quest that is off in
Canada; it does not apply country gating).

**Why per city.** A tile's map data misses what lies outside it: a mall's or building's outline with no
node inside the tile, a bridge over a road whose crossing is in the next tile, an area with an address
around a building. The tile is the smallest download, so it gives the lowest counts. The whole city is
what a user sees after downloading it all, and the counts don't depend on where tile edges fall.
All 48 cities, 2026-10-11, per tile → per city (Toronto in brackets):

| quest | per tile | per city | |
|---|---:|---:|---:|
| AddHousenumber | 336,938 | 369,422 | +9.6% (11,658 → 12,541) |
| AddCycleway | 203,787 | 205,869 | +1.0% (26,704 → 26,811) |
| AddMaxHeight | 7,557 | 8,180 | +8.2% (1,968 → 2,045) |
| AddIsAmenityIndoor | 745 | 1,184 | +58.9% (243 → 345) |
| AddLevel | 1,126 | 1,235 | +9.7% (448 → 534) |
| AddLevelThing | 696 | 736 | +5.7% (64 → 71) |
| AddForestLeafType | 14,060 | 14,108 | +0.3% |
| AddMaxWeight | 3,813 | 3,823 | +0.3% |
| AddOneway | 19 | 25 | (3 → 5) |
| AddRoofShape, AddCrossingIsland, AddCrossing | | | within ±21 |

Every other area quest is equal. The Toronto per-city numbers are the oracle's (SC's own classes on the
same data, see above). The verify run (`-Dopenquests.verifyFast=true`, 871 s) found every twin equal to
its port on all 48 cities.

## Notes

`--notes <clip.jsonl>` models OSM notes, which the app downloads with the map data
(`notes?bbox=…&closed=0&limit=10000`). The clip is cut from the planet notes dump by
`tools/clip_notes.py` (`run.py` fetches the dump through osm-extracts and clips it once per dump). The
dump holds every note with every comment and its timestamp, so the notes open at any past asOf can be
rebuilt: created by then, and the last of opened/closed/reopened up to then is not a close; comments
after asOf are dropped, and so are notes without comments (as `NotesDownloader` does, #1338). The run
refuses a dump whose newest comment is older than asOf.

- **Quests hidden by notes.** `OsmQuestController` hides every OSM quest whose position, truncated to 6
  decimals (`LatLon.truncateTo6Decimals()`, vendored), equals the truncated position of any open note,
  quest or not. Notes left from the app sit exactly on the quest they are about. Both passes apply it
  after a quest matched; the denominators are unaffected.
- **The note quest** (`OsmNoteQuestType`) is a note SC's own filter shows: `shouldShowAsQuest` in
  `OsmNoteQuestController.kt`, ported verbatim into `openquests/NoteQuest.kt` and pinned in
  `PORTED-QUESTS.txt` (it runs on SC's vendored `Note`). It is counted for a user who wrote none of the
  notes, with "show all notes" off, the app's default: the first comment holds a question mark (SC's list
  includes `;`, the Greek question mark's look-alike) or any comment holds `#surveyme`. Counted where the
  note's position is in the city.
- Snapshots record the dump in `notes`; without `--notes` it is null, nothing is hidden and the note
  quest is `unsupported`.

## Resurvey settings and tile grids

- **The app's three resurvey settings.** `RelativeDate.MULTIPLIER` (SC's ResurveyIntervals: 0.5 "more
  often", 1, 2 "less often") is a global in SC. The `multiplier` patch makes it read a thread-local
  override first, so each match of an age quest (`usesAge`) is evaluated at 1, 0.5 and 2 in the same
  pass, like agedOnly (`matchVariants`; area quests run `getApplicableElements` once per setting). Every
  setting runs the quest's own test: `newer` tests make the results no subsets of each other. Checked:
  a whole run with `--resurvey-multiplier 2` (or 0.5) as the default gives exactly the `open2`/`aged2`
  (`open05`/`aged05`) of a default run, every city and quest.
- **Show all notes.** The note quest is also counted with the app's other setting (`openAllNotes`).
- **`--grid <dir>`** writes `<asOfDate>.json.gz`: counted quests per z14 tile (DATA-FORMAT.md).

## What still differs from the app

All counted quests are marked `supported`: none of the differences below is specific to a quest.

- **Notes** (with `--notes`): moderator-hidden notes are not in the dump, so a note hidden after asOf is
  missing from past counts. The app downloads at most 10,000 notes per download; the engine logs a warning
  if a city's bounding box holds more open notes than that.
- **What the app has downloaded**: the app builds relation geometry from whatever member ways it has in its
  local database (`allowIncomplete`). The engine has every member way in the extract, so for a large
  multipolygon or route the app's position can differ, depending on download history. Members outside the
  extract (relations crossing the Ontario border) are missing for the engine as well.
- **Relations without geometry**: 1,360 tagged Ontario relations have no usable member way (node-only
  relations such as `public_transport=stop_area`, relations of sub-relations). SC gives them no geometry
  either, so they get no quest in the app; this is not an engine gap.
- **Country gating** is evaluated per city, not per element position. Exact while every city lies inside
  one region (CA-ON, or DE).
- **Default-disabled quests** (30 filter quests) are counted like the others; the site leaves them out of
  headline totals (`defaultDisabled` in quests.json). The resurvey multiplier is the app default, 1.

## Timings and memory

Ontario 2026-10-11, 24 threads, area pass per city: total about 216 s (ways 6.4 s: 4.85M ways near a
city, 37.4M nodes; then the cities one by one, Toronto 43 s with map data 5.8 s for 7.9M nodes and 1.07M
ways, Mississauga 17 s, Ottawa 13 s). Peak heap 30-33 GB (sum of pool peaks; 33 GB
under `-Xmx32g`, so close to the cap); the launcher's default is `-Xmx40g`. Per z16 tile (`--area-unit tiles`) it was about 115 s and 22 GB.

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
