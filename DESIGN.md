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
  first such country.

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
  uPlot is, loaded only when the tab opens, so the other pages pay nothing. Tiles are turned grey by a CSS
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
