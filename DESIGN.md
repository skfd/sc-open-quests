# Design

Status: dos and don'ts drawn from the prior-art survey, discussed 2026-10-11. Decisions below are agreed.

## The one idea

Count what the app would show. Each number on the site should be "how many quests of type T a StreetComplete
user standing in city C would see, with default settings, on app version V". Each knob that moves that number
is recorded alongside it.

## Do

- **Take filters from the app's build, not from reading its source.**
  - 21 filter strings splice in Kotlin constants, so a regex over the source gets them wrong.
  - Run SC's own registry, either through a small JVM harness next to `PrintQuestFiltersAsOverpassQL` that
    prints each resolved `elementFilter` in SC syntax, or by evaluating with SC's Kotlin directly.
  - Pin the SC release tag (v63.4 today) and store it on every snapshot.
- **Stamp each snapshot with the three knobs:**
  - SC version.
  - Resurvey multiplier: the app's user setting of 0.5, 1 or 2 (proposed default 1).
  - Whether the 34 default-disabled quests are counted.
- **Classify every quest from the code, not by hand.**
  - The 138 `OsmFilterQuestType` (v63.4) start as *supported*.
  - The 51 custom quests start as *unsupported*.
  - A custom quest moves up to *approximated* or *supported* only when someone writes its logic and checks it
    against the app.
  - Show the class on the site. Since every quest reached *supported* (2026-11), the quest table shows it
    only where a quest is not counted: such rows sit greyed at the bottom under their reason (not offered
    in the city, no count in the latest run, not counted yet), and the Support and Status columns are gone.
    Where the app doesn't offer a quest, the site says so by the city's country (`countryCodes` in
    cities.json): "not offered in Canada", "only in 13 countries, not Canada", in the quest table and in
    the compare view, whose all-quests subtitle notes that totals cover different quest sets by country.
- **Split the aging signal from the mapping signal by using the filter itself.**
  - The 48 quests whose filters use `older` can reopen with no edit at all.
  - For those, record the count from the plain tag test and the count that only exists because the element
    or check_date has aged, separately.
- **Apply country gating for Canada and Ontario** (`enabledInCountries`, 27 quests; codes include subdivisions such as CA-ON). Leaving it out
  overcounts.
- **Count by the quest's center point inside the real city polygon.** This matches the app (`OsmQuestController`
  creates a quest only if its center is inside the downloaded area) and avoids starsep's bounding-box
  overcount.
- **Take boundaries from `ontario-farmland`.** Toronto is relation 324211 at admin_level **6**; other cities
  are at 8. Configure cities by relation id, not by admin level.
- **Store denominators beside counts:** element count per quest's base selector, road km, land area from
  `areas.json`.
- **Read the extract from the shared store, don't download it.** `../osm-extracts` owns the Geofabrik
  download into `~/Code/.osm-data` (`OSM_DATA_DIR`). The run calls `osm_extracts.py fetch ontario`, then
  opens the dated file named by `ontario/latest.json` and records its name and sha256 with the snapshot.
- **Reuse the sibling plumbing:**
  - Skip the run when `latest.json`'s `source_last_modified` hasn't changed, so reruns change nothing.
  - One row per day, rewritten if run again the same day.
  - Static JSON under `docs/` served by Pages, published by `run.py update`.
- **Rely on extract timestamps.** Checked 2026-10-11: Geofabrik's public Ontario PBF keeps `version` and
  `timestamp` and strips `uid` and `changeset`. That covers what `older` needs.
- **Adding a city is a line of config.**

## Don't

- Don't hand-write Overpass queries, and don't take filters from the OSM wiki's Turbo links (#2072). They
  drift and some are wrong.
- Don't use ohsome as the engine. Its filter language can't express regex, numbers, dates or element age,
  and v1 dies 2026-11-30. At most, use it to backfill history for the plain key/value quests.
- Don't silently approximate. A quest counted with simplified logic says so on the page.
- Don't compare raw counts across cities on the default view; normalize first.
- Don't mix runs from different SC versions or settings in one line without marking the break.
- Don't treat open OSM notes as noise. The app hides a quest whose center sits exactly on an open note.
  Modelled since 2026-10-12 (see "Notes" below).
- Don't schedule at 12:00 or 12:30; the sibling trackers already use those slots.
- Don't stall on the 51 custom quests. Ship the filter quests first.

## Decisions (agreed 2026-10-11)

- **Engine: Kotlin on the JVM, using SC's own filter code.** No port of the grammar. SC is a pinned
  dependency (or source checkout at a release tag). The first task is a spike that confirms `commonMain`
  `ElementFilterExpression` runs on a plain JVM, reading the PBF with a JVM library (e.g. osm4j or
  GeoDesk). Python stays an option for glue only if it earns its place.
- **Headline counts use app defaults:** resurvey multiplier 1, default-disabled quests excluded from totals
  but still computed and stored, so the site can offer a toggle.
- **Hosting:** Windows Task Scheduler on the owner's machine plus static JSON in `docs/` on GitHub Pages,
  same as toronto-streets-osm. Run slot away from 12:00/12:30, e.g. 13:15.
- **Outreach: nobody yet.** Build the Toronto milestone, then contact starsep, the SC devs and jmizv with
  something to show.

## Spike result (2026-10-11)

- **The engine works without patches.** 26 SC v63.4 `commonMain` files are vendored byte-for-byte by
  `engine/sync-sc.ps1`, which records sha256s in `SC-VERSION.txt`. They compile on a plain JVM with Kotlin
  2.4.0 and kotlinx-datetime 0.8.0, the same versions SC uses.
- **PBF reading:** `osmpbf` protobuf classes with our own three-stage parallel decoder. One full Ontario pass
  takes about 9 s, with a 9–10 GB peak heap and about 132.6M nodes indexed.
- **Cross-checked against pyosmium:** AddBenchBackrest (2,931) and AddBusStopShelter (3,719, which uses
  `older`) matched exactly in the Toronto polygon.
- **Filters come from the build:** `tools/sc-harness` dumps all 190 quests to `data/quests/v63.4.json`, and
  all 138 filter strings re-parse.
- **Semantics to remember:**
  - Date filters use the system time zone. Pin `-Duser.timezone=America/Toronto`.
  - **"Today" must be the extract's replication timestamp, not the wall clock.** The spike used the
    wall-clock date, 2026-10-11, against a 2026-07-16 extract. That miscounts the 48 `older` quests, and a
    rerun of the same extract on another day would change the counts.
    - The vendored `util/ktx/Instant.kt` calls `Clock.System.now()` directly. That's the one place vendoring
      has to deviate: add a settable clock, and have `sync-sc.ps1` apply it as a recorded patch.
    - The same lesson as toronto-streets-osm: "date a row by its extract".
  - `tag older X` is also true when the *element* hasn't been edited since X, so element age counts as well
    as check dates.
- **Known approximations** still to replace (the first two are fixed in milestone 1, below):
  - Way centres are a plain average of their nodes, not SC's centroid or midpoint.
  - Relation centres ignore sub-relations; 776 Ontario relations got no centre.
  - Notes aren't modelled.
- **Licence:** the engine is a GPL-3.0 derivative, so this repo needs a GPL-compatible licence.

## Engine (milestone 1, 2026-10-11)

What changed since the spike (details in `engine/README.md`):

- **All 138 filter quests**, read from the registry dump, for **all 48 cities in one pass**. The CLI
  `sc-open-quests-engine count` writes `docs/data/snapshots/<asOfDate>.json` and `docs/data/quests.json`
  per DATA-FORMAT.md. Custom (51) and note (1) quests are `unsupported`.
- **Settable clock, one patch.** `util/ktx/Instant.kt`'s `systemTimeNow()` reads a settable clock;
  every other wall-clock read in the vendored code goes through it. `sync-sc.ps1` applies it by exact
  line match and records it in `SC-VERSION.txt`. Age filters now run at the extract's replication
  timestamp, so a rerun on another day gives the same bytes (checked).
- **agedOnly** in the same pass: each match of an age quest is re-checked on the same thread with the
  clock at 1900. Toronto, 2026-07-16: 4,256 of 937,458 open quests match only because of time.
- **Country gating** per city as SC's `isInAny`; checked against SC's own `boundaries.ser`, which gives
  Ontario positions both `CA-ON` and `CA`. 11 filter quests are off in every Ontario city.
