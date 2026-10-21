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
  - Show the class on the site.
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