- **Quest positions from SC's own code.** `ElementGeometryCreator` and its maths are vendored unchanged
  (a stub enum stands in for osmfeatures' `GeometryType`): polygon centroid for areas, half-length point
  for lines, multipolygon ring assembly, member ways only. The 776 relations without a spike centre are
  now 1,360 relations without SC geometry: node-only relations and the like, which get no quest in the
  app either.
- **Denominators**: tagged nodes and ways in the city, and `highwayKm` (road classes motorway…service plus
  links, SC's spherical length).
- **Regression**: with the clock at 2026-10-11 the 12 spike quests in Toronto match the spike exactly
  except AddWayLit (117,651 vs 117,654). Centre changes move very few elements across a city boundary.
- **Speed**: about 20 s wall for Ontario on 24 threads, peak heap ~10.5 GB.

Known gaps:

- Notes are not modelled (the app hides a quest on an open note's position). (Since done: see "Notes".)
- Relation positions assume every member way is present; the app uses what it has downloaded.
- Country gating is per city, not per position; fine while every city is inside CA-ON.
- Custom quests (51) are not counted yet. (Since done: see the sections below.)

## Custom quests, first batch (2026-10-12)

- **Port, don't vendor; check against SC itself.** Custom quests sit in SC's androidMain beside their
  forms. The 9 whose applicability depends only on the element's tags are transcribed into
  `engine/src/main/kotlin/openquests/custom/`, each upstream file pinned by sha256 in
  `engine/PORTED-QUESTS.txt` (sync-sc.ps1 fails when one changes). Their commonMain helpers are vendored
  unchanged. SC's real classes, run on its unit-test classpath (`tools/sc-harness` CheckCustomQuests),
  are the oracle: on all 1.6M tagged Toronto elements of 2026-10-11 the port and SC agree on every one
  of 40,594 quests. So they are `supported`, not `approximated`.
- **The bucket was chosen mechanically:** a custom quest qualifies when `isApplicableTo` never returns
  null and needs no feature dictionary or country info. Next: the 6 that need SC's feature dictionary
  (osmfeatures has a JVM artifact and SC ships its presets), then the ~36 that need surrounding data.
- **Feature-dictionary quests (same day):** CheckShopExistence, CheckOpeningHoursSigned and AddPlaceName
  call `getFeature`. The engine builds SC's own: osmfeatures 8.0.0 (JVM build) over SC's preset files,
  in the JVM locale, pinned to en-CA like the time zone. Oracle again exact: 55,271 Toronto quests for
  all 12 ports. The app's locale is a knob like the resurvey multiplier, but it only decides whether a
  feature has a name; en-CA is the assumption for every city.
- **New quests show as a break, not a jump.** Only the newest snapshot (2026-10-11) was recounted; older
  ones keep `null` for the new quests. The site marks where the set of counted quests changes on the
  totals chart, and the "since last snapshot" tile compares the same quest types on both dates.

## Area quests (2026-10-12, decided while the owner was away)

- **ignoreRelation**: the app drops route (except ferry), boundary, waterway and similar relations on
  download, so both passes skip them (9,835 in Ontario). It changed none of the 150 earlier counts.
- **36 more custom quests**, the ones that need the surrounding map data, are counted. Only AddHousenumber,
  AddCycleway and AddRoofShape remain: they need SC's country metadata (`CountryInfo` from the
  `country_metadata` files plus the boundaries), the next step.
- **Generated ports.** `engine/port_area_quests.py` copies each quest file and drops only the UI and answer
  members; output and pins as for the hand ports. Generated, so a version bump is a rerun, not a rewrite.
- **The unit is the app's download tile (z16), not the city.** The app runs `getApplicableElements` on the
  data of one download; a whole city as one map data is a model of nobody's phone, and SC's quests are not
  written for it (AddMaxHeight is quadratic in roads x bridges and took over ten minutes on Toronto). Per
  tile, the counts match the app's behaviour after a one-tile download. Toronto per tile vs. per city:
  equal or within 0.1% for most quests, but 15-30% lower per tile for the quests that look for a large
  containing polygon (AddIsAmenityIndoor, AddLevel, AddLevelThing). **Open for the owner:** keep the
  smallest download (z16, now), or model a bigger one (z15, or a tile with its 8 neighbours).
- **Oracle again**: city mode on Guelph, Kingston, Barrie and Toronto (147,956 quests) gives identical sets
  with SC's own classes. It found one real bug: a quest returning an element twice was counted twice.
- Cost: the run goes from about 25 s to about 2 minutes and needs a 24 GB heap. Fine for a daily job.

## Country-metadata quests (2026-10-12)

- **All 51 custom quests are now counted.** The last three are AddHousenumber, AddCycleway and
  AddRoofShape. They take `getCountryInfoByLocation`, and the engine answers it as the app does:
  - SC's countryboundaries data gives the position's region ids;
  - SC's own `CountryInfos`, vendored unchanged with a `Res.readBytesOrNull` stub, merges `CA-ON.yml`,
    `CA.yml` and `default.yml`.

  `port_area_quests.py` maps the parameter to `ScCountryInfos`, as it maps `getFeature` to `ScFeatures`.
- **Per position, not per city.** The boundaries are cheap (527 KB) and this is the app's own lookup, so it
  is not modelled on the cities' `countryCodes` the way the quest gating is.
- **Oracle**: the harness registry now gets the real lookup instead of a mock. City mode on Guelph,
  Kingston, Barrie and Toronto gives identical sets for the three quests (502,915 quests).
- **AddHousenumber is the fourth quest the tile unit lowers.** In Toronto it gives 11,658 per z16 tile and
  12,541 per city (-7%). The cause is SC's own rule: a building must lie completely inside the downloaded
  bbox. The owner's open question about the unit size (z16 now, or bigger) covers it too.
- AddRoofShape is default-disabled in the app and very large: 365k in Toronto, since roofs are "not usually
  flat" in Canada. It is out of the headline totals like the other default-disabled quests.

## Area unit: the whole city (2026-10-12)

- **The owner chose the whole city over the z16 tile.** Area quests now run on one map data per city:
  the city's bbox padded by 1 km. That is what the app shows after downloading the whole city, and the
  counts no longer depend on where tile edges fall. Per tile undercounted the quests about a containing
  polygon or a crossing: over the 48 cities, AddHousenumber +9.6%, AddIsAmenityIndoor +59%, AddLevel +10%,
  AddMaxHeight +8% per city (table in engine/README.md). `--area-unit tiles` keeps the old unit.
- **Fast twins.** SC's code is written for small downloads. On a whole city, three quests compare
  everything with everything: AddMaxHeight took 231 s on Mississauga (a run of all cities did not finish in 30 minutes),
  AddIsAmenityIndoor 306 s on Ottawa. `openquests/fast/` holds a copy of each with one change that skips
  only work SC throws away. Toronto's area pass is now 43 s, and the whole run 216 s (was about 115 s per
  tile).
- **Exactness.** Toronto per city equals the oracle (SC's own classes) for every quest. A verify mode
  runs each port next to its twin on every city and fails on a difference. A test fails when SC's file
  moves away from the version a twin copies.
- **History.** Only 2026-10-11 holds area quests, so it was recounted and no chart has a break. Snapshots
  now carry `areaUnit`.

## Monthly history from the planet history file (2026-10-12)

- **Source.** Geofabrik keeps no old dailies. The planet full-history file (`history-261005`, 163 GB) was
  clipped once to Geofabrik's `ontario.poly` (`osmium extract --with-history -s complete_ways`, 50 minutes,
  2.0 GB) into `~/Code/.osm-data/ontario-history/`. `tools/backfill_history.py` cuts one snapshot per
  month with `osmium time-filter` at the 1st, 12:00 UTC, and writes that instant as the file's
  `osmosis_replication_timestamp`, so the engine's clock (age filters) is the month, as for a daily.
- **Today's rules on past data.** Every month is counted with the current registry (v63.4) and engine.
  The series answers "what would this app version have shown then". It does not show what the app of
  that time showed: many quest types did not exist, and SC's resurvey intervals changed.
- **Check: a slice equals a Geofabrik extract.** Slicing at the 2026-08-22 extract's replication time
  and counting both with the same engine gave the same snapshot: 7,506,807 open, every quest, every city,
  every denominator. So the monthly points and the dailies sit on one line without a seam. The slice
  lacks some relation members across the Ontario border (`complete_ways` cannot complete relations in a
  history file), which does not reach any count.
- Months are counted into `data/backfill/` (gitignored), reviewed, then merged into `docs/data/<region>/snapshots/`.

## Notes (2026-10-12, decided while the owner was away)

- **Source: the planet notes dump, not the Notes API.** The API knows only today. The daily dump
  (`planet-notes-YYMMDD.osn.bz2`, 410 MB) holds every note with every comment and its timestamp, so the
  notes open at any asOf can be rebuilt: dailies and the monthly backfill take the same code path.
  `osm-extracts fetch notes` downloads it into the shared store (newest 2 kept, each dump supersedes the
  last); `tools/clip_notes.py` cuts the Ontario bounding box into `data/notes/` once per dump (about 3
  minutes, 88,128 notes, 35 MB).
- **Two effects, both SC's own logic.** Every open note hides the quests at its position, truncated to
  6 decimals (`OsmQuestController`); and a note is a note quest by SC's own filter (`OsmNoteQuestController`,
  ported verbatim and pinned) for a user who wrote none of the notes, with "show all notes" off, the app's
  default: a question mark in the first comment (SC's list includes `;`) or `#surveyme` in any comment.
  `OsmNoteQuestType` is now `supported` and in the headline totals.
- **Size of it.** 2026-10-10: 3,624 notes open in the clip's box (it reaches into the US), 763 of them note
  quests, 189 inside the 48 cities (Toronto 71); 322 of 7,588,287 quests hidden (AddWheelchairAccessBusiness 30, AddOpeningHours 26, CheckShopExistence 23...;
  Toronto 120, Ottawa 95). Checked independently: the run with notes equals the run without minus exactly
  the matches whose truncated position is an open note's.
- **A dump must reach the extract.** The dump of day D is made about 05:00 UTC and ends there; Geofabrik's
  extract of day D is stamped about 20:20 UTC. So day D is counted with the dump of D+1, and `run.py`
  waits a run rather than count without notes. `update` now goes over every stored extract, so a snapshot
  made before its dump existed is recounted once it does.
- **History.** Snapshots record the dump in `notes`; history meta carries `notes: true` and the site marks
  the date notes start (or stop) as a break. Extracts no longer in the store (2026-07-16, 2026-10-02) keep
  their counts without notes; the monthly backfill passes the newest clip too. Recounting 2026-08-22 and
  2026-10-10 with notes also brought them the 49 custom quests they lacked.

## Resurvey settings, "show all notes" and tile grids (2026-10-13)

- **Asked for so that the history is counted once.** Before the final backfill, the owner chose three
  things to store that would otherwise need another full reprocess: the app's other resurvey settings,
  the note quest with "show all notes", and positions for heatmaps.
- **Resurvey ×0.5 and ×2** for every age quest (`open05`/`aged05`, `open2`/`aged2`), in the same pass:
  a second patch (`multiplier`) makes SC's global `RelativeDate.MULTIPLIER` thread-local, as the clock
  patch did for "today". Exact: whole runs at ×2 and ×0.5 equal the in-pass numbers for all 8,448 city ×
  quest pairs (2026-10-10). Ontario's 48 cities: 7,588,154 open at ×1, 7,777,301 at ×0.5, 7,516,201 at
  ×2. Toronto AddBusStopShelter: 6,093 / 3,732 / 1,674. Run time unchanged (about 266 s).
- **"Show all notes"**: 822 note quests instead of 189 (Toronto 274 instead of 71).
- **Tile grids**: counted quests per z14 tile (about 2.2 × 1.6 km) per quest, `data/grid/`, about 0.5 MB
  gzipped per snapshot, not committed. The sums equal `open` for every quest. Publishing (all of it, or
  newest plus yearly) is still open, with the heatmap page.
- History files and the site do not show any of it yet; `run.py history` can add them from the snapshots
  without a recount.

## Site look: StreetComplete's own (2026-10-13)

- **Colours from the app's theme** (`ui/theme/Color.kt`): indigo `#4141ba` for the header, the hero tile
  and "needs mapping"; orange `#D14000` (`#ff6600` dark) for "aged"; traffic-sign green and red for
  changes. Rounded white cards as in the app, and its white map pin as the motif.
- **Quest icons and titles.** `tools/sc_assets.py <sc-checkout>` follows each quest class's
  `override val icon` and `override val title` to `res/graphics/quest/*.svg` and the English
  `strings.xml`, writing `docs/icons/` (index.json, the SVGs, SC's graphics `authors.txt`). The table and
  charts name a quest by the question the app asks ("Does this bench have a backrest?"), class name below.
  Icons are CC-BY-SA 4.0, credited in the footer. Rerun on every SC version bump.
- **Releases on the timeline.** `tools/sc_releases.py` writes the stable GitHub releases to
  `docs/data/sc-releases.json`; run it by hand after a release (not in the daily run, to keep that free of
  another network dependency). Pins sit in a strip above each chart: over a long range only major
  versions, each labelled where its label fits and a dot otherwise; hovering one names it and its date.
  They are context only: every count uses the pinned version's quests whatever the date, which the chart
  says under the legend. They are kept apart from the break lines, which mark changes in *this site's*
  counting.
- Both files are optional; without them the site falls back to class names and hides the releases toggle.

## Selection, pins and the link (2026-10-21)

- **The reader picks the quests that count.** Every quest in the table has a tick; the totals, the tiles
  and the summary chart sum the ticked ones. The default is the app's own: every quest it turns on by
  default, so the off-by-default ones sit in the table unticked and muted rather than behind a checkbox.
  The header tick ticks or unticks every row the search box leaves ("bench", tick), and "App defaults"
  resets. The compare view still ranks by the app-default total, which `cities.json` carries
  precomputed; it says so.
- **Pins are the per-quest charts.** The pin button beside a quest adds its own chart above the table,
  up to six, in the app's pin shape; the old tick-to-chart is gone.
- **The query string reproduces the view**, hash-free since this date: `city`, `view=compare`,
  `pin=A,B`, `cq` (compare quest), `rel=0`, and the selection as a base plus a diff: `base=app` (left
  out), `none` or `all`, with `on=A,B` ticked on top and `off=C,D` unticked from it. The site writes the
  base whose diff names the fewest quests, in registry order, so one selection gives one link. Quest
  class names are the key because they outlive releases: a name the site no longer knows is dropped,
  and a new quest follows the base, so a link made under v63 still opens under v64 and means what it
  said. Old `#city=…&q=…` links are read once (`q` were the charted quests, now pins) and rewritten.
  `?data=` is carried through.

## Regions: Germany's city-states beside Ontario (2026-10-13)

- **Why.** Ontario's totals barely move: few people solve quests there. The owner wanted cities where
  quests are being closed, small enough to be cheap. Germany is StreetComplete's largest community, and
  its three city-states are Geofabrik extracts of their own (Berlin 95 MB, Hamburg 51 MB, Bremen 20 MB),
  so each extract is the city: Berlin, Hamburg, and in the Bremen extract the cities Bremen and
  Bremerhaven.
- **A region is an extract.** `config/regions.json` lists them; a city names its region. The engine runs
  once per region, on that region's cities only, into `docs/data/<region>/`; `run.py history` merges the
  regions. One run is one time zone (SC's date filters read the JVM's), so a region's cities share its
  zone, and `run.py` sets it with `JAVA_OPTS=-Duser.timezone=…`. Notes and the planet history are clipped
  per region, with Geofabrik's `.poly`.
- **Country metadata.** SC v63.4 ships `DE.yml` and no `DE-*` file, and its boundaries give German
  positions only `DE`, so the German cities' `countryCodes` are `["DE"]`. Bundling `DE.yml` matters:
  without it a Berlin position reads `default.yml`, where cycle lanes are never advisory.
- **Approximations for the German cities.** The feature presets stay `en-CA` (`getFeature()` matches by
  tags; only names differ from a German phone). `landAreaKm2` is the OSM boundary's area, water
  included, as for Ontario: Hamburg's 980.9 km² against the official 755 km² is the Neuwerk exclave's
  boundary running out over the Wadden Sea mudflats. Populations are Destatis's, 31.12.2025.

## Repin to StreetComplete v64.0 (2026-10-21)

- **The operation has a name: repin.** Everything the engine counts with is pinned to one SC tag (the
  vendored source, the ports, the registry dump, icons, release pins); moving them all is a repin, the
  routine is [REPIN.md](REPIN.md). The scheduled update now ends with `run.py check-release`: it
  refreshes `docs/data/sc-releases.json` and opens the GitHub issue "Repin to StreetComplete vX.Y"
  once when a stable release is newer than `engine/SC-VERSION.txt`. It is the one network dependency
  the daily run has besides the extracts, and it cannot fail the run: the data is published first, and
  any error in it is logged and ignored.
- **What v64.0 changed for the counts.** 193 quest types (was 190): added AddDoctorType,
  AddVendingMachineType, AddGeneralAccess (replaces AddPlaygroundAccess and AddTowerAccess),
  AddChargingStationSocket (custom: a charging station without mapped charge points) and
  AddChargingStationMotorcar (the two replace AddChargingStationCapacity and
  AddChargingStationBicycleCapacity), AddParkingCharge, AddMotorcycleParkingSurface, AddLockable; removed
  AddProhibitedForPedestrians. 57 filter quests and three hand-ported ones (AddOpeningHours,
  CheckOpeningHoursSigned, AddPlaceName) now take relations; CheckShopExistence no longer requires a
  name (a nameless shop whose preset has a name counts, so it rises); AddIsAmenityIndoor asks for
  bicycle repair stations too. A removed quest leaves the table (quests.json is the newest registry)
  while its series stays in the history files.
- **What v64.0 changed for the engine.** SC became multiplatform: every quest moved from androidMain
  to commonMain, with a Compose form instead of an Android one, so sync-sc.ps1 and the port generator
  read commonMain, the generator drops Compose imports and annotations, and a `Foo.*` import of a
  quest package stays only when the kept code names Foo. SC started caching a date filter's threshold
  (`by lazy`); that would freeze the engine's movable clock and resurvey multiplier after the first
  evaluation, so a third recorded patch, `nolazy`, makes both getters again. New stubs: Compose's
  `LocaleList` (the phone's locale list is the JVM's default locale, en-CA, so
  `getLanguagesForFeatureDictionary()` gives en-CA, en, null), `DrawableResource` and
  `Res.allDrawableResources` (osm/Feature.kt grew an icon lookup), `ApplicationConstants`
  (`MAX_OSM_TAG_VALUE_LENGTH`; `Element` now requires every tag key and value to be at most 255
  characters, which OSM's API guarantees), `readYamlOrNull`. SC's harness needs a JDK 25 since v64
  (Gradle downloads it: tools/sc-harness/README.md).
- **Checked.** The oracle (SC's own classes on the same map data) gives identical sets for all 52
  custom quests on Guelph (33,389 quests) and, for the first time, on a German city: Bremerhaven
  (20,404; AddCycleway, AddHousenumber and AddRoofShape read DE.yml there). The three fast twins
  match their ports on both. The engine's unit tests pass; TorontoRegressionTest stays on v63.4.json
  on purpose (it regresses the vendored filter and geometry code, not the quest set).
- **Where the break is.** After a repin `run.py count` (also inside `update`'s backfill) recounts
  the newest extract of each region with the new registry and leaves the older ones in the store
  alone, so by default the first v64 snapshot is the newest extract at merge time and the totals chart
  marks the change of the counted set there ("+8 types 64.0"), as it did for the custom quests. **For
  v64.0 there is no such break:** the Canada backfill of the same night (next section) recounted every
  published Ontario and German snapshot with v64.0 too, so every series carries one registry and the
  site's break list, which compares consecutive snapshots, has nothing to mark. The branch carried no
  data commit on purpose: the daily "data" commits would conflict with it in the generated history
  files; the first run from main after the merge made it.
- **Merging `sc-v64` into main** (written while another session had uncommitted province work in
  main): `engine/SC-VERSION.txt` is generated, never hand-merged; after the merge rerun
  `engine/sync-sc.ps1 -ScPath <Temp/sc-v64.0> -Tag v64.0` with whatever the other side added to
  `$resources` (its `CA-*.yml` must exist in the v64 checkout). `sync-sc.ps1`, `engine/README.md`,
  `CountriesTest.kt` and `CountryInfoQuestsTest.kt` hand-merge, both sides are additive. Then, from
  main and before the next 13:15: `engine/gradlew installDist` and `test` (the first build downloads
  Kotlin 2.4.20; do not leave that to the scheduler), `python run.py count`, `history`, and commit the
  data. `tools/sc_assets.py` ran already (the icons commit). Ontario's count went from 196 s to
  245 s: CheckShopExistence now asks the feature dictionary for every nameless place before its age
  filter, as SC does. `gh` under Task Scheduler is unproven; a failure shows as
  "check-release failed (ignored)" in `logs/scheduler.log`.

## Regions: the rest of Canada (2026-10-21)

- **Why and what.** The owner asked for the whole of Canada. The rule is one that holds everywhere:
  **every municipality of 50,000 or more in the 2021 census** (Wikipedia's list of the 100 largest,
  parsed from the wikitext). 63 cities joined: 58 in eight new regions, and the five Ontario ones the
  farmland list lacked (Clarington, Caledon, Norfolk County, Halton Hills, Aurora); the 11 Ontario cities
  under 50k stay, their history exists. The territories are out: no municipality clears the bar, and
  Nunavut's extract is 1.4 GB for Iqaluit's 7,000 people.
- **A province is a region.** Geofabrik cuts Canada by province, so `config/regions.json` has one entry
  and one `.poly` per province, with its time zone (Quebec counts in America/Toronto, Saskatchewan in
  America/Regina, Newfoundland in America/St_Johns). `~/Code/osm-extracts` knows the eight URLs. The site
  groups the city list by region group, so every province is its own group, Ontario as before.
- **Relations.** Wikidata's P402 (OSM relation id) for each article; 37 of 42 Ontario rows resolved to a
  relation already in config, which checks the method. Five had no P402 (Levis, Repentigny, Saint-Jerome,
  Saint-Hyacinthe, Halton Hills) and came from Nominatim. `tools/add_city.py` fetched each boundary and
  checked it against the province's `.poly`. Populations are StatCan 2021 (`populationSource`); North
  Vancouver is two cities, the city (`north-vancouver`) and the district (`north-vancouver-district`).
- **Country metadata.** SC ships a `CA-<province>.yml` for all 13 provinces and territories, and its
  boundaries give a Montreal position `CA-QC`, `CA`, so `sync-sc.ps1` now bundles all 13 (it had CA-ON
  only); the engine's tests cover Montreal (`officialLanguages: [fr]`, `hasBicycleBoulevard`) and
  Vancouver, and accept `CA-<province>` and `CA` for every city. Montreal's quest gating equals
  Toronto's: none of the 14 quests the app withholds in Ontario distinguishes provinces. German counts
  did not move by a single quest from bundling the files.
- **Cost, measured** (v63.4 engine, 40 GB heap, 24 threads): Ontario with 53 cities 305 s and a 41 GB
  peak (was 196 s, 33 GB with 48; the four large rural municipalities are most of it), Quebec 19 cities
  109 s / 29 GB, British Columbia 20 cities 90 s / 24 GB, Alberta 10 cities 63 s / 23 GB, the five
  small provinces 10 to 22 s each. A full count of the twelve regions is about 13 minutes; the eight
  new extracts are 3.4 GB a day (about 10 minutes to download here) and about 48 GB in the store at the
  14-day retention. The planet history was clipped to all eight provinces in one osmium pass (1 h 4 min;
  Quebec 1.6 GB, British Columbia 1.7 GB, the rest 0.1 to 0.3 GB each). `backfill_history.py`'s quiet
  window around the 13:15 run is now 12:55 to 13:50.
- **History.** The overnight job (`.scratch/canada-backfill.sh`) counts the eight provinces' months
  2017-01 to 2026-10 and recounts Ontario's and Germany's published snapshots, all with v64.0 (merged the
  same evening), so one registry holds everywhere and the chart needs no "+8 types" break. Ontario
  dailies whose extract is gone and that lie after the history file's end (2026-10-06) keep their 48-city
  counts; the five new Ontario cities have monthly points to 2026-10-01 and dailies from 2026-10-07.


## Planet coverage: what was measured (2026-10-24)

The owner asked for planet coverage. Before building, four checks; the owner's choices are still open
(HANDOFF.md, "Planet coverage").

- **Clipping keeps the counts exact.** Ontario clipped to its cities' bboxes padded by 2 km
  (`osmium extract -s smart`, 46 s, 985 MB to 339 MB, `--output-header=osmosis_replication_timestamp=...`
  or the engine refuses the file) gives the same snapshot, grid and quests.json as the published
  2026-10-23. One relation more lands "in some city" (a route or boundary losing far members); no count
  moves. A production clip should keep `-S types=multipolygon,boundary,route` (not yet run).
- **Heap follows the biggest city, not the extract.** The 34 GB peaks are a lazy collector under
  `-Xmx40g`. Ontario runs in 12-16 GB, clipped or not; Berlin's 7.9M nodes need 4-8 GB, all of it
  the whole-city area pass. Time is the same story: about 150 s of Ontario's 188 s is the area pass.
  So the planet is not a memory problem once it is clipped to city envelopes; a Tokyo or a Chongqing
  is, and needs an area cap or a split.
- **Engine limits for arbitrary countries** (file:line in the session report, summarised):
  at most 64 cities per run (a 64-bit city mask, AreaPass.kt); one time zone and one output folder per
  run (Main.kt, run.py), so a region cannot be split into two runs on one extract; only 16 of SC's
  country_metadata files are bundled, and a missing one falls back to default.yml silently;
  `add_city.py` needs country codes and zone typed by hand and its `slug()` drops non-ASCII names;
  notes are clipped once per region (46 s each, the whole dump each time); osm-extracts knows 12 URLs
  and has no replication diffs. Already global: SC's boundaries.ser, quest gating, geometry, the grid.
- **Cities from Wikidata** (P1082 population, P402 relation; `.scratch/world-cities/`):

  | population at least | settlements and municipalities | with an OSM relation | of those, not province-sized |
  |---|---|---|---|
  | 1M | 732 | 536 | 255 |
  | 500k | 1,313 | 898 | 594 |
  | 250k | 2,482 | 1,602 | 1,287 |
  | 100k | 6,001 | 3,666 | 3,342 |

  P402 is missing for nearly all of India, Pakistan, Bangladesh and Egypt, and half of Russia and China;
  where OSM has the boundary it often links the parent province item instead (Istanbul, Izmir, Tokyo).
  "Province-sized" is mostly China's prefecture-level cities (Chongqing 82,403 km²), Turkey's
  metropolitan provinces and Tokyo-to. Wikidata areas and populations are often wrong by a factor.
- **Publishing breaks first, and already at today's size.** GitHub Pages publishes at most 1 GB.
  `docs/` holds 334 MB, 316 MB of it the 1,485 snapshot files kept forever, growing 2.5 MB a day: the
  cap is about 9 months away with no new city. A snapshot is 21.8 KB per city, history 1.2 KB per city
  per date, and the compare view downloads every region's snapshot. At 1,000 cities the monthly history
  alone is 2.6 GB. Fix, needed regardless of the planet: publish only the newest snapshot per region
  (archive outside `docs/`), a small per-quest file for compare, and at a few thousand cities daily data
  out of git (R2 or release assets).
- **Disk.** 151 GB free on C:, with the 163 GB planet history file in the store. A planet pbf is about
  85 GB more.

## Planet coverage: the owner's direction (2026-10-24)

- **Players come first.** The site is for StreetComplete players asking "how is my place doing?", not
  for planet totals per quest type.
- **Every place on Earth gets a name, but only requested places get counted.** A named breakdown of
  the whole world exists up front; stats are counted for a place only when its community asks for it.
  Whether land outside any city (rural roads) counts is still being debated.
- **Wandrer.earth is the model.** Its nested named regions (country down to neighbourhood) are the
  inspiration, and possibly the data source for the breakdown. Whether its regions can be reused, and
  under what licence, is for the session that explores the breakdown.
- **Cities stay as they are for now:** the population bar of today. Inside a city, counts go down to
  neighbourhoods, Wandrer-style.
- **History and cadence (asked in the measuring session):** monthly history since 2017 for every place
  that gets counted, as for Canada and Germany, cut from the planet history file; then weekly counts from
  one planet file, clipped to the counted places' envelopes in one pass. Canada and Germany stay daily.
  Disk is set aside for later; the owner will solve it.

## Places: naming the world, counting on request (proposal, 2026-10-24)

Proposal from the breakdown session; nothing built. Sources are in the session's two research reports
(Wandrer.earth; world boundary datasets), the URLs repeated here where a choice rests on them.

- **Wandrer cannot be the data source; it is the model.** No API, no export, region pages behind a
  login, "All Rights Reserved" (wandrer.earth/terms). Its regions are OSM boundaries plus neighbourhoods
  patched in one city at a time from 38 municipal open-data sources, each credited on its terms page, and
  added when a user emails the source (wandrer.earth/faq). It rebuilds from one planet file about monthly.
  Copy that: OSM as the backbone, neighbourhoods patched per request from open data, a data-licences
  page, requests that bring their source.
- **Names from Overture Maps `divisions`.** ODbL like our output; one world hierarchy with
  `parent_division_id`, normalised `subtype` (country, region, county, localadmin, locality, borough,
  macrohood, neighborhood, microhood), local names, wikidata, monthly releases (latest 2026-10-21.0),
  6.4 GB for the world, downloadable per bbox (docs.overturemaps.org/guides/divisions). Each feature
  names its OSM source (`sources[].record_id` such as `r166560@15`, plus bridge files). Raw OSM
  `admin_level` cannot be the hierarchy: its meaning changes per country. Who's On First (sporadic, 42 GB,
  CC-BY parts), geoBoundaries (no parents, mixed licences) and GADM (no redistribution) are out.
- **Two layers, two ids.** The *name layer* is every Overture division: id, name, parent, subtype, bbox,
  centroid, OSM relation. No polygons, nothing counted. The *count layer* is the places someone asked
  for, counted on OSM geometry by relation id as `add_city.py` does today, so the boundary and the counts
  come from the same data. The public id is a readable path (`ca/on/toronto/the-annex`, Unicode-safe),
  mapped to the GERS id; GERS ids survive Overture's conflation but subtypes move with OSM tagging
  (Czechia and Slovakia, 2026-06 release), so a monthly diff flags places whose subtype or parent moved.
- **Three kinds of counted place.**
  - *Run place*: today's city. Its own map data, so the area quests stay exact (DESIGN.md, "Area unit").
  - *Sub-place*: a neighbourhood or borough inside a run place. Counted from quest positions inside
    its polygon, in the run place's pass: the engine already counts one element towards several
    overlapping places (`Engine.kt` `offer`, the `cityIdx` loop), so a sub-place is one more polygon in
    the index with no map data of its own. Its numbers are the city's numbers split by position, which is
    what a player there sees. Lifting the 64-place mask (taken by the measuring session) is the one
    engine prerequisite.
  - *Roll-up*: a region or country. Only the sum of its counted children, labelled "N of M places
    counted". Never a number that looks like full coverage.
- **Land outside cities** then has an answer that costs nothing to decide later: it is a county or
  localadmin in the name layer, and counting it means requesting it as a run place. Neighbourhoods
  never cover what their city does not, and children are not promised to add up to the parent
  (OSM neighbourhood polygons overlap and leave gaps).
- **What it costs before anyone asks.** A name shard per country, loaded when the reader opens that
  country, and per city for its neighbourhoods. Size unmeasured; with the Pages cap (DESIGN.md,
  "Planet coverage: what was measured") it must stay well under 100 MB for the world or live outside
  `docs/` like the archive.
- **The request.** The site's search finds any place. An uncounted place shows its hierarchy and an
  "Ask for this place" link: a GitHub issue form, prefilled with the place id, where a 👍 is a vote and
  a reply can name an open neighbourhood source. Adding a requested place stays a reviewed commit.
- **Where Overture is thin.** Neighbourhoods are spotty below county (Overture's own docs); some
  features come from geoBoundaries with no OSM relation, and those count on Overture's polygon or not at
  all. Fill neighbourhoods from OSM (`admin_level` 9-11, `place=suburb|quarter|neighbourhood` areas,
  `boundary=place`) attached under the Overture parent by containment, then municipal open data per
  request (Toronto's 158 neighbourhoods are OGL-Toronto, which Wandrer already uses).
- **Disputed areas** (Kashmir, Crimea, ...): Overture carries perspectives; pick one policy before the
  first such country. Decided 2026-11-10: countries come from SC's own boundary data, below,
  "Countries in the place index: StreetComplete's, not ours".

**The owner's answers (2026-10-24, late evening):** names from Overture `divisions`, counting on OSM
geometry, as proposed. Neighbourhoods from **OSM only**: where neither OSM nor Overture has one, the
city has none; no municipal open data, so no per-source licence checks. Requests through a **GitHub
issue form** (players without an account cannot ask; accepted). The spike below runs that night.

**Next, a spike before any building:** pull Overture divisions for Canada and Germany with DuckDB (not
installed; `pip install duckdb` in the .venv) and measure: features per subtype, the share with an OSM
relation, whether the 115 counted cities are found by relation id, neighbourhoods inside Toronto and
Berlin, and the size of a name shard per country, extrapolated to the world.

## Publish format: newest snapshot only (2026-10-24)

- **What the site fetches** (read off `app.js`): `cities.json`, `quests.json`, `sc-releases.json`,
  `icons/index.json`, `history/<city>.json`, and, in the compare view with a quest picked, every
  region's newest snapshot (each city's `asOfDate`). No view and no link reads an older dated snapshot:
  the query string has no date, and the charts read the history files.
- **The archive leaves `docs/`.** The engine writes `data/archive/<region>/snapshots/<asOfDate>.json`
  and its `quests.json` (gitignored; `--out data/archive/<region>`, no engine change), and
  `run.py history` reads the archive. `docs/data/<region>/snapshots/` keeps the region's newest
  snapshot only, a byte copy: 12 files, 2.5 MB. It stays in git, so git history holds each day's
  published newest; months merged later by `backfill_history.py` are in the archive only.
- **Compare reads one small file per quest**, `docs/data/compare/<quest>.json`: each city's open count
  in its newest snapshot, 184 files of about 1.75 KB. Picking a quest fetches 1.75 KB instead of
  12 snapshots (2.5 MB). Checked equal to the old lookup for all 22,195 city × quest pairs.
- **Sizes.** `docs/` went from 1,795 files, 332.7 MB, to 506 files, 19.3 MB (history 15.0 MB). It now
  grows by the history files only, about 0.1 MB a day at 115 cities instead of 2.5 MB. The archive is
  317 MB on disk and grows as `docs/` used to.
- **History did not move.** Rebuilt from the archive, all 115 history files, `cities.json` and
  `quests.json` are byte-identical to the ones built from `docs/data`.
- **Migration is a step, not a commit.** `run.py migrate-archive` moves any snapshot still in
  `docs/data/<region>/snapshots/` (and the engine's old `docs/data/<region>/quests.json`) into the
  archive; `count` and `history` run it first, so the scheduled `update` migrates by itself and its
  `git add docs/data` stages the 1,473 deletions. Idempotent; a file that differs from the archive's
  copy is left in place and logged.
- **A lost archive cannot shrink the site.** `history` refuses to run when the archive lacks a date
  that the published `cities.json` has (a fresh clone, a deleted `data/`), instead of rebuilding a
  shorter history. The snapshots up to 2026-10-24 can be restored from git history; of later ones git
  has only each day's published newest, so the archive is the one copy of the rest (not backed up).

## Planet history kept current with diffs: measured (2026-10-24)

- **It works.** `osmium apply-changes -H` takes the history file plus daily diffs
  (`replication/day/000/005/NNN.osc.gz`, sequence 5137 is the first after the 2026-10-05 dump; 5136 +
  days since 2026-10-05) and writes a new history file. Re-applying a diff changes nothing, and
  apply-changes sorts the diffs itself. Never use `merge-changes --simplify` on history: it keeps only
  the last version.
- **Always pass `-H`.** The store's file is named `.osm.pbf`, not `.osh.pbf`; without `-H` osmium exits
  0 and silently collapses the history (Ontario: 232.9M node versions to 184.7M).
- **The cost is the rewrite, not the diffs.** Ontario's 1.98 GB clip plus two diffs: 66 s, the same as a
  plain `osmium cat`; memory about 3.4 GB plus 0.85 GB per daily diff (a week is about 10 GB). For the
  163 GB planet that predicts about 1-1.5 h a week, plus about 1 h to clip the counted places' envelopes,
  and a week of diffs is 0.75 GB to download (1-2 minutes here).
- **Disk decides it.** The update cannot work in place: it needs a full second copy, about 165 GB free.
  C: has 150 GB. The history file also has a second hard link (`name-ru-repair\data\planet\`), so the
  old copy frees no space until both links go. A weekly `planet-latest.osm.pbf` download (about 85 GB,
  about 4 h) fits today, but the history then stays frozen at 2026-10-05.
- **What tips it:** whether a place first requested later (say 2027-06) must get monthly points from
  2026-11 on. If so the history has to stay current (weekly, or monthly plus a weekly planet). Disk is
  the owner's (see the owner's direction above).

**Spike result (2026-10-24, night).** Overture release 2026-10-21.0, read straight from S3 with DuckDB 2.0
(`tools/overture_pull.py RELEASE CC...`; Canada and Germany: 141,000 divisions in 39 s, 52,789 areas, 430 MB,
in 5 min; data in `data/overture/`, not committed; the measuring scripts in `.scratch/overture/`).

- **Places per subtype**, with a polygon / with an OSM relation as source:

  | | Canada | with polygon | OSM relation | Germany | with polygon | OSM relation |
  |---|---|---|---|---|---|---|
  | region | 13 | 13 | 13 | 16 | 16 | 16 |
  | county | 1,537 | 1,537 | 1,537 | 399 | 399 | 399 |
  | locality | 13,001 | 5,830 | 5,623 | 89,341 | 23,237 | 21,774 |
  | macrohood | 1,058 | 502 | 493 | 7,239 | 2,823 | 2,676 |
  | neighborhood | 6,623 | 4,022 | 3,632 | 14,293 | 9,327 | 8,540 |
  | microhood | 679 | 303 | 160 | 6,799 | 4,717 | 587 |

  Overture has no `localadmin` in either country. A place without a polygon is an OSM `place` node, so
  it can be named but not counted.
- **Our cities: 113 of 115 are found by their relation id**, every one with a polygon, as `locality`,
  `county` (Toronto, admin_level 6) or `region` (Berlin, Hamburg). The two misses show the link is not
  always the admin boundary: Laval's Overture locality cites relation 1438336, not our 3532125
  (admin_level 5), and Markham's cites a way (w1499781347), not relation 324213. The fallback is
  wikidata, then name plus containment, and a city keeps the relation it is counted on.
- **Neighbourhoods inside a city** (descendants in `hierarchies`, with a polygon): Toronto 176 of 446
  neighborhoods, 37 of 55 microhoods; Berlin 96 of 105 macrohoods (the Ortsteile), 55 of 364
  neighborhoods, 297 of 549 microhoods; Hamburg 102 of 106 macrohoods; Montreal 19 macrohoods, 16
  neighborhoods; Vancouver 22 macrohoods, 4 neighborhoods. With OSM only, a city gets the polygons
  OSM has, and Toronto has 176, not the city's 158 official ones.
- **The world:** 4.70M divisions in 272 countries, **1.08M with a polygon** (556k localities, 325k
  neighborhoods, 89k microhoods, 47k macrohoods, 39k counties, 22k localadmin, 3.9k regions). The most
  are Russia 144k, India 62k, US 60k, France 57k, Ireland 52k, Germany 41k, Brazil 40k, China 40k; India,
  China, Nigeria, Egypt, Pakistan and Bangladesh together 118k. Coverage there is better than the
  Wikidata city list suggested (DESIGN.md, "Planet coverage: what was measured").
- **The name layer's size.** Id, name, subtype, parent, OSM id, wikidata, bbox and population as
  compact JSON: Canada 22,912 places 3.8 MB (1.2 MB gzipped), Germany 118,088 places 19.1 MB (6.1 MB).
  About 160 bytes a place, so the 1.08M places with a polygon are about 175 MB raw: too much for
  `docs/` under the Pages cap, and too much for one download. **Proposal:** name only the places with a
  polygon (a point cannot be counted), shard by region (a file per country listing its regions, a file per
  region listing what is inside it), and keep the files out of `docs/` with the archive, or trim the
  record to id, name, parent and bbox (about half the size).
- **The owner chose it (2026-10-24, later that night):** the history file is kept current weekly with
  diffs, so a place requested later still gets monthly points without a gap; the owner is preparing the
  disk (about 165 GB free beyond today's files). The updater is `osm-extracts fetch planet-history`
  (only osm-extracts downloads into the store); sc-open-quests' weekly job slices and counts.


## Pipeline: shared extracts and one notes pass (2026-10-24)

Groundwork for counting many places from one planet file (weekly) and the planet history (monthly).

- **A region names its extract.** A region was its extract: one id for the store folder, the
  osm-extracts fetch and the output folder. An optional `extract` key in `config/regions.json` (default:
  the id) now names the store folder and the fetch, and an optional `url` goes to `fetch --url` for an
  extract osm-extracts does not know by name. The region stays the engine run: one time zone, its own
  cities, its own `data/archive/<id>/` and `docs/data/<id>/`, grid and notes clip. So a country across
  time zones, or more cities than one run takes, is several regions over one extract. `download`
  fetches each extract once; a snapshot is matched to its extract by sha256 inside the region's own
  archive, so each region counts a shared extract once and skips it after. Today's twelve regions need
  no change.
- **Notes: one pass for every region.** `clip_notes.py` decompressed the whole 433 MB dump once per
  region (46 s each, twelve a day even on days without a new extract). It now takes many polys
  (`--config`, or repeated `--poly`/`--out`) and writes every clip from one pass: a 1-degree grid of the
  clips' bounding boxes picks the few notes worth an exact test. The first region to need a clip of a
  dump makes all missing ones. 2026-10-24 dump, twelve regions: 102 to 173 s on a busy machine, where
  the old tool took 79 to 140 s for one region at the same time (46 s when quiet). So twelve regions now
  cost about one and a half old single-region passes, against twelve (about 9 quiet minutes) before.
- **The polygon, not its bbox, plus the cities' boxes.** The clip was the poly's bounding box (Ontario's
  reaches deep into the US). It is now the poly itself (holes subtracted, edges in, antimeridian-safe),
  united with the region's cities' bounding boxes padded by 1 km, the engine's own padding. The engine
  reads notes only inside city polygons (hidden quests, the note quest) and counts open notes in each
  city's bbox (the 10,000 warning); Geofabrik's polys are simplified, and `add_city.py` warns about
  border cities whose boundary pokes out of them by metres, so the poly alone could lose a note it uses.
  Against the per-region clips of the same dump: every common note byte-identical, every note in a padded
  city box kept, 77,300 notes dropped (all outside both the poly and every box; Ontario 40,780, British
  Columbia 18,460), 965 added (within 1 km outside the poly's bbox: the regions Berlin 536, Bremen 295,
  Hamburg 133, Alberta 1 at Wood Buffalo). Counts do not move; a snapshot's `notes.open` does, as it counts the clip's open
  notes. Existing snapshots are not recounted for it.
- **The planet history file is a parameter.** `backfill_history.py --planet history-<YYMMDD>`, by default
  the newest in the store's `planet/` folder (today the same `history-261005`).

## Engine: ready for any country (2026-10-24)

Three of the engine limits listed in "Planet coverage: what was measured", lifted; the
one-time-zone-per-run limit stays.

- **All of SC's country metadata.** `sync-sc.ps1` bundles every `country_metadata/*.yml` SC v64.0 ships,
  515 files (1.2 MB; was 16), and writes their codes to `sc/country_metadata.index`. A region SC has no
  file for is skipped, as in the app; a file SC ships that the bundle lacks now fails the run instead of
  falling back to `default.yml`. A test compares the bundle with the SC checkout byte for byte and
  decodes all 515; Tokyo reads `JP.yml` (left-hand traffic), Sydney `AU-NSW`, `AU`, Houston `US-TX`, `US`.
  The 16 old files are unchanged, so a Canadian or German position reads nothing new.
- **Any number of cities per run.** The area pass kept city membership in a 64-bit mask; it is now the
  id of an interned set of cities (an Int, 0 for none, c + 1 for city c alone). A grid of at most
  512 x 512 cells over the cities' boxes finds the candidate cities of a point, in the area pass and in
  the main pass's `citiesAt` (it tested all 53 Ontario boxes per tagged element). A test runs 80
  synthetic cities and gets each city's counts equal to two runs of 40.
- **Ontario unchanged.** The 2026-10-23 extract recounted with the arguments of the published run gives
  the same 53 cities x 179 quests (9,487 counts, all fields), denominators, notes and tile grid. Under
  `-Xmx16g` the pass took 261-271 s, the old engine under the same heap 282 s, the published run under
  `-Xmx40g` 188 s: the small heap costs about 80 s of collection, the grid and the set ids nothing
  (area pass ways 6.4-7.1 s vs 6.8, nodes 3.7-4.0 s vs 3.9; Toronto 38-46 s vs 50).
- **City ids in any script.** `add_city.py` drops accents (Montréal → `montreal`, Łódź → `lodz`); a name
  that does not transliterate (Москва, 東京都) or a slug another relation holds gets `r<relation>`;
  re-adding a relation keeps its id. Country codes and time zone are still typed by hand.

## Engine heap: what the machine can spare (2026-10-24)

- **The owner's rule:** as much heap as the machine can spare, and run when memory is not busy. No fixed
  cap. `run.py engine_env(heap=True)`, used by `count` and `backfill_history.py`, reads Windows'
  `GlobalMemoryStatusEx` at each engine start and passes `-Xmx` = the smaller of free physical memory and
  free commit charge, less 8 GB, at most 75% of physical memory. An explicit `-Xmx` in `JAVA_OPTS` wins;
  the build's `-Xmx40g` stays as the default off Windows.
- **The commit charge is the real limit here.** On 2026-10-24 at 22:55: 50 GB of RAM free, but only 28 GB
  of commit charge left (the paging file is 27.8 GB, and something holds committed memory it does not
  touch). That is what killed the 2026-10-17 run: a 5.3 GB commit failed with physical memory to spare.
  Spare heap at that moment: 19 GB.
- **Busy memory waits, then skips.** Under 12 GB spare (Ontario counts in 12-16 GB), the engine waits and
  re-reads every minute, up to 60 minutes (`SCOQ_HEAP_WAIT_MINUTES`), then the run stops with a clear
  error. A skipped count is not lost: the next run goes over every stored extract.
- **Same counts.** Bremen 2026-10-23 with `-Xmx19g` equals the archived snapshot. A smaller heap is a
  little slower (Ontario 260 s at 16 GB against 188 s at 40 GB), not different.

## Weekly planet job (2026-10-24)

The sc-open-quests side of the owner's choice above: places counted on request get monthly history since
2017 and then weekly counts, all from the planet history file that `osm-extracts fetch planet-history`
keeps current with replication diffs. Canada and Germany stay daily from Geofabrik. No place is weekly yet:
the place list is the breakdown session's.

- **A region says how it is counted.** `"cadence": "weekly"` in `config/regions.json` (default `"daily"`).
  `download`, `count`, `backfill` and `update` skip a weekly region (it has no extract); `history`, the
  notes clip and `cities.json` see every region. An unknown cadence fails the run.
- **`run.py weekly`**, one code path with `tools/backfill_history.py` (`weekly()`): (1) `osm-extracts fetch
  planet-history`; any failure, disk the likely one, is logged and the file is used as it is (an older
  history is still a valid source); (2) clip every weekly region from the newest history file in one
  pass, deleting each region's older clip; (3) count the 1st of each month since 2017-01 that the region
  lacks, at 12:00Z as before; (4) a slice at the history file's own replication timestamp, skipped if a snapshot already
  counts that slice (a history file the fetch could not move on); the engine dates it in the region's zone
  and the snapshot is dropped if the region has that date already (no tzdata needed); (5) merge into
  `data/archive/`, rebuild history, commit `data weekly <UTC date of the history file>` and push
  (`--no-push` commits only, on `update` too). With no weekly region it stops after (1).
- **History file naming.** `backfill_history.py` takes `history-<YYMMDD>.osm.pbf` (the planet site's dump,
  today's 261005) or `.osh.pbf` (osm-extracts' diffed file), the newest by date; the meta's
  `derived_from` goes into clip and slice metas, and a slice of a diffed file has no `source_url`.
  `months --to` defaults to the last month whose 1st, 12:00Z, the file reaches: 2026-10 for 261005, as the
  hard-coded default was. Clips are named after the history file, so a new file means new clips.
- **Never across the daily run.** The job takes the pipeline lock per step, not for its ten hours: each
  count (as `backfill_history` always did) and merge + history + publish together. No step starts that
  would reach the 13:15 update's window (12:55-13:50): the fetch waits if the window is under two hours
  away, the planet clip under 90 minutes, a count or the publish inside it. The fetch itself touches only
  the store, which osm-extracts locks. The planet clip, like the engine, waits while memory is busy
  (`run.engine_heap_gb`); a region's slices are small and do not.
- **Schedule:** `schedule-weekly-add.ps1` registers `kk-SCOpenQuests-weekly`, Mondays 07:30, ten hours,
  start when available, no second instance; not registered yet. A new weekly region's first run counts
  118 months (Bremen under a minute each with its slice, Ontario 5 min: past the ten hours, so run `backfill_history.py
  months` by hand first, or let the next weeks finish it; staged months are kept across runs).
- **One snapshot per date.** A month's 12:00Z slice beats a weekly slice of the same local date (a file
  ending 2026-11-02T00:00Z is still the 1st in Toronto). A file ending on a 1st before 12:00Z gives that
  date's snapshot from the weekly slice, and the month's 12:00Z slice is then skipped.
- **Checked end to end without the planet.** A stand-in history file: Bremen's 261005 clip plus the
  planet's daily diffs 5137 and 5138 (`osmium apply-changes -H`, 25 s, 73 MB to 166 MB: the diffs carry the
  whole world's edits), named `history-261007.osh.pbf` with a meta at 5138's 2026-10-07T00:00:00Z, in a
  scratch store; a clone of the repo with one region `bremen-weekly` (Bremen's poly and two cities), its
  archive seeded with Bremen's published monthlies up to 2026-09, notes dump 261022 (the one the published
  months used), and a stand-in osm-extracts that fails for disk. `run.py weekly --no-push`: the failed
  fetch is logged and the run goes on; the clip is back to 73 MB; 2026-10-01 is counted and its slice is
  **byte-identical** to the published one's (same sha256), with all 366 city x quest counts and every
  denominator equal (`notes.open` 645 against 634: the one-pass notes clip's wider area, as above); the
  'now' slice is dated 2026-10-07 (02:00 in Berlin), totals Bremen 258,140 and Bremerhaven 65,856 between
  the published 2026-10-01 (258,131 / 65,896) and the 2026-10-12 daily (258,251 / 65,785). A second run
  counts nothing (119 dates already there), rebuilds history and commits `data weekly 2026-10-07`
  (188 files) without pushing.

## Planet job: monthly while nothing counts from it (2026-10-30)

- **First update, measured.** `history-261005.osm.pbf` plus the 24 daily diffs 5137-5160 became
  `history-261029.osh.pbf` (158.8 GB) in one pass: 7,281 s, osmium peak 15.6 GB (osm-extracts estimated
  23.8 GB). Almost all of the time is the rewrite: the PBF is sorted, block-compressed and unindexed, so
  any change means reading the 159 GB file and writing a new one.
- **Every run writes about 160 GB**, whatever the number of diffs. Weekly that is about 8 TB of SSD
  writes a year, daily about 58 TB, for a file no counted place reads yet (no region has
  `"cadence": "weekly"`). The owner chose monthly: `kk-SCOpenQuests-weekly` runs on the first Monday of
  each month at 07:30 (`schedule-weekly-add.ps1`), about 2 TB a year. Names stay "weekly": the command,
  the task, the log and the cadence key.
- **Not longer than monthly.** A pass takes at most 31 diffs (`--max-diffs`, the memory cap: about
  3.4 GB + 0.85 GB a diff estimated, 15.6 GB measured at 24), so a two-month backlog costs two rewrites.
  A place requested later still gets monthly points without a gap: the history file only has to reach
  each month's 1st.
- **When a region goes weekly,** a monthly history file gives it the same data four weeks running.
  Then either schedule the job weekly again, or count current data from a small extract of the counted
  places kept current with each daily diff (about 100 MB a day, applied and clipped in minutes; the
  history file stays monthly). The second also fits moving the 115 Geofabrik cities to one daily diff
  (4.7 GB of extracts a day today). Its open risk is edges (a way joined to nodes outside the clip); the
  check is a week side by side with the Geofabrik counts of the same cities. Not built.

## World: a seeded bar plus requests (2026-10-30)

The owner's answers to "are we ready to build all the places in the world":

- **Both roads.** The biggest cities of some countries are counted up front, chosen by a bar, and
  any other place is counted when a player asks for it. This replaces "only requested places get
  counted" from 2026-10-24. The bar and the countries are still open.
- **Any place with a polygon can be requested:** a town, a village or a county. No population floor.
- **The first planet-counted places are actively mapped European cities.**
- **Current numbers come from the daily planet diffs.** The history file is still rewritten once a
  month, but the daily diffs are downloaded every day and used for the current counts. How to do that
  cheaply is still being discussed (below).
- **Not built yet:** nothing turns a place id from the request form into a counted region.
  `add_city.py` needs a Geofabrik extract id, country codes and a time zone typed by hand.

**Proposal for the current counts (under discussion).** Once a month, right after the history
rewrite, cut a *current clip* from the new history file: its last state inside the counted places'
envelopes, padded, with `-s smart` so multipolygons keep far members. Every day, apply that day's
diff to the clip (`osmium apply-changes`, no `-H`), re-clip it to the envelopes (the diff carries the
whole world's edits), and count. Ontario's 1.98 GB clip took 66 s with two diffs, so a European
city set should take a few minutes a day. The next month's cut from the history file throws the clip
away, so errors last a month at most.
The risk is the clip's edge. Say a diff moves a way inside our envelope and the way uses a node that
lies outside the clip and was not edited. The diff does not carry that node, so we lack its
position. `osmium check-refs` counts such missing nodes each day. Berlin, Hamburg and Bremen are
already counted daily from Geofabrik, so a week of both side by side gives exact answers to check
against.

**The owner's second answers (2026-10-30, early morning):**
- **Test the clip-plus-diffs plan before building on it.**
- **osm-extracts owns it:** a daily planet-diff fetch, and a current clip of given boxes kept up to
  date by those diffs, as a store product. Other projects can use it. Only osm-extracts downloads into
  the store, as before.
- **Choose the European cities by StreetComplete edits:** rank them by StreetComplete changesets in
  the last 12 months, from the changeset dump (every changeset carries `created_by` and
  `StreetComplete:quest_type`). Show the owner the top 10-20 before counting.
- **The seeded bar waits for the European pilot:** pick it from what a city really costs on disk, in
  time and on the site.

**The test, replayed rather than waited for.** The history file holds the true state of every past
day, so a week need not pass in real time:
1. Clip `history-261029` around Berlin, Hamburg and Bremen in one planet pass. Pad the clip about
   20 km, so a padded `-s smart` cut taken from it equals a cut taken from the planet.
2. Take the state at 2026-10-05T00:00Z from that clip and cut it to the counted places' padded
   envelopes. That is the starting clip.
3. No download: each day's diff is derived from the history clip itself (`osmium derive-changes`
   between the slices of day D-1 and day D). The owner's point: the history file already holds
   every version. Like a real diff, a derived diff carries only what changed, so the clip's edge is
   tested the same way. It lacks edits more than 20 km out, which cannot reach the counted area.
   Real diffs are first used when this goes live, and are checked against Geofabrik then.
4. For each day, apply its diff to the clip, re-clip, run `osmium check-refs`, and count. Compare
   each day with the true slice of the history clip at the same moment.
That gives 24 days of drift, close to the month a clip lives, and it can be done in one unattended
run. The Geofabrik dailies of the same cities are a second check.

**The test's result (2026-10-30, 04:30 to 12:02).** Berlin, Hamburg and Bremen, 24 days each
(2026-10-05 to 10-29). Each day's diff was derived from the history file and applied to the clip, and
the clip was compared with a fresh cut of the true state at the same moment
(`.scratch/diff-replay/replay.py`, results in `data/backfill/replay/results.jsonl`):

- **Every count matched, every day:** 72 region-days, all city × quest counts and denominators equal.
  That is about 1.11M open quests in Berlin, 569k in Hamburg and 324k in Bremen.
- **Objects:** Berlin (11.88M) and Bremen (4.26M) matched exactly on every day. Hamburg is the one
  edge case. On 2026-10-06 at 23:33 an untagged way, 1125039855 (94 nodes, likely a multipolygon
  member), was edited so that 17 of its nodes lay outside the clip. Those nodes were not edited
  themselves, so the diff did not carry them. From 10-07 on, the clip lacked those 17 nodes; `check-refs`
  reported "Nodes in ways missing: 17", the fresh cut had 0, and no count moved. The gap did not
  grow over the next 22 days. It was fixed at the next monthly cut.
- **So:** the plan holds. The one failure is rare, `check-refs` reports it, and it clears at the
  monthly re-cut. To close it sooner, a day with missing nodes can fetch exactly those nodes
  (`/api/0.6/nodes?nodes=...`, a handful), or the clip can keep a wider ring than it counts. Not built.
- **Costs measured:** the planet pass took **3.2 hours** (11,608 s; three bbox clips `--with-history -s
  complete_ways` of the 159 GB file), not the hour estimated. So cutting clips for requested places
  must be batched, preferably with the monthly rewrite. Clips: Berlin 146 MB, Hamburg 159 MB, Bremen
  49 MB. The derived diffs were only 0.3-0.7 MB a day, because they cover the 20 km ring only. A real
  daily planet diff is about 100 MB of the whole world. Applying it to a small clip is unmeasured;
  Ontario's 1.98 GB clip took 66 s with two diffs.

## Current clips in osm-extracts (2026-10-31)

**Real diffs, measured.** Daily planet diffs 5161 and 5162 (117 and 108 MB, the whole world)
applied to Berlin's replay clip of 2026-10-29 (146 MB): `apply-changes` (without `-H`) 31-105 s at
about 0.85 GB peak per diff (1.4 GB for both at once); the result 182 MB; the `-s smart` re-cut back
to the envelope 20-101 s at about 4 GB peak, giving a 138 MB clip with about 3,000 more nodes a day
(the smaller file is just compression; objects were counted). `check-refs`: no nodes in ways
missing. The spread in seconds is machine load. So a day costs a few minutes, and memory follows
the clip's size, not the diff's.

**The design**, which an agent builds in osm-extracts:
- **A clip is a store folder with a `clip.json`:** its polygon (GeoJSON, copied into the folder),
  the history file it was cut from, and the last diff applied. `osm_extracts.py clip <name>
  --polygon FILE` registers it. `fetch <name>` sees `clip.json` and brings the clip up to date. It
  never downloads a file of its own.
- **The output follows the store's conventions:** `<name>-YYYY-MM-DD.osm.pbf`, dated by its
  replication timestamp, with a meta (sha256, replication timestamp and sequence, `check-refs`
  result), `latest.json`, prune. Both replication headers are written into the file, because the
  engine refuses a file without them. sc-open-quests counts a clip like a Geofabrik extract
  (`"extract": "<name>"` in `config/regions.json`), with no new code path.
- **Diffs:** `fetch planet-diffs` downloads every daily diff after the history file into
  `planet/diffs/`, which the monthly rewrite already reads. A clip fetch takes any diff it lacks the
  same way and never deletes one. The rewrite deletes a diff only once every clip is past it.
- **The monthly re-cut** (`recut`): one planet pass for all clips, each cut to its polygon's
  bounding box padded 20 km. Each cut is kept as `<name>-history-YYMMDD.osh.pbf`, which also gives the
  clip's monthly points since 2017, so the 3.2 h pass is paid once a month, not twice. A slice at the
  history file's timestamp is then cut to the polygon with `-s smart`, and diffs are applied from
  there. A daily fetch never re-cuts. It applies diffs, re-downloading any that are gone (the planet
  site keeps them all).
- **The `"cadence": "weekly"` key becomes unused:** a planet-counted region is daily from its clip.
  Left in place until the first clip region runs.

**Built (osm-extracts 5c898c2, 2026-10-31):** `fetch planet-diffs`, `clip NAME --polygon`, `recut`,
`fetch NAME` for a clip, and a rule that the monthly rewrite keeps every diff a clip still needs
(the osm-extracts README). Tested on a Bremen clip from the replay's history cut: the recut equals the
replay's cut object for object (4,257,302 same, 0 different); the fetch applied the real diffs
5161-5162 in about 2 minutes, with no nodes in ways missing. Two changes from the plan:
- **History cuts use `-s complete_ways`.** osmium 1.18 does not support `-s simple` on history files.
- **A planet pass holds about 4 GB per clip** (8.1 GB for one, 12.1 GB for two). So a pass takes at
  most 7 clips in docker's 43 GB, and each further group is another 3-hour read of the planet.
  **So cities are not one clip each:** one clip's polygon holds every counted city's padded box, a
  MultiPolygon, and the regions of `config/regions.json` share it (`"extract"`), one region per time
  zone as now. One clip, one pass a month, however many cities.

## The first European cities: ranked by StreetComplete changesets (2026-10-31)

`tools/rank_sc_cities.py` over the changeset dump of 2026-10-26 (`osm-extracts fetch changesets`,
8.9 GB). In the 12 months to 2026-10-26 it found 3.76M StreetComplete changesets worldwide by 41,287
mappers (715k of them from the StreetComplete_ee fork, counted in), 2.93M (78%) in Europe by 29,316.
A changeset is counted where its bbox centre lies inside the city's land polygon (Overture 2026-10-21.0,
a county or region where the city is only a point; London is OSM r175342, Greater London is no Overture
division). The top 40 are exact for the 1,583 European cities and towns of 50,000 and over. The result
is in `data/rank/sc-cities-europe-261026.md` and `.csv`. The top 10: Berlin 36,804 (counted), London
30,709, Hamburg 24,788 (counted), München 20,189, Paris 19,599, Wien 19,510, Praha 17,455, Budapest
15,325, Warszawa 13,942, Kraków 13,565. Bremen is 51st. Caveats: Albacete (21st) is 4 mappers, most of
it the fork; Kyiv, Riga, Salzburg and Moscow have few mappers per changeset. Russia counts west of
60°E and Turkey Istanbul plus Thrace; whether Russia and Belarus belong on the list is the owner's call.
Scanning the dump takes 86 s: it is sorted by id, so a binary search finds the window's start and
only the last 10% is decompressed, in 22 processes.

**The owner's pick (2026-10-31): spread by country, all 32.** The busiest city of each of the
ranking's 28 countries (München for Germany, after Berlin and Hamburg), plus the four second cities
in the top 40: Toulouse, Salzburg, Kraków and Stockholm. Albacete is skipped: 4 mappers. Russia and
Belarus are eligible like anywhere else. They are on branch `europe` (worktree
`../sc-open-quests-europe`, b249b76), kept off main until they count and the site shows them right:
the 13:15 update downloads every region's extract, and `fetch europe` fails until the clip is cut.
- **Four regions, one per time zone, one clip:** `europe-west` (Europe/London: London, Lisboa,
  Dublin), `europe-central` (Europe/Berlin: 20 cities), `europe-east` (Europe/Helsinki: Helsinki,
  Rīga, Kyiv, Sofia, Vilnius, Athens), `europe-msk` (Europe/Moscow: Moscow, Minsk, Istanbul). Each
  group has kept one offset all along since 2017-01, the first month counted: the EU's summer-time
  rules apply alike in each of the first three; Moscow has been UTC+3 since 2014, Minsk since 2011 and
  Istanbul since 2016-09. So a monthly slice is dated the same day in every city of a region.
- **Relations:** the ranking's, except Moscow, whose ranking area is a `place=city` multipolygon. It
  is counted on its administrative boundary r102269 (2,563 km², with New Moscow). Istanbul's province
  boundary is 11,283 km² as drawn (the sea included). Moscow and Istanbul are the biggest areas
  counted yet; if one fails the engine, it is dropped and the rest go on. Oslo's and Athens'
  populations were the metro area's; they are the municipality's now.
- **Country codes** from CountriesTest: Antwerpen `BE-VLG, BE`, Barcelona `ES-CT, ES`, London
  `GB-ENG, GB`; the rest the country alone.
- **The clip:** `tools/clip_polygon.py europe` writes `config/europe.geojson` (the 32 boxes padded
  2 km, unioned: 32 parts, 6.8 square degrees) and each region's `.poly`. Registered as osm-extracts
  clip `europe`; its first `recut` started 2026-10-31 20:10 (log `logs/recut-europe.log`).

## The planet job, monthly, with clips (2026-10-31, on branch `europe`)

- **`run.py planet`** replaces `weekly`, which stays as its old name. The task is renamed too: from
  `kk-SCOpenQuests-weekly` to `kk-SCOpenQuests-planet`, with its log in `logs/planet.log`. The steps:
  `fetch planet-history`, then `osm-extracts recut`, then the months each clip region lacks, from the
  clip's history cut, then the weekly-cadence regions as before; merge, history, and "data planet <date>".
  The re-cut takes no pipeline lock, and a clip's daily fetch carries on beside it, so it need not keep
  out of the 13:15 window. The task's limit is 14 hours, because the job is two planet passes: the
  rewrite (2-2.5 h) and the re-cut (3-4 h).
- **The months of a clip's regions share one slice.** `backfill_history months` takes several
  `--region`. Regions reading one history file get one `time-filter` per date, counted once per region
  and then deleted. A region on a clip reads `<clip>/<clip>-history-<YYMMDD>.osh.pbf` and does not make
  a clip of its own.
- **Containers: one name per run** (osm-extracts 3413b63). The first Europe re-cut was killed after 8
  minutes by a `recut --from-history` test. Both used the fixed container name `osm-extracts-recut`, and
  the test's cleanup on failure removed the running one. Now each run's container is named
  `<role>-<pid>` and labelled with its role. A run removes only its own container. Leftovers of a role
  are removed only under the lock that role's runs hold, and a `--from-history` pass, which holds no
  planet lock, has a role of its own.

## Repin to StreetComplete v64.1 (2026-11-03)

- **What v64.1 changed for the counts.** No quest type added or removed (the registry imports only
  moved: AddAcceptsCards and AddAcceptsCash now live in `quests.payment`). Filters that move:
  - **AddAcceptsCards and AddAcceptsCash ask again with age.** Both share the new
    `PLACES_THAT_REQUIRE_PAYMENT_FILTER` (`osm/PaymentUtils.kt`), so AddAcceptsCards covers every place
    AddAcceptsCash did (fuel, cinemas, hotels, saunas, crafts...), not just food, drink and shops
    (branded places still do not ask for cards). Cards ask again when either payment tag is older than
    3 years; cash when `payment:cash = yes` is older than 2 years, or any `payment:cash` older than 4.
    Both now have `usesAge`, so the engine splits out their aging part by itself. AddAcceptsCards'
    rise is nearly all the wider place list: Ontario +3,385, of which 138 aged. AddAcceptsCash is only
    offered in FI, GB, IS, SE and NL, so it moves London, Amsterdam, Helsinki, Stockholm and Göteborg
    and nothing in Canada. `attraction` with a fee is gone from its list, `alpine_hut` joined it.
  - **`access !~ private|no`** on AddAerialwayBicycleAccess, AddAirCompressor, AddAirConditioning,
    AddAtmCashIn, AddAtmOperator, AddBicyclePump, AddBoatRental, AddClothingBinOperator (hand port),
    AddGritBinSeasonal, AddHairdresserCustomers and AddVendingMachineType: each loses its private
    places, a small drop.
  - **AddOpeningHours** (hand port): `healthcare`, `craft` and `office` join `updateFilterFragment`, so
    such a place is asked again once its `opening_hours` is over a year old, and a place without the
    tag is not asked. The whole rise is aged (Ontario +284).
  - **AddFirewood**: `fuel ~ ".*wood.*"` instead of `fuel = wood`, and shelters with a fireplace. Only
    offered in the Nordic countries, so it moves only Göteborg, Helsinki, København, Oslo and Stockholm.
  - **The note quest**: `#surveyneeded` in a comment makes a note a quest, as `#surveyme` does.
  - AddHousenumber, AddKerbHeight, AddTactilePavingKerb and AddMaxWeight changed only in their forms,
    answers or highlights: re-pinned, ports unchanged. AddBoardType likewise (highlights only).
- **What v64.1 changed for the engine.** SC's own fix for tag lengths in code points (8fe4c925) ships,
  so the `codepoints` patch is dropped and `util/ktx/CharSequence.kt` is vendored; `onepoint` stays (the
  same check is in v64.1). `MapDataXt.kt`'s filter cache takes an atomicfu lock, so the engine depends on
  `org.jetbrains.kotlinx:atomicfu:0.33.0`, SC's version. Kotlin, kotlinx-datetime, serialization,
  osmfeatures, the opening-hours parser, kaml and countryboundaries are unchanged, and so are the
  country metadata, presets and boundaries.
- **Checked.** The oracle gives identical sets for all 52 custom quests: Guelph 33,311 quests and
  Bremerhaven 20,413, both from the 2026-11-02 extracts, with the JVM of each side in the city's time
  zone. AddOpeningHours' new rule was exercised (Guelph's count rises by 4 against v64.0).
  AddClothingBinOperator's `access` line barely was (at most one private container in the two inputs),
  and the oracle does not cover the note quest (`#surveyneeded` has a unit test). 58 engine tests pass
  in the worktree. SnapshotReproductionTest and TorontoRegressionTest were skipped there: the first needs
  the untracked `data/cities/`, the second a pruned extract.
- **What the counts do**, measured in a scratch folder against the published v64.0 snapshot of the
  same extract, with the same notes: Ontario 7,876,687 to 7,880,332 (+0.05%; five quests move: AddAcceptsCards
  46,453 to 49,838, AddOpeningHours +284, AddAirCompressor -11, AddAirConditioning -11, AddGritBinSeasonal
  -2). London +0.10% (AddAcceptsCards 50,797 to 54,166, AddAcceptsCash 69,161 to 69,372 with 226 aged),
  Dublin +0.11%, Lisboa +0.42% (AddAcceptsCards 8,316 to 9,532). So a total barely breaks at the repin,
  and one quest's own line does, by 6 to 15%.
- **Where the break is.** The owner chose no recount: about 5 days of machine time for a move this small.
  Each region's newest extract was recounted with v64.1 at the merge and older snapshots stay on v64.0,
  so the series break there (Canada and Germany 2026-11-02, Europe 2026-11-03). AddAcceptsCards and
  AddAcceptsCash are off by default on the site, so the one visible step is not in a reader's default totals.
- **SnapshotReproductionTest cannot pass between the merge and the first v64.1 count.** It recounts a stored
  snapshot with that snapshot's own registry, but the hand ports are v64.1, so AddOpeningHours,
  AddClothingBinOperator and the note quest may differ from a v64.0 snapshot. Run `test` after
  `run.py count`, or read a failure limited to those quests as expected.

---
## Only quests the app had then (2026-11-03)

The owner asked whether history could be recounted with the SC version of each date, so the jumps show
where quests were added. Measured from a bare clone of SC (194 stable tags, git only, nothing built) and the
published `docs/data/history/`, then built as a switch on the totals chart; nothing was recounted.

- **"The version of the day" is three things, at very different prices.**
  - *Which quests existed:* every tag's registry parses, so each quest's first release is known. Free.
  - *Each quest's filter:* about 800 text changes over the 193 quests (a rough count: it hashes the string
    literals, so it misses constants defined elsewhere); 30 never changed. AddRoadSurface had no resurvey
    until v30. Filter quests could take an old string through the registry dump, but the strings
    interpolate Kotlin (`${ROADS_WITH_SURFACES...}`), so each era needs resolving, and every month a recount.
  - *Custom quest logic:* 52 hand ports pinned to one tag, and they hold 77-80% of Toronto's open quests,
    41-57% of Berlin's and London's. An old engine means a repin per release, half a day each at best,
    worse going back (quests are Java until v10, in 2019, and Android-only). Not worth doing.
- **The mask alone gives the jumps.** Each quest's published series, kept only from its first release:

  | Default-on quests | 2017-01 | 2018-01 | 2019-01 | 2021-01 | 2024-01 |
  |---|---|---|---|---|---|
  | Toronto | 6% | 40% | 70% | 93% | 100% |
  | Berlin | 8% | 35% | 61% | 77% | 98% |
  | London | 7% | 50% | 64% | 85% | 98% |

  (share of the today's-rules total). Largest steps: London AddRoadSurface +122,897 (2017-04), Berlin
  AddPathSurface +59,599 (2018-07), Toronto AddCycleway +30,008 (2017-12) and CheckShopExistence +21,671
  (2023-04).
- **What the mask is not.** A step's date is exact to the next monthly point; its height is today's rule on
  that date's data, not what the app showed. It shows arrivals only: of 19 names gone from
  the registry, nine live on in a successor, and ten have none (AddStreetParking, AddShoulder,
  AddProhibitedForPedestrians, AddSuspectedOneway...). Those are not in the counts, so early totals are low
  and no removal shows.
  `defaultDisabled` and country lists are today's too.
- **Built.** `tools/sc_first_release.py` writes `docs/data/quest-releases.json`; the site's "Only quests the
  app had then" (`then=1` in the link) applies it to the total and the pinned quests, and lists the five
  largest arrivals under the chart. The quest table, the tiles and the compare view stay as they are: the
  newest date is the same either way. Arrivals are not breaks: `breaks()` still reads the counted set.
- **Renames decide the steps.** A renamed quest would look like a new one, so `PREDECESSOR` carries twelve
  names from SC's changelog and git's rename detection. Without it AddCrossingMarkings and AddCrossingSignals
  arrive in 2024, though AddCrossingType asked since 2017. AddIsAmenityIndoor stays new (v55): it took over
  from AddIsDefibrillatorIndoor but asks for far more. Tag `v0.3` is a stray on an ordinary 2017-08 commit.
- **Dates.** A quest's date is its GitHub release, so a step sits on its release line; 22 tags have none
  (mostly before v3.1) and use the tag's own date, which agrees within a day wherever both exist.
- **Reading the chart.** Not every step is an arrival: Toronto's largest, 2019, is the AddHousenumber rise
  this file already records, and the 2026 drop the address import. They stay, unlisted.

## The city picker (2026-11-06)

A dropdown stopped working once the list was the world's: 147 cities in 37 groups that mixed provinces
with countries, Moscow only under "Москва", and no way to the 4,200 counted neighbourhoods or to anything
uncounted. The owner chose a search sheet over an inline type-ahead box.

- **The control.** A button naming the city and where it is; it opens a sheet, full screen on a phone.
  Before typing: recent cities, then counted cities by country, a country listing its cities under its
  provinces. While typing: counted cities, a name match above a place match, a place matching only from a
  word's start ("ber" is Berlin, not all of Alberta). `?city=` is unchanged.
- **Only counted cities are searched here.** The name layer is 1.08M rows, 17 MB gzipped as a flat list and
  8.8 MB for localities alone, so no typing box can hold it. The last row carries the query to the Places
  search, inside the country browsed or else the current city's, because that search has no towns without
  a country. The owner chose this over a site-wide index (about 29 MB more in `docs/`, split by first letters).
- **Names are English, the owner's word.** A city's `name` is its English one (Vienna, Moscow, Krakow); the
  local name stays as an `aka`, because `fold()` strips accents and does not transliterate, so "wien" still
  finds it. Ids stay, so `?city=wien` still works. Quebec's French names (Lévis, Trois-Rivières) are their
  English names too. The 18 are by hand: Overture's `en` has 21 of the 147, some raw ("Copenhagen
  Municipality"), Göteborg none. `add_city.py` takes `name:en` when the relation has one.
- **The Places tab shows `en` first too**, the local name only where there is no English one, and searches
  both. `places/index.json` gained `en` for countries and regions, sorted by it; it was patched from the
  shards, and `places.py build` writes the same.
- **Cyrillic with no English name is romanized**, the owner's choice: 184,099 of the 1.08M names (17%) were
  in another script with no `en`, about 147,000 of them Cyrillic, 116,517 in Russia. `places.py romanize`
  puts them in `en`, by BGN/PCGN letters per country (Г is G in Russia, H in Ukraine); spelled, not
  translated, so "сельское поселение" stays "selskoye poseleniye". The shards were patched with the same
  function. Other scripts stay local: Japanese readings and Arabic vowels cannot be derived from the name.
- **The first city is Guelph, the owner's choice**, for the flavour of it; it was Toronto. A link's city wins,
  then the last city seen on this browser (localStorage). A bare link to the site now shows Guelph.
- **Not done.** Compare still lists every city; the owner put its country filter off. `cities.json` costs
  2.3 KB a city and loads on every page, about 100 bytes of it for the picker: at some thousands of cities
  the picker wants its own slim file. No map picker: no map library, no city centres in the data.

## The coverage map (2026-11-06)

The owner asked to see what is covered and what is not, on a map. A fourth tab, Map (`?view=map`).

- **Covered means counted: the 147 city boundaries.** The extracts are not drawn: Ontario's reaches the
  whole province, and most of it is not counted, so drawing it would say the opposite. Neighbourhoods are
  not drawn either: they lie inside their cities and add no area.
- **`docs/data/coverage.json`, from `run.py history`,** so a new city appears with no extra step (DATA-FORMAT.md).
  547 KB, 151 KB gzipped, built in under a second; 186,000 boundary points become 29,000 at about 30 m. Only
  the map tab fetches it. It holds ids and shapes, not names or counts, or it would rewrite every day.
  Plain Python, not shapely as the tools use: the daily task runs `run.py` on the system Python, and a
  missing package must not stop a count for a picture. Neighbouring cities are simplified apart, so their
  shared edges can differ by up to the tolerance; it does not show until about zoom 14.
- **Leaflet 1.9.4 and OSM's standard tiles.** The site's second library, from jsdelivr with an SRI hash as
  uPlot was (both from `docs/vendor/` since 2026-11-10), loaded only when the tab opens, so the other pages pay nothing. Tiles are turned grey by a CSS
  filter so the indigo stands out (inverted in the dark theme). If traffic ever outgrows OSM's tile policy,
  the URL is one line.
- **Dots below zoom 9.** A city is a pixel or two at the zoom that holds both continents, so each has a dot at
  its bounding box's centre until its shape is big enough to see. Hover names a city; a click gives its
  name, where it is, its open quests and a link to its page.
- **The link holds the view:** `at=zoom/lat/lon` once the reader has moved the map; without it, every city fits.
- **Not done.** The map is not yet a city picker, though it now could be (the "Not done" of "The city picker"
  above). No per-quest heatmap: the z14 grids are still unpublished. Uncounted land has no click; the
  sentence over the map sends the reader to Places to ask for it.

## Hosting headroom: measured (2026-11-06)

How many more cities fit on GitHub, at 147 cities, the site on Pages from `main:/docs`. GitHub's stated
limits: a published site at most 1 GB, a source repo 1 GB recommended ("less than 5 GB is strongly
recommended", 10 GB on disk at most), 100 MiB a file, 2 GB a push, 3,000 entries a directory, 100 GB a
month soft, a deploy times out at 10 minutes.

- **Today:** `docs/` 127 MB, of which about 96 MB does not grow with cities (the name layer, the site).
  The repo is 102 MB as GitHub reports it.
- **A city costs the site** about 210 KB when added (history 142 KB, snapshot 55 KB, the rest small),
  then about 1 KB a date, 0.37 MB a year counted daily.
- **A city costs git** about 10 KB a day compressed, 3.7 MB a year: ten times the site's growth, because
  every run rewrites every city's history file. Measured by `git pack-objects --thin` per data commit,
  the two clean days at 147 cities: 1.33 and 1.52 MiB (others 0.6 to 2.75 MiB, so this is rough).
- **So the limit is city-years, and git history reaches it first:**

  | total cities | repo passes 1 GB | repo passes 5 GB | site hits 1 GB |
  |---|---|---|---|
  | 147 | 20 months | 9 years | 15+ years |
  | 500 | 6 months | 2.7 years | 4.4 years |
  | 1,000 | 3 months | 1.3 years | 1.9 years |
  | 2,000 | 6 weeks | 8 months | 8 months |
  | 4,300 | 3 weeks | 4 months | at once |

  One-off jumps are not in the table: a name layer rebuild, a recount for a new SC version.
- **The idea, for when the city count grows:** about 350 more cities are comfortable as things stand.
  Near 1,000, not "a few thousand" as "Planet coverage: what was measured" says, take the daily data out
  of git history. That leaves only the site cap. Thinning old daily points to monthly then stops the
  per-city growth and holds the site at about 4,000 cities. Past that the data leaves Pages (R2).
  `docs/data/history/` is flat and needs sharding before 3,000 cities.
- **Not a size problem:** the one failed deploy, 2026-11-04, sat in `updating_pages` to the 10-minute
  timeout; others take about 35 s and later ones went through with more data.
- **Page weight:** `cities.json` loads on every visit, 830 bytes a city gzipped: 830 KB at 1,000 cities,
  3.3 MB at 4,000.

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

## Canada and Germany onto a clip (2026-11-06)

The owner asked whether every region can read the planet history route, as Europe does; yes, after a week
side by side. Why: one pipeline, one timestamp (today Toronto and Berlin have different dates; on 11-06
Bremen's newest Geofabrik extract was 11-04), 4.7 GB less to download a day, and the world count needs the
same route. Against: Docker and one clip stop every region at once, no independent source any more, a new
city waits for a re-cut, the re-cut's memory grows, and series step slightly when the timestamp moves to 00:00Z.

- **The clip:** `config/canada-germany.geojson`, the 115 cities' boxes padded 2 km: 54 parts, 39 square
  degrees (18 of them Wood Buffalo). Registered in osm-extracts, first `recut canada-germany` from
  `history-261102` started 2026-11-06 20:21, log `logs/recut-canada-germany.log`. Europe's clip is untouched.
- **The week:** task `kk-SCOpenQuests-sidebyside`, 15:10 daily, 2026-11-07 to 11-14, runs
  `.scratch/side-by-side/compare.py` (log `logs/side-by-side.log`): fetches the clip, counts each region from
  it into that folder, appends per-city differences from the archived Geofabrik snapshot to `report.csv`.
  Nothing the site reads changes. Self-test on Bremen's own extract: difference 0.
- **Reading it:** the two files are hours apart and Geofabrik can be days behind, so the numbers will not be
  equal; a difference has to look like that gap's edits. Look at the days both timestamps are close.
- **After the week, if it holds:** `"extract": "canada-germany"` on the 12 regions; a check that Docker is up
  before the daily fetch, retrying; raise the re-cut's budget if the first run shows it tight. The Geofabrik
  code stays until a monthly cycle has passed.

**Daily, on local machines (asked 2026-11-06, late evening; hosting elsewhere).** Measured, nothing built.
- **Where the engine's time goes** (JFR, Czechia's 11.8M-node column, 12,680 samples): area quests 64%, the
  pass over the file 27% (reading the pbf 16%), map data 9%. By operation: evaluating element filters 38%,
  walking tag maps and collections 17%, hash lookups 8%. Most of it is a quest asking "is this you?" of an
  element that holds none of its keys. CheckExistence alone is 12%, AddLevelThing 7%, AddTactilePavingKerb 7%.
- **Memoizing by tag set does not work:** 1.1M distinct tag sets among 1.8M tagged elements (1.6 each; names and
  addresses make them unique), the top 1,000 covering 32%.
- **A fast reject should:** each filter expression works out the keys it cannot match without and returns
  false at once when the element has none of them, in the one place all filters pass through. Exact by
  construction. Expected 1.7 to 2.5 times on the whole pass, not yet tried.
- **Recounting only changed tiles pays in quiet places, not busy cities.** One day, nodes in z14 tiles touched:
  Ontario (16,600 objects) 1.8%, 8.5% with a one-tile ring (22% at z12); Hamburg (860 objects) 21%, 64% with a
  ring (98% at z12). Most of the planet should look more like Ontario, so this is a real later step: maybe a
  fifth of the count on a normal day, unmeasured for the world. It needs per-tile state, and age-based quests
  (52 of 193 mention a date) change with no edit at all, so a regular full pass stays.
- **Keep the ~80 region files current from the daily diff** instead of a new planet and cut each day: the
  clip method, exact over 72 region-days. Guessed at 1 to 3 hours against 8.
- **`run.py history` will not scale:** 72 s for 147 cities over 2,093 snapshots, a rebuild of everything each
  run; linear to a million places that is days. Publishing must append.
- **The owner's answers (2026-11-06, late evening):** willing to buy a machine for the count, sized after the
  speed-up is measured; R2 on a subdomain the owner has; the fast reject waits for the cell test.
- **Budget for a day:** diffs 2 h, count 7-9 h, publish 1 h: about 11 hours, if the fast reject delivers.
  Without it 19 hours, on paper only. A second machine divides the count, since files share nothing.

## A rewrite in a systems language: discussed, nothing built (2026-11-06)

The owner asked whether a rewrite into a memory-efficient systems language would give a speed-up. Answer: yes,
but not first. The profile above was read again (`.scratch/world-spike/prof.jfr`), and it changes one earlier
conclusion. No engine code changed and nothing was run.

- **What a rewrite would buy, estimated, not tested:** 3 to 5 times on CPU work, about 10 times less memory (about
  1 GB per million nodes today), no collection.
- **What it would cost:** the engine is trusted because it runs SC's own code, checked against SC by the oracle.
  A rewrite ports about 10,500 lines of vendored and ported Kotlin plus the opening-hours, preset and
  country-boundary libraries, and every repin (REPIN.md) becomes a manual port and a full recheck. Geometry maths
  would have to match the JVM closely enough to keep the same counts. Only the 140 filter quests move easily,
  being strings; the 52 custom quests are logic. No port of `ElementFilterExpression` exists (PRIOR-ART.md).
- **Kotlin/Native and GraalVM native-image** keep SC's code, but should help start-up and memory, not sustained
  speed. Expected, not measured.
- **The profile, weighted by CPU.** JFR samples at most 5 threads a tick, so stages with few threads count for
  too much. Weighting each 10 s window by the JVM's CPU load: filters, tag walks and hash lookups about 61%,
  reading the pbf 17%, the rest 21%. Area quests 59%, the pass over the file 30%, map data 11%. CheckExistence
  falls from 12% to 6%. Most of the 61% is quests checking elements that hold none of their keys, which is an
  algorithm problem: a Rust port would need the same fix.
- **Collection:** 9.2 s of pauses in 106 s here, more on a small heap (Ontario about 80 s longer at 16 GB than at
  40 GB). Boxing is a large part of the allocation: `Long` 19%, `Float` 8%, `Pair` 4%.
- **"CPU is the limit" (above, 2026-11-06) is not proven.** The 520 s was five columns on two engines; the 522 s
  was 15 cells on one. Different work, and no run put the five columns through one engine. Larger areas also
  cost more per node in that run: column 1, 31.4M nodes, 14 s per million; column 4, 11.8M, 6.2 s.
- **The engine averaged 7.3 of 24 threads in this run.** About 20 s of 106 s was the serial map build
  (`assemble`, `putNode`) and about 25 s was CheckExistence alone. The recut was running at the same time
  (machine 51-97% busy, JVM far less), so times are rough, but both stretches come from how the code is built.
  So 5.4 s per million nodes includes idle time, and HARDWARE.md's L-hours may be pessimistic for a machine
  that overlaps cells. With 12 physical cores, filling the idle threads will not give 3 times.
- **A repeated run.** `AreaPass.countIn` (`AreaPass.kt:256`) reruns every area quest with a result at LONG_AGO,
  also those with `usesAge = false`, 27 of the 40. They are 31% of CPU, so about 15% is repeated work, if a
  snapshot diff confirms they ignore the clock.
- **The 13 age area quests walk the map data four times** (now, 0.5, 2, 1900), 28% of CPU. The clock and
  multiplier overrides are thread-local, so the four runs can go in parallel without touching SC's code, which
  shortens the tail. One walk with four evaluations would save more, but patches SC's code.

**Proposed order, none of it built:**
1. Clean test on an idle machine: one column alone, then two at once, same files, with process CPU time. About 15
   minutes. It settles the concurrency question and HARDWARE.md's figures.
2. Skip the repeated run: about 1.18 times.
3. Run an age quest's four passes in parallel.
4. Fast reject: 1.7 to 2.5 times, the estimate above. It waited for the cell test, which passed.
5. A compact tag map behind `Map<String,String>` (built in `Pbf.kt` and `AreaPass.kt`, so SC's code is untouched),
   less boxing, a trial of ParallelGC. Not measured, and it overlaps with the fast reject.

Steps 2 and 4 alone would give about 2 to 3 times if they hold, which meets the 2 times a daily count needs in
8 hours on this machine.

**When native code makes sense.** A native data layer only if the planet still does not fit after these
steps; reading the pbf is 17% of CPU, so that alone gives about 1.2 times at most. A full rewrite only if the goal
changes: 16 GB workers, much larger cells, or a count of an hour or two. That is a separate project with its
own repin process.

## The cell test: passed (2026-11-06)

Do cells change the numbers? Tiles as the engine's "cities", each real city a part inside every tile it
touches, on the same extract, notes clip and quests file as each region's archived snapshot. No engine
patch: a city's membership is by the element's centre in both passes, so nothing crosses twice and city
numbers do not lose border elements. Harness and results in `.scratch/world-spike/cell-test/` (`REPORT.txt`).

| cell | cities | every quest | app-default total | over 0.1% | worst city (default) |
|---|---|---|---|---|---|
| z10 | all 147 | 39,695,236 to 39,695,249 | 11,367,386 to 11,367,397 | 0 | Orangeville +0.0124% |
| z12 | 115 (not Europe; out of time) | 20,436,529 to 20,436,513 | 5,788,935 to 5,788,920 | 0 | Saguenay -0.0405% |

- **The owner's bar of 0.1% holds at both sizes.** 114 of the 147 cities are equal in every quest at z10.
- **What moves:** AddHousenumber (44 quests in all at z10, 34 at z12; a building must lie wholly inside the map
  data), then AddMaxHeight and AddBarrierOnPath by 3 each.
- **The harness can see an edge:** Bremen as bare z16 tiles with no ring is -0.66%. The 1 km ring removes that.
- **The four filter quests that moved are the test's, explained 2026-11-07.** Each pair is one way whose centre
  lies exactly on the city boundary: Burlington's way 401631538 (0.0 m from relation 2407513), Athens' way
  901806046. The even-odd test gives a point on an edge either answer depending on the order of the
  segment's ends, and the test's stitched rings reverse some of them (`.scratch/cleanup/pip.py` replays
  `Polygon.contains` on both). For the world count it is real all the same: roads often are the boundary, so a
  centre on the edge between two places can land in both or neither. Rare, and worth one rule (half-open edges)
  in the place lookup.
- **Cost:** z10 passes 3,727 s against 2,525 s whole-city, most of the gap one cell: Paris's AddAddressStreet
  1,434 s against 582 s, on a machine shared with the re-cut at the end. It wants a fast twin first. z12 was 3 times
  slower (Alberta 4,721 mostly empty cells): empty tiles are expensive as cities, so cells should be sized by
  nodes, not by zoom.
- **Not tested:** a ring other than 1 km; a file cut to a region's edge (every run read the whole extract);
  land outside counted cities; country rules and time zone by position.

## The engine speed-up: built (2026-11-06)

The owner chose to build the steps of "A rewrite in a systems language" first and run the clean engine test
after. All of it is on main; `engine/README.md` has how each part works.

| area | old pass | new pass | old peak heap | new peak heap |
|---|---|---|---|---|
| Bremen, 2026-11-04 | 24.6 s | 15.0 s | 2.7 GB | 2.1 GB |
| Berlin, 2026-11-04 | 81.6 s | 47.2 s | 11.2 GB | 7.8 GB |
| Ontario, 2026-11-05 | 366.5 s | 204.3 s | 35.8 GB | 22.8 GB |

- **About 1.8 times on Ontario, below the 2 to 3 expected.** Not a clean number: the recut ran through every
  timing, and each old run came first, so it may also have read a cold file. The clean test decides.
- **A small heap no longer seems to cost much.** Ontario under `-Xmx16g` took 182 s with a 16.7 GB peak, faster
  than the 204 s at 40 GB, though it ran later and warm. It was 80 s slower before (2026-10-24).
- **What changed:** an area quest with no age test runs once; each run of an age quest is its own task; the fast
  reject (patch `fastreject`) with `TagMap`; `ArrayMapData`, which ends the serial map build (Berlin 12.4 s to
  4.6 s); the main pass skips all resurvey variants of a rejected element, and no longer boxes a Float for each.
- **Same counts:** Bremen, Berlin and Ontario, snapshot and grid, equal the old engine's apart from `runSeconds`
  and `engineCommit`. So does Bremen with `--area-unit tiles`, and Ontario under `-Xmx16g`. Berlin with
  `-Dopenquests.verifyFast=true` passed: all twins equal their ports, and every `usesAge = false` quest gives
  the same result at 1900. All other tests pass. SnapshotReproductionTest and TorontoRegressionTest were skipped.
- **The check earned its keep:** map data in id order moved Bremen's AddHousenumber by one. The quest gives a
  shared address node to the first building that reaches it, so it depends on the order a `HashMap<Long, ...>`
  iterates in, in the app too. `ArrayMapData` keeps that order. Any quest may depend on it, so it must stay.
- **Not done:** the age quests still walk the map data four times; one walk would save more, and patches more of SC's code.
- **What is left in a Berlin run:** about 85% of the machine while quests run, with a tail of about 5 s of 47
  (AddLevelThing). `LongIndex` lookups and the walk over all nodes lead the profile.

## The clean engine test (2026-11-07)

Czechia's five columns, 97.5M nodes, from 00:06 with the recut finished and the machine idle. Old engine is
d4b4fe25, new is 4c8784c3. CPU is the processes' own time; heap 26 GB, 20 GB with three engines. Script and
results in the session's scratchpad, not kept.

| engine | at once | wall | CPU | threads used | machine busy |
|---|---|---|---|---|---|
| old | 1 | 691 s | 6,287 s | 9.1 | 42% |
| old | 2 | 452 s | 6,321 s | 14.0 | 62% |
| new | 1 | 305 s, 318 s | 4,040 s, 4,095 s | 13 | 58% |
| new | 2 | 219 s | 4,074 s | 18.6 | 82% |
| new | 3 | 211 s | 4,356 s | 20.6 | 90% |
| new, ParallelGC | 1 | 307 s | 3,935 s | 12.8 | 57% |

All seven runs give the same snapshots.

- **The speed-up is 2.2 times like for like** (691 s to about 311 s), and 3.2 times with two engines against the
  old way of running one. CPU fell by a third; the rest is threads that used to sit idle.
- **"CPU is the limit, running more buys nothing" was wrong for the old engine.** A second engine took it from 691 s
  to 452 s. The 520 s against 522 s of 2026-11-06 compared different work.
- **Run two engines, not three.** The second gives 1.4 times, the third 4%: at 90% of 24 threads on 12 cores, CPU
  really is the limit.
- **2.25 s per million nodes**, against 5.4 measured on 15 cells: about 2.4 times, and a planet of 10-11 billion
  nodes in 6.1 to 6.9 hours on this machine. On paper a daily world count fits here: diffs 2 h, count 6.5 h, publish
  1 h, about 9.5 hours. These runs were 4 minutes; a laptop chip holding speed for 6 hours is still untested.
- **ParallelGC buys nothing:** the same wall time, 3% less CPU, 35 to 75% more peak heap. G1 stays.
- **Large areas gained most:** column 1 (31.4M nodes) fell from 278 s to 109 s, a
  bigger gain than column 4's 68 s to 33 s. Its peak heap is 19.5 GB, from 27.3 GB.

## A fast twin for AddAddressStreet (2026-11-07)

Paris took a quarter of a day's engine time on one quest. SC's AddAddressStreet asks, for every address,
whether any `associatedStreet` or `street` relation lists it, by scanning every member of every such relation;
France maps its streets that way. `openquests/fast/FastAddAddressStreet.kt` looks the members up in a set:
the same members, so the same result.

- **Checked:** `-Dopenquests.verifyFast=true` on Paris and Toulouse (europe-2026-11-06) ran SC's port next to the
  twin and found no difference; the twin's snapshot equals the published one in every field of all 183 quests.
- **Speed:** Paris's area pass 473 s to 22 s, Toulouse 79 s to 7 s, on the engine after the 2026-11-06 speed-up.
  The quest drops out of the slowest three in both. The planet estimate's worst known cell goes with it.

## Two engines at once: measured with equal work (2026-11-07)

The same five Czechia column files (`.scratch/world-spike/par.py`), each engine at 20 GB heap, on the engine
after the 2026-11-06 speed-up and the AddAddressStreet twin, the machine otherwise idle:

| engines at once | wall | each file |
|---|---|---|
| 1 | 342 s | 30-126 s |
| 2 | 248 s | 39-178 s, about 1.4 times slower each |

- **One engine does not fill the machine: two give 1.38 times the throughput.** The first measurement compared
  different work. So a world run counts two cells at once, about 20 GB of heap each.
- **The rate is now about 2.5 s per million nodes with two engines** (3.4 alone; 5.4 on 2026-11-06 before the
  speed-up). The planet's count is then about 7 hours, not 15-17, close to the 6.5 the speed-up session found.
  Not measured: three engines, which memory allows only at a smaller heap.

## Optimisation directions after the speed-up (2026-11-07)

Read off the 11-07 daily run (`logs/scheduler.log`, engine with the speed-up and the AddAddressStreet twin): 16
passes 1,100 s, against 2,468 s on 11-06. The log names each city's three slowest quests, so these sums are a floor:

| quest | summed over cities | worst |
|---|---|---|
| CheckExistence | 866 s | Istanbul 36 s |
| AddKerbHeight | 768 s | London 67 s |
| AddTactilePavingKerb | 725 s | London 70 s |
| AddHousenumber | 80 s | London 55 s |

Proposed, none built, in order:
1. **Kerbs once per map data.** AddKerbHeight and AddTactilePavingKerb both start from SC's
   `findAllKerbNodes()` (`sc/.../osm/kerb/KerbUtil.kt`), which reads no clock, and both are age quests run four
   times: eight identical searches per map data. Twins that share one result per map data give the same
   counts. Guess 1.2-1.4 times on the area pass; check with verifyFast on Berlin and London.
2. **Profile CheckExistence** (an age quest, four runs). If its feature lookup (`ScFeatures::getFeature`) is the
   cost, cache it per element across the four runs.
3. **One walk for the age quests, four evaluations** ("A rewrite in a systems language", not done there).
4. **For a world run:** two engines, largest file first, many cells in one JVM (about 6 s start-up a run), cells
   sized by nodes (z12 Alberta, 4,721 mostly empty cells, was 3 times slower).
5. **Owner's call, less work:** world places at resurvey x1 only, counted cities keep the 0.5 and 2 variants;
   and a daily world that recounts only cells a diff touched plus cells where a quest's check date ages out that
   day (computable ahead), which needs per-cell results kept.
6. **Not worth it now:** a rewrite, a native pbf reader (17% of CPU, at most 1.2 times), ParallelGC, a third engine.
   To measure, not code: whether this laptop holds speed through a 6-hour run.

## Kerbs once per map data: built (2026-11-07)

Direction 1 above. `openquests/fast/FastKerbs.kt`: twins of AddKerbHeight and AddTactilePavingKerb that take the
kerb nodes from one call of SC's own `findAllKerbNodes()` per map data (`PerMapData`) instead of a search in each
of their four runs. The quests' own filters are copied verbatim, and KerbUtil is called, not copied. In a city
AreaPass runs the search next to the quests that need none and the eight kerb runs after it, so no thread waits
for it; the log names it `(shared) kerb nodes` (London 13-16 s, Berlin 5-8 s, once).

- **Same counts.** London (europe-west 2026-11-07) and Berlin (2026-11-06), run as the 11-07 daily run did, give
  snapshots equal to the published ones in every field apart from run time and commit.
  `-Dopenquests.verifyFast=true` passed on Berlin (6 map data runs, 29 min) and on europe-west (Dublin, Lisboa,
  London: 18 runs, 1 h 55 min; London alone 6,710 s, because the ports' all-against-all code runs too).
  verifyFast compares only the asOf run with the port. The other three runs are the same by argument: the search
  reads no clock, and the filter applied to it is SC's own, run under each clock as before.
- **CPU: 9% less on europe-west, wall time unchanged.** Old engine (58506f45) and new alternating, idle machine,
  process CPU sampled every 0.5 s:

  | engine | CPU | London area pass | pass |
  |---|---|---|---|
  | old | 1,492 s, 1,496 s | 85.4 s, 83.3 s | 141.1 s, 138.2 s |
  | new | 1,358 s, 1,361 s | 79.7 s, 84.0 s | 135.9 s, 138.3 s |

  Berlin alone (two runs each): area pass 27.5 s both old runs, 26.7 and 27.7 s new.
- **The guess of 1.2-1.4 times on the area pass was wrong for one engine.** A city's area pass lasts as long as its
  longest single task, not its total work: London waits on AddHousenumber, one run of about 62 s (no age test, so
  one task), and the pass cannot end before about 70 s however much else is saved. The saving shows only where CPU is
  the limit: two engines at once in a world run (not measured).
- **What would shorten London's area pass:** AddHousenumber's one 62 s task, already a twin. It comes after every
  age quest's runs in the task order (age quests first); started first it would at least not start late, and only a
  faster AddHousenumber lowers the floor. CheckExistence is about 62 s over its four runs, about 16 s each: it costs
  CPU, but it does not set the floor.
- **Not shown:** whether running the search ahead of the kerb runs gains anything over letting seven threads wait
  for it; with AddHousenumber setting the floor, these runs cannot tell. `--area-unit tiles` was not run (there the
  first kerb run of a tile searches and the other seven reuse it).

## CheckExistence profiled: untagged nodes slipped past the fast reject (2026-11-07)

Direction 2 above. JFR (`settings=profile`) on europe-msk 2026-11-07, the day's slowest CheckExistence (Istanbul
36 s), run as the daily run does but without grid and parts. Script and recordings in `.scratch/prof-ce/`.

- **The feature lookup is not the cost.** `ScFeatures::getFeature` is about 4% of CheckExistence's samples. The lock
  around it was waited on for 14.6 s of thread time in the run, mostly by CheckShopExistence and AddPlaceName, not
  CheckExistence. Caching features per element would not help.
- **The cost was evaluating its filter on untagged nodes.** 74% of its samples sit in `AnyOf`/`AllOf.matches`, only
  5% in `TagMap.get`. AreaPass gives an untagged element `emptyMap()`, not a `TagMap`, and `KeyReject` let anything
  that is not a `TagMap` through. SC's own check for untagged elements did not stop them either: its table says
  `key ~ regex` may hold with no tags, so CheckExistence's whole tree (about 40 leaves) ran on every one of
  Istanbul's 7M untagged nodes, four times. The fix is one line in `KeyReject.mayMatch`: an element with no tags
  fails every clause. It is exact for the same reason as the rest of the fast reject.
- **Same counts.** europe-msk: snapshot and `quests.json` equal before and after, apart from `runSeconds`. Berlin
  2026-11-06 with grid and parts: snapshot and grid equal the published ones.
- **Speed**, one run each, back to back:

  | | before | after |
  |---|---|---|
  | CheckExistence, Istanbul | 36.5 s | 6.9 s |
  | CheckExistence, Moscow | 47.0 s | 15.8 s |
  | area pass Istanbul, Minsk, Moscow | 19.9, 5.6, 60.7 s | 18.4, 4.4, 51.0 s |
  | pass | 132.1 s | 117.0 s |
  | JVM CPU (JFR's CPU load, rough) | about 1,120 s | about 1,065 s |

  CheckExistence fell from 6.1% to 1.1% of samples. CPU fell by about that much, so few other quests were caught
  the same way. Unlike the kerbs, wall time moved too: Moscow's area pass was waiting on CheckExistence among others.
- **Next by the same profile: AddLevel and AddLevelThing, 22% of samples together** (Moscow 39-55 s each, which
  the log's slowest three hide in the sums above). Both start from `getMultiLevelMallGeometries()`, which asks for
  the geometry of every candidate (`LongIndex.get` is half their time), in every run. As with the kerbs: twins that
  share one result per map data, if the function reads no clock.

## The level quests: a grid per mall, and one ordered queue (2026-11-07)

Next by the CheckExistence profile. AddLevel and AddLevelThing have no age test, so each runs once; what made
them slow was SC's `getMultiLevelMallGeometries()` (`LevelUtils.kt`): for every mall it walks every element
with a level tag and looks up its geometry again. Moscow has thousands of stations (`public_transport =
station`) and many elements with a level tag. `openquests/fast/FastLevel.kt`:

- **The level points once per map data** (`LEVEL_POINTS`, logged `(shared) level points`, about 2 s in Moscow):
  each element with a level tag, its center and level, in a 0.002-degree grid. A mall looks only at the points
  its bounds contain, which are the only ones SC's loop gets past its own bounds check; the answer (two
  different levels inside) does not depend on the order. The shops and things inside the malls come from a
  grid the same way, and SC's `isPlace()`/`isThing()` is asked only of a node inside a mall, in SC's order.
  Mall filters copied verbatim; a test pins `LevelUtils.kt` too (`helperSha256`), since the twins copy it.
- **One ordered queue.** With the level twins among the runs that need a shared search, Istanbul's area pass
  got 4 s slower: those runs started only after every other run had finished. `parallelInOrder` starts a
  city's runs strictly in order from one queue: the shared searches, the runs that need none (age quests
  first, which `parallelMap`'s range split had not kept), then the runs that need a search, once all others
  have started.
- **Same counts.** europe-msk 2026-11-07: snapshot and `quests.json` equal in all seven runs. Berlin
  (2026-11-06) and europe-west (2026-11-07) with grid and parts equal the kerb session's outputs, which equal the
  published ones. `-Dopenquests.verifyFast=true` passed on Berlin (8 map data runs, 25 min) and europe-msk (22,
  87 min). 71 engine tests pass, SnapshotReproductionTest included.
- **Speed**, europe-msk, old engine (22a2f470) and new alternating; another project's job used about one core
  throughout:

  | engine | Moscow area pass | Istanbul area pass | pass |
  |---|---|---|---|
  | old | 56.3 s, 67.0 s | 23.1 s, 21.7 s | 129.3 s, 138.8 s |
  | level twins, old two phases | 29.2 s, 29.3 s | 25.6 s, 27.3 s | 105.1 s, 109.6 s |
  | level twins, one queue | 27.4 s, 23.8 s | 23.7 s, 23.8 s | 102.4 s, 97.6 s |

  Old AddLevelThing and AddLevel in Moscow: 51-54 s and 43-49 s. New, neither is among the city's slowest three
  (the third was 13 s). Moscow's slowest are now AddChargingStationSocket, CheckExistence and AddHousenumber,
  13-17 s each. **London is unchanged** (78.9 s against 78.6 s): AddHousenumber's one long run still sets its floor.
- **Not run:** `--area-unit tiles` (there the first level twin of a tile gathers the points and the other
  reuses them). `.scratch/prof-level/` (scripts, logs, outputs) can be deleted.
- **Next:** AddHousenumber, the floor in London; now that the queue keeps its order, starting it first is
  a cheap test. AddChargingStationSocket leads Istanbul and Moscow.

## AddHousenumber: one removeAll, not one per area (2026-11-08)

Next by the level session. London's area pass was 67.9 s in the 11-08 daily run, AddHousenumber alone 57.6 s of
it, one run (no age test). Starting it first in the queue would have saved about 5 s, so it was profiled first:
JFR on London alone, 11-08 clip (`.scratch/prof-hn/`).

- **77% of its samples were one line of step 5:** `buildings.removeAll(buildingsInArea)`, once for every area
  with an address that holds a candidate building. Each call scans every remaining candidate and hashes the
  whole `Way` (its node list, boxed, and its tags) to ask the set. The twin already skipped the call when the
  set was empty; London still has enough non-empty ones.
- **The change** (`FastAddHousenumber.kt`): gather the buildings of every area into one set by identity, and
  remove them once at the end. Exact: an area's `buildingsInArea` comes from `buildingPositions` and
  `buildingsByCenterPosition`, which step 5 never changes, and its elements are the very objects in
  `buildings`, so removing the union once leaves the same list in the same order.
- **The rest** (23%, about 13 s without JFR) is step 5's sort of every area by measured size and the
  address-node consume that follows, which depends on that order. Left alone: AddHousenumber is no longer among
  London's slowest three.
- **Speed**, europe-west 11-08, the daily run (old engine) against the new one with the same flags (grid and
  parts), and once without them:

  | | old (daily run) | new | new, no grid |
  |---|---|---|---|
  | London area pass | 67.9 s | 32.8 s | 31.1 s |
  | AddHousenumber, London | 57.6 s | not among the slowest three (third: 24.6 s) | same (25.2 s) |
  | pass | 124.4 s | 96.4 s | 91.4 s |

  London's slowest three now: AddKerbHeight 27.9 s, AddTactilePavingKerb 24.7 s, AddChargingStationSocket 24.6 s,
  each a sum of four runs; the shared kerb search, 16.4 s, is logged apart.
- **Same counts.** The new snapshot equals the published 11-08 one apart from `engineCommit`; its grid equals
  `data/grid/europe-west/2026-11-08.json.gz` byte for byte.
- **AddChargingStationSocket, read off the same London profile: nothing to fix in it.** It is an age quest
  (four runs), and each run filters every node of the map data twice (charge points, then its filter): 81% of
  its samples are `ElementFilterExpression.matches`, 47% the fast reject itself. It is a scan, not a pathology,
  and it is not a city's floor: in Moscow and London the kerb twins lead, and the log's figures are sums of
  four runs that go on different threads.
- **Next, proposed, not built:** candidates by key once per map data. Most area quests' filters require a key
  (`amenity`, `building`, `highway`), and every run of every quest scans the whole map data to find the few
  elements that hold it. An index from key to elements per map data, built once, would let `mapData.filter`
  walk only the elements holding a clause's required key, in map data order (SC's results depend on order),
  for every quest at once. Worth a profile of the whole area pass's CPU first: London's area pass is 25 s of
  quests on 24 threads now, so it may be CPU-bound rather than held by one run.
- `.scratch/prof-hn/` (scripts, recording, outputs) can be deleted.
- **verifyFast on London passed (2026-11-08, late):** the fast twins, the new AddHousenumber included, matched
  their ports on all 8 map data runs. It took 9 h of wall time: SC's AddMaxHeight port (all against all) logged
  32,921 s on one thread but used only about 6,400 s of CPU, close to the 6,710 s the last London verify took in
  all. The rest is the laptop sleeping or throttling the JVM while the owner was away, not the port.

## The whole area pass profiled: a tail of three runs, and 30% spent rejecting (2026-11-08)

Next by the AddHousenumber session. London alone, europe-west 11-08, the engine after AddHousenumber's fix, idle
machine. A new opt-in trace, `-Dopenquests.taskTrace=<file>` (engine/README.md), writes each area task's start,
end, thread and CPU time. JFR alone cannot say how many threads are busy, because it samples only a few threads
per tick. Scripts and outputs are in `.scratch/prof-area/` (`run.py`, `region.py`, `cpu.py`); the trace reader is kept as
`tools/task_trace.py`. Same counts: London's
snapshot with the trace equals the published one.

- **London's run phase is 26.7 s; perfectly spread, its CPU would take about 15-18 s.** It is 252 s of thread CPU:
  10.5 s over 24 hardware threads, 21 s over 12 cores. The tail runs earned their CPU alone on a core, at full
  speed, and the same work costs more thread time while both threads of a core are busy, so the floor lies
  between the two. The tail costs about 8-11 s, not 16. The tally after the runs is 1.8 s, and the whole area
  pass is 35.7 s with the map data. The first 14 s are CPU-bound with all 24 threads busy. Then a tail: 3
  single runs go on alone for about 10 s.

  | run | starts | wall | CPU |
  |---|---|---|---|
  | AddHousenumber (one run) | 6.0 s | 20.7 s | 17.2 s |
  | AddMaxHeight (one run) | 6.5 s | 17.2 s | 14.1 s |
  | AddLevelThing (one run) | 11.8 s | 14.4 s | 12.7 s |
  | (shared) kerb nodes | 0.0 s | 17.5 s | 13.1 s |

  Busy threads by second: 24 for 0-11 s, then 23 22 18 15 14 9, then 3 3 3 3 3 3 2 2 1.
- **The 8 kerb runs hold 8 of the 24 threads for about 8 s with no CPU** (0.1 s each), waiting for the shared
  kerb search. They start at 9.3 s, once every other run has started, but the search started at 0 and runs
  17.5 s. That is about 64 thread-seconds idle in the CPU-bound part.
- **Where the CPU goes** (JFR, 2,097 samples in the area pass): 60% inside `ElementFilterExpression.matches`,
  half of it (30% of all) in `KeyReject.mayMatch`, the fast reject saying no to elements that lack a required key.
  13% is id lookups (`LongIndex`, `HashMap`) and under 3% is geometry. GC paused for 7.3 s over the whole run.
  By quest: FastAddMaxHeight 16.6%, FastAddHousenumber 7.4%, FastAddIsAmenityIndoor 5.7%, and the rest under 5%
  each.
- **FastAddMaxHeight spends 42% in `HashSet<Long>.contains`.** The twin kept SC's order:
  `it.id in roadsNodeIds && nodeFilter.matches(it)` hashes a boxed id for each of London's 14.7M nodes, and the
  railway crossing filter does the same with two sets, before the cheap tag filter would reject nearly all of
  them. Putting the filter first is exact, since both are pure tests joined by `&&`.
- **Under JFR at stack depth 256 the run phase was 45 s, not 26.7.** Use JFR's shares, not its times.

Proposed, none built, in order of how little each costs:
1. **FastAddMaxHeight: the filter before the set lookup.** Two lines; it shortens one of the 3 tail runs by
   perhaps a third. Check: same snapshots, and verifyFast, since the twin is what changes.
2. **Start the longest runs first.** Order the queue by the cost each run had last time, or by a fixed list:
   AddHousenumber, AddMaxHeight, AddLevelThing, then the rest. If the tail runs started at 0, London's run phase
   would end near the longest run's own length under load, about 21 s instead of 26.7, near the 15-18 s floor
   once (1) shortens AddMaxHeight. This is the cheap test the level
   session named for AddHousenumber. Start the kerb runs only once the search is done, not once every other run
   has started, so they never hold a thread while they wait.
3. **Candidates by key once per map data**, as proposed in the AddHousenumber section. It targets the 30% spent
   in the fast reject, plus some of the filter tree. For one city it shortens only the CPU-bound first half,
   because the tail stays. For a world run, where two engines keep the CPU full, it is the largest saving left:
   perhaps 1.3-1.5 times on the area pass. Largest change of the three: it touches `mapData.filter` for every
   quest, and must keep map data order.
4. **Not worth it now:** GC (7.3 s of pauses across a 95 s run, much of it outside the area pass) and geometry
   (under 3%).

The area pass is 36 of London's 88 s pass (clean run). The rest is reading the file and the map data (nodes 11 s,
ways 16 s, the area's ways and nodes 18 s, for all of europe-west's 128M nodes, though only London was counted), which none of the above touches.

## AddMaxHeight and the queue: built (2026-11-08, late)

The first two proposals above, at the owner's word. Same counts: europe-west and europe-msk (all six cities)
give snapshots equal to the published 11-08 ones. europe-west with the daily run's grid and parts gives a
snapshot equal as text (parts included) and a grid equal byte for byte. `-Dopenquests.verifyFast=true` on
Dublin and Lisboa (16 map data runs, 144 s) found every twin equal to its port, the new AddMaxHeight
included. 71 engine tests pass. All timings are clean runs with the task trace on, the machine otherwise idle.

- **AddMaxHeight** (`FastAddMaxHeight.kt`): the tag filter before the node id sets, as proposed. That alone
  took London's run from 14.1 to 11.8 s of CPU, not the 42% the profile suggested. A second JFR run, by source
  line, put about half of what was left in the bridge loop: for every road and bridge pair it built the
  bridge's node set again (`toSet()`, boxed), looked up its geometry and parsed its layer. Each bridge now
  carries its geometry, layer and node set, worked out once. The bounds test that SC's `intersects` starts with
  also moved ahead of the node set test. All of these are pure tests joined by `&&`, so the result is the same.
  London's run: 17.2 s wall and 14.1 s CPU before, 12.7 s and 10.5 s after.
- **The queue** (`AreaPass.countCity`, `parallelWhenReady` replacing `parallelInOrder`). The shared searches
  start first, then the runs in `LONG_RUNS` (AddHousenumber, AddLevelThing, AddMaxHeight), then the age quests'
  runs, then the rest. A free thread takes the first run that is *ready*: one that needs a shared search is
  ready once that search is done. The kerb runs no longer hold threads idle (0.1 s each instead of 8 s
  waiting), and AddLevelThing starts once the level points are in (0.5-2.6 s) instead of after every other run
  (8-12 s). Order cannot change counts: each run is independent.
- **Run phase**, before tonight, then after each step:

  | city | before | AddMaxHeight | + queue |
  |---|---|---|---|
  | London | 26.7 s | 24.4 s | 24.0 s |
  | Moscow | 20.7 s | | 18.1 s |
  | Istanbul | 10.9 s | | 10.8 s |
  | Minsk | 4.6 s | | 3.7 s |

  London's last two columns are not like for like: London alone, then London after Dublin and Lisboa in one
  JVM, so its 0.4 s is noise. Moscow's is the like-for-like gain from the queue.
  Area pass with map data: London 35.7 s to 31.1, Moscow 26.6 to 23.1, Istanbul 15.3 to 14.4, Minsk 6.0 to 4.9;
  the europe-msk pass 93.8 s to 87.7.
- **What is left: the long runs themselves.** Starting them at 0 means they run while all 24 threads are busy,
  at about half a core each. London's AddHousenumber now takes 23.4 s of wall time for 18.6 s of CPU, against
  20.7 s for 17.2 s when it started at 6 s. The floor is the slowest of AddHousenumber (London 18.6 s CPU),
  AddLevelThing (14.0 s) and AddMaxHeight (11.6 s), running alongside everything else. A shorter pass needs one
  of these faster, or split across threads, not reordered. A world run, where two engines keep the CPU full,
  gains nothing from the queue; candidates by key (proposal 3) is still the saving for that.
- `LONG_RUNS` is a fixed list from these traces. If another quest turns out long in some city, the trace
  (`-Dopenquests.taskTrace`) shows it as a run still going alone at the end.

## Candidates by key: built (2026-11-08, late)

Proposal 3 of "The whole area pass profiled", at the owner's word. 30% of the area pass's CPU was the fast
reject saying no, and much of the filter tree's share was the same walk: every scan of the map data asked every
element "is this you?". Now a scan walks only the elements that hold a key its filter cannot match without.

- **How** (`engine/src/main/kotlin/openquests/KeyIndex.kt`; engine/README.md, under `fastreject`). Each map
  data keeps a `KeyIndex` per list (nodes, ways, relations): tag key to the ascending positions of the elements
  holding it, built the first time a quest asks. `mapData.candidates(list, expr)` takes `expr`'s clauses (the
  key sets `KeyReject` already works out: an element `expr` matches holds a key of every clause), picks the
  clause with the fewest elements, and returns those elements in `list`'s order. The caller's predicate still
  runs on each one, so `candidates(list, f).filter { f.matches(it) && ... }` equals `list.filter { ... }`: the
  elements left out could not match, and the order and any side effects in the predicate are unchanged. An
  expression with no clause, or any other map data, gives the whole list.
- **Where:** `port_area_quests.py` rewrites the ports' scans by one regex, `CANDIDATES`, the only change it
  makes to their kept code, for 40 regenerated ports. The rewrite catches `mapData.nodes`, `ways` or `relations`
  followed by `.filter { f.matches(it)` (also after `.asSequence()`, or after an `it.id in set &&`). Rerunning the
  script before the change reproduced every port exactly, so the diff is the rewrite alone. The fast twins call it
  directly, including a whole-map-data `candidates(expr)` (nodes, then ways, then relations, the map data's own
  iteration order) for AddHousenumber's buildings, AddIsAmenityIndoor, AddAddressStreet and FastLevel's
  `mapData.filter(expr)`. Not touched: the hand-ported custom quests whose `getApplicableElements` is
  `mapData.filter { isApplicableTo(it) }`, and SC's own `MapData.filter(expr)` (an SC patch would be needed).
- **Same counts.** europe-west and europe-msk (six cities) equal the published 11-08 snapshots. europe-west with
  grid and parts: snapshot equal as text, grid equal byte for byte. Bremen and Bremerhaven (Geofabrik, 11-07)
  equal their published snapshot. verifyFast on Dublin and Lisboa passed (16 runs), though both sides now use
  `candidates`, so the snapshots from the older engine are the check that matters here. A new `KeyIndexTest`
  runs every quest filter of v64.1 (and a few edge cases) over random nodes, ways and relations, a third untagged,
  and checks that `candidates(list, f).filter(f::matches)` equals `list.filter(f::matches)`, order included, per
  list and for the whole map data. 73 engine tests pass. Peak heap is unchanged within noise (europe-west 30.9 to
  28.1 GB, europe-msk 27.4 to 29.3). Not run: `--area-unit tiles`, where each tile builds its own index.
- **Run CPU down by a quarter to a third**, run phase down less (the long runs still set it):

  | city | run CPU before | after | run phase before | after |
  |---|---|---|---|---|
  | London | 241 s | 162 s | 24.0 s | 19.6 s |
  | Moscow | 161 s | 121 s | 18.1 s | 17.2 s |
  | Istanbul | 91 s | 67 s | 10.8 s | 9.7 s |
  | Minsk | 40 s | 27 s | 3.7 s | 3.3 s |

  Area pass with map data: London 31.1 s to 26.2, Moscow 23.1 to 22.2; the europe-west pass 94.5 s to 79.7, the
  europe-msk pass 87.7 to 86.3. One run each, so a second or two either way is noise.
- **For a world run**, where two engines keep the CPU full, the run CPU is what counts: about 1.3-1.5 times on
  the area pass, as proposed. Not measured with two engines.
- **Left:** the hand-ported custom quests' per-element scans (CheckShopExistence, AddPlaceName, AddOpeningHours
  and others: `mapData.filter { isApplicableTo(it) }`), which would need their first filter named; and the long
  runs' own work. A JFR run of the new engine would show what leads now.

## Germany as cells: the world prototype (2026-11-09, night)

DESIGN "The whole world", items 1-2, on one country. `tools/world_cells.py`, output in `.scratch/world-de/`
(gitignored), Geofabrik `germany-2026-11-07` (4.6 GB, 442.6M nodes). Nothing published, no pipeline change.

- **Steps and costs:** `nodegrid` (new engine command, nodes per 0.05° square) 36 s; Overture places 109 s;
  cells cut k-d by node count into 4 files of about 110M nodes and 34 cells of 7-15M; one `osmium extract`
  (smart, 2 km padding, the input's replication header copied: the engine refuses a file without it) 475 s;
  notes clip 362 s; count with two engines at once (30 GB heap each) **1,007 s**, about 2.3 s per million
  nodes, each file 475-532 s, peak heap 34-38 GB. The places: 40,520 Overture divisions of Germany with an
  area and an OSM relation or way as their own source (add_parts.py's rule), land area, 495 MB of GeoJSON,
  each a part of every cell its bbox meets (9-13k part entries a file).
- **The check passes:** the five counted German cities, their own OSM polygons as parts, against a whole-city
  count of the same file, notes clip and quests: Berlin, Bremen and München differ by one AddHousenumber each
  (at most 0.002%), Hamburg and Bremerhaven not at all. As Overture places they are within 0.015% (Hamburg's
  land polygon). Germany: 20.09M open quests in the app's defaults, 75.7M of every kind; the 16 states sum
  to it within 0.007% (their borders overlap). 39,446 places have a number; the rest are squares and plazas
  with nothing open.
- **Found: the summit quests.** AddSummitRegister and AddSummitCross asked every peak of every hiking path,
  all against all: 1,114 s summed in one Alpine cell, f1 1,164 s of the first run's 1,433. Now a fast twin
  (`FastSummit.kt`, segments gridded once per map data, SC's own distanceToArc asked of nearby ones): the
  same snapshots in all four files, SummitTest against SC's loop, 74 engine tests. The slowest cell's area
  pass is now 62 s.
- **Not exercised:** country rules and time zone by position (one country); a file cut at Germany's border
  has no ring beyond it (as the baseline); stray nodes in the extract stretch the box to lon -20..28, so edge
  cells are large and the notes clip holds 2.09M notes (955 MB): a world run clips notes per file. Publishing
  and R2 untouched; `.scratch/world-de/` (about 7 GB with the cut) can be deleted.

## Country rules and time zone by position: built, checked on Europe (2026-11-09)

DESIGN "The whole world", item 3. The Germany prototype had one country and one zone; a world run's cell
crosses both.

- **Country gating by position** (engine 92cc9ab0, `Gating.kt`). A city without `countryCodes` is gated as
  the app gates: OsmQuestController skips a quest type whose countries do not meet the downloaded bbox, then
  `mayCreateQuest` asks `isInAny(position, enabledInCountries)` of each quest. The engine asks the city's bbox
  first (a region holding the whole box, or none touching it, settles the quest for the city) and the
  quest's position only where the box cannot decide, in the main pass, the area pass and for notes. SC's
  `getContainingIds` is conservative in a raster cell that a border crosses, so a box near a border is asked
  per position even when it lies in one country: a lookup, not a count. Typed `countryCodes` mean what they
  meant; the 147 configured cities keep them.
- **A time zone per city** (the `zone` patch on SC's ktx date helpers, `EngineZone`). SC reads "the system
  default timezone" for `today` and for the start of a day; the patch takes a thread's override first, and
  the engine sets each city's zone in both passes. A region run (JVM in its zone) overrides nothing.
  Cities that overlap must share a zone; `--area-unit tiles` needs one. The snapshot's date stays asOf in the
  JVM's zone (UTC for a world run).
- **Cells** (`tools/world_cells.py`): no `countryCodes`; the zone that holds most of the cell's nodes
  (timezonefinder at each 0.05° square of the node grid); a notes clip per file in one pass over the dump;
  the baseline one run per zone, as the daily regions; `plan --cities` for a check without Overture places.
- **The production runs are unchanged:** the four baselines are the daily Europe regions' configuration
  (typed codes, the JVM in the region's zone) on the same extract (same sha256) as the archived 11-08
  snapshots, and all 32 cities equal them in every quest entry and denominator.
- **Tests:** GatingTest (a cell across the Dutch-German border at Enschede and Gronau: AddHousenumber counts
  the German house only, AddAcceptsCash the Dutch bakery only, as two small cells do; typed codes still gate
  the whole city) and ZoneTest (a filter under an override equals a JVM started in that zone, for Auckland,
  Los Angeles and Moscow; two cities in two zones in one run equal each counted alone in its zone). 79 engine
  tests, SnapshotReproductionTest unchanged. ZoneTest sets
  the JVM's default zone while it runs, so the suite must stay sequential in one JVM (it is).

**The check: the Europe clip as cells.** `europe-2026-11-08` (127.8M nodes, the 32 European cities' 20 km
rings, asOf 2026-11-08T00:00Z), `.scratch/world-eu/` (gitignored, about 6 GB with the cut and the clips;
can be deleted). 16 cells of 6.8-9.2M nodes in 2 files, 11 zone names. Cut 2 min, notes clips 5 min,
cells 228 and 231 s (one engine at a time: two at 30 GB each failed on Windows' page file this time, with
49 GB of commit free; the Germany run had managed it), baselines 180 + 71 + 88 + 87 s.

- **Every city within 0.004% of its whole-city count** (app default quests), 18 of 32 exact: far inside the
  owner's 0.1%. In all quests together, 11 cities differ by 1 to 4.
- **What differs:** 1-2 elements of a quest, most of them area quests (AddHousenumber in Barcelona, Budapest,
  Dublin, London, München; AddMaxHeight, AddCrossing, AddBarrierOnRoad, AddBarrierOnPath, AddPathSurface): a
  cell's edge, as Germany's check supposed, or the part's copy of the city polygon, as Athens shows below;
  not dumped one by one. **Bratislava +4 AddCycleway is the gate at work:** the quest is on in Austria and
  Hungary, not Slovakia, and four cycleways inside Bratislava's polygon (Petržalka, Jarovce, Devínska Nová Ves)
  lie where SC's boundary data says Austria; the app shows them there, the typed `["SK"]` city does not count
  them. Athens +1 on three road quests is the check's own polygon copy: dumped, both runs match the same
  13,374 elements inside the city's polygon, and the part's GeoJSON copy of it holds one road more.
- **The zone shows nothing here.** 14% of the clip's nodes lie in a zone whose UTC offset differs from their
  cell's (Toulouse in a London-zone cell, Athens and Sofia in an Istanbul one), yet no difference traces to
  it: at 00:00Z every European zone has the same date, so the cell's zone only moves the hour at which a day
  starts, and with it the few elements last edited in that hour N years ago. A run at another hour, or
  zones a day apart (the Pacific), would show more; cutting a cell along zone lines (the minority zone's
  squares as their own "city") is the remedy if it ever matters.

Next, the owner's: a larger country or a continent stage. Per-file notes clips are large where a file's box
is (f0: 2.3M notes, 1 GB, western Europe's box); clipping to the cells' squares rather than the box would cut that.

## Counting from the day's diff: one day measured (2026-11-09, late evening)

The owner asked whether the daily diffs, far narrower than a recount, can drive the count: look only at what
each changeset touched. This is the finer form of "recounting only changed tiles" above (2026-11-06): changed
elements, not z14 tiles with a ring. Nothing built. Scripts and output in `.scratch/diff-flips/` (gitignored,
about 900 MB of match dumps; can be deleted).

**The measurement.** europe-west (London, Dublin, Lisboa) counted on `europe-2026-11-08` and `-11-09` with
every match dumped (`--dump-matches`, all 193 quests, the same quests file and notes clip; 106 s and 97 s).
A flip is a quest on an element that is in one dump and not the other. Each flip was held against planet day
diff 5171 (3.9M nodes, 705k ways, 39k relations).

| what explains the flip | opened | closed | share |
|---|---|---|---|
| the element itself is in the diff | 699 | 256 | 73.5% |
| ageing: opened as agedOnly, element untouched | 339 | 0 | 26.1% |
| a note at the element's exact position: 5320352 closed that day (three quests of one shop), 5622513 opened (CheckShopType, way 218331258) | 3 | 1 | 0.3% |
| a changed element within 20 m, not the element itself (AddIsAmenityIndoor, node 302134936; which neighbour was not looked up) | 0 | 1 | 0.1% |
| not explained | 0 | 0 | 0% |

- **4,623,562 matches became 4,624,345; 1,299 flipped, on 742 elements.** 0.03% of the state moved in a day,
  and the full count reads all 128M nodes to find it.
- **Neighbours barely matter, on this day.** The custom quests hold 36% of the matches and 721 of the 1,299
  flips (AddBuildingLevels 212, AddHousenumber 175, AddRoofShape 145), yet all but one were on an element in
  the diff. No flipped way had only a changed node, and no relation flipped.
- **Ageing is a quarter of the flips** and needs no diff: CheckShopExistence alone 322.

**So: yes, as the daily step between full counts.** What it takes:
1. **State:** yesterday's matches per element. The dump is 95 bytes a match as text; about 1.5 billion open
   quests in the world is 15 to 30 GB packed.
2. **Edits:** re-evaluate every element in the diff and what lies within a small radius of its old and new
   place (the one neighbour flip was within 20 m; the radius is not settled by one day). A moved node does not
   re-version its ways, so parents come from the file, not the diff. An engine mode "these elements only, with
   the map data around them" does not exist; SC's `isApplicableTo` returns null for most custom quests.
3. **Ageing:** a main-pass re-evaluation of the 52 date quests, or a due date stored per element.
4. **Notes:** the two dumps compared by exact position (`Notes.hides`).
5. **A full count stays the oracle**, weekly, to reset drift and to catch what this misses; a repin or a
   changed polygon is a full count too.

**The floor.** Since the engine speed-ups, reading is the larger half: of the 85 s pass on 11-09, the scans
of the file took 48 s (member scan, nodes, ways, relations, and the area pass's three) and the cities' area
runs 37 s. A daily step that still scans every region file gains under 2 times; the gain the 0.03% promises
needs a store that finds an element and its surroundings without the scan.

**A byproduct, and a listed non-goal:** every "self" flip names an element version, so a changeset: quests
solved per day, by StreetComplete or by another editor. `changeset` is stripped today (line 54).

**Not shown by one day:** a day with a building or address import; a rural region; a moved node flipping its
way; an element whose position moved across a city or part boundary (still open, counted elsewhere: not a
flip here); denominators; the note quest itself, which the dump leaves out. The diff's ids were taken planet-wide, positions only inside the clip.

**Next, if wanted:** the same comparison over the stored week of clips and all four Europe regions (about 2
minutes a region-day), to settle the radius and the unexplained share. Then a prototype of step 2 on one
region, checked flip for flip against the full count.

## The stream: probed, and the plan (2026-11-09, near midnight)

The owner wants to pursue counting from diffs, perhaps as a stream that takes changesets one at a time. The
aim, in the owner's words: an efficient way to reach daily world processing; this is one strategic idea,
there can be others. It lifts two listed non-goals (real-time updates, solved quests from changesets) as far
as a test goes. Nothing built.

**Probed at 04:31Z on 2026-11-10** (`curl`, a generic client name):
- **Minute diffs are live, about a minute behind** (sequence 7366220, 04:30:50Z). One file: 45 KB, 761 element
  versions of 27 changesets. So the unit to apply is a minute file; a changeset is what a flip is credited
  to, and it can span files. Not yet checked: object order inside a file.
- **The changeset feed is live too** (sequence 7261488): 19 changesets in one minute, 4 by StreetComplete,
  carrying `StreetComplete:quest_type` (AddParkingCharge; SurfaceOverlay, which is an overlay, not a quest).
- **No public before/after source to lean on.** Overpass's augmented diffs answered "at capacity" (502), and
  OSMCha's real-changesets bucket gave 404 for two changesets (one just made, one about a day old). The state
  before an edit is ours to hold.

**Tiers, from the day already measured** (europe-west, the 11-09 dump):

| tier | quests | matches | flips that day |
|---|---|---|---|
| 1: decided from the element alone (filters, 12 hand-ported custom quests) | 153 | 3,236,635 (70%) | 941 (72%) |
| 2: the 40 area quests, which read their surroundings | 40 | 1,387,710 (30%) | 358 (28%; AddHousenumber 175, AddRoofShape 145) |

**What this suggests for the world.** A planet day is 3.9M nodes, 705k ways and 39k relations against 10-11
billion nodes scanned: about two thousand times less to look at.
- **Tier 1 needs no old versions.** The state is the set of open (quest, element) with its position.
  A changed element is evaluated in its new version and its entries replaced; a deleted one loses them. What
  it does need: node positions for a changed way (a location store, about 80 GB flat for the planet, or the
  region files), country and place by position, and a due date per element for the date quests, written by
  the full count, since ageing has no event (a quarter of the measured flips).
- **Tier 2 needs surroundings**, so a store that answers "what lies around this element", or a recount of
  only the cells an edit touched. One neighbour flip in 1,299 says the radius is small; one day does not
  settle it.
- **A full count stays the check**, weekly. Notes: 4 flips of 1,299; whether they have a feed is unchecked.

**Plan, in order.** Each step is checked against the full count of the same day.
1. **Replay 11-08's minute files** (the sequence range from the state files) through tier 1 for europe-west:
   seed from the 11-08 clip, emit (minute, changeset, quest, element, opened or closed). Pass: net events per
   (quest, element) equal the 941 measured tier-1 flips less ageing and notes. Report the surplus (opened and
   closed within the day), which is what a stream shows and a daily diff does not. New engine code: an
   "evaluate these elements" command.
2. **The changeset feed as a second check:** for StreetComplete changesets with a `quest_type`, does the stream
   show that quest closing on the edited element?
3. **Due dates** for the date quests, checked against the 339 aged flips.
4. **Tier 2:** dirty cells or a neighbourhood store, flip for flip against the full count.
5. **Then the world's cost:** state size, the location store, and one planet day through tier 1.

**Other routes to a daily world, not ruled out:** recounting only the cells a day's diff touched (measured
2026-11-06 as tiles: 8.5% of Ontario's nodes, 64% of Hamburg's); an own Overpass instance, which keeps a
planet with augmented diffs (HARDWARE.md: fits 64 GB and 300 GB); a faster scan, now the larger half of a pass.

## The stream, step 1: a day of minute diffs replayed, exact (2026-11-10, just past midnight)

The owner: "do it now". Plan step 1 and 2 above. `.scratch/stream-replay/` (gitignored; `fetch.py`,
`replay.py`, `RESULT.txt`, `events.tsv`; 120 MB of minute files). No engine change.

**How.** The 1,415 minute files of 2026-11-08 (sequences 7363129 to 7364543, found from the feed's state
files; 3.93M node, 747k way and 49k relation versions) read in order. Every node and way version inside the
three city boxes, 3,304 of them on 3,078 elements, became its own element in a synthetic PBF (a new id per
version, a way's nodes beside it), which the unchanged engine counted with `--dump-matches` in 2.7 s. Each
version's match set, in stream order, against the element's state before (the 11-08 dump) gives the events,
each with its minute and changeset. Tier 1 only, the 153 quests decided from the element alone.

**Result: the stream reproduces the day.**
- **606 net flips, the same 606 the two full counts show on touched elements; none extra, none missing.**
  No element ends the day in a state other than the 11-09 dump's. These are one fact, not two: net events
  per element add up to the final state less the state before. It proves that evaluating an element alone
  is exact and that the minute stream ends where the 11-09 clip does. It cannot see a wrong event in between
  or a wrong changeset; only the StreetComplete check below tests those.
- **The other 335 measured tier-1 flips have no event, as expected:** 331 opened by ageing, 4 by the two notes.
- **660 events from 113 changesets, in 82 of the 1,415 minutes.** 27 quests went there and back within the
  day (54 events), which a daily diff cannot see. One changeset made 100.
- **A changeset is not one unit of input:** of the 178 changesets with a version in the boxes, 27 span more
  than one minute file, at most 4. The minute file is what is applied; the changeset is what an event is
  credited to.
- **By editor (opened / closed):** iD 215 / 22, StreetComplete 46 / 111, JOSM 114 / 26, Every Door 17 / 73,
  StreetComplete_ee 11 / 8. Mappers with other editors open quests; StreetComplete and Every Door close them.
- **The changeset feed as a second check:** 69 StreetComplete changesets name a tier-1 quest and touch an
  element in the boxes; the stream shows that quest closing in 63. The other six were traced, and in none was
  the quest open before and left open after. Four touch only elements that match no quest in any version
  (AddBusStopShelter, AddSidewalk, AddParkingType, AddParkingAccess: in the boxes, outside the city polygons,
  or hidden; not told apart). Two are date quests on a counted element where the engine did not have the
  quest open yet (AddOpeningHours on node 11119491490, CheckShopExistence on node 2681302751 and way
  42527973): the mapper's app showed it earlier than the default resurvey interval the counts use.

**What the replay did not have to do, and a live stream must:**
- **Hold the state.** The before-state came from the 11-08 dump, and a way's node positions from the stream
  or the two clips (the day's last position, not the one at that minute). A stream needs the open-quest set
  and a node location store of its own.
- **Find the elements without the boxes' help at world scale:** here 3,304 of 4.7M versions were in the boxes;
  for the world all are, about 55 a second on average.
- **The clock.** Every version was evaluated at 11-09T00:00Z, not at its minute.
- **The day's edges.** The range is cut where the feed's state files say, not at 00:00:00Z, so up to a minute
  at each end can differ from the day diff. It moved nothing that day.
- **Relations** (49k versions) were not replayed; none flipped that day in these cities.
- **Tier 2,** ageing and notes, as planned.

**Next:** tier 2 (step 4) before due dates (step 3): the neighbourhood test decides whether this route beats
the others, and it is where the store is decided; due dates are low risk. What this cost at world scale is
still unmeasured: exact is not yet efficient. One more day or region of this replay costs about 10 minutes if wanted.

## Where a cell run's time goes: one Germany file measured (2026-11-10)

The owner asked what would make the recount by cells faster. First read off the Germany prototype's logs,
then measured at the owner's word: file f0 of `.scratch/world-de` (113M nodes, 9 cells, 9,363 place entries),
one engine alone at 30 GB, the machine otherwise nearly idle (another session's small runs). Runner, traces,
collector logs and the profile are in `.scratch/cells-fast/` (gitignored; `run1.py`, `jfr_phases.py`).

**The reading of the logs was wrong in one thing.** A cell's log names its three slowest quests by the sum of
their runs, and an age quest has four. AddChargingStationSocket "41 s" is four runs of about 6 s on other
threads, not the run a cell waits for. The trace shows that run is AddHousenumber or AddLevelThing.

| run of f0 | wall | process CPU |
|---|---|---|
| the engine as it was (d1cebeb7), three runs | 406, 416, 475 s | 4,122, 4,234, 4,235 s |
| 44 GB heap | 384 s | 3,926 s |
| the parallel collector, 30 GB | out of memory in the first cell | |
| two scan twins (below) | 364 s | 3,850 s |
| scan twins and the grid key (below) | 333 s | 3,670 s |

The 475 s run is the one without places: its CPU equals the others', so **places cost nothing measurable**
(9,363 entries; 790 had cost Ontario 4% of a pass). Wall time alone varies by 15% between equal runs.

**CPU by phase** (process CPU against the log's lines, the run with the collector's log; 4,234 s):

| phase | CPU | share |
|---|---|---|
| main pass over the file (nodes 232 s, ways 670 s) | 966 s | 23% |
| the area pass reading the file again | 356 s | 8% |
| map data built per cell | 452 s | 11% |
| the cells' quest runs and tallies (the task trace) | 1,155 s | 27% |
| in the cells' run phases, outside any task: the collector | 1,248 s | 29% |

- **The quest runs are a quarter of the CPU, not half.** The 51% read off the logs was wall time: alone, a
  cell's run phase keeps 3 to 8 of the 24 threads busy and waits for its longest single run.
- **The collector is the largest single cost.** In 416 s: 190 young pauses (25.5 s), 6 full collections
  (29.3 s), and a concurrent marking cycle running for 139 s. A 44 GB heap changes little (about 6% less wall and CPU,
  4 full collections), so it is not the heap's size.
- **What fills the heap** (live class histograms at four moments): 9.7 GB after the main pass; 19.3 GB in a
  middle cell, 15 of it the file's own records, kept for every cell: 114M `NodeRec` objects 5.5 GB, long
  arrays 4.9 GB (way refs, the node index, ids), tags 2.0 GB, the pbf blobs 1.7 GB. The cell's own map data
  is about 4 GB.
- **The first cell held 30.0 GB: two arrays of 5.7 GB each.** SC's `LatLonRaster(bbox, 0.0005)` (AddHousenumber,
  AddIsAmenityIndoor) is sized by the map data's box, and cell f0c0's box is 26.5 by 13.45 degrees, because
  stray nodes stretch Germany's grid to longitude -20: 1.43 billion slots. Four of the six full collections
  are in that cell, and it is why the parallel collector runs out of memory there. **For the world this is a
  blocker, not a cost:** a cell sized by nodes over an ocean or a desert is far larger than this one.
- **Inside the quest runs** (profile of the engine with the scan twins, shares of the samples there): hash
  maps 24% (gets, puts, and the tree walks below), `mapData.getNode` 10%, the fast reject still 13% (scans
  through SC's own `mapData.filter(expr)`, which walks every element), `includesElementType` 4% (a hash set
  of three enum values). In the main pass's ways: the filter
  tree 31%, the fast reject 22%, `Polygon.contains` 8.5% (a cell is a rectangle and is tested as a polygon).

**Built, same counts** (engine/README.md, "Fast twins"):
- **Twins for the two age quests that walked every element four times,** CheckExistence and
  AddChargingStationSocket (`FastScans.kt`): candidates by key first. Their CPU in the file: 197 s to 29 s.
- **A grid key that spreads** (`gridKey`, the three grids of `openquests/fast/`): `(x shl 32) or y` hashes to
  `x xor y`, so a dense grid's buckets turned into trees; 6% of the quest runs' samples were tree walks while
  the level grid was built. AddLevelThing's CPU 113 s to 85 s.
- **Checked:** f0's snapshot equals the unchanged engine's, and the Germany prototype's of 11-09, in every
  field but `runSeconds` and `engineCommit`, places included; `-Dopenquests.verifyFast=true` on Dublin and
  Lisboa found every twin equal to its port (20 map data runs), before and after the grid key; 79 engine
  tests pass, SnapshotReproductionTest included (Ontario recounted; TorontoRegressionTest skips, its extract
  pruned).
- **f0 alone: about 410 s to 333 s, CPU about 4,180 s to 3,670 s** (one run of the new engine). Not run with
  two engines at once, where the CPU is what counts: expect the 12%, not the 19%.

**Not worth doing, measured:** a larger heap; the parallel collector; clipping notes to the cells (cells tile
their file's box, so the file's clip is already theirs; the 21 s here is the prototype's single clip of 2.09M
notes for the stretched box).

**Next, in order, none built:**
1. **No giant boxes.** The planner must not hand the engine a cell far larger than its data: trim a country's
   grid to where its nodes are, and for the world cap a cell's sides in degrees. A long way's centre can lie
   in a square with no nodes, so empty cells cannot simply be dropped; and a near-empty cell is not free
   today (item 2). The engine should refuse a box whose raster would not fit, by name, instead of dying in a
   full collection.
2. **The file's records as arrays, and per-cell lists made once.** `NodeRec` as five arrays, tags only for
   the 5.3M tagged nodes: about 3 GB less live and 114M fewer objects for every marking cycle. Each cell's map
   data starts by filtering all 133M records of the file (`buildMapData`), so its cost grows with the number of
   cells in a file.
3. **`mapData.filter(expr)` asks for candidates** (a patch to SC's `MapDataXt.kt`, exact as on 11-08): every
   scan the ports and SC's helpers still do, at once. About 13% of the quest runs.
4. **Smaller things in the profile:** a rectangle cell tested by its box; `includesElementType` without a
   hash set.
5. **One read, not two** (8% of the CPU, and the second read is where the records of item 2 are made).
6. After 1 and 2, measure two engines again: the 2.3 s per million nodes is from before all of this.

The count is still about 6.5 hours of a chain whose cut is 6 and whose daily upkeep is unmeasured. Item 1 is
needed before any stage larger than a country; the rest is worth perhaps a third off the count.

## The stream, tier 2: only the ground a day's diff touched, recounted (2026-11-10, night)

Plan step 4 of "The stream: probed, and the plan": the 40 area quests, which read their surroundings. The
test is daily, not per minute: mark the ground the day's diff touched, recount only there, compare with the
two full counts of `.scratch/diff-flips/`. `.scratch/tier2/patch.py` (gitignored; `plan`, `count`,
`compare`; a `RESULT.txt` per ring in `r100/`, `r300/`, `r1000/`). One engine change, opt-in:
`-Dopenquests.areaPaddingM=<metres>` sets the ring around a city's box (default 1 km, snapshots unchanged).

**How.** europe-west, 11-08 to 11-09, planet day diff 5171.
- **The ground touched**, as cells of 50 m in each city's own flat grid, then one more cell all round:
  a changed node's old and new place; every segment of a changed way, old and new, and a closed way's whole
  bounding box; for a way that is not in the diff but holds a changed node (a moved node does not re-version
  its ways; found by reading every way of both clips), the segments next to that node and the way's own
  quest position; a changed multipolygon's bounding box. Changed `route`, `public_transport` and
  `restriction` relations (165) were left out. Ferry routes would have been covered; the summit quests
  read hiking routes and have no match in these cities; the other quests were not checked one by one.
- **Rectangles.** The cells are merged greedily: two rectangles become their bounding box when that box with
  its ring is no larger than the two with theirs. Each rectangle is a "city" for the unchanged engine (its
  parent's country codes and time zone, the same quests file and notes clip), counted on both clips.
- **Three comparisons**, inside the real city polygons. *Control:* the patch count against the full count of
  the same day, inside the rectangles; any difference there has nothing to do with the diff. (The city
  test is even-odd over the boundary's rings; it puts all 178,000 patch matches the full counts also have
  inside their city.) *Splice:* the
  old state with the rectangles' matches replaced by the new day's patch count. *Delta:* the patch counts'
  own flips (new less old) applied to the old state.

**Result.**

| ring | rectangles | control, each day | splice | delta | London: nodes read, area runs |
|---|---|---|---|---|---|
| 100 m | 90 | 1 match the patches lack (of 14,775) | 1 wrong | exact | 2.1%, 0.5 s |
| 300 m | 81 | equal, all 17,055 and 17,337 | exact | exact | 5.3%, 2 to 5 s |
| 1 km | 48 | 1 match the patches have extra (of 56,575) | 1 wrong | exact | 22.7%, 12 to 14 s |

The whole of London is 14.8M nodes and 26.7 s of area runs. "Exact" leaves out the aged flips, as planned.
- **All 350 flips an edit caused lie inside a rectangle, and the delta reproduces them at every ring:** 316
  opened, 34 closed. The other 8 of the 358 measured tier-2 flips are CheckExistence opening by ageing, on
  untouched ground: step 3's. (At 1 km one of the 8 falls inside a rectangle and the delta has it too.)
- **The patches are 1.1% of the tier-2 state** (14,775 of 1,387,420 matches at 100 m) and 12 km2 of London's
  1,595. Two changed ways are three quarters of London's 2,805 touched cells: a `landuse=residential` outline
  (way 23298277, 1,249 cells) and Harrow Lodge Park (way 23051299, 894), each covered by its whole box.
- **The two control differences**, the same on both days, so the delta cancels them and the splice does not:
  at 100 m the patches lack AddMaxHeight on way 437671407 in Lisbon, which the 300 m run finds (not traced;
  a bridge further than 100 m from the rectangle is the likely cause). At 1 km a patch gives AddHousenumber
  for way 1176630809 in London where the whole city does not (not traced; AddHousenumber depends on the order
  of the map data, engine/README.md). So a local count is not always the whole-city count, at any ring.
- **Splice or delta is a design choice of the store.** The delta needs the old evaluation of the same
  ground but never brings a patch's disagreement into the state; the splice needs only the new one and did
  bring it in, once in 15,000 matches.

**What this does not show.**
- **A radius.** One of the 358 flips was on a neighbour (20 m). The day settles that the method works, not
  how wide the cover or the ring must be.
- **A speed-up.** The engine still read the whole clip for each run (37 to 69 s a pass); and the plan step
  read every way of both clips to find the parents of changed nodes, 10 minutes a clip in Python. A store
  must answer both "what lies in this box" and "which ways hold this node" without a scan.
- **The stream form.** Per day, not per minute or changeset.
- **Other days:** an import, a rural region, a day on which a route relation matters.

**Next:** the same over the stored week and the four Europe regions if a radius is wanted (the plan step's
way scan is the slow part); due dates (step 3); then step 5, the store and one planet day's cost.

## The stream, step 3: ageing is yesterday's data with today's clock (2026-11-10, night)

Plan step 3 of "The stream: probed, and the plan". A quarter of the measured flips had no edit behind them.
`.scratch/due/due.py` (gitignored; `RESULT.txt`). No engine change: `--today` moves the clock.

**The test.** The 11-08 clip of europe-west counted again with the clock at 11-09T00:00Z, same notes clip,
every match dumped, against the two full counts of `.scratch/diff-flips/`.
- **On elements the diff did not touch it opens exactly the 342 quests the full counts show opening, and
  closes the one they show closing by a note.** 339 are agedOnly (CheckShopExistence most of them); the
  other 3 opens and the close are the day's note flips: the notes clip holds each note's dates, so the
  moved clock replays the notes too.
- **One measured flip is not predicted:** AddIsAmenityIndoor on node 302134936 closing, the neighbour flip,
  which tier 2's patch recount has.
- **9 more quests were due on elements the diff then touched; 1 of them is open on 11-09.** The edit's
  re-evaluation decides those, not the clock.
- So on this day the three parts explain every flip: the element's own edit (tier 1), the ground an edit
  touched (tier 2), and the clock with the notes clip.

**The due-date table, sized.** The same clip without notes (the engine refuses a clock past the notes
dump's end), clock moved on, against a no-notes count at 11-08 (4,626,985 matches):

| clock moved by | quests opened | closed |
|---|---|---|
| 2 days | 728 | 0 |
| 7 days | 1,595 | 0 |
| 30 days | 4,122 | 0 |
| 365 days | 64,992 | 0 |
| to the year 2100 | 971,545 | 0 |

- **The clock only opens.** No quest closed at any later clock, so a due date is one date per (quest,
  element): the first day it matches. That holds for these three cities and v64.1's quests.
- **About 970,000 quests wait for their date**, a fifth again of the 4.6M open ones: AddWayLit 191k,
  AddPathSurface 145k, AddRoadSurface 135k, CheckExistence 131k, CheckShopExistence 75k. A year brings
  65,000 of them (CheckShopExistence 23k, AddOpeningHours 13k, CheckExistence 12k); a day 140 to 360, by the horizon averaged over.
- **What was not built:** the table itself. These runs find a due date only to the nearest clock tried;
  an engine output "first day this matches" does not exist. An edit to an element replaces its due
  dates, as it replaces its open quests.

**Next:** step 5, the store (open quests, due dates, node locations, "what lies in this box", "which ways
hold this node") and one planet day's cost through it.

## The stream, step 5: a planet node store, and one planet day through tier 1 (2026-11-10, night)

Plan step 5 of "The stream: probed, and the plan": the world's cost. Of the store's five parts one was
built and used (node locations), one was measured on real data (the open-quest state), three are sized
by arithmetic (due dates, "which ways hold this node", "what lies in this box"). Then 11-08's 1,415 minute
files went through tier 1 for the whole planet. `.scratch/store/` (gitignored; `store.py`, `day.py`,
`state_size.py`, `count_nodes.py`, `planet.sh`, `RESULT.txt`, `events-world.tsv`). One engine change,
opt-in: `-Dopenquests.areaPass=false` skips the area pass (snapshots never set it).

**The node location store: built, 107 GiB, 35 minutes.**
- **What it is:** pyosmium's `dense_file_array` (4.3.1, natively on Windows, no Docker): one memory-mapped
  file, 8 bytes for every node id, absent ids empty. `planet.loc` has 14,361,507,332 slots and is
  106.8 GiB (114.8 GB).
- **Built from `history-261102.osh.pbf` (159 GiB) in 2,072 s:** the node pass 1,455 s (every version read,
  the last one wins, a deleted node reads as absent), then a way pass of 617 s that the store does not need
  (it fetched the versions before the day, below). About six cores busy, 2 GB of memory. The six day diffs
  to 11-08T00Z went in at 32 to 39 s each.
- **Checked against the clips:** every 50th node of the 11-08 Europe clip, 2,556,447 of them, is at the same
  place in the store; after the day's replay, every 50th node of the 11-09 clip, 2,556,762, likewise. None
  missing, none elsewhere. So the history file, the day diffs and the minute files all land where
  osm-extracts' own clip does.
- **The planet has 10,988,329,357 live nodes** at the end of 11-08 (the slots that hold a place, 76.5% of
  them; counted from the file in 288 s, after the fourth trap below was mended). The "10-11 billion" used
  for the count's hours was an estimate; it holds.
- **Two things the pilot found** (the Europe history cut, 7.4 GiB): with the location handler in the same
  chain the ways took twelve times as long (400 s against 32 s), so nodes and ways are two readers; and a
  dense file is as large for a region as for the planet (the pilot's was 107 GiB too), so a region's store
  would be the sparse kind.

**The day: how.** The minute files in order. For each file: every node version first (the old place read,
the new one written), then each way version placed from the store as it is at that minute, then that
file's node deletions. Every tagged, visible version becomes its own element in a synthetic PBF, as in
step 1, a way's nodes beside it as one synthetic node per (node, place). The version before the day of
every touched element (from the same pass over the history file, then the six diffs: 80,025 tagged nodes
and 236,781 tagged ways) goes into a second file, counted with the clock at 11-08; the day's versions with
the clock at 11-09. The engine sees the world as one "city" without country codes, so each quest is gated at
its position; UTC, no notes, the area pass off.

| stage | wall | |
|---|---|---|
| the 1,415 minute files parsed: 4,727,281 versions | 115 to 126 s | Python, one thread |
| 3,931,249 node versions into the store, a read and a write each | 243 to 251 s | 62 µs each |
| 747,133 way versions; the 454,782 tagged and visible ones placed with 6.2M lookups | 28 s | 4.5 µs a lookup |
| **the day, two runs** | **386 and 405 s** | 447 s CPU, 3.1 GB of private memory; the slowest minute file 5.1 s (57,203 versions) |
| the engine over the day's 611,840 versions | 10.9 s | 109 s CPU, 1.8 GB |
| the engine over the 316,806 versions before the day | 8.0 s | 80 s CPU |
| those prior ways placed: 3.5M lookups in a store not yet in memory | 73 s | 21 µs a lookup |

- **A planet day through tier 1 is about seven minutes on one thread and twenty seconds of engine.** A
  minute of the world's edits takes a quarter of a second on average and five seconds at worst.
- **The node step is the wrapper, not the disk.** Reading an absent slot through pyosmium raises a Python
  exception: 74 µs against 11 µs for a present one (a million of each), and three quarters of the node
  versions are new nodes, so about 225 of the 243 s. The undo of all 3,931,249 writes took 24 s. Without the
  exception the day would be about three minutes (arithmetic, not run).
- Of the node versions 3,025,623 made a node, 399,080 moved one, 425,947 deleted one and 80,599 changed
  only tags.

**Result: the world's tier-1 events of one day.**
- **350,162 events: 240,991 quests opened and 109,171 closed, on 231,524 elements, from 27,580
  changesets.** 4,610,980 nodes and ways had a version that day; they held 363,278 open tier-1 quests
  before it and 495,098 after. Net flips 336,574; 13,588 events went there and back within the day.
- **Every minute has events:** 194 in the median minute, 4,299 in the busiest.
- **By editor (opened / closed):** iD 112,185 / 37,939, JOSM 91,232 / 29,656, StreetComplete 12,478 /
  22,499, Rapid 9,726 / 1,945, StreetComplete_ee 3,759 / 5,606, Vespucci 2,663 / 1,522, osm-revert 176 /
  2,826, atp2osm 0 / 2,133. StreetComplete and its fork close 28,105 of the 109,171, a quarter.
- **By quest (opened / closed):** AddBuildingType 74,969 / 21,170, AddBuildingLevels 22,625 / 3,466,
  AddWayLit 19,027 / 6,476, AddRoadSurface 16,901 / 10,173, AddPathSurface 12,344 / 5,324. Closed more
  than opened: AddMaxSpeed 6,426 / 7,710, AddSidewalk 5,313 / 6,464, AddOpeningHours 2,709 / 5,323,
  CheckShopExistence 33 / 6,280.

**Checks.**
- **europe-west is exact.** The same two files counted with step 1's cities file and notes clip give 660
  events, the same 660 as step 1, each in the same minute, changeset, quest and element. The state before
  the day, from the store's prior versions, equals the 11-08 dump on every touched element (218 of them
  hold a quest), and the state after equals the 11-09 dump. So places taken from the store at the minute
  and prior versions taken from the history file reproduce what step 1 took from the two clips and the dump.
- **The world's StreetComplete changesets:** 7,228 name a tier-1 quest and have a node or way version in
  the stream; the stream shows that quest closing in 7,101, 98.2%. The 127 others were not traced (step 1
  traced its six: the quest was not open before, or the app showed a date quest earlier than the default
  interval). 4,045 more name an area quest or an overlay.
- **Nothing else checks the world's numbers:** no full count of the planet exists for either day.

**Four traps.**
- **A node deleted in the same minute.** 15 way versions named a node that the same minute file deletes:
  a file lists nodes before ways, and in time the way version came first. With a file's deletions applied
  after its ways, no version is left unplaced (the figures above are from that run).
- **A box from -180 to 180.** The country lookup wraps an east edge of 180 to -180 and takes the world for
  a sliver on the antimeridian, so every country-limited quest was gated wrongly (AddAcceptsCash off in
  London). The test's world ends at 179.9999999. A world cell must not span every longitude; the cap on a
  cell's sides (cells' list, item 1) covers it.
- **The engine wants every ported quest in its quests file,** so "tier 1 only" is the switch above, not a
  shorter file.
- **A deletion in a day diff carries the node's last place,** and the location handler stored it: 4,482,349
  nodes deleted between 11-02 and 11-07 still held a place (found at review, after the run). No way names
  a deleted node, so no event moves and the clip checks could not see it; only the node count was too high.
  They were emptied by hand and `store.py` now empties them with each diff. The history file's own
  deletions carry no place (419,657 deleted nodes of the Europe cut checked: none in the store), and the
  replay writes the empty slot itself.

**The state, sized on real data, not built.** The 11-09 dump of europe-west, 4,624,345 matches on
2,371,321 elements (`state_size.py`):

| layout | bytes a match | zlib |
|---|---|---|
| the text dump | 95.1 | |
| fixed records (quest, type, id, place) | 18.0 | 6.1 |
| by element: id deltas, one place per element, its quest list | 6.2 | 4.1 |
| the same without places | 2.1 | 0.5 |

Germany as cells is the only whole country counted: 76,065,341 open quests on 442,630,768 nodes, 0.172 a
node. The planet's 10.99 billion nodes at that rate are **1.9 billion open quests, about 12 GB by element**
(the guess had been 15 to 30 GB). Whether the world is tagged like Germany is not known. Due dates add about
a fifth as many entries (971,545 waiting against 4.6M open in europe-west), each with a date: 2 to 3 GB.

**The other two lookups, estimates only.**
- **"Which ways hold this node":** the 11-09 Europe clip has 21,368,006 ways with 168,134,144 node
  references on 127.8M nodes, 1.32 a node; that is cities, and the planet's ratio was not measured. At that
  ratio the planet has about 14.5 billion pairs: 116 GB at 8 bytes each, perhaps half sorted and
  delta-coded. Its load is the 399,080 moved nodes a day.
- **"What lies in this box":** the elements themselves with their tags, by tile; that is the planet as
  files, about 90 GB (HARDWARE.md), plus an index, kept current. Nothing measured.
- With the node store that is roughly 300 GB kept current by the minute: what an Overpass instance already
  is (250 to 300 GB, HARDWARE.md).

**What this shows.** Tier 1 for the whole world, 70% of the matches and 72% of the flips of the measured
day, costs minutes a day, one 107 GiB file and no new engine command. The full count is 6.5 hours of a chain
that has not yet run once.

**What it does not show.**
- **The state itself.** The state before the day came from prior versions out of the history file, a
  ten-minute pass, not from a table of open quests. A live stream is seeded by a full count of the world.
- **Tier 2,** 30% of the matches: it needs the two lookups above, or a recount of the ground touched.
- **Relations** (48,899 versions) were again not replayed. A way whose node moved without a new version
  keeps its events; only its place moves.
- **Places, notes, time zones, ageing:** which place holds each event, the notes that hide quests, a zone
  per position and the due-date table were not part of the run. One clock for the whole day.
- **Other days:** one day, a Sunday.

**The disk.** `planet.loc` was deleted after the run; `planet.sh` rebuilds it in 40 minutes from the
history file in the store. With it C: had 120 GiB free, and the planet job of 2026-12-07 needs about 170.

**Next, the owner's call.** Both ways forward wait for the first count of the whole world: it seeds the
stream's state and is the oracle for it. That count waits for the cells' list (item 1, no giant boxes).
After it, tier 1 can follow the minute diffs at minutes a day while tier 2 is recounted weekly or on the
ground touched; whether tier 2's store is built here or is an Overpass instance is the open strategic
question.

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

## Hosting on Cloudflare (2026-11-10)

The owner chose to move the whole site to Cloudflare, not just the data, at
`https://street-complete-statistics.comentality.com`. This replaces the plan in "Hosting headroom:
measured", where the site stayed on Pages with `DATA` pointing at R2. The reason is the same: GitHub
Pages' 1 GB cap and a git history that grows about 10 KB per city per day. `cloudflare/README.md`
has the commands.

- **Shape:** a Worker serves every path from the R2 bucket `sc-open-quests` through a binding. The
  page and its data share an origin, so there's no CORS and no change to `app.js`. "/" and "…/"
  serve `index.html`. A missing file is a real 404 with `no-store`, never `index.html`. Responses
  carry Content-Type by extension, `Cache-Control: public, max-age=300` and the object's ETag, and
  `If-None-Match` and `If-Modified-Since` get a 304. Cloudflare compresses JSON with Brotli on the way
  out. The Worker has no `workers.dev` URL; the custom domain made its own DNS record.
- **Upload:** `tools/cloud_publish.py` runs rclone over R2's S3 API, with credentials derived from the
  one API token (access key = token id, secret = SHA-256 of the value). It uses `--checksum`, deletes
  files gone from `docs/` (old snapshots leave daily) up to 2,000 a run, and refuses a `docs/` that
  lacks `index.html`, `app.js` or `data/cities.json`, or holds under half the bucket's count.
  First upload: 4,836 files, 133 MB, 2 min 10 s. An unchanged rerun takes seconds.
- **Checked 2026-11-10:** all 4,836 files are byte-equal over HTTPS once the Web Analytics beacon is
  taken out. The zone has Cloudflare Web Analytics on, which injects one script into HTML; that's the
  owner's zone-wide setting, left as it is. Toronto, Berlin, Montreal and London load in headless
  Chromium with no page errors and no failed requests.
- **Daily:** `run.py update` and `planet` sync to R2 after the git push. A failure is logged as
  "cloud publish FAILED" and doesn't stop the run, because Pages is still the fallback. `docs/` stays
  in git for now: the dual write is what makes Pages a fallback.
- **The flip:** after one scheduled run has uploaded by itself (from Task Scheduler, reading the token
  file), the old address `skfd.github.io/sc-open-quests/` gets a redirect that keeps path, query and
  hash, so shared links still reproduce their view. It's served from a separate Pages branch, because
  `main:/docs` is also what R2 copies. The revert is pointing Pages back at `main:/docs`. Later, once
  the week has held, the daily data can leave git history (the reason for the move).

### Static assets, no script (2026-11-10, built on `assets-switch`; live after the flip)

The owner wants the site to survive being posted somewhere busy; so far it has no readers. As a
Worker reading R2, every request was an invocation: about 71 for a first city view, so Workers Free's
100,000 a day ran out after about 1,400 of them, and past it readers get an error until midnight UTC.

- **Shape:** `cloudflare/wrangler.jsonc` deploys `docs/` as Workers static assets with no `main`.
  A path that matches a file is served without running code, and Cloudflare bills no asset request,
  so nothing a reader does counts against the cap. There is no script on purpose: with one, a path
  that matches nothing (a favicon, a scanner's `/wp-login.php`) would still run it. Without one such
  a path is an empty 404.
- **Publish:** `tools/cloud_publish.py` syncs R2 first, then runs `wrangler deploy`, which uploads
  the files that changed: 42 s for all 4,836, 20 s when nothing changed. The R2 bucket stays equal
  to `docs/`. It's the way back (`wrangler.r2.jsonc`), and its object count is what the partial-site
  guard compares against.
- **What changed for the reader:** nothing in the bytes (all 4,836 files compare equal on a local
  `wrangler dev`). Data is `max-age=0, must-revalidate` where it was five minutes; `app.js` already
  asks with `no-cache`, so that is the same in practice. `docs/_headers` keeps icons and images a
  day. JSON's Content-Type has no charset. The page declares the StreetComplete mark as its icon.
- **The first switch looped on `/` (2026-11-11), fixed the same night.** The comentality.com zone has a
  URL Rewrite rule for the blog, "Serve index.html for folder paths", that turns every path ending in `/`
  into `…/index.html` before a Worker or its assets see it (`wrangler tail` on the R2 Worker showed `/`
  arriving as `/index.html`). The assets' `auto-trailing-slash` answered `/index.html` with 307 to `/`,
  and the rule rewrote that again. Now `html_handling: "none"` serves files at their exact path only,
  and `docs/_redirects` (`/ /index.html 200`) serves `/` whether or not the rule stays; `/vendor/` and
  other folders are a 404, as they were in practice. `cloud_publish.py --check` fetches `/` too, since
  every file had compared equal while `/` was broken.
- **Limits now:** 20,000 files in a version and 25 MiB a file. `docs/` is 4,836, of which 4,202 are
  the name layer and don't grow with cities; a city adds about two.
- **Not shown before the switch:** production serving. The trial Worker had no route. A full
  `--check` after the switch should pass and leave the Worker's invocation count where it was.

## Before a spike: what a first visit asks of whom (2026-11-10)

The owner's goal is that the site survives being posted. Three things were done on main, and the
third parties were looked up; nothing here touches the engine or the Worker.

- **No CDN.** uPlot 1.6.31 and Leaflet 1.9.4 are served from `docs/vendor/` (the npm `dist` files,
  byte-equal to what jsdelivr served: the SRI hashes the page pinned match, `docs/vendor/README.md`).
  jsdelivr states no limits, so this removes a dependency, not a known cap. On today's Worker the two
  uPlot files are two more requests of a first view (71 to 73) at `max-age=300`; as static assets
  they are free.
- **`cities.json` is 8 KB gzipped, from 124.** `trendAll` (59 KB) was read by nothing and is gone.
  Each city's `trend` (57 KB) is only Compare's sparkline column, so it moved to `data/trends.json`,
  which the page asks for when Compare first opens. A page reading older data with `trend` in
  `cities.json` still draws the column.
- **Checked headless on the real data, from a local server only:** Toronto, Compare (147 sparklines)
  and Map load with no page errors and no failed request; the only other hosts asked are `gc.zgo.at`
  and, on Map, `tile.openstreetmap.org`. Not yet served by the Worker or by Pages: a hand sync to the
  live bucket was refused to Claude (a production deploy), so the 12:15 run of 11-11 is the first.
  Pages builds `legacy` with `docs/.nojekyll`, so `vendor/` is served as it is. The vendored bytes
  survive git (a checkout's `leaflet.js` has the pinned hash).
- **The archive has a second copy.** `tools/archive_backup.py` copies `data/archive/` to the private
  R2 bucket `sc-open-quests-archive` under `archive/`: 2,161 files, 467 MiB, 79 s the first time,
  checked equal by checksum. It never deletes, and a file a rerun rewrote keeps its old version under
  `replaced/<date>/`, so it guards against a dead disk, a wrong delete and a bad rerun. `run.py
  update` and `planet` run it last, after the site sync; a failure is logged "archive backup FAILED"
  and the run goes on. The per-region `quests.json` files change every count, about 1.6 MB a day
  into `replaced/` (0.6 GB a year against R2's 10 GB free); prune old `replaced/` dates by hand if
  it matters. `data/grid/` (2,145 files, 316 MB, the z14 tile grids) goes to the same bucket under
  `grid/` at the owner's word, checked equal too; `data/notes/` (255 MB) is not in it, as the clips
  can be cut again from the notes dumps.
- **Third parties (looked up 2026-11-10 by an agent through a summarising fetch; re-read a sentence
  before relying on it):**
  - *tile.openstreetmap.org*: the tile policy gives no number. It asks for visible attribution, a
    valid Referer (the page sets no Referrer-Policy) and normal caching, and says access may be
    blocked without notice if use degrades the service. Tiles load only when Map is opened. With the
    tile host blocked in a headless browser the Map tab still draws all 147 boundaries, on an empty
    ground, with no page error; the rest of the site doesn't use tiles.
    The durable fix, if wanted, is a self-hosted PMTiles basemap on R2. Keyed free tiers (Stadia
    200,000 credits a month, MapTiler 100,000 requests a month, then paused) turn a possible block
    into a certain stop on a spike day. The owner chose to stay on OSM's tiles (2026-11-10).
  - *GoatCounter*: free "for reasonable public usage", no stated monthly cap; "millions of pageviews
    a day" is what it names as too much. The script is `async`, so it doesn't block parsing or
    drawing (a hanging host can still delay the `load` event); with its host blocked the views load
    with no page error.
  - *jsdelivr*: no bandwidth limits stated; no longer used.

## Countries in the place index: StreetComplete's, not ours (2026-11-10, evening)

**The problem.** The place index (`docs/places/`, 272 countries) took Overture 2026-10-21.0's `country`
field as shipped; `tools/places.py` reads no perspectives. That files Western Sahara wholly under Morocco
(its "Western Sahara" region overlapping two Moroccan regions), gives Palestine no country (the West Bank
and Gaza are bare `XW`/`XG` stubs), and makes Golan, the Kurils, Senkaku and the Spratlys stubs of their
own. Places with no country are dropped. No counted city is in a disputed area, so no numbers were
affected, only search, the hierarchy and roll-ups. The Map tab's OSM tiles draw a third view.

**The owner's rule:** avoid controversy, and a Western view is no answer; leaning on SC's decisions
completely is fine. So the site files a place where StreetComplete applies a country's rules, and says
so: "Filed where StreetComplete applies that country's rules. This site describes the app; it takes no
position on borders."

**What SC's data says** (`engine/src/main/resources/sc/boundaries.ser`, library
`de.westnordost:countryboundaries:3.0.0`, probed with a throwaway test at 36 points): it follows who
governs. Simferopol `UA-43, RU`, Sevastopol `UA-40, RU` (no plain `UA`, so a UA-only quest is off there;
`UA-43.yml` has Russian banks and uk/ru/crh); Donetsk, Luhansk, Melitopol `UA`; Laayoune, Dakhla `MA`
but Tifariti, east of the berm, `EH`; Ramallah, Gaza `PS`; East Jerusalem, Golan `IL`; Srinagar, Leh
`IN-JK, IN`, Gilgit `PK`, Muzaffarabad `PK-AJK, PK`, Aksai Chin `CN-XJ, CN`, Itanagar `IN-AR, IN`; Pristina
`XK`; Taipei `TW`; Kunashir `RU`; Liancourt `KR`; Halaib `EG`; Woody Island `CN-HI, CN`; North Nicosia,
Kyrenia `CY`; Hargeisa `SO`; Khankendi `AZ`; Sukhumi `GE-AB, GE`; Tskhinvali `GE-SK, GE`; Tiraspol
`MD-SN, MD`; Senkaku, Itu Aba, Bir Tawil nothing.

**Decided (owner, 2026-11-10):**
- **A place goes under every country SC's data names at it.** A code's country is its part before the
  hyphen (`UA-43` is Ukraine), so Crimea is under both Ukraine and Russia. A place SC splits (Overture's
  "Western Sahara" region: `MA` and `EH`) goes under each, tested at several points inside it, not only
  its centre. A place with no code is left out of the tree (owner, later the same evening; this replaces a "no country" group).
- **Country names as SC shows them.** SC names a country by asking the platform's locale data:
  `Locale("en-$countryCode").displayRegion` (`screens/user/edits/CountryDialog.kt`, the per-country
  statistics dialog; the same in `ProfileScreen.kt` and `QuestSelectionScreen.kt`), which is
  `getDisplayCountry` on Android and NSLocale on iOS, both Unicode CLDR, in the phone's language. The
  browser has the same data: `new Intl.DisplayNames(["en"], {type: "region"}).of(code)`, so the site
  names countries there, in English like the rest of the site, and ships no name table. Node's: `PS`
  Palestinian Territories, `EH` Western Sahara, `XK` Kosovo, `TW` Taiwan, `HK` Hong Kong SAR China,
  `MK` North Macedonia, `TR` Türkiye. SC never names a subdivision (`UA-43`), and the top level only
  uses a code's country part. (Owner, 2026-11-10: names, not codes; this replaces "codes only".)
  Regions and everything below keep Overture's names and hierarchy, but see "Below the country
  level" next: that hierarchy is not neutral either.
- **Palestine is named "Palestine"** (owner, 2026-11-10: "just giving palestine a polite name"). Its
  borders stay SC's, like every other country's (Ramallah and Gaza `PS`; East Jerusalem and Golan `IL`).
  The name is CLDR's own short form (`Intl.DisplayNames` with `style: "short"` gives "Palestine" for
  `PS`; the long form is "Palestinian Territories"); every other country keeps the long form, since short
  also gives "US", "UK", "Bosnia". Briefly decided and withdrawn the same evening: Palestine in its 1967
  borders from Overture's `XW` and `XG` polygons (which do include East Jerusalem). Rule kept: borders
  are always SC's.
- The Map tab keeps OSM's tiles; their borders are OSM's and credited as such.

**Below the country level: Overture's view is one unlabelled view (checked 2026-11-10, evening).**
The owner: "there is no neutral overture; there could also be problems at this level". Overture's
schema has the toggles (`perspectives` with `mode` accepted_by/disputed_by and `countries`, on
`division` and `division_boundary`; `hierarchies` as a list of parent chains), but release
2026-10-21.0 fills none of them: 0 of 4,700,999 divisions have `perspectives`, every division has
exactly one hierarchy, and 0 of 87,536 boundaries have `perspectives`; only 47 country-level boundary
lines carry `is_disputed` (Kashmir and Aksai Chin, Golan, Gaza and the West Bank, Kosovo, Western
Sahara, Abyei, Halaib and Bir Tawil, Essequibo, Cyprus's buffer zone, and others). So nothing was
toggled wrongly, but there is nothing to toggle: the parent chains and the polygons below a country are
Overture's single choice, unmarked. Where it can disagree with SC:
- *A place whose Overture chain leads to a country SC does not name there.* Crimea's places sit under
  "Autonomous Republic of Crimea" under Ukraine; under Russia (where SC also files them) Overture has no
  region for them. Moroccan-held Western Sahara has Overture's "Western Sahara" region overlapping
  Laayoune-Sakia El Hamra and Dakhla-Oued Ed-Dahab; SC splits the land `MA`/`EH`. Golan is Overture's
  `XH` stub; SC says `IL`.
- *Names.* Overture's primary name is mostly OSM's `name` tag, which is also what SC shows a player.

**Decided (owner, 2026-11-10, evening):**
- **A disputed place goes under both.** "It is just search in a tree structure", so a duplicate costs
  nothing. Disputed is mechanical: SC names two countries at the place (Crimea: `UA-43, RU`), or SC and
  Overture name different countries (Overture's chain says Morocco where SC says `EH`). The place then
  appears under every one of those countries, each time inside its Overture region and below, so
  Crimea's places sit in the same Crimea region under Ukraine and under Russia. Undisputed places follow
  SC, which there agrees with Overture.
- **Overture's placeholder "countries" are not countries** (Claude's default, not yet confirmed: the
  `X?` codes, e.g. `XW` West Bank, `XG` Gaza Strip, `XH` Golan, `XU` Kunashir, `XD` Senkaku). They have no
  CLDR name and are no claimant; their places go under SC's countries, or are left out where SC
  names none (Senkaku). So they never make a place disputed.
- **No source we lean on files the Golan under Syria** (checked 2026-11-10): SC says `IL`; Overture's
  stub is named "Golan Subdistrict" (the Israeli district) with no perspective; its Wikidata item
  (Q5423040, the district, not Q83210 the Golan Heights) has country Israel only. Wikidata is no claims
  source either: Kunashir has JP and RU but Iturup and Shikotan only RU; Gaza lists historical
  occupiers. Overture's `X?` stubs are not all disputed: Saba, Sint Eustatius and Jan Mayen are among
  them. Syria for the Golan, or Japan for the southern Kurils, would be a hand-written claims list, the
  kind of position the owner ruled out with Palestine's borders.
  Rechecked the same evening at the owner's question: 2026-10-21.0 is Overture's newest release; its
  docs (docs.overturemaps.org, schema `perspectives`) describe the mechanism (a map for country X = the
  features with no perspective, plus those `accepted_by` X, minus those `disputed_by` X) and name no
  place that has one; the release fills it nowhere, names included (0 of 513,892 divisions with name
  rules). Around the Golan: Katzrin and Majdal Shams are in the `XH` stub, 4 of the 47 `is_disputed`
  boundaries ring it, and the UNDOF buffer zone (old Quneitra) and Syrian Hermon are under Syria. SC at the
  buffer zone is unchecked.
- **Every perspective at once (owner, 2026-11-10):** "toggle them different ways so that we show smaller
  places in each bigger place a perspective can put it". The index takes every parent chain in
  `hierarchies` and every division whatever its `perspectives`, and files a place under each parent any
  of them gives, alongside SC's countries. A no-op on 2026-10-21.0 (one chain each, no perspectives
  anywhere, the Golan included), so it changes nothing today and fills in by itself if a release
  populates them; the monthly Overture diff should report when one does.
- **Names are OSM's** where the division has an OSM relation: its `name` tag, what SC shows a player;
  Overture's name only where Overture has no OSM source. English stays shown first as today.
- **A world total, if there ever is one, counts each place once**, not once per country it is under.

**Other touchy things, decided (owner, 2026-11-10, late evening):**
- **No home-made romanisation.** "I don't think we should bake our own anglification." `places.py`'s
  Cyrillic tables (BGN/PCGN simplified, chosen by the filing country, so Crimea would get two spellings)
  go. English names come from sources only: Overture's `en` (mostly OSM `name:en`), then the Wikidata
  English label of the division's `wikidata` item; with neither, the local name is shown as it is, as for
  every other script today. Measured on the world's divisions: 289,516 with a Cyrillic primary name,
  196,526 of them with no Overture `en`, 130,716 of those with a Wikidata item (how many of those have
  an English label is unmeasured).
- **Places SC files under no country are left out of the tree** (owner: "they do not appear in tree
  search, is it ok?": yes). Senkaku, the Spratlys, Bir Tawil and the like: no country heading, no
  label to word. The measurement lists them; anything populated among them comes back to the owner.
- **Never flags.** The site shows none and never will (no official emoji flag for Kosovo, Taiwan's
  hidden on iPhones sold in China, Western Sahara's is Polisario's).
- **Fine as they are:** `aka` names such as "Kiev" for Kyiv are only searched, never shown; names in
  occupied areas are OSM's own practice; Hong Kong and Macao keep CLDR's long names; counting uses land
  polygons, so sea claims never matter; time zones are tzdb's, which follows practice.

**To build (nothing built yet):** an engine command that maps points to SC's codes (about a million
lookups); OSM `name` tags for the divisions with an OSM relation (from the planet already on disk); `places.py` files by those codes instead of Overture's `country`; a test pinning the probed
points (Crimea under both, Tifariti under `EH`, Senkaku left out); the note on the about page and
beside the country level; a first measurement of how many places move.

## Place statistics for the whole world: the final product (proposal, 2026-11-10, late evening)

The owner asked for neighbourhood statistics designed for the end state, with the whole world counted.
Nothing built. It takes as given what is decided: every Overture division with an OSM source and an area
gets per-quest counts; a quest counts once in every polygon holding its position, from country down to
microhood (DESIGN "The whole world"); a world count weekly, monthly points since 2017 from the history
file; the 147 cities keep their daily run.

**Scale, from the Germany prototype (`.scratch/world-de/`, 2026-11-09):** 40,520 places: 23,237
localities, 2,823 macrohoods, 9,327 neighbourhoods, 4,717 microhoods, 399 counties, 16 states, 1
country; 39,446 with a number; median 50 quest types with something open, at most 183. One snapshot of
every place: 47 MB raw, 6.3 MB gzip. The world is about 1M places, so about 25 times that: a weekly
snapshot of roughly 1.2 GB raw, 160 MB gzip.

### A neighbourhood is a place: one page for every level

There is no separate neighbourhood page. Every place, country to microhood, gets the same page, and a
level only changes which children it lists. A neighbourhood is one level among them, as today's
"parts" are.

1. **Header:** the name, and the chain above it as links (Canada > Ontario > Toronto > Agincourt
   North); a disputed place shows one chain per country (DESIGN "Countries in the place index"). Then
   one big number (open quests, ticked types), a change chip (4 weeks; green when it falls), quests
   per km² and "as of <date>".
2. **Trend chart:** stacked map (indigo) under resurvey (orange), the same as a city's: monthly since
   2017, weekly since the world count began, daily inside the 147 daily cities. App releases on the
   time axis. The two parts need the aged split per place (below).
3. **Among its neighbours:** the rank among siblings of the same subtype by quests per km² ("12th of
   158 neighbourhoods in Toronto"), and the place against its parent's average. Places with under 50
   quests are left out of ranks, so plazas and squares do not top them.
4. **Children:** a table (name, kind, open, per km², 4-week change), sortable, and the same children
   on a map shaded by per km². Children overlap and leave gaps; the existing note says so.
5. **Quest types:** the existing table, plus aged and 4-week change columns; each row links to that
   quest in this place.
6. **Out of the same files:** the share card (outline, number, sparkline) and the widget's small file.

### Hosting: place data on an R2 public bucket, not static assets

A million places is 50 times the static-asset cap of 20,000 files, and packing them into fewer files
makes one place's page download its neighbours' history. So the app stays on static assets, and place
data goes to an **R2 bucket served on its own subdomain** (for example `data.` beside the site), read
straight from the bucket with no Worker:

- **No Worker means no 100,000-a-day cap.** Cloudflare's cache in front of a custom-domain bucket
  answers repeat reads without touching R2 (to be verified with a test bucket; `r2.dev` URLs have no
  cache and are rate-limited). Uncached reads are 10M a month free, then $0.36 a million. There is no
  hard cap, so a spike costs a few dollars rather than taking the site down.
- **Writes set the cadence:** 1M free a month, then $4.50 a million. Rewriting every place weekly is
  about 4.3M writes a month, about $15. So the plan below rewrites each place monthly and writes only
  small per-parent files weekly.
- **Storage:** about 16 GB of place history (DESIGN "The whole world", item 5), about $0.10 a month
  past the free 10 GB.

### The files: three requests per place page, each cacheable for a week

| file | holds | written | count |
|---|---|---|---|
| `place/<id>.json` | name, subtype, chain, land area, outline bbox; series: dates and per-quest `open` and `aged` columns, 0 told apart from "not counted" | monthly (the 1st), weekly points since the last month folded in | about 1M |
| `latest/<parentId>.json` | the newest per-quest `open`/`aged` of every child of that parent | weekly; daily for children inside the 147 daily cities | about 100k (places with children) |
| `geo/` (PMTiles, one file) | every place's outline, id only, no numbers | when Overture's release changes | 1 |

- **A page reads** its own `place/` file, `latest/<self>` (its children, newest) and
  `latest/<parent>` (itself newest, plus its siblings, which is the rank). All three follow the quest
  ticks, because they keep the per-quest split. The children's map joins the PMTiles outlines with
  `latest/<self>` by id in the browser, so the tiles never go stale and the shading follows the ticks.
  PMTiles is read with HTTP range requests: one file, no tile server.
- **Writes a month:** 1M place files plus about 430k `latest` files, about 1.4M, roughly $2.
- **Sizes:** a place file is about 50 quests x 170 points (118 months, then weeks), about 40 KB raw
  and 10-15 KB gzip after a year; `latest/` files are tens of KB at most (a county with 300 children
  is about 60 KB raw).
- **Search** stays on the name layer's shards; a result links to `/<country>/.../<slug>/` (DESIGN
  "Share previews", readable addresses).

### What the engine and pipeline need

1. **The aged split per place:** a second array beside `partOpen`, filled where `countParts` is
   called (the mask is at hand there). Without it the chart is one colour and aging reads as neglect.
2. **Land area per place,** for per km²: the polygon's area less water, computed once per Overture
   release in the place build. Cities already use `landAreaKm2`.
3. **The world's weekly snapshot archived privately** (about 160 MB gzip a week, 8 GB a year) in the
   backup bucket. It is the source every `place/` and `latest/` file is rebuilt from. Publishing it
   as open data, one file a week, is cheap on R2 and the owner's call.
4. **The monthly history recount with places on,** once (DESIGN "The whole world", item 6: about 7
   weeks on this machine with per-cell cuts).

### Open, for the owner

- **R2 public bucket for place data** (unlimited files, Cloudflare's cache, billed past the free tier
  with no hard cap) or packing into static assets (free and capped, but a page downloads its
  neighbours too).
- **What "per km²" divides by:** land area (simple, fair across city and country) or mapped elements
  (open per 1,000 tagged things, which is closer to "how done is it", but harder to explain).
- **Freshness:** weekly for the world and daily only inside the 147 cities, or something else.

### The owner's answers (2026-11-10, late evening), and what daily changes

- **R2 public bucket for place data:** yes.
- **Freshness: daily for the world is the MVP goal,** not weekly. A daily world recount does not fit
  on this machine (a world count is about 24 hours), so daily comes from the stream (DESIGN "The
  stream", steps 1-5), not from recounting the planet every day.
- **Daily makes writes the cost to design around.** Ontario's 790 parts, 10-29 to 11-08: 87 to 197
  change on a given day (11-02: 435), so about 12-25% of places a day. Measured:

  | plan | R2 writes a month | about |
  |---|---|---|
  | every `place/` file daily | 30M | $130 |
  | only changed `place/` files daily, plus `latest/` per parent | 5-6M + 3M | $32 |
  | **`place/` monthly; `latest/<parentId>` daily holding its children's days since the 1st, as per-quest changes** | 1M + 3M | **$13.5** |

  Proposed: the last row. A page reads the same three files: its `place/` file (history to the 1st),
  `latest/<parent>` (its own days this month, and its siblings for rank) and `latest/<self>` (its
  children). Daily files are cached until the next publish; a tiny `latest.json` (the date) is cached
  for minutes.
- **The density divisor was explained in chat,** with no decision yet. The site already shows "per km²
  of land" and "per km of road" for cities (`app.js`, Compare and the city tiles).
- **Correction (owner):** the per-km² and per-km-of-road tiles came with the prototype; they are
  not agreed design. A divisor is needed only where places are compared (rank, shaded children map,
  "against the parent's average"). Proposed for the MVP: no comparison, so no divisor. A place page
  shows its raw count, change, trend, quest types and children by raw count, and the children's
  map shows clickable outlines without shading.
- **Owner, same evening:** the daily R2 plan (about $13.5 a month) is fine. Comparison stays where it
  is today, the Compare tab's city table (open, per km² of land, per km of road, per 1,000 people), and
  places below a city are not compared. So place pages carry no divisor, and the engine needs no area or
  road length per place. Open for later, at world scale: which places Compare lists once there is no
  fixed list of 147 (for example, cities over a population bar with a country filter).

### The R2 cache premise: half checked (2026-11-11, overnight)

- **JSON is not cached by default.** Cloudflare's docs (cache/concepts/default-cache-behavior): "The
  Cloudflare CDN does not cache HTML or JSON by default", and caching goes by file extension, not MIME
  type; the R2 public-buckets page: "By default, only certain file types are cached. To cache all files
  in your bucket, you must set a Cache Everything page rule." So the place-data subdomain needs a Cache
  Rule (eligible for cache, respect origin TTL; the Free plan has 10) before launch, or every read of a
  `place/` or `latest/` file is an R2 read. Neither page says whether a cache hit counts as a Class B
  operation; that is what the test below measures.
- **The test is ready but not run.** The test bucket `sc-open-quests-cachetest` exists (empty). Attaching
  its custom domain `sc-r2-cachetest.comentality.com` is a DNS change the auto-mode classifier refused to
  Claude, so the owner runs that one command (`.scratch/r2-cachetest/run.py` has it, and the clean-up),
  then the script: it uploads a JSON with Cache-Control, one without, and a PNG, fetches each 30 times,
  and compares cf-cache-status with the bucket's GetObject count from the GraphQL analytics (the deploy
  token can read them; checked). Expected: the PNG HITs, both JSONs stay DYNAMIC until a Cache Rule.

## Countries in the place index: built on branch `countries`, not merged (2026-11-11, overnight)

Built as decided above, measured, and left on the branch for the owner: it rewrites `docs/places/`, and
nothing that rewrites published files rides the first cloud-synced run before the flip.

- **Engine `regionids`** (`RegionIds.kt`): SC's region ids at each point, the same lookup that gates
  quests. 1,082,287 points in 4.5 s. `RegionIdsTest` pins the probed points (Toronto `CA-ON,CA`,
  Simferopol `UA-43,RU`, Laayoune `MA`, Tifariti `EH`, Ramallah `PS`, Senkaku nothing).
- **The point is Overture's label point:** a division's own `bbox` is its point rounded outwards to
  float32, so its centre is the point (checked against the `geometry` column pulled once from S3: the
  same answers). No polygons are needed.
- **`places.py`:** countries per place = SC's at its label point (a code's part before the hyphen) plus
  Overture's `country` unless a placeholder; a region, county and anything below also takes the
  countries of the places below it, so a chain is whole (Overture's "Western Sahara" region gains `EH`
  from Tifariti, the Crimea region `RU` from its towns); country and dependency roots take only their
  own. Filing under a country that is not the place's own: inside its own root when that root is
  under the country too (United States > Puerto Rico > San Juan; Palestine > Gaza Strip > Gaza; Russia >
  Kunashir), else inside its Overture region. Places neither source files are left out (12, the
  Spratly reefs among them). Romanisation is gone; Wikidata English labels and OSM `name` tags are not
  done yet (the planet extraction is its own job).
- **Site:** the country level is named by `Intl.DisplayNames` (Palestine by the short form), sorted by
  that name; the borders note beside the country list and in the footer. A country no Overture
  division heads opens by its code (`?place=ps`). Checked headless: 255 countries; Russia lists Crimea;
  Palestine, Western Sahara, the Canaries and Ceuta & Melilla open with their regions; Palestine > Gaza
  Strip and United States > Puerto Rico > San Juan open; no console errors.

**Measured (Overture 2026-10-21.0, 1,082,287 places):** 1,075,781 agree with Overture's country at
their own point; 6,846 are filed differently, 6,333 under two or more countries. 272 index countries
become 255: the 23 placeholders go, and `AC`, `EA`, `EH`, `IC`, `PS`, `TA` arrive. The big moves are the
decided ones: Crimea (1,176 places also under Russia), every dependency also under its sovereign as SC
names both (Puerto Rico 1,655 under the US, Curaçao 275 and Aruba 94 under the Netherlands, French
Polynesia 268 under France, the Faroes and Greenland under Denmark, Hong Kong 140 and Macau under China),
the Canaries under `IC` and Ceuta and Melilla under `EA` as well as Spain, the West Bank and Gaza under
Palestine, Golan under Israel, Kunashir and Iturup under Russia. `.scratch/countries/` has the full
lists (`measure-labelpoint.log`, `index-diff.txt`).

**Border noise: decided (Claude, with the owner's "do it all yourself", 2026-11-11 10:20).** The first
build showed about 150 regions under a neighbour with 1 to 18 places each (Canada > Maine, Ireland >
Northern Ireland, the UK > Donegal), where a label point sits on SC's simplified border. Its signature:
SC files the point only under other countries, yet files ground within 3 km under the place's own
Overture country. Such a place keeps its own country only (`on_the_line`, `RING_KM = 3`, 8 points; 360
places tested, 2,880 lookups). Real cases do not look like that: Tifariti has no Morocco near it, and SC
names both countries in Crimea, Puerto Rico and Gibraltar. Nothing loses its own country. After it,
6,238 places are filed differently and 5,725 under two or more countries; the noise entries are gone,
and about 15 entries of 2 to 5 places remain (Pando, Rivera, Omsk, Tuva, Amur: places more than 3 km
inside SC's line, unexamined).

**What SC's own data says and stays:** Gibraltar under Spain as well (`GI, ES-AN, GB`), Japan > Senkaku,
Korea > Liancourt, China > the Paracels, and **Matsu (Lienchiang, 27) and 4 Kinmen places under China**:
SC's boundaries give Nangan `CN-FJ, CN` (Kinmen town, Penghu and Taipei `TW`), so the app applies
China's rules on Matsu. That is an error in SC's data, not noise; a report for countryboundaries is
drafted in `.scratch/countries/upstream-matsu.md`, not posted (it would go out in the owner's name).
## The stream: its state (2026-11-13)

The owner (2026-11-13, midday): "were building current world processing as an etalone for data and performance.
big hopes that streaming version will be faster." So the full count is the reference twice over: for the
numbers (the stream must reproduce it) and for the cost (the stream must beat it). Steps 1-5 above compared two
evaluations; nothing held a state and carried it forward. This adds that.

**The reference's cost, from `logs/planet-places.log` (11-13):** plan 1 min, slice from the history file 74 min,
notes 5 min, cut into 128 files 262 min, count 124 s a file on one engine (about 4.4 h; two engines never fit
beside what else holds memory). About 10.5 h of machine time for one instant of the world, 60% of it slice and
cut. Tier 1 of the stream did a planet day in about 7 min (step 5).

**What the state is.** Per (element, quest): the quest's position, the bits of `matchVariants` (open now, aged,
at 0.5, at 2), whether an open note hides it, and for a quest not open now at the default resurvey setting but
open from some day on, that day. Notes are a layer of their own: every match is kept, flagged when hidden, and
the checks leave notes out.

**Engine `--dump-state <file.bin>`** (`StateDump.kt`): 24-byte little-endian records written as the pass goes
(key i64 = id*4+type, lat/lon i32 at 1e-7, quest u16, flags u8, kind u8, due i32 in minutes since the epoch),
plus `<file>.json` naming the quests in index order (the order differs between runs with and without notes).
A main-pass age quest not open now is asked at 40 years ahead; if open then, the first whole day after asOf it
opens is found by halving (about 14 evaluations). Without the option nothing changes (86 engine tests pass).
Checked on step 1's 11-09 versions (europe-west): the open, unhidden records equal `--dump-matches` exactly
(1,350); counted again with `--today 2028-06-01`, all 37 quests dated by then are open and none dated later;
at `2034-03-01` all 208. The only quests opening that the dates did not foresee were the area quests
CheckExistence and AddCycleway (42): **area quests are not dated yet** (AreaPass asks a whole map data at once,
so halving per element does not fit; to do before the world seed if the Europe test shows their ageing).
Quests that only `newer` tests open, and the dates at the 0.5 and 2 settings, are not dated either.

**`world_cells.py count --state`:** every file of a kept cut again with `--dump-state` to
`files/<f>/state.bin`, beside the count (`out-state/`, `state-done.json`), so a recount never touches the
count's results. For the world seed from the 11-08 cut kept by chain4.sh.

**`tools/stream/stream.py`:** the state of a region in memory as one sorted table (`rows.npy`); `apply` takes
one day diff: the last version of every node and way in it (a day diff is sorted by type and id), node places
from the seed clip's sparse index plus an overlay of the diff's nodes, the tagged ones into a small PBF (way
nodes as synthetic nodes), the engine over that with the area pass off, and every tier-1 row of a touched
element replaced. Ageing has no event: a row waiting for its date is open from its date on. `check` holds the
state against a whole count's dump of the same instant, by tier. Measured on diff 5171 (11-08 to 11-09, the
whole planet's): reading the diff 124 s in Python, the small PBF 28 s (222,496 tagged ways placed in the
Europe clip, 209,608 outside it), the engine over europe-west's touched elements 2.4 s, the state 10 s.

**Known gaps, each visible in `check`:** a way whose nodes moved but which has no version keeps its old
position; relations are not recounted (48,899 relation versions that day); tier 2 keeps the seed's rows (the
patch recount of "The stream, tier 2" is not wired in); area quests do not age.

**The Europe test (started 11-13, 13:07):** `tools/stream/europe-test.sh`, log `logs/stream-europe.log`, state
in `.scratch/stream/europe-west/`. After the world count ends: the Europe clips 11-08 to 11-13 counted whole for
europe-west's cities with `--dump-state` (one engine, about 2 min each), the 11-08 one as the seed, then the day
diffs 5171-5175 applied one at a time, each followed by a check against that day's count. The clips of those
days are pinned in `~/Code/.osm-data/europe/pins.json` (unpin when done). Result: below.

**The Europe test: the result (11-13, 16:35 to 17:04, after the world count ended).**
- **`--dump-state` changes nothing else, and costs nothing visible.** Days 08 and 09 held against the old
  engine's `--dump-matches` of the same clips: 4,623,562 and 4,624,345 open unhidden matches, equal both ways
  (0 only new, 0 only old). Each whole clip counted in 55.6 to 57.9 s (the old engine's count of 11-09: 89.6 s,
  under other load), due searches included. Main's engine was rebuilt after this (`installDist`).
- **The seed:** 5,472,907 rows from the 11-08 count, 706,179 of them waiting for a date; 6.1 s.
- **A day through `apply`: 171 to 256 s,** of which reading the planet's day diff in Python 106 to 164 s (the
  same for any region), the small PBF 24 to 32 s, the engine 1.7 to 2.2 s, the state 31 to 58 s (growing with
  the node overlay, 492 MB after five days).
- **Tier 1 is exact for nodes and ways, five days running, ageing included.** Every difference is a relation:

| day | tier 1, state | full count | only in the state | only in the count | tier 2 (seed's rows), only state / only count | of the count's, on touched elements |
|---|---|---|---|---|---|---|
| 11-09 | 3,239,807 | 3,239,807 | 0 | 0 | 34 / 324 | 316 |
| 11-10 | 3,240,633 | 3,240,634 | 0 | 1 relation | 178 / 956 | 922 |
| 11-11 | 3,241,307 | 3,241,308 | 0 | 1 relation | 212 / 1,380 | 1,321 |
| 11-12 | 3,242,161 | 3,242,160 | 2 relations | 1 relation | 272 / 2,040 | 1,960 |
| 11-13 | 3,242,868 | 3,242,867 | 2 relations | 1 relation | 434 / 3,146 | 3,038 |

  The relations: r21949748 (AddBuildingType) opened on 11-10 and the state lacks it; r5328319
  (AddOpeningHours) and r21447069 (AddBuildingLevels) closed on 11-12 and the state still has them. No way
  missed a place, no moved node changed a way's quest, no due date was missed or early.
- **Tier 2, kept from the seed, drifts by about 700 differences a day** (3,580 of 1.39M after five days, 0.26%).
  96 to 98% of the count's extra quests are on elements the diff touched (an edited building gets
  AddRoofShape and AddHousenumber, an area quest, so tier 1's recount does not reach them); the rest (8 to 108)
  are on untouched elements: neighbours and area quests ageing.
- **So the next gaps, by size:** tier 2 (the patch recount of "The stream, tier 2", which needs the map data
  around each touched element: a day clip here, a store in the world), then relations (one a day or so here;
  48,899 to 55,199 relation versions a planet day), then area quests' due dates. The world seed is a whole
  recount of chain4's cut: chain4's 128 files took 4.4 h of engine (15,853 s summed), 8.9 h on the clock
  with the daily window and waits for memory.

**Every row checked, and dates for the 0.5 and 2 settings (11-13, evening).** `check` compared only the open
set; it now holds every tier-1 row too (position, variant bits, dates; the note flag apart, since `apply`'s
runs have no notes clip). On the first run's 11-13 that showed the default setting exact in every bit, but
the 0.5 and 2 settings drifting (838 matches the count had and the state lacked, 173 rows with other bits:
they had no dates), and untouched ways whose nodes moved off by a median 0.3 m (774 rows, 90% under 3.2 m,
max 30 m; that position is what a place counts by). So `--dump-state` now dates each setting (a DUE row's
flags carry `M_NOW`, `M_05` or `M_2`; a dump with no bit there means the default). Main's engine with it:
still equal to the old engine's dumps on 11-08 and 11-09, snapshot unchanged with the option off (only the
commit and run time differ); the pass 57 to 65 s against 52 to 54 s (about 12% more, so about 5 h of engine
for the world seed); the seed 6.83M rows, 2.06M of them dates (0.71M before). Rerun of the five days: no
variant bit differs on any day; tier 1 is left with the relations and the moved-node positions.

**Untouched tier-2 differences, by quest:** on 11-13, 100 of the 108 the count has and the state lacks are
area quests opening by age (CheckExistence 72, AddCycleway 20, AddTrafficSignalsSound and -Vibration 8);
8, and 15 the other way, are neighbours (AddHousenumber, crossings). So area-quest dates are about 20 a day
here, tier 1's own changes about 1,000: the first world seed goes without them (the stream reseeds with each
StreetComplete release anyway), recorded as a known gap.

**Tier 2 in `apply`: built and run on the five days (11-13, evening).** `stream.py apply --tier2-clip`,
`tools/stream/tier2.py`, `tools/stream/europe-t2.sh` (state in `.scratch/stream/europe-west/t2/`, log
`logs/stream-t2.log`). After tier 1's small PBF, the ground the diff touched (as "The stream, tier 2", plus
the old position of every row of a touched element) becomes rectangles of 50 m cells with a 300 m ring; the
rectangles are counted as cities on the day's clip (`map_data`, the one place a world store would answer);
inside each rectangle and its own city every row (all quests, tier 1 too) is replaced by the recount's
(splice). The parents of a changed node come from a way store of the seed clip (`stream.py ways`: 21.4M
ways, 168M refs, 3.7 GB, 7 min) plus the diffs' ways since.

| day | rectangles, km2 | nodes the area runs read | tier 1 differences | tier 2 differences (inside a rectangle / outside all) | control, inside the day's rectangles |
|---|---|---|---|---|---|
| 11-09 | 81, 15 | 0.95M | 0 | 8 (0 / 8) | equal (42,399 and 17,332) |
| 11-10 | 82, 22 | 1.18M | 0 | 30 (1 / 29) | equal |
| 11-11 | 104, 111 | 2.05M | 0 | 55 (1 / 54) | equal |
| 11-12 | 189, 140 | 3.62M | 0 | 98 (38 / 60) | tier 2: 36 AddHousenumber the recount lacks, 1 extra |
| 11-13 | 104, 298 | 3.71M | 11 (2 ways) | 130 (60 / 70) | tier 1 and 2: 2 Dublin ways the recount has (19 rows) |

- **Against tier 2 kept from the seed (3,580 differences on 11-13), 130.** Tier 1 is exact in every field on
  four days (positions of ways whose nodes moved, and the three relations, now right).
- **Outside every rectangle: area quests ageing** (CheckExistence, AddCycleway, the traffic-signal sound and
  vibration quests), 8 to 70: the area-quest dates the dump lacks.
- **Inside: the recount's own disagreements, brought in by the splice.** 11-12: 36 AddHousenumber the whole
  count has and the recount lacks (AddHousenumber depends on the order of the map data, engine/README.md); they
  stay on 11-13. 11-13: ways 71455532 and 168339841 lie on Dublin's boundary; the recount counts them, the whole
  count has no row for them at all. The engine's own point test puts both positions inside Dublin (checked with
  its arithmetic), so the cause is elsewhere: not traced. The delta form (the recount's own flips) would keep
  both out; the splice was the first choice because it needs only the new day's data.
- **Cost a day: 5 to 7 min** (300 to 432 s): reading the planet's diff in Python 110 to 156 s, the small PBF
  27 to 35 s, the cover 38 to 80 s, the engine over the whole clip for the rectangles 23 to 36 s (its area runs
  0.9 to 8 s; the whole count's area pass for these cities is about 25 s), the splice and state 30 to 60 s. The
  engine still reads the whole clip for its main pass; with a store, the rectangles' map data (1 to 4M nodes a
  day here, against 14.8M in London alone) is all it needs.

**Tier 2 in the delta form (11-13, night; the owner held the world seed for this).** The splice brought the
recount's own disagreements with a whole count into the state. Two probes, before building anything, asked
whether the delta form would keep them out: it does only if the old-day recount of the same rectangles has the
same disagreement.
- **The 36 AddHousenumber of 11-12:** 11-12's rectangles recounted on the 11-11 clip lack all 36 too (the whole
  11-11 count has them). So the recount's change between the days does not touch them, and the delta leaves the
  state's rows alone.
- **The two Dublin ways of 11-13 (71455532, 168339841):** 11-13's rectangles on the 11-12 clip have the same 9
  rows each, at the same position. Unchanged, so kept out.
- **The Dublin cause, traced:** the two roads are Dublin's boundary, and their centres lie 3 and 4 mm from it
  (2.6e-8 and 4.0e-8 degrees). The whole count, with all three cities or with Dublin alone, puts them outside
  (no row at all); the dump stores positions at 1e-7 degrees (about 1 cm), and at that rounded position the
  engine's even-odd test says inside. One step of 1e-7 south says outside. So `tier2.inside`, deciding on the
  dump's position, kept rows that the engine itself had not put in the city. Any recount whose own city test is
  a rectangle meets this for elements within a centimetre of a boundary; the delta keeps an existing
  disagreement out, but an edit to such an element would still bring its rows in. A full fix would hand the
  engine the real outline (the rectangle cut by the city) so the engine decides at full precision.
- **Built:** `stream.py apply --tier2-old-clip Y` (yesterday's clip): the rectangles are counted twice, on
  yesterday's clip at the state's clock and on today's, and `tier2.delta` compares the two per (element, quest)
  group of rows (a match and up to three dates). Old absent and new present: set to new. Old present and new
  absent: removed. Both present and different: set to new only if the state holds the group. Equal: untouched.
  Each case is counted, with how often the state disagreed with the old recount (the measure of drift). The delta
  never heals: the splice resynced everything inside a rectangle, earlier misses included, so the measure is the
  total of tier-2 differences each day. In a world store this means "the map data of these boxes at D-1" too,
  asked before the diff goes in. `tools/stream/europe-t2d.sh` (state `.scratch/stream/europe-west/t2d/`, log
  `logs/stream-t2d.log`); `tests/test_stream_delta.py`.

**The delta form on the five days: the result (11-13, 20:05-20:46).** Against the splice (`t2/`, same seed,
same diffs, same rectangles):

| day | tier 1, splice / delta | tier 2 differences, splice / delta | delta's inside a rectangle | seconds a day, splice / delta |
|---|---|---|---|---|
| 11-09 | 0 / 0 | 8 / 8 | 0 | 289 / 325 |
| 11-10 | 0 / 0 | 30 / 30 | 1 (CheckExistence) | 302 / 298 |
| 11-11 | 0 / 0 | 55 / 55 | 1 (CheckExistence) | 286 / 339 |
| 11-12 | 0 / 0 | 98 / 73 | 12 CheckExistence, 1 AddHousenumber the state has extra | 405 / 457 |
| 11-13 | 11 / 0 | 130 / 99 | 27 CheckExistence, 1 AddCycleway, the same extra AddHousenumber | 386 / 434 |

- **Tier 1 exact in every field on all five days**, and the 36 AddHousenumber and the two Dublin ways stay out.
- **What tier 2 has left is area quests ageing** (CheckExistence, AddCycleway, the traffic-signal sound and
  vibration quests), 98 of 99 on 11-13, plus one AddHousenumber (way 1577774915) that the 11-12 recount has and
  the whole count lacks, new that day, so the delta took it in as an addition. Inside the rectangles the delta
  keeps the ageing misses the splice resynced (1 against 27 on 11-13): it never heals, as expected. So the next
  gap by size is the area quests' dates, about 20 a day here.
- **Cost:** the second engine run adds about 35-50 s a day (tier 2 160-285 s against 100-235 s).
- **The drift counters measure the overlap with tier 1, not drift:** "added, the state had it" (449 to 1,098 a
  day) and "removed, the state lacked it" (173 to 289) are mostly tier 1's own replacements of touched elements,
  made before the delta. To read drift from them, count tier-2 quests only. Not done.

## Area quests' dates (2026-11-13, night)

The last tier-2 gap the delta form left: area quests opening by age (CheckExistence, AddCycleway, the traffic-signal
sound and vibration quests...), about 20 a day on europe-west, 98 of the 99 differences on 11-13. The main pass
dates a waiting quest by asking the element at 40 years ahead and halving (about 14 evaluations of one element);
an area quest asks a whole map data at once, and London's AddCycleway is about 2.8 s a run, so halving whole cities
does not fit. The design (advisor-checked):
- **A horizon, not 40 years:** an age area quest runs once more at asOf + `AREA_DUE_DAYS` (64,
  `-Dopenquests.areaDueDays`; [Run.AHEAD]), in city mode with `--dump-state` only. Its results not open now are the
  candidates. Dates beyond the horizon are not looked for: the sidecar's `areaDueDays` says how far the state's
  area dates reach, and the stream must reseed before then (it reseeds with each StreetComplete release anyway,
  and the second world reference is the 12-07 planet).
- **The day on a small map data:** the candidates of one z16 tile share a map data of that tile with a 300 m ring
  (the ring the tier-2 recounts found to reproduce a whole city), built from the city's records as the tile mode
  builds its tiles. On it the SC port (not its fast twin, whose shared searches belong to the whole city) is asked
  at asOf and at the horizon: an element the small data does not give at the horizon, or gives already now, stays
  undated (counted). The rest are halved together, one run per distinct middle day: 6 levels for 64 days.
- **Rows:** a DUE row at the default setting (the 0.5 and 2 settings are not dated for area quests), hidden flag as
  for a match. The candidate list carries the city, so an element in two cities is dated in each, as it is counted.
- **Not checked by the design:** a quest that opens and closes again within the horizon (the halving assumes it
  stays open, as the main pass does).

`AreaDatesTest`: four benches (CheckExistence, six years since `check_date`, the edit recent), at asOf 2026-12-01:
one open now, two within the horizon, one after. Two dates written; for each, a whole count the day before has it
closed and one on the day has it open. `tools/stream/europe-area.sh` (log `logs/stream-area.log`) waits for the
world seed, installs the engine, runs every engine test, counts the 11-08 clip again with the dates, holds them
against the whole counts with `.scratch/stream/areacheck.py`, and streams the five days from that seed
(`.scratch/stream/europe-west/t2a/`). The baseline from the old seed: 108 area quests open on untouched ground over
11-09..11-13 (CheckExistence 72, AddCycleway 20, the signal quests 8, and 8 that neighbours opened: AddEntrance,
AddBarrierOnRoad, AddBarrierOpening, AddChargingStationSocket); none dated.

**The result on europe-west (11-14, 03:07-03:11).** Every engine test passes with the dates in. The 11-08 recount
with `--dump-state` dated **1,462 candidates, 1,462 dated, 0 undated** (the small map data agreed with the whole
city every time), the dating adding about 5 s in all to a 71 s engine pass (London: 1,305 candidates in 581 tiles,
5,190 runs, 3.2 s). Its dump is the old 11-08 dump plus exactly those 1,462 DUE rows, nothing else changed
(`.scratch/stream/seedsame.py`). Against the whole counts of 11-09..11-13 (`areacheck.py`): of the 108 area quests
opening on untouched ground, **100 dated on the day, 0 on another day**, 8 without a date, all quests a neighbour
opens (AddEntrance 3, AddBarrierOnRoad, AddBarrierOpening, AddChargingStationSocket, AddKerbHeight,
AddTactilePavingKerb), which ageing cannot date; and **no date up to 11-13 without such an opening**. The dates on
untouched ground reach only seed + 64 days; inside the recount rectangles the delta form rolls the horizon on (the
recount at today's clock dates up to today + 64, the one at yesterday's clock up to yesterday + 64, and the delta
applies the difference; both recounts print their "area dates" lines in `t2a/work/t2/`).

**The five days streamed from the dated seed (`t2a/`, the delta form, 11-14 03:11-03:51).** Tier 1 exact in every
field on all five days, as before. Tier 2 differences after each day, against the delta form without area dates
(`t2d/`):

| day | t2d (no area dates) | t2a (area dates) |
|---|---|---|
| 11-09 | 0 / 8 | 0 / 0 |
| 11-10 | 0 / 30 | 0 / 0 |
| 11-11 | 0 / 55 | 0 / 0 |
| 11-12 | 1 / 72 | 1 / 0 |
| 11-13 | 1 / 98 | 1 / 0 |

(only in the state / only in the count, of about 1.39M open tier-2 quests). The one row left is
`w1577774915 AddHousenumber`, which a diff touched on 11-12: that day's recount counts it and the whole count does
not (the control line: recount against whole inside its rectangles, the same family as the 36 AddHousenumber the
whole count has and the recount lacks on 11-12), and the delta applied the recount's word. So every ageing gap is
closed and what is left is a recount's own disagreement with the whole count; the Dublin boundary ways the 11-13
recount still counts stay out, as in t2d. A day costs 6.5-10 min here (reading the planet diff about 2 min, the
two tier-2 recounts 1.5-4 min, the engine's area runs 2-10 s of that).

## The world state store (2026-11-14, early morning)

The world seed is done (128 files, 2,011,107,291 rows, 48.3 GB, checked against its count file by file) and does
not fit in memory, where `stream.py`'s `State` loads and sorts all of europe-west's 6.8M rows. Measured on the seed
(`.scratch/planet/seedkeys.py`, `seedkeys.log`):
- **The files partition the world by element:** 1,061,205,063 distinct elements (116.9M nodes, 942.7M ways, 1.7M
  relations), and only 95 keys in more than one file (112 extra copies). An element belongs to the file whose
  `rect` (plan.json) holds it, as the count decided; 2,244 cells, each with its time zone, are the files'
  "cities".
- **Lookups need the files sorted, not an index:** a file's rows come in engine-thread order. Looking five planet
  days of touched keys (25.9M) up in one file of 18.6M rows takes 20.7 s with `np.isin` (45 min for the world), but
  1.4 s with `searchsorted` once the file is sorted; sorting a file takes 11-14 s (about 28 min for the world,
  once). One day's touched keys (about 4.6M) against all 128 sorted files is then well under a minute.
- **So the store is the seed's own 128 files, sorted by (key, quest, kind)** (what `State.save` sorts by), each
  rewritten only when a day changes it (a 450 MB file writes in about a second), with a manifest of each file's
  rect, rows and key range. A removal searches every file (a deleted or moved element has no position to route
  by, and searching is cheap); an addition goes to the file whose rect holds the element; the 95 keys in two files
  stay in both, as the count has them.
- **What a world day still needs beyond this:** the node location store (`planet.loc`, 107 GiB, built from
  `history-261102.osh.pbf`, which the 12-07 planet job retires, and on a disk that job needs about 170 GB of) for
  tier 1, and a store answering "map data of these boxes at D and D-1" for tier 2 (estimated about 300 GB). Both
  are the owner's call on disk and timing. The daily touched-element engine run must use the seed's cells and
  zones (one engine run, the 2,244 cells as its cities), not `stream.py`'s single `--zone`.

**Sorted (11-14, 04:17-04:31):** `world_state.py sort` on 4 processes, 832 s; 2,011,107,291 rows kept, 1,061,205,175
keys over the files, the same 95 in two files. `world_state.py find` with the five planet days' touched keys
(25,862,383, of which 1,112,729 have rows in the state: most touched nodes carry no quest) against all 128 key lists
takes 153 s, warm or cold: CPU, about 1.2 s a file, so about 30 s for one day's 4.6M keys. Fast enough to leave
unindexed; a file's key range (in the manifest) could skip most files for most keys if it ever matters.

**The one tier-2 row left, traced (11-14, 05:00; `.scratch/stream/housetrace.py`, output beside it).**
`w1577774915` (`building=house`, no address) is one of about 45 houses (ways 1577774915-1577774989) mapped on 11-12
over Fortune Green Road, London, where buildings with addresses already stand (`w12391097xx`, 110-118, with
`entrance` address nodes on their outlines: 110A and 110B lie a few metres west of the new house). No address node
lies inside the new house itself. A hypothesis, not shown: AddHousenumber decides such a building by order: step 1 lets each address-less
building take ("consume") a shared set of address nodes in map-data order, and step 5 lets areas take address nodes
on their outlines smallest first, then drops every building whose centre lies in such an area (and
`associateBy { center }` keeps one building per centre). Map-data order follows a `HashMap`'s iteration, which
changes with how much map data is loaded (the Bremen check of `ArrayMapData`, above), so the recount's rectangle and
the whole city can hand these nodes out differently. The app's own answer depends on what it downloaded in the same
way. If so, not fixable by the stream short of recounting with the whole city's map data. The 36 AddHousenumber the 11-12 recount lacked (w191632543,
w525502455, w526944931...) are likely the same family; not traced.

**Tested (11-14, 05:15; `.scratch/stream/ring.py`, `ring.txt`): mostly map data extent, not order.** 11-12's 189
rectangles recounted on the 11-12 clip. At the stream's 300 m ring: 22,001 open AddHousenumber inside them against
the whole count's 22,036, lacking 36 (35 of them in one block near 51.47, -0.02, one at 51.48, -0.29) and adding
`w1577774915`. At a 1,500 m ring: 22,039, lacking none and no longer adding `w1577774915`, but adding 3 others
(`w378203971`, `w378204031` near 51.584, -0.040; `w1176630809` near 51.474, -0.027). So 37 of the 37 came from how
far the map data reaches (some address-carrying area or building beyond 300 m decides them), and a wider ring
brings a few disagreements of its own (not traced; order is still a candidate for those). The 1,500 m ring reads
24.6M nodes against 3.6M and took 73 s against 46 s here. For the world store this is the ring-size trade-off:
the store must serve the ring the recount needs, and 300 m is not exact for AddHousenumber.

**The world seed agrees with europe-west's 11-08 count (11-14, 05:25; `.scratch/planet/seedvseurope.py`, log
beside it).** The read-back passes (`seedcheck.py` on the sorted files, 0 problems); every row lies in its file's
rect but 9 on an edge (rounding); the 95 keys in two files are all relations (`seedroute.py`). On the elements both
hold (2,152,775 keys in f34, f44, f90 and f106: Lisboa, Dublin, London), **all 5,405,119 tier-1 rows are equal in
every field** (key, quest, kind, flags, date, position), none on one side only. The world's cells and time zones
give the same tier-1 rows as the Europe cities, so europe-west's day dumps (11-09..11-13) can check a world-path
stream on those elements.

**The world's tier 1 on five days (11-14, 05:12-05:48; `tools/stream/world-europe.sh`, log `logs/world-europe.log`).**
`world_state.py subset` copied the four world files holding Lisboa, Dublin and London (f34, f44, f90, f106) to
`.scratch/planet/world-test/`; `apply` ran diffs 5171..5175 through the world's cells (one engine run over the
small PBF with the 64 cells of those files as its cities, each with its time zone, at UTC like the count) with
europe-west's 11-08 node locations, and `check` held each day against europe-west's whole count on the 2.46M
elements it has inside those rects plus those its 11-08 dump had. At 11-08 the copies equal the count (3,239,324
open, 2,064,743 waiting). On 11-13, every field compared as `stream.rows_check` does: matches 3,343,307 against
3,343,305, waiting 2,065,352 against 2,065,355; 774 matches and 706 waiting rows equal but for the position (ways
whose nodes moved while they kept their version, 28 of them touched earlier; and 4 relation rows), and 3 + 1
matches and 3 + 6 waiting rows on four untouched relations. **The same numbers, row for row, as europe-west's own
tier-1-only stream** (`europe-west/check-2026-11-13.txt`: 3,343,307 / 3,343,305, the same three relations, 774
positions with 28 touched): the world path adds no difference, and what is left is tier 1's known limits, which
tier 2's recount removes (t2a). A day took 5.5-7 min here: reading the diff 2 min, the small PBF 1 min with
europe-west's node index (200-250k ways not placed: they lie outside europe-west), the engine 2.7 s, and **writing
the four files 140-165 s**, which at 128 files would be about half an hour: re-sorting each whole file is the cost.
**Then merged, not sorted (11-14, 06:00):** `replace_in_file` now inserts the day's rows into the sorted file
(`merge`: one int64 per row for (key, quest, kind), `searchsorted`, `np.insert`) instead of sorting it again: on f90
(24.7M rows) with a day's touched keys, 1.0 s against 31 s, the same rows in the same order. A file's update is then
about 3 s (finding the rows 1.2 s, merging 1 s, writing 0.6 s), so a world day's files about 6-7 min if every file
changes.
**Rerun with the merge (11-14, 06:05-06:30, `logs/world-europe-2.log`):** the four files at 11-13 hold the same rows
as the sorting run's, the 11-13 check unchanged; the files' step 47-51 s a day against 140-165 s. Then `in_keys`
marks with `bincount` instead of `np.add.at`, and the key list is taken from the sorted keys without `np.unique`'s
sort: one update of f90 with a day's keys is 4.0 s in all (read, find, merge, write, key list), so the files of a
world day at most about 8.5 min.

**The world's first day (11-14, 12:56-13:08; `tools/stream/world-days.sh`, log `logs/world-days.log`).** `planet.loc`
rebuilt (115 GB, 34 min with the six diffs to 11-08), the stream state hard-linked to the seed
(`.scratch/planet/world-stream/`), and diff 5171 applied to all 128 files: reading the diff 114 s, the small PBF
74 s (432,104 tagged ways, **none unplaced**: the planet store places every way), the engine 11 s over the 2,244
cells, the files 459 s (569,034 tier-1 rows dropped, 840,698 added, none outside every file's rect); 11.5 min in
all. On the elements europe-west's whole count of 11-09 has: matches 3,340,642 = 3,340,642 and waiting 2,064,632 =
2,064,632, all equal but for the position of 17 + 15 rows of untouched ways (nodes moved, the way kept its version:
tier 1's known limit).

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

Stage 3's answer against stage 1's: 4,966,517 objects the same, 463 differ, 366 only in tag order and 97 only in the
user name (attic gives a renamed user's current name); the engine reads neither. So **one attic db answers D and D-1
exactly**. Also exact: stage 2 with relation member ways only by role outer/inner (output 997 MB against 1,125 MB: the
bulk is ways and nodes over the big boxes, not relations).

*Cost here* (internal NVMe; timings vary up to 2x between identical runs while other work runs):
- Load of the 1.64 GB clip: 1,842 s, single-threaded; db 13.7 GB (8.4x the PBF). Day diff 5175 (the whole planet's day,
  so worldwide objects too): 409 s; db 18.7 GB after. A planet db takes a daily diff in minutes (dev.overpass-api.de keeps
  up minutely); not measured on a planet-size db.
- One union query per date: 84-206 s warm, 86-113 s cold, of which most is writing 1.1 GB of XML (16k read requests,
  0.8 GB read from cold). XML to PBF (61 MB): 10-16 s. The engine on it: 21-23 s (48 s under load).
- Each rectangle alone, 103 queries: current 87 s warm / 169 s cold; dated 130 s warm / 221 s cold (median 1.07 s warm,
  1.9 s cold; 0.3-0.5 s of each is `docker exec`). **Dated costs 30-50% more than current** on a db with one day of attic.
  The 65 rectangles under 1 km2 still take about 1.7 s each cold: a per-query floor, so a world day must batch rectangles
  into union queries (per file or region), not query thousands one by one.
- Reads from cold: 306k-361k requests, 18-20 GB, for the 103 alone; the union 16k requests. At a USB4 NVMe's latency
  (some tens of microseconds more than internal) that adds seconds, not minutes: the external drive is not the limit.
- Against the tile store (Python prototype): its read of these rectangles was 34-45 s (31-41 s of it pyosmium writing a
  PBF); Overpass gives both dates in about 3.5-4 min with conversion. Fine for europe-west; for the world, the time goes
  with the output's size (about 10-25 MB of XML a second), which goes with the rectangles' area, not their count.

*What this cannot show:* a planet db's speed with fourteen years of attic (here one day). Tried on the public
overpass-api.de with a 0.2 km2 London box, current and dated (11-12 and 2019): 35-46 s each with two gateway errors, so
the server's load drowned any difference; stopped there. The **size to buy**: the current clone
(dev.overpass-api.de/clone/2026-11-10/, listing read 11-14) is **about 708 GB with attic** (attic files about 253 GB;
nodes.bin 95 GB, nodes_meta.bin 84 GB, ways.bin 80 GB), against "about 400 GB" for 2023 above. **A 2 TB drive**: 1 TB
would hold it with under 300 GB to grow and no room for a second copy during a re-clone.

Sources: wiki.openstreetmap.org, User:Mmd/Overpass_API/install/attic and Overpass_API/Installation (attic from history
files unsupported; `--keep-attic`); dev.overpass-api.de/clone/ (sizes); hub.docker.com wiktorn/overpass-api (tags).
