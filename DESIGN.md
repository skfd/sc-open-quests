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
- Don't stall on the 51 custom quests. Ship the filter quests first. (Superseded: every quest is supported
  since 2026-11, and the rule below now holds.)
- **Don't publish a count of a subset of quests (the owner, 2026-11-16).** Any number that goes on the site,
  in a snapshot, a series or a place page, covers every quest type of the pinned SC version, as the full
  count does: filter quests, custom quests, area quests, notes and ageing. A faster path that handles only
  some of them (the stream's tier 1, element-only quests, a world day without area quests or their dates)
  is a test or a building block, never a publication. A world day is publishable only when it gives every
  quest, checked against a full count.

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
- **The chart's ends from its gutters (2026-11-16).** The first and last snapshots sit on the plot's
  edges, and the latest days of daily counts share the last few pixels, so they were hard to hover. Level
  with the plot, the white beside it out to the card's edges (the y-axis and the card's padding on the
  left, the margin and padding on the right) reads out the first and the last snapshot, synced to the
  other charts like any hover; above or below the plot stays off. One document listener, finding the
  chart by its card, since a redraw replaces the charts. On a phone a tap does it 10px or more outside the
  plot; nearer, the browser's tap adjustment puts the tap on the plot itself. The idle legend's
  hold on the last index also kept uPlot from drawing the hover rings when the pointer arrived there;
  the cursor hook now clears it first.

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

### The R2 cache premise: checked (2026-11-17, 02:20)

- **JSON is not cached by default.** Cloudflare's docs (cache/concepts/default-cache-behavior): "The
  Cloudflare CDN does not cache HTML or JSON by default", and caching goes by file extension, not MIME
  type. Measured on the test bucket `sc-open-quests-cachetest` at `sc-r2-cachetest.comentality.com`:
  30 fetches each of a JSON with `Cache-Control: public, max-age=3600` and one without were all
  `cf-cache-status: DYNAMIC`, every one an R2 read.
- **A cache hit is not an R2 read.** The PNG beside them: 1 MISS, 29 HITs, and the bucket's GraphQL
  analytics (`r2OperationsAdaptiveGroups` by `objectName`) show exactly 1 GetObject for it. So
  Cloudflare's cache in front of a custom-domain bucket does answer repeat reads without R2, once a
  file is eligible for cache. (The script's own verdict line said otherwise; it counted bucket-wide
  reads, which included scanner bots, below.)
- **The zone's Browser Cache TTL is 4 hours** (comentality.com, `browser_cache_ttl` 14400) and it
  raises a lower origin `max-age`: the PNG uploaded with 3600 went out with 14400. A file meant to be
  cached for minutes (`latest.json`, the date) needs the rule below to respect origin TTL.
- **Scanners arrive within two minutes of a new hostname's certificate** (Certificate Transparency):
  about 30 GetObject probes for `.env`, `.ssh/id_rsa`, `backup.sql`, `wp-admin/...`. Each missing key
  is a Class B read (10M a month free), harmless, and a reason the data bucket holds only published
  files.
- **The place-data host is `sc-data.comentality.com`** on bucket `sc-open-quests-data` (ENAM, created
  2026-11-17; domain attached by the owner). Its Cache Rule "sc-data cache" is deployed on the zone
  (2026-11-17, the zone's first): `(http.host eq "sc-data.comentality.com")`; eligible for cache; Edge
  TTL "use cache-control header if present, bypass cache if not"; Browser TTL "respect origin TTL".
  Checked: a JSON uploaded with `max-age=120` went MISS, HIT, HIT and kept its 120 (no 4-hour
  rewrite). So each upload's `Cache-Control` sets both: a week for `place/`, until the next publish
  for `latest/<parent>`, minutes for `latest.json`. A file uploaded without one is not cached.
- **The test is cleaned up:** the test domain removed, the bucket `sc-open-quests-cachetest` and its
  three objects deleted. The script stays in `.scratch/r2-cachetest/`.

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

## Batch engine speed-up (2026-11-14 night to 11-15; owner: "spend some time doing optimizations for current implementation of batch engine. think outside of the box too")

A rewrite in a systems language is the owner's other track; this is the JVM engine as it is. Built on branch
`batch-speed` (worktree `../sc-open-quests-batch`). Runner and comparer: `.scratch/batch-speed/run1.py`, `same.py`
(gitignored); test file Germany f0 of `.scratch/world-de2` (113M nodes, 18 cells, 30 GB heap, 24 threads).

**Where the world count's time went** (its own logs, `.scratch/planet/world/files/*/log.txt`): 128 files, 15,217 s of
passes; **12,465 s (82%) is the cells' area runs, one cell after another**, 3,520 s of that building map data. And
on f0, by process CPU: of 2,467 s only 651 s was quest runs. The collector was the largest consumer: the file's
records kept the heap about 70% full of small objects (114M node records, 19M way records, 24M tag maps with their
arrays and strings), walked by every marking cycle, and each cell allocated three 0.7-1 GB arrays of references
(SC's `LatLonRaster` over a box of 8 by 7 degrees) that ended in full collections.

**Built, each step with the same snapshot** (`same.py`: every field but runSeconds and engineCommit):

| step | f0 wall | f0 CPU |
|---|---:|---:|
| the engine as it was (d148d0e1) | 245 s | 2,467 s |
| the area pass's nodes as columns; a city's elements picked from int arrays | 202 s | 2,074 s |
| key indexes and the node index of a map data built on all threads; a sparse twin of `LatLonRaster` | 171 s | 2,059 s |
| ways as columns, tags as numbers of one dictionary (a `TagMap` is made when a city's map data wants the element) | 161 s | 1,959 s |
| one node table for both passes (`NodeStore`): the area pass no longer decodes the nodes again; the file's blocks let go before the cells | 162 s | 2,173 s |
| `-XX:MaxGCPauseMillis=5000` (a larger young generation, less copying; `world_cells.py` sets it, the launcher the daily runs share does not: it is measured on a cell file at 30 GB only) | 145 s | 1,817 s |
| **two cells at once** (`-Dopenquests.areaCities=2`, `world_cells.py`'s setting) | **123 s** | 1,912 s |
| three cells at once, 30 GB / 40 GB | 120 s / 118 s | 2,032 s / 2,016 s |
| two cells, and AddHousenumber's twin measuring only the areas that hold an address node (its step 5 measured and sorted every area of a city; the sort is stable, so the few kept come in the same order: 79 s to 30 s of its CPU) | **117 s** | 1,893 s |

Single runs; wall time varies by about 5% between equal runs.

- **2.1 times on f0** (245 s to 117 s; f1 110 s). With `--dump-state`: 272 s to 172 s, `state.bin` the same 31,695,753 rows.
  A daily-style run (Ontario's 53 cities on the 11-13 clip, with notes, parts and the tile grid): 78 s to 54 s, the
  snapshot equal and the grid files byte for byte.
- **Cells at once needed the memory work first.** At the start three at once gained 6% and cost 6-12 full collections;
  the cells' phase is now CPU-bound at two (19 of 24 threads busy with three, and no faster).
- **The sparse raster keeps SC's squares** (same corner, same square size, the points of a box row by row, west to east,
  each square's in insertion order) and holds only the squares that have a point. `-Dopenquests.verifyFast=true` on
  Bremen: every twin equal to its port on 24 map data runs. The 500M-slot refusal stays (the ports still build SC's).
- **Checks:** 87 engine tests pass (SnapshotReproductionTest and TorontoRegressionTest skip in the worktree: no
  `data/cities`, extract pruned); f0's snapshot at every step; Ontario's snapshot and grid; f0's state dump.
- **Measured and dropped:** JDK 25 with compact object headers (220 s against 210 s); a later marking start
  (`InitiatingHeapOccupancyPercent=80`: 11% less CPU, the same wall); an earlier one with 12 marking threads; the
  parallel collector (46 full collections with three cells); `MaxTenuringThreshold=0`; a fixed 35-45% young generation;
  ZGC (not in this JDK build); a way's geometry sharing its nodes' position objects (kept, no measurable change).
- **What the CPU is now** (JFR samples of a three-cell run, Java threads only; the collector's pauses are another
  330 s of CPU): quest runs 35%, the main pass over the ways 26% (two thirds of it `offer`: 140 quests asked of every
  way), the main pass over the nodes 12%, the area pass's ways 6%, map data 8%.
- **Built, exact, and taken out again: quests by key in the main pass** (an element offered only to the quests that
  name one of its keys, a bit per quest, instead of every quest's reject test). The same snapshots on f0 and f1; the
  ways' CPU 401 s to 377 s, the nodes' 160 s to 180 s: nothing net. The reject test is not where the main pass's time
  is; the filter trees of the quests that pass it are.
- **Next for the engine, none built:** (1) one read of the ways too (the area pass still decodes them a second time,
  6%); (2) AddHousenumber and AddLevelThing are a city's longest runs and 50% of the quest runs' samples; (3) the
  filter trees of the main pass (a highway is asked by some forty quests, each walking its own tree).
- **One engine or two** (f0 and f1 of the rehearsal, the pause target set): one engine with two cells at once, the
  files one after the other, 243 s at 30 GB; two engines side by side with one cell each, 223 s at 22 GB each; two
  engines with two cells each, 243 s. The CPU is the limit, so **`world_cells.py count` runs one engine by default**
  (it ran one in practice: two never fit). The 1.4 times of a second engine (2026-11-07) is gone with the idle threads.
- **More checks, after the table:** Dublin and Lisboa with `verifyFast` and two cities at once: every twin equal to
  its port on 20 map data runs (Hamburg's was stopped after 17 min in the port's own AddMaxHeight, not hung).
  `SparseLatLonRasterTest`: random points and boxes against SC's raster (a city, a ten-degree cell, across the
  antimeridian, both poles, empty, coarse). On main after the merge: 93 engine tests pass, SnapshotReproductionTest
  among them (a stored extract recounted to its committed snapshot). f1 to f3 equal between the settings above.
  **Not checked: a real world file with a polar, antimeridian or open-sea cell** (the world's cut is deleted): the
  12-07 count should run its canary file first, as before.

**The cut is slow because of Docker's bind mount** (`.scratch/batch-speed/cutio.sh`, the 11-08 europe clip, 1.75 GB,
osmium 1.18 in the `name-ru-repair-osmium` image):

| | through the Windows bind mount | on the container's own disk |
|---|---:|---:|
| `osmium fileinfo -e` (one read of everything) | 19-20 s | 4.4 s |
| one region pass (`extract -s smart`, 2 outputs) | 74 s | 40 s |
| the same, `pbf_compression=none` | | 38 s |
| the same, `-s complete_ways` | | 36 s |

- osmium reads 4.5 times slower through the mount (a plain `cat` of the file: 143 MB/s, so it is the many small reads,
  not the disk), and a whole pass is 1.85 times slower. The world's cut was 262 min and its slice 74 min, both through
  the mount (with cold caches the same: 80 s against 43 s, `cutcold.sh`, a clip not read that day and the container's
  page cache dropped): **on a native disk the cut should be about 140 min**, and the slice (a 130 GB history file read through
  the mount) should gain too. Compression and the strategy are not the cost.
- **Two ways to get there, the owner's call (nothing installed):** a native Windows osmium (conda-forge has
  `osmium-tool` for Windows, to be checked; no VM, no limit of 8 outputs a pass from Docker's 43 GB), or the planet
  and the cut's outputs on the WSL disk (about 270 GB of a VHDX that does not shrink: does not fit today).
- **Beyond that, osmium itself is the limit** (40 s for 1.75 GB with most of 24 threads idle: one thread routes
  everything). A cutter in the engine's own build, on its parallel block reader (this clip's 128M nodes decoded in
  6.7 s), could cut the planet in one stage: a table of each node's files by id (about 28 GB in memory), the ways
  routed by their nodes, a second read to write. An estimate of 30-40 min against 262, not built; its risk is
  matching `smart`'s relations exactly (the bar: the same counts on the rehearsal's 16 files).
- **For the monthly history** (118 world months, each a slice and a cut today): cut the *history* file once into
  the 128 files (`extract --with-history`, as the regions' monthly history does) and `time-filter` each small file per
  month. That removes the slice and the cut from every month (5.6 h of 10.5 h). `--with-history` has no `smart`:
  relations lose member ways outside a file's box, which reached no count for a region ("Monthly history", above)
  but file borders run everywhere.
  **Measured on the Germany rehearsal (`cwcut.sh`, `diffsnap.py`): none move.** Its four files cut again from
  `germany-2026-11-07.osm.pbf` with `-s complete_ways` (0.05% smaller) and counted: every city field of all 46 cells
  equal to the smart cut's, quests and denominators (76,063,895 open); only the file's hash differs. So relations
  completed across a file's border decide no count here, and the history cut is worth a rehearsal of its own (a
  history clip cut into files and time-filtered, against a slice cut the usual way: what `--with-history` adds beyond
  `complete_ways`, all versions' nodes, is not covered by this). An estimate, not measured: the once-only cut some
  8-10 h through the mount in two stages; then a month is 128 small time-filters (several at once) and the count,
  about 2.5 h against 10.5 h: 118 months in about 12 days of machine time against 52.

**The world chain with what is built** (estimates from f0's ratio, not a world run): slice 74 min, cut 262 min,
count about 4.4 h to about 2.2 h: 10.5 h to about 8.3 h. With the cut off the bind mount: about 6 h.

## Batch engine speed-up, second round: a match cache and the level quests (2026-11-15)

Same test file, runner and comparer as the section above (Germany f0, 30 GB, two cells at once, the pause target).
Built on `batch-speed` and merged into main the same afternoon (main's engine rebuilt; 96 engine tests pass
there, SnapshotReproductionTest among them). Each step with the same snapshot.

| step | f0 wall | f0 CPU | main pass (nodes + ways) | cells |
|---|---:|---:|---:|---:|
| main (fa262f11) | 117.4 s | 1,874 s | 8.1 + 19.8 s | 70.1 s |
| the level twins keep only the nodes near a mall | 101.1 s | 1,781 s | 8.3 + 19.6 s | 53.2 s |
| **the main pass settles a quest once per tag signature** | **91.5 s** | 1,566 s | 6.2 + 10.9 s | 54.4 s |

Single runs; wall time varies by about 5% between equal runs. f1: 110 s to 86.9 s. With `--dump-state`: 187.6 s
on main (measured the same hour) to 129.8 s, the same 31,695,753 rows. **2.7 times since the engine of 11-14
(245 s).** Ontario's daily-style run shows no gain that can be told from noise: its pass was 51.7 s in today's
daily run (36 GB, main's engine) and 51.4 s recounted alone at 30 GB; the main pass in it went from 17.2 s to
13.3 s (nodes 8.9 to 5.3 s, ways 7.2 to 6.2 s) and the rest took as much longer in that one run. Only 4.6M of
Ontario's ways lie in a city and reach the quests.

**The level quests.** The task trace of the last run showed that a cell's run phase lasted as long as one run:
AddLevelThing, 1.1 s to 10.8 s of a phase of 10.8 s (f0c10), the others done by 7.3 s. Its filter (`!level and
(!location or location = indoor)`) holds for almost every node, untagged ones too, so the twin copied the map data
into a list, looked up every node's geometry by id and put all 14M positions into a grid of boxed lists, to ask a
handful of malls which points they contain. Now a node goes on only if it lies in a 0.01 degree square that some
mall's bounds touch (`NearBounds`, a set of primitive keys), tested before the filter; a node's position is the
node's own. A point outside every mall's bounds was never returned by the grid, and the order of the rest is
kept, so the result is the same. AddLevelThing's wall time over the file's cells: 82.6 s to 31.9 s; the cells'
phase 70 s to 53 s. A cell's longest run is now AddHousenumber (7.9 s).

**The match cache** (`MatchCache.kt`, `-Dopenquests.matchCache=true|false|verify`, on by default). A profile of
last night's engine (`k3.jfr`, a three-cell run from before AddHousenumber's twin) had a quarter of the Java samples in the main pass's `offer`: some 120 quests asked of
each of 23.8M tagged elements, 40% of it in SC's filter trees, 24% in the fast reject, 20% in the custom ports, 15%
in the loop. Most elements are alike in everything a filter can see, so:

- A filter's leaves are of two kinds: those that read tags only, and the *open* ones that read the clock, the
  resurvey setting or the element's timestamp (`older`, `newer`, a date tag against `today`).
- An element's **signature** is, for each tag whose key a tag leaf names (or a key regex matches), the key and the
  *class* of its value: two values are of one class when every tag leaf on that key answers the same for both. The
  classes come from asking SC's own leaves about an element holding just that tag; no leaf is re-implemented.
  `surface=asphalt` and `surface=concrete` may be one class; a house number is not in the signature at all.
- Per signature and element type each filter quest is evaluated once in three values (a tag leaf by SC's `matches`
  on the element at hand, an open leaf as unknown): false whatever the clock (not asked again), true whatever the
  clock (counted with the bits `matchVariants` gives when every variant holds), or unknown (asked of every such
  element, as before, with its dates for `--dump-state`).
- A ported custom quest is never settled as open. It is asked unless the filter its port starts from
  (`CustomQuest.necessary`, the `filter.matches(element) && ...` of each port) is false for the signature.
- Gating by position, notes, parts and the grid stay per element.

On f0: 18.5M ways have 336,774 signatures and 5.2M nodes 75,863, so 98.2% and 98.5% of elements reuse an answer;
**2.2 quests are asked of a way and 1.7 of a node, of 125 and 118**. 694 keys are named by a filter, of 14,868
seen. `fixme` is the only key with many values remembered (12,691, two classes); a key stops remembering at
200,000 values and a type at 2M signatures, and works the answer out each time past that.

**Checks.** `matchCache=verify` asks every quest of every element as before and stops at the first difference,
the `--dump-state` dates too: f0's 23.8M elements passed, and Dublin and Lisboa. f0 and f1 snapshots equal to
main's; f0's state dump the same 31,695,753 rows; Ontario's recount of 2026-11-14 equal to the snapshot main's
engine published that day, its tile grid byte for byte. `verifyFast` on Dublin and Lisboa: every twin equal to
its port on 20 map data runs (AddLevelThing 3 and 179 open there). `MatchCacheTest`: 60,000 random elements made
of the filters' own keys and values, every settled answer checked against SC's matcher at five clocks and three
resurvey settings. 96 engine tests pass in the worktree (SnapshotReproductionTest and TorontoRegressionTest skip
there).

**What the CPU is now** (JFR of f0, Java threads): the area pass 59%, the main pass over the ways 19% and the
nodes 9%, the match cache itself 2.7%. No single item is large any more: reading the ways a second time for the
area pass (`collectWays`) 7.9%, the kerb search shared by two quests 5%, a cell's way geometries 4.2%,
AddHousenumber 3% (a third of it a `HashSet<Long>` asked for every node of every area), AddIsAmenityIndoor,
AddEntrance, AddCycleway and AddMaxHeight about 2.5% each. The collector's pauses are 15.6 s of a run.
**Next, none built:** one read of the ways; AddHousenumber's set as primitives (it is a cell's longest run); the
kerb search; then the cut, which is now the larger part of a world chain.

## Batch engine speed-up, third round: one read of the ways, and node sets by place (2026-11-15, afternoon; owner: "continue engine optimisation")

Same test file, runner and comparer as the two sections above (Germany f0, 30 GB, two cells at once, the pause
target). Built on `batch-speed`, each step with the same snapshot. **The machine was not quiet this time:** another
session cut and read tile stores in Rust on all threads through the afternoon, and main's engine took 98 s to
134 s from one run to the next (it was 91.5 s at midday). So every figure below is from runs interleaved with
the engine it is held against, a few minutes apart (`.scratch/batch-speed/batch.sh`), and the CPU seconds say
more than the wall seconds.

| step | f0 wall, against the step before in the same minutes | f0 CPU |
|---|---|---|
| one read of the ways for both passes | 95.7 and 100.3 s against 109.6 and 105.9 s | 1,508 and 1,536 s against 1,700 and 1,694 s |
| a node found through a table of id stretches | 106.5 and 106.8 s against 109.8 and 110.9 s; alone, below | 1,690 and 1,704 s against 1,691 and 1,758 s |
| node sets as marks by place (the kerb search, AddEntrance, AddCrossingKerbHeight, AddHousenumber) and AddCycleway's clock-free work once | 117.7 and 99.9 s against 125.9 and 116.8 s | 1,549 and 1,572 s against 1,802 and 1,705 s |
| all of it against main (6d7ee700's engine), the other session's cuts running | 117.7 and 99.9 s against 133.9 and 127.6 s | 1,549 and 1,572 s against 1,866 and 1,911 s |
| **the same, after those cuts had ended (15:35)** | **89.5 and 87.4 s against 102.2 and 104.0 s** | 1,518 and 1,485 s against 1,796 and 1,828 s |

**About 15% less wall time and 17% less CPU on f0** (13 to 17 s of about 103 in the calmer pair; 16 to 28 s of
about 130 in the busy one). Main's 102 to 104 s in that last pair is still above its 91.5 s of midday, so the
machine was calmer, not quiet: the ratio is what these runs show, not a new absolute figure.

**Where the time was** (the midday run's phases, trace and profile: `m2-cache`, `m2.jfr`): of 91.5 s, the cells'
area runs 54 s, the main pass's ways 10.9 s and nodes 6.2 s, and the area pass reading the ways a second time
7.0 s, all of that last one before the first cell starts. In the cells the quest runs are about 450 s of about
1,040 s of CPU; the rest is map data and the collector (281 GB allocated in a run by the profile's samples;
15.6 s of pauses; marking beside the program for most of the run). With two cells at once a run takes about
twice its CPU in wall time, so CPU taken out of the cells shortens them.

**One read of the ways.** The area pass decoded every way block again to find the ways with a node in some
padded cell box (`collectWays`), looking each node up twice (its place, then its coordinate): two thirds of
its samples were that search. The main pass looks the same nodes up for every tagged way. Now the main pass's
read hands each way to the area pass (`AreaPass.citySetOf`, `collectWay`): one decode, one lookup a node, one
tag map for both. "ways" plus "area: ways" went from about 20 s to about 14 s in the paired runs. The chunks
are let go once they are one table (the first build kept them reachable through the cells, several GB more
for the collector to walk).

**A table of id stretches.** `NodeStore.indexOf` searched the blocks' first ids and then inside the block,
some 27 steps. It now reads where the stretch of 256 ids that holds the id starts (one `Int` for each 256 ids
between the file's first and last: about 210 MB for a file whose ids span the planet's) and searches the few
nodes there; a stretch is longer where a file's ids span more than 2^27 of them (OSM's do not).
`NodeStoreTest`. **A small gain, shown only when measured alone:** the main pass by itself
(`-Dopenquests.areaPass=false`), four interleaved rounds: "ways" 13.0 to 14.3 s with the table against 14.4 to
15.6 s without, "nodes" 6.6 to 7.7 s against 6.1 to 7.1 s (the table is filled there, on one thread): about
0.75 s net, 3% of that pass's CPU. In whole runs it does not stand out of the noise.

**Node sets as marks by place.** A third of the quest runs' samples were `HashMap` code, and its callers were
SC's own quest code doing one thing: gathering the node ids of some ways into a `HashSet<Long>` (an object an
id, millions in a cell) and then asking it about the map data's nodes. On a city's map data a node is known by
its place in the map data's nodes (`ArrayMapData.nodePosition`), so such a set is a mark at that place; an id
that is no node of the map data is asked of nothing by SC's code either. Each twin gives the port's elements
in the port's order and falls back to the port on any other map data:

- **The kerb search** (`fastKerbNodes` in `FastKerbs.kt`, a copy of SC's `KerbUtil.kt`, pinned as
  `helper:KerbUtil`). SC's code keeps the footway nodes in a set of whole `Node`s (hashed with position and
  tags), counts crossing ends in a map of boxed ids, removes every node of every road and path from it one by
  one and looks each up again for `barrier=kerb`. The twin keeps a byte of marks a node. SC's counts and
  removals do not depend on each other's order, which is why marks can stand for its sequence of steps.
  `-Dopenquests.fastKerbs=false` runs SC's. It was the longest task of the two cells looked at (6.6 s and
  11.1 s of wall).
- **AddEntrance**: three marks (a building's node, an incoming path's, an excluded way's). SC's code also
  offered its building filter every node of the map data.
- **AddCrossingKerbHeight**: the excluded ways' nodes as a bit a node, found once for the quest's four runs.
- **AddHousenumber**: the address nodes' ids in a `LongSet` (plain longs, open addressing, a removal closes
  its gap) in place of the key view of a `HashMap<Long, Node>`.
- **AddCycleway** is the other kind: an age quest whose four runs each filtered the roads and, for every
  eligible road, found its centre and country before looking at its tags. Its twin does what reads no clock
  once per map data (`CYCLEWAY_ROADS`: the roads with no cycleway tagging, and for each road with some what
  `hasOldInvalidOrAmbiguousCyclewayTags` decides before and after its one test of age), and places only the
  roads whose answer turns on the country.

Quest CPU over f0's cells, from the traces of the same two rounds (the engine before these twins, then with them):

| | before | after |
|---|---:|---:|
| the kerb search | 44.5 and 41.8 s | 17.8 and 18.0 s |
| AddCycleway, with its shared part | 37.6 and 36.7 s | 7.1 and 6.9 s |
| AddEntrance | 28.7 and 27.1 s | 8.8 and 9.2 s |
| AddCrossingKerbHeight, with its shared part | 24.5 and 21.9 s | 6.2 and 6.1 s |
| AddHousenumber | 36.6 and 35.3 s | 32.6 and 31.2 s |
| every quest run | 507 and 489 s | 409 and 399 s |

The cells' CPU as a whole went from 1,260 and 1,203 s to 1,017 and 1,008 s, more than the quest runs lost: the
sets were also what the collector was fed. AddHousenumber's set was a tenth of it, not the third the midday
profile suggested.

**Checks**, on the final build unless said. `same.py`: f0's snapshot after each step, f0's and f1's at the end,
equal to main's; f0's state dump the same 31,695,753 rows; `matchCache=verify` on f0 (the main pass now makes
one tag map for both passes). Ontario's 11-14 recount equal to the snapshot main published, its tile grid byte
for byte; europe-west's 11-15 recount with the daily run's settings (London, Dublin, Lisboa) equal to the
snapshot published that morning, its grid byte for byte. `verifyFast` on Dublin and Lisboa: every twin equal
to its port on 25 map data runs, and that snapshot equal to the second round's (run before the last commit to
the node table and again on the final build). New tests: `NodeStoreTest`;
`LongSetTest` (against a `HashSet` through 60,000 adds, removals and questions a seed); `NodeSetTwinsTest`: the
kerb search and the twins of AddEntrance, AddCrossingKerbHeight, AddCycleway, AddKerbHeight and
AddTactilePavingKerb against SC's own code on 400 random small map data (shared ends, closed ways, ways of one
node, nodes the map data lacks, ways with no geometry), in order and at two clocks; it fails when a rule is
taken out of a twin (tried on the kerb search and on AddCycleway). 101 engine tests, none failing, in the
worktree (SnapshotReproductionTest and TorontoRegressionTest skip there).

**What it does not show.** A quiet machine's wall time. The daily runs' gain: Ontario and europe-west were
recounted for equality, and their one pass each (49.4 s against 51.4 s at midday; 37.7 s against the published
run's 43.1 s) is on different loads. London under `verifyFast`: not run, since SC's own code takes tens of
minutes there; London's counts are held by the europe-west recount instead, which shows the same totals and
grid, not twin against port. AddHousenumber's twin is not in `NodeSetTwinsTest` (it needs building polygons);
Dublin, Lisboa and the recounts hold it. As before, no world file with a
polar or antimeridian cell (run the canary first on 12-07). The `helper:KerbUtil` pin is the hash of the
vendored copy with LF endings, not of a StreetComplete checkout (none is on this disk): if the next repin
reports it moved without a change in `KerbUtil.kt`, that is why.

**Next for the engine, none built.** The same line, `.flatMapTo(HashSet()) { it.nodeIds }`, is in twelve more
ports that run as they are (AddBollardType, AddCrossingIsland, AddTactilePavingCrosswalk, AddBarrierOpening,
AddCrossingMarkings, AddCrossingSignals, the two traffic signal quests, AddRailwayCrossingBarrier, AddStileType,
AddStepCountStile, AddEntranceReference): about 67 s of the 390 s of quest CPU left in f0's cells (bollards 13 s,
tactile paving at crosswalks 11 s, crossing islands 10 s, railway crossings 8 s). It is also in AddMaxHeight and
AddAddressStreet, whose hand-written twins run instead of the ports and would take the marks by hand.
**One rule in `port_area_quests.py` would reach the twelve instead of a twin each:** rewrite that line to a call that gives marks by place on a city's map data and SC's
`HashSet` on any other, as `CANDIDATES` rewrote the scans; the oracle and `verifyFast` then hold every port at
once. After it, `WaysCrossingUtils.groupByNodeIds` behind AddBarrierOnRoad, AddBarrierOnPath and AddCrossing
(about 46 s together; maps of boxed ids to lists of ways; a twin there has geometry to keep, so more to check). Then what the collector is fed:
decoding a block is a sixth of a run's allocated bytes, and SC's `getLastCheckDateKeys` builds its strings for
every age test. The longest runs of a cell are now AddHousenumber, AddMaxHeight and AddIsAmenityIndoor (about
30 s of CPU each over the file). The cut is still the larger part of a world chain.

## Batch engine speed-up, fourth round: the node ids of some ways as marks, by one rule in the port script (2026-11-15, evening; owner: "continue engine optimization")

The rule the section above proposed, built and merged into main. **A small gain: about 14 s of quest CPU on
Germany f0 (the twelve ports 63.5 and 60.0 s to 48.2 and 47.4 s), not the 67 s the section above named:** that
figure was the twelve ports' whole CPU, and most of it is their scans and filters, not the set. A whole run
shows 2 to 3% less wall time in two interleaved pairs, which is within what the same engine varies by.

| | third round's engine (`eng-final`) | with the rule (`eng-marks`) |
|---|---|---|
| f0 wall | 91.0 and 84.6 s | 88.6 and 82.3 s |
| f0 CPU | 1,365 and 1,319 s | 1,366 and 1,284 s |
| every quest run, CPU | 355 and 342 s | 345 and 324 s |
| the twelve ports | 63.5 and 60.0 s | 48.2 and 47.4 s |
| AddBollardType | 11.5 and 9.9 s | 4.7 and 4.9 s |
| AddCrossingIsland | 10.0 and 9.8 s | 8.0 and 7.5 s |
| AddTactilePavingCrosswalk | 10.9 and 10.0 s | 9.1 and 8.7 s |
| AddRailwayCrossingBarrier | 7.7 and 7.7 s | 6.8 and 6.9 s |
| AddStileType | 3.9 and 3.2 s | 2.3 and 2.4 s |
| the two traffic signal quests | 9.4 and 9.5 s | 9.5 and 9.4 s |

(Runs `d-final-1`, `d-marks-1`, `d-final-2`, `d-marks-2` in `.scratch/batch-speed/`, in that order, the machine
calmer than in the afternoon; the per-quest figures are thread CPU summed from the task traces.)

**The rule** (`NODE_IDS` in `engine/port_area_quests.py`): in a port, `.flatMapTo(HashSet()) { it.nodeIds }`
becomes `.nodeIdsIn(mapData)`, which gives an `openquests.NodeIds` (`NodeIds.kt`). On a city's map data that is
a bit at each node's place in the map data's nodes, plus a `LongSet` of the ids of nodes the map data lacks (a
way at the edge of the data names some), so **every id is answered as SC's `HashSet<Long>` answers it, whoever
asks**; the third round's twins could leave those ids out because their own code never asks about them, a rule
applied blind to every port cannot. On any other map data it is SC's `HashSet`. `NodeIds` has `contains` and
nothing else and is no `Set`: a port that iterates such a set or asks its size does not compile after the
rule, so a future SC change cannot be rewritten into a different result. `-Dopenquests.nodeMarks=false` keeps
SC's set everywhere.

**Not applied to a quest with a fast twin** (the script reads `FAST_TWINS` from `FastTwins.kt`): AddEntrance,
AddCrossingKerbHeight, AddMaxHeight and AddAddressStreet keep SC's line, since their ports do not run in a
count and are what `verifyFast` and `NodeSetTwinsTest` hold the twins against. The other line of
AddCrossingIsland (`{ it.nodeIds.firstAndLast() }`, asked about way ends) is left as it is. Before the rule was
added, the script was rerun on all 40 ports from the SC v64.1 checkout
(`%TEMP%\sc-v64.1`) and reproduced every file and pin; with the rule, the diff is the twelve ports, each with
one line, one import and its header.

**Checks.** `same.py`: f0 twice and f1 equal to the third round's engine; f0's state dump the same 31,695,753
rows; europe-west's 11-15 and Ontario's 11-14 recounts equal to the published snapshots, their grids byte for
byte (Ontario and one more f0 on the final build, after the last commit).
`-Dopenquests.verifyFast=true` on Dublin and Lisboa: the twelve ports have no twin, so under that switch
`nodeIdsIn` builds SC's `HashSet` beside the marks and asks both about every node of the map data, every id
of the set and every id a port asks about, and stops the run on a difference (`CheckedNodeIds`); the run
passed, with the twins equal to their ports on 25 map data runs and the snapshot equal to the third round's.
`NodeIdsTest` (four tests): every id from 0 to past the last one answered as SC's set answers it on 200
random map data whose ways name nodes the map data lacks, failing when those ids are dropped
(`KEEP_OTHER_NODE_IDS`, the test's switch); each of the twelve ports on 300 random `ArrayMapData` against the
same data seen as plain `MapDataWithGeometry` (no marks, no candidates by key: SC's path), same elements in
the same order at both clocks, each port finding something; the set of ports that hold `nodeIdsIn` is exactly
those twelve and none has a fast twin; the check that `verifyFast` turns on passes on whole sets and throws
when the lacking nodes' ids are dropped (called with its switch as an argument, so the test does not depend
on the property). 105 engine tests on main, none failing, SnapshotReproductionTest among them
(TorontoRegressionTest skips, its extract pruned).

**What it does not show.** The port test cannot fail on the dropped ids, since none of the twelve asks about
an id that is no node of the map data (the direct test does). The wall gain is not separated from noise.
London under `verifyFast` and the polar and antimeridian cells: as in the third round. The oracle
(`tools/sc-harness` CheckCustomQuests), which the third round's text said would hold the rewritten ports, was
not rerun: the ports are held by the tests and recounts above, not against the app's own run.

**Where the time is now** (`d-marks-2`: 82.3 s wall, 1,284 s CPU): the main pass's nodes and ways about 370 s
of CPU; the cells about 845 s (the log's cell lines), of which the quest runs are 324 s, so **about 515 s of the cells' CPU is making
map data and the collector, and no one quest is above 27 s** (the shared searches 33 s together, AddHousenumber
27, AddMaxHeight 25, AddIsAmenityIndoor 21, AddBarrierOnRoad 19, AddLevelThing 18, CheckExistence 14). More
quest twins now buy a percent each.

**Next for the engine, none built, in the order of what they could take out.** (1) What the collector is fed
and the map data's making, the 515 s: profile one cell's allocation again (decoding a block was a sixth of a
run's bytes at midday; `getLastCheckDateKeys` builds its strings for every age test) before choosing. (2)
`WaysCrossingUtils.groupByNodeIds` behind AddBarrierOnRoad, AddBarrierOnPath and AddCrossing (41 s together
now; maps of boxed ids to lists of ways; a twin has geometry to keep). (3) Small: five of the twelve ports are
age quests whose four runs each gather the same set from a filter that reads no clock; a rule that keeps such
a set once per map data and filter could take a few seconds more out of their 32 s.

## Batch engine speed-up, fifth round: a profile, and SC's pairs of positions from a plain iterator (2026-11-15, evening)

A JFR run of the fourth round's engine on f0 (`r5.jfr`, `r5-alloc.txt`, `r5-cpu.txt`, read with
`.scratch/batch-speed/jfrtop.py`: weight by the first frame that is not the JDK's), to choose what to take out
of the 515 s above. **Built from it: one patch to the vendored SC code, about 11% less allocated in a run;
CPU 1 to 5% less in four interleaved pairs, wall time not shown.**

**What the profile says is allocated** (238 GB by the samples' weights; shares of that):

| | share |
|---|---:|
| `asSequenceOfPairs` (pairs, coroutine objects, iterators), nine tenths of it under `ElementGeometryCreator.create` | 10% |
| decoding blocks (protobuf's `long[]` and `int[]` of dense nodes and their info, inflating) | about 13% |
| `LongArrayAsList.get`: a way's node id made an object (`Way.isClosed` 3.3 GB, the crossing search, AddCrossingIsland, AddMaxHeight) | 3.2% |
| `getLastCheckDateKeys`' strings | 2.8% |
| `TagMap`'s entries, nearly all from `Element.checkValidity` when a way or node is made | 2.4% |
| `hasPrefixed` (`asIfItWasnt` in LifecycleUtils) | 2.3% |

**The patch (`pairs` in `sync-sc.ps1`).** SC's `Iterable<T>.asSequenceOfPairs()` is a `sequence { }` coroutine;
its geometry code (`isRingDefinedClockwise`, `centerPointOfPolygon`, `measuredLength`, `centerLineOfPolyline`,
the area) walks every way's positions through it, some of them twice. The patched function gives
`openquests.pairsOf` (`Pairs.kt`): the same pairs in the same order from a plain iterator, the source first
read when the first pair is asked for, as SC's. SC's body stays in the file under another name
(`asSequenceOfPairsAsInStreetComplete`), and `PairsTest` holds the replacement against it (lists of 0 to 40
items, nulls, a second walk, a list changed between `iterator()` and the first pair, the end of the iterator,
as many items taken from the source). No result changes.

| f0, interleaved, with collector logs | fourth round's engine | with the patch |
|---|---|---|
| allocated, from the young collections' sizes | 215 and 215 GB | 191 and 191 GB |
| CPU | 1,479 and 1,455 s | 1,463 and 1,437 s |
| wall | 94.0 and 85.9 s | 90.3 and 98.0 s |
| young pauses | 12.1 and 11.1 s | 10.9 and 11.9 s |

(Runs `g-marks-3`, `g-pairs-3`, `g-marks-4`, `g-pairs-4`. Two pairs before, on a first form of the same change:
CPU 1,494 and 1,476 s against 1,452 and 1,396 s, wall 94.8 and 92.7 s against 94.9 and 88.7 s.) The machine
was busy again (the fourth round's engine was at 82 s an hour before and at 86 to 97 s here), so **the wall
time shows nothing either way; the allocation figure is the one that repeats.** The pairs are short-lived, so
what they cost is young collections, and the pauses did not move in a way these runs can show.

**Tried and dropped: the filter's test of an element's type.** A quarter of the quest runs' `HashMap.getNode`
samples (6% of all Java samples) sat under `ElementFilterExpression.includesElementType`, which asks a
`Set<ElementsTypeFilter>` on every `matches`. With three flags worked out once in its place, two interleaved
pairs gave quest CPU 375 and 368 s against 354 and 363 s, snapshots equal: not a gain these runs can tell from
noise, and likely the sample of the first read of an element that is not in the cache, not of the set. Not
kept: a patch to SC's code has to earn its place.

**Checks**, on the final build: `same.py` on f0 (four runs) and f1; f0's state dump the same 31,695,753 rows;
Ontario's 11-14 and europe-west's 11-15 recounts equal to the published snapshots, grids byte for byte;
`verifyFast` on Dublin and Lisboa (25 map data runs, snapshot equal to the third round's); 108 engine tests on
main, none failing, SnapshotReproductionTest among them (TorontoRegressionTest skips, its extract pruned).
`sync-sc.ps1` ran
whole against the v64.1 checkout and changed only `Collections.kt` and `SC-VERSION.txt`. **That run also
settles the third round's open point:** `helper:KerbUtil`'s pin was checked against a real checkout and holds.
The checkout at `%TEMP%\sc-v64.1` had lost its index and most files outside the quest sources (a temp cleaner,
by the look of it); it was restored with `git reset` and `git checkout -- .` at the same commit, f8a754b1, and
the harness's own untracked files in it were left as they were.

**What it does not show.** A wall-clock gain. The oracle and London under `verifyFast`: as in the fourth round.

**Next for the engine, none built.** From the same profile, by what they allocate: (1) decoding: the dense
nodes' `long[]`/`int[]` builders are a tenth of a run's bytes and the main pass's nodes and ways are 370 s of
CPU; a reader that decodes a dense block's packed fields straight into the engine's arrays, without
protobuf's builders, is the largest single piece left, and a larger change (its own oracle: the same nodes,
ways and tags from both readers on a whole file). (2) `LongArrayAsList` as a `List<Long>`: `Way.isClosed`
makes two objects a call; a patch like `pairs` or a cache of the two ends. (3) `Element.checkValidity`
iterating a `TagMap`'s entries: give `TagMap` a walk without entry objects. (4) `groupByNodeIds` (4% of Java
samples). Each of 2 to 4 is 2 to 3% of the bytes.

## Batch engine speed-up, sixth round: a cell's map data, about 6% off a run (2026-11-15, 17:20 to 19:35; owner: "fifth round of speedup", which was already merged, so this is the next)

**Built and merged: four changes to how a cell's map data is put together, every snapshot equal. On f0, in
three interleaved rounds, the cells' phase is 12% shorter (50.2 s to 44.4 s) and a whole run 6% (87.4 s to
81.9 s, 4.5% less CPU). Five more changes, all in the main pass, were built, shown exact, measured, and taken
out again: nothing net.** The build that still had those five showed 17% and 9.5% (80.0 s to 72.4 s) in three
pairs on a calmer machine, and no difference from the four alone when the two ran side by side.

**Read first, from what was on disk** (the fifth round's profile `r5.jfr`, the runs `g-*`, a new reader
`jfrtree.py`: of the samples under a function, the share of each callee):

- **About 9 s of f0's wall time here is not the engine's in a world run.** The rehearsal's f0 has no notes clip
  of its own, so the run reads the whole clip (954 MB, 2,091,648 notes) in 10.6 s on one thread before the
  passes. A world file has its own (`world_cells.py notes`): at most 166,178 notes, read in 1 to 2 s
  (`.scratch/planet/world/files/*/log.txt`). Not changed.
- **The collector is still the largest single consumer:** in `g-pairs-4`, 87 pauses, 13.4 s of 98 s, and 227 s
  of 1,437 s of CPU. What a pause copies is what survives (a cell's map data, promoted at age 1 or 2), not what
  is allocated, which is why the fifth round's 11% fewer bytes moved no pause. The flags were tried in the
  first round. Not addressed.
- **One lock:** `ScFeatures.getFeature` serializes every call into osmfeatures. The profile holds 609 waits
  for it over the recording's threshold, 24 s of threads waiting (CheckExistence's twin 10.7 s, AddPlaceName
  in the main pass 9.0 s), for 0.6% of the samples spent inside. Not built: its `getByTags` reads plain
  `HashMap`s of lazily made indexes, which is safe to read unlocked only after every index a call can want
  exists, and that needs osmfeatures' source read, not its bytecode skimmed. Worth about a second.
- A quest task's clock time was twice its thread's CPU time in `g-pairs-4`. That was the busy machine, not a
  finding.

**What stays** (all in `AreaPass.assemble` and `NodeStore`; none is an SC patch; shares are of the profile's
Java samples):

| | where the profile or the trace had it | |
|---|---|---|
| a bit per node, "tagged", asked before the search among the tagged | `NodeStore.tagsOf` for each of a cell's 15M nodes, 1.3% | |
| a cell's nodes in the order they first come, from a bit set over the file's nodes (`firstSeen`) | two parallel sorts per cell (every node of every way, then the distinct ones: 15M in a large cell), most of 3.0% | a tile's few nodes still sort: clearing a bit per node of the file would cost more |
| a way's node found at the place after the one before (`NodeStore.indexOfAfter`), else the search, when a cell looks up its ways' nodes | the loop over a way's nodes, about 1% | a way's nodes were mostly made together, so the next id is the next of the file |
| a cell's ways and geometries put into arrays by the threads that make them; node ids taken as the nodes are made | not CPU: one thread reading 2.5M pairs twice and 15M ids at random | below |

**One-threaded steps of a cell's map data** (`-Dopenquests.assembleTrace=true`, new: a log line per cell with
each step's seconds). On the large cells, before the last row above: the two lists off the pairs 0.25 to 0.68 s,
the id table 0.18 to 0.30 s, of 2 to 5 s for the whole map data. After: 0.00 s and mostly 0.05 to 0.18 s. Both
runs under load, so the steps' sizes are rough; that they are gone is not. Still on one thread: the bit set walk
(0.1 to 0.4 s) and parts of the hash order (0.2 to 0.6 s with its sort).

**Built, exact, and taken out again: five changes to the main pass.** The same next-place search for a way's
nodes in `processWays` (the profile's 4.1%); a way's place among the relations' member ways by walking both
lists instead of a search per way (1.0%); a raw coordinate taken as it is in a block of 1e-7 degrees and no
offset (a line of 1.6%); "does a note hide this position" asked once per element, not per matching quest
(0.9%); tags kept by their places in the block's string table instead of a look-up per string (about 2.5%).
Together a tenth of the samples, and in the pairs below the main pass's CPU is the same with and without them.
Why is not known. One reading, not tested: those lines are where a thread waits for memory, and the wait moves
to the next read instead of going away. They are in the history (e95f9b6c, taken out in the commit after) with
their tests.

**Timing, f0, interleaved** (`quiet6.sh` and `quietn.sh` in `.scratch/batch-speed/`: they wait until no
`tilestore` or engine runs, 50 GB is available and the load is under 25%, and note the load at each run's start).

Five pairs, the fifth round's engine against all nine changes (`q6-*`, 18:42 to 18:56). Pairs 1 to 3 on a calm
machine; before pair 4's second run something else started (load 63%), so 4 and 5 are not clean:

| pair | wall | CPU | the cells' wall | the cells' CPU | the main pass's CPU |
|---|---|---|---|---|---|
| 1 | 80.7 to 72.9 s | 1,234 to 1,169 s | 45.6 to 38.1 s | 814 to 726 s | 348 to 390 s |
| 2 | 80.8 to 71.5 s | 1,286 to 1,138 s | 47.8 to 38.7 s | 863 to 712 s | 367 to 355 s |
| 3 | 78.5 to 72.7 s | 1,264 to 1,186 s | 45.5 to 38.7 s | 838 to 728 s | 362 to 372 s |
| 4 | 82.9 to 84.7 s | 1,322 to 1,395 s | 48.6 to 44.9 s | 884 to 836 s | 365 to 478 s |
| 5 | 86.1 to 82.9 s | 1,385 to 1,370 s | 49.3 to 46.1 s | 908 to 863 s | 415 to 436 s |

Three rounds of three, a less calm quarter of an hour (`q7-*`, 18:59 to 19:12): the fifth round's engine, all
nine changes, and the four that stay:

| means of three | fifth round | all nine | the four that stay |
|---|---:|---:|---:|
| wall | 87.4 s | 81.4 s | 81.9 s |
| CPU | 1,419 s | 1,320 s | 1,355 s |
| the cells' wall | 50.2 s | 43.7 s | 44.4 s |
| the cells' CPU | 922 s | 812 s | 846 s |
| the main pass's CPU (nodes and ways) | 425 s | 438 s | 435 s |

- **The cells: 12% less wall for the four that stay (second batch), less in each of its three rounds; 17% for
  all nine in the clean pairs (46.3 to 38.5 s), less in each of the five.** A whole run: 6% less wall and 4.5%
  less CPU for the four that stay; 9.5% and 8% for all nine in the clean pairs. The two builds side by side
  (second batch): 81.9 s and 81.4 s.
- **The main pass: nothing.** In the second batch its CPU is 438 s with the five changes, 435 s without, and
  425 s in the fifth round's engine; in the first batch's clean pairs 372 s with them against 359 s. So they
  went, by this project's rule for exact changes that show nothing net.
- The build that is merged (the four, with the others' code removed) was not timed by itself: it differs from
  the second batch's third column only by code that no longer runs.
- Before these, under the planet timing's load (17:26 to 18:23), three pairs said 10% less CPU, 2% more, 3%
  less: nothing, and they are not used.

**Checks, on the merged build** (`eng-six5`; the build with all nine changes passed the same set before): f0
and f1 snapshots equal to the fifth round's engine; f0's state dump the same 31,695,753 rows; Ontario's 11-14
and europe-west's 11-15 recounts equal to the published snapshots, grids byte for byte; `verifyFast` on Dublin
and Lisboa (25 map data runs, snapshot equal to the fifth round's); `matchCache=verify` on f0; 111 engine tests
on main, none failing, SnapshotReproductionTest among them (TorontoRegressionTest skips, its extract pruned).
New tests: `FirstSeenTest` (the bit set and the sort against a plain set, both sides of the line between
them), and two more in `NodeStoreTest` (every node asked after right and wrong places; a tagged node's tags and
every other node's none). With four pieces broken on purpose, all at
once, on the build with all nine changes, five of its six new or changed tests failed (not rerun one by one).

**What it does not show.** The oracle and London under `verifyFast`, as in the rounds before. A world run: f0
is one file of the Germany rehearsal.

**Next for the engine, none built.** (1) The collector: fewer objects that outlive a pause, which means a
cell's untagged nodes not as 15M `Node` objects (made when asked for), perhaps a quarter of what a cell
promotes (a guess from object sizes, not measured); SC's code iterating `mapData.nodes` decides whether that
is possible. (2) What is still on one thread in a cell's map data (above), and whether three cells at once
gain now that a cell's one-threaded part is smaller (they did not in the first round). (3) The lock above.
(4) The main pass is 30% of a run's CPU and none of this round's guesses moved it: measure it by itself (a
run of only the node and way passes, repeated) before another change there; the dense-node decoder belongs
after that measurement, not before. (5) `Way.isClosed`, `Element.checkValidity`, `groupByNodeIds`: bytes, and
bytes have not bought time.

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

## The place page: one page for a city and each of its parts (2026-11-16, evening; owner: "the place page comes first")

**Status: preliminary (owner, 11-16 late evening).** Accepted and merged, but the design itself has not been reviewed by
the owner; the direction (one page per place, places processed down to neighbourhoods) is confirmed as right and
valuable, the details below are a first draft.

Built on branch `place-page` from the product review's answers (`design/product-review-2026-11-16.md`).
The city view is now the place page of "A neighbourhood is a place", for the 147 cities and their 4,214 parts.

- **One renderer, fed by a series.** A city reads `history/<city>.json`; a part reads its 35-day file
  (`history/<city>/<part>.json`) made whole on load: the city's `meta` on the same dates (so version breaks
  show on a part too) and every quest the city has, 0 where the city counted it and the part had none, null
  where the city did not count it. Ticks, pins, the table, "Only quests the app had then" work on both levels.
- **Links.** `?city=X` and `?city=X&part=<placeId>`. A `?place=<id>&in=` link to a counted place (the widget's,
  and the place browser's) opens the same page and is rewritten to `?city=`. Old hash links still work.
- **Head:** the chain from the name layer (`cities.json` now carries each city's `place` and `in`; a part's
  file has `in`), filled once the region file is in, so the page paints from the series alone. London, GB is
  the one city without a row: its chain stops at the country text.
- **Tiles:** open quests with the net change in words ("9 fewer than yesterday": edits, aging and new map
  data together, since solves are not counted); need mapping; aged; **the 4-week change split mapping vs
  resurvey** (a part, younger than 4 weeks, says "Since Oct 27"); **the quest type with most open**. The
  density tiles are gone from the page; density stays in Compare.
- **Chart:** opens on the last 90 days (`RECENT_DAYS`); "All since 2017" is `range=all`, hidden where the series
  is shorter (parts). The window is one slice of the series, so chart, sparklines, legend, breaks and gutters agree.
- **Steps:** one quest type moving by a tenth of the total or more (and at least 500) between two counts gets a
  faint band and a line under the chart saying size and quest; consecutive steps of one quest in one direction
  are one note; the largest four. What a step *is* is said only where known (`KNOWN_STEPS` in `app.js`: Toronto's
  2026-05 address import; the 2019 rise is not confirmed, so it is only sized). Across the 147 cities, 125 such
  steps exist, nearly all before the 90-day window, mostly house numbers in 2019 and power poles.
- **Table:** counted quests with nothing open fold into one line, "N quest types done here", opened on a click.
  On a phone the trend, aged share and class name give way and chips wrap, so the table fits from 320 px.
- **Children:** the city's parts from its newest snapshot (name, kind, open over the ticked quests), each a link
  to its page, the current one marked on a part's page; then the name layer's places inside. No per-child change:
  that would be a file per child (`latest/<parent>` does that, later). **Loaded when the reader nears them**: the
  snapshot is the region's (Ontario's is 2.4 MB, 249 KB gzipped, against Toronto's 37 KB history). The chain's
  region file loads at once (15-80 KB gzipped; the largest a counted city sits in, France's, 79 KB).
- **Wording:** "fewer than the day before", not "yesterday": the counts can land two days late. The 4-week tile
  says "across an app release" when a version break falls inside it.
- **Navigation:** three tabs, Places, Compare cities, Map. The place browser (countries, regions, the ask card)
  is reached from "All countries" in the chain and from the city sheet ("Every place, by country").

Checked with `.scratch/place-page/drive.py` (every link shape and level at 1200 and 390 px: no page errors, no
sideways scroll except Compare's table, which scrolls the same on main; city-states and a Berlin part included),
`clicks.py` (range, fold, ticks and pins on a part, crumbs, sheet, tabs, a widget link then Map's "find a place")
and `fixtures.py` (the test fixtures through `?data=`, one snapshot and no parts; dark mode). **Observed, not a page bug:** 1,715 of the 4,214 part series do not move
at all over their 17 days, Casa Loma's 1,105 among them; they are the small and quiet ones (200 of Toronto's
218 move, and every large one does).

## Release 1: the world day, designed (2026-11-16, late evening; owner: "lets push towards first release")

Release 1 publishes a count of every place in the world for every day from 2026-11-01, each day every quest
(the rule in "Don't"). The pieces, in the order they are built. Nothing below is built unless it says so.

**Where a day runs.** Inside the planet store's daily run (`tools/stream/planet_store_day.py`), between `update`
and `loc advance`: there the node file still holds D-1 and both generations' tile indexes exist (`compact` keeps
only the newest generation readable, so the day must be read before it). The store and the world state move
together; the store never runs ahead of the state.

**Step 1, the seed: built, being checked.** `world_cells.py storecut` reads each plan file's padded box from the
store (`tilestore read`, ring 0, stamped with the store's day) into `cut/`, so `notes`, `count --state` and `report`
run unchanged. `tools/stream/store_lock.py` holds the store while it is read (HOLD; the daily run takes no day
while it exists, and keeps RUNNING while it works). The reader's blocks are bounded by size too (a blob must stay
under 32 MiB; byte-identical output on the clip's rectangles). Checks, in order: `tools/stream/storecheck_cities.py`
(the 32 European cities read from the store against the same day's clip, row for row), then two world files at
full size (f0, the most nodes; f19, the widest box: time and peak memory), then the seed at 11-01 against the
published 11-01 snapshots.

**Step 2, tier 1 for the world.** `world_state.apply` as it ran on 11-09..11-14, but with the store's node file
read-only (a `DenseLocations` that never saves: the store's `loc advance` moves the file). The diff read in Python
was two thirds of a day's 8-14 min; it is read once for both tiers.

**Step 3, tier 2 for the world.** `tier2.cover` as on Europe (the delta form: the same rectangles recounted on D-1
at D-1's clock and on D at D's, only the recount's own changes applied), with four changes for the planet:
- the cover in one global grid of 50 m cells, vectorised, not per city: `near_idx` loops over every city's box per
  point, which is 2,244 boxes for each of millions of changed nodes;
- changed ways' old refs, and changed relations' member ways, from the store's generation D-1 (a new `tilestore`
  lookup by way id through the way pair index), so no way index of our own. `NO_WAY_INDEX` (today's refs at
  yesterday's places) was measured equal on Europe's five days, but it has no refs for a **deleted** way, whose
  key then also misses the old-row lookup: its area-quest rows would stay. The lookup at D-1 covers both. Ways
  holding a changed node are left out (the same measurement; a tier-1 row of an untouched way can stay up to about
  1 m from its true point, which moves no count unless it crosses a cell edge);
- the rectangles split at cell edges, each a city with its cell's time zone and no country codes (gated by
  position, as every cell is); map data by `tilestore read --gen D-1` and the newest generation, ring 300 m.
**Checked (22:00):** after `update --prune-pairs` the generation before reads byte for byte as before the update
(the clip store, diff 5175), so both dates are readable until `compact`.
**Measured (`.scratch/manyrects/probe.py`, the clip store, random 150 m rectangles in inner London, 300 m ring,
area pass on, while the store's catch-up ran):** 100 rectangles: engine 6 s (pass 4.7); 1,000: 17 s (pass 14.4,
5.9M nodes read); 10,000: 157 s (pass 148, 57.9M nodes read over 9.7M in the PBF). So about 14 ms a rectangle
city on top of the map data, linear from 1,000 to 10,000 at the same data; whether it grows with the run's total
data is not measured (grouping by plan file bounds that). The store's read cost 97 s for 10,000 cities against
12 s for 1,000 over the same tiles: it opened each city's boundary file. A city's box is now read inline
(`"box"` in the cities file; `tier2.write_cities` writes it): 1.8 s, the same bytes. Still unknown: how many
rectangles a planet day makes.

**Step 4, notes and ageing at the clock.** Ageing is the state's dates against the clock (step 3 of the stream,
exact on Europe). Notes are not handled yet: `apply` has no notes clip, so a row keeps the seed's hidden flag until
its element is edited, and the note quest itself is not counted. Each day: notes opened and closed between D-1 and
D (the daily notes dump) set and clear the hidden flag on rows at the note's exact position, and the note quests
are counted from the dump at the clock.

**Step 5, counts per place from the state.** The seed's snapshots come from the engine; a day's must come from the
state. **The engine assigns places, not a second test in Python:** a test on dumped positions already disagreed on
Dublin's boundary (1 cm rounding), and a million polygons would multiply that. So the state dump carries each
row's places as the engine found them (`--dump-state` extended, or a sidecar), decided **before** the seed runs,
since a seed without them is a second planet count. A day's rows (tier 1 and the two rectangle recounts) come with
their places the same way; per-place counts move with the day's changed rows and the rows whose date comes. Also
the aged split and the three resurvey settings, as the engine's snapshots carry them.

**Step 6, the checks every day.** The gate is like for like: Europe's 32 cities from the world state against
today's engine on the Europe clip of the same instant (11-02 to 11-16 are pinned; 11-01 is cut from the history
file at 11-01T00:00Z while it is on disk, step 7). A day that misses the 0.1% bar stops the run, as the store's own
check does. The 147 published city snapshots are reported beside it, not gated: 11-01 and 11-02 are v64.0, and
Canada's and Germany's extracts are not at 00:00Z (the 11-08 report's Regina -0.42% was that).

**Step 7, catch up and publish.** The store cut again at 2026-11-01T00:00Z from a new history file (and, from the
same file, the Europe polygon at 11-01T00:00Z for step 6's day one) and held there (HOLD) until steps 2-6 exist, then store and state together, one day at a time, to today; then daily. Publishing:
place data on the R2 subdomain (DESIGN, "Place statistics for the whole world"), its DNS step the owner's.

**The world publishes the default resurvey setting only (the owner, 2026-11-17).** The engine dates settled
matches and area quests at the default setting only, so the 0.5 and 2 counts would drift from the seed; the site
shows the default. The world's counts and its daily gate are the default setting's; city snapshots keep all three.

**Before release 1, two rules.** Steps 2-6 are built and held against a clip-sized world-mode store first
(`.scratch/tiles/store-rsw`, the Europe clip with cells as cities), where every day has a whole count to compare
row for row; only then the planet. A StreetComplete release before release 1 means a reseed at the store's day
(the state is one quests file's).

### What tier 2 must recount, from the code (2026-11-17, overnight; fork E of the release-1 build)

Tier 2 marked a changed closed way's or multipolygon's whole box; on planet day 5172 the largest was 2.7M km2, and a
25 km2 cap lost 69% of tier 2's own cells on the Europe day. The 40 area quests (`engine/src/main/kotlin/ported/`,
paths below under `quests/`) were read for what OTHER elements can change whether an element is a quest, and how
far that reaches. Only three things read a polygon's inside for other elements; everything else is the element's
own quest at its own quest point, or happens on vertices and segments the outline marking already covers.

| quest (file) | what else decides it | reach | how the cover catches it |
|---|---|---|---|
| AddIsAmenityIndoor (`amenity_indoor/AddIsAmenityIndoor.kt`) | a building (`building and building != roof`) holding the node | the building's inside | **container**: a changed building's whole box; the changed node marks itself |
| AddLevel, AddLevelThing (`level/AddLevel.kt`, `AddLevelThing.kt`, `LevelUtils.kt`) | a mall or station polygon (`shop ~ mall\|department_store`, `aeroway = terminal`, `railway = station`, `amenity = bus_station`, `public_transport = station`) holding the node; elements with `level` inside it make it multi-level | the polygon's inside | **container**: its whole box; a changed `level` element: R_CONTAINED (100 m) around it |
| AddHousenumber step 5 (`address/AddHousenumber.kt`) | an addressed area that is no building (`nonBuildingAreasWithAddressFilter`), or any area way with an address node on its outline (`areasWithAddressesOnOutline`), holding the building's centre | the area's inside | **container**: its whole box. The outline case needs to know the vertices' tags: from the diff for changed nodes, or from an address-node index (`address_nodes`, not built) |
| AddHousenumber steps 1, 4 | address nodes on the building's outline or inside it | the building's inside, for the building's own quest | the building's quest point (centroid); a changed address node: R_CONTAINED around it, for the building holding it |
| AddHousenumber step 2 | a relation that is no multipolygon, with an address, holding the building | membership | **new**: such relations' member ways (lines and centroids) |
| AddHousenumber, AddIsAmenityIndoor step 3 | the map data's bbox: a building not completely inside it is no quest | the recount's ring | the recount's own limit (300 m ring), not a changed element |
| AddChargingStationSocket (`socket/AddChargingStationSocket.kt`) | `man_made = charge_point` nodes inside the station way | the station's inside, for its own quest | its quest point; a changed charge point: R_CONTAINED around it |
| AddAddressStreet (`address/AddAddressStreet.kt`) | `associatedStreet`/`street` relations holding the address; `addr:interpolation` ways' vertices | membership; vertices | the relation's member ways and **new: its member nodes**; interpolation ways by their segments |
| AddSummitCross, AddSummitRegister (`summit/SummitMarkingsUtil.kt`) | `sac_scale` hiking paths and **`route = hiking` relations** within 10 m of the peak | 10 m of the line | changed paths by their segments; **new: hiking routes' member ways** (tier2.WANTED_REL left them out: a real gap) |
| ferry quests, AddMaxWeight (`ferry/*.kt`, `FerryUtils.kt`, `max_weight/AddMaxWeight.kt`) | `route = ferry` relations: the relation is the quest, its member ways are not | membership | the relation's member ways and their quest points |
| AddMaxHeight (`max_height/AddMaxHeight.kt`, `MaxHeightUtils.kt`) | bridges (and `building = roof`, overhead pipelines) crossing a road, road and railway vertices | the crossing: `intersects` is outlines crossing (`util/math/ElementGeometryMath.kt`), not an inside | segments |
| AddEntrance, AddEntranceReference (`building_entrance*/`) | building outline vertices, incoming and private footways' vertices | vertices | segments |
| AddKerbHeight, AddTactilePavingKerb (`osm/kerb/KerbUtil.kt`) | footway vertices, `barrier = kerb` ways' vertices, crossing ends | vertices | segments |
| AddCrossing, AddBarrierOnPath, AddBarrierOnRoad (`osm/WaysCrossingUtils.kt`, `DetectWayBarrierIntersectionUtil.kt`) | shared vertices and their neighbours' places | vertices and the next segment | segments |
| AddCrossing\*, AddRailwayCrossingBarrier, AddTactilePavingCrosswalk, AddTrafficSignals\*, AddStileType, AddStepCountStile, AddBollardType, AddBarrierOpening, AddMaxHeight's nodes | the vertex sets of included or excluded ways | vertices | segments |
| AddOneway (`oneway/AddOneway.kt`) | roads meeting the way's end vertices | vertices | segments |
| AddForestLeafType (`leaf_detail/AddForestLeafType.kt`) | its own area (under 1 ha) | itself | its quest point (centroid) |
| AddRoofShape, AddCycleway | the country at its own centre | itself | its quest point |
| AddBicycleIncline | its own length (under 200 m) | itself | its segments |
| AddAmenityCover, CheckExistence | nothing (getFeature of the element) | itself | itself |

**The rule, in `tools/stream/world_tier2.py`** (`container_kind`, `contained_kind`, `wanted_relation`):
- a changed closed way's ring (new at D, old at D-1) or a changed multipolygon is marked **whole** if its tags make it
  a container (above), or its box is at most `SMALL_BOX_KM2` (0.25 km2: cheap, and a planet diff's deletions carry no
  tags, so a deleted building is still boxed); otherwise by its outline and its **quest points** (the half-length
  point and the polygon centroid, as SC places a way's or area's quest), which every changed line now gets;
- the old ring's tags come from `old_tags(kind, id)`; without it the new tags stand in (logged as unknown);
- a changed node that a container reads (an address, a `level`, a charge point) marks `R_CONTAINED` (100 m) around
  its old and new place, for the container's quest point; so does a deleted node no changed way held (its tags are
  gone, and such deletions are mostly points of interest);
- relations: multipolygons (member lines, boxed only as containers), street relations (member ways and nodes),
  ferry routes, **hiking routes**, **addressed relations that are no multipolygon**;
- `CAP_KM2` (5,000 km2) is only a logged safety net: no container comes near it.
- **The merge changed too** (`merge_rects_overlap`): tier2.merge_rects counted two padded boxes' sum, so a long strip
  grew one 50 m run at a time across a polygon's whole inside (a 7 km outline became its 52 km2 box). The gain now
  counts what the two padded boxes share, with 0.1 km2 of slack (a rectangle city costs the engine about 14 ms):
  the same outline is 5 rectangles, 8.6 km2.

**Not exact yet, and what makes it exact:**
- **Old tags.** A planet diff's deletion has no tags and no refs, and a modification only its new tags. A big way
  or multipolygon that stops being a container (a 2 km2 campus losing its address, a station polygon deleted) is
  marked by its outline only. Fix: `tilestore ways` returning each way's tags at D-1 (the payload has them; a small
  Rust change), passed as `old_tags`; the same for relations through the relation store.
- **Addresses on an area's outline.** Without an index of address nodes, only addresses changed that day are seen.
  Fix: a sorted array of every address node id, built once from the store and moved by the diffs (`address_nodes`).
- **Containers wider than R_CONTAINED.** A changed address or `level` node inside a building or mall whose quest
  point is more than about 100 m away (plus a cell's padding) is missed. Fix: look the containers up (the store's
  tiles at the node), or measure how often it happens on a real day before choosing a radius.
- **A multipolygon's old members** are not known (only its new ones, by `member_refs`); its old rows cover its own
  quest.
- **A changed ring of a container multipolygon.** An untagged closed way is usually a multipolygon's member; when
  only the way changes, the relation is not in the diff, so a big building or mall multipolygon's changed outer ring
  is marked by its outline. Fix: the relations holding a changed way, with their tags (a reverse lookup in the
  relation store, Rust).

**Measured (2026-11-17, night).**
- **Europe day, diff 5175, europe-west's three cities, tier2.cover against the world cover on the same inputs**
  (`WORLD_TIER2_EUROPE=1`, log `logs/world-tier2-europe-rule.log`): of tier 2's 103,785 cells, 7,401 are justified
  by the rule (not from a box, or from a box the rule marks) and **0 of them lie outside the rule's rectangles**.
  96,384 came only from boxes the rule leaves to their outline; 81,470 of those fall outside its rectangles: 80,181
  from one `place = island` multipolygon (no area quest reads an island's inside), 1,277 from untagged closed ways
  (multipolygon member rings: safe unless their relation is a container, the gap above), 15 from
  `landuse = greenfield`.
- **Planet day 5172**, world plan, the 11-08 seed's rows, the node file read only (`.scratch/world-tier2/5172-rule/`,
  log `logs/world-tier2-5172-rule.log`), against fork A's run with the 25 km2 cap:

| | fork A (cap 25 km2) | the rule |
|---|---|---|
| marked cells | 10.0M | 5.31M |
| rectangles | 52,128 | 128,544 |
| km2 per date | 217,299 | 101,651 |
| rectangle km2: median, 90th, 99th percentile, largest | 0.19, -, 50, 1,207 | 0.49, 1.8, 4.9, 52.5 |

  626,044 closed boxes: 610,982 small and marked whole, 141 marked whole as containers (115 addressed areas, 18
  buildings, 6 malls or stations, 2 areas with an address on the outline), 14,921 by outline (their boxes 6.4M km2
  together; 5,850 of them with old tags unknown, 11,701 ways with outline addresses unknown); 9 over the safety cap,
  none a container, the largest 2.7M km2. Relations marked: 14,386 multipolygons, 330 hiking routes, 128 streets (2,659
  member nodes), 1 ferry, 1 addressed; 1,436 wanted relations had no member geometry (the store lookup gives it).
  Contained nodes: 17,455 addresses, 1,865 `level`, 80 charge points, and **390,467 deleted nodes no changed way
  held**, which mark 965k of the 5.3M cells: most are vertices of deleted ways, whose refs a planet diff does not
  carry, so with old refs from `tilestore ways` (generation D-1) they drop out. Time: read the diff 123 s, old rows
  63 s, cover 146 s, rectangles 44 s, the engine's files 177 s.
  **The trade:** half the area, but 2.5 times the rectangles, since outlines no longer swallow their boxes; at about
  14 ms a rectangle city that is about 30 min of engine per date against 12, on top of half the map data. The slack
  (`MERGE_SLACK_M2`, 0.1 km2) is the knob: it also sets how wide a non-container polygon may be before its inside is
  no longer filled (about 2 km at 0.1 km2).

### The world day, rehearsed on the Europe clip (2026-11-17)

`tools/stream/world_day.py` (prepare before the store's update, finish after it; `run` for a rehearsal; `check`
against a whole count) and `tools/stream/world_europe_r1.py` (the driver; out dir `.scratch/r1/eu/` of the worktree
it ran in). The Europe clip of 11-09 as a world plan: 16 files, 57 cells, 15,875 places as parts plus the 32 cities'
own outlines (`osm-<city>`); a clip store cut at 11-09 and moved by the planet's day diffs 5172 on (polygon mode);
a sparse node index; the seed counted from the store (`storecut`, `count --state` with parts, 947 s at 8 GB a file):
50,273,232 rows, 16,682 place sets. Each day D is held against a whole count of the same plan from a fresh store cut
of D's Europe clip, with the seed's notes clips on both sides.

**Day 0 (the seed through the stream's own counting): exact.** 0 of 36,795,912 (element, quest) groups differ; 0 of
631,304 counts per place and cell (note quests by the engine included); all cells' open quests 29,983,203 both.

**Days 11-10 to 11-13, streamed:**

| day | groups differing (of 36.8M) | at the default setting | 0.5 / 2 settings only | outside the clip's polygon | the 32 cities' counts differing (of 5,306) | all cells open, whole / stream |
|---|---|---|---|---|---|---|
| 11-10 | 1,093 | 15 | 831 | 247 | 1 (by 1) | 29,989,003 / 29,989,161 |
| 11-11 | 2,390 | 45 | 1,754 | 591 | 3 (by 1-2) | 29,993,706 / 29,994,157 |
| 11-12 | 3,551 | 66 | 2,579 | 906 | 7 (by 1) | 29,999,555 / 30,000,246 |
| 11-13 | 4,489 | 83 | 3,118 | 1,288 | 7 (by 1) | 30,005,680 / 30,006,664 |

Rows are compared at the clock: a date the stream kept that has come counts as the open, aged match the whole count
writes (the same count). By cause:
- **Outside the clip's polygon** (1.6-7.5 km out): the moved store keeps edge ways a fresh extract of the clip drops,
  as the planet store's daily check found. Not the stream; it is also most of the all-cells difference.
- **The 0.5 and 2 settings only:** quests the seed did not date at those settings come open there (CheckExistence and
  other quests the match cache settles: `Engine.offerInZone` dates only `!isSure` matches; area quests are dated at
  the default only). The default setting, which the site shows, is not touched. Fix in the engine (date settled
  matches too, area quests at all three settings) or publish the default only.
- **At the default setting**, growing by about 20 a day:
  - most are a quest point moved by under a metre on an untouched way whose node moved (tier 1's known limit; no
    count changes unless it crosses a place's edge);
  - AddRoofShape of building multipolygons whose member way changed while the relation is not in the diff: the cover
    marks the outline, not the relation's quest point (Göteborg -1 from day one);
  - AddMaxHeight of roads under a changed bridge whose quest point lies outside the bridge's rectangles: the recount
    takes elements by centre, so a road crossing a rectangle is not recounted (Praha -2, Moscow -1);
  - a few recount-vs-whole disagreements on touched keys inside rectangles (AddMaxHeight again).

**Time per day** (the clip's share of the planet diff: about 42k nodes, 12.6k ways): read the planet diff 150-190 s,
old ways 1-4 s, store update 45-60 s, cover 2-3 s, rectangles 2-3 s (2,700-3,000 rectangles, 1,600-1,900 km2),
engine files 15-21 s, tier 1 215-245 s (16 engine runs, one per plan file), tier 2 reads 19 s, tier 2 engine
240-260 s, delta 31-34 s, notes 165-185 s, counts and note quests 200-285 s (16 engine runs): 20-23 minutes.

**What blocks the planet:**
1. **Loading parts per engine run.** Tier 1 and the note quests run once per plan file (all of a world's parts in one
   run do not fit: Europe alone has 502,597 part entries, and 8 GB ran out); a note-quest run is 120 s of which the
   pass is 0.2 s, the rest loading the file's 63k outlines. At 128 planet files that is hours a day. Needed: the
   engine kept running with its parts loaded, or the note quests as state rows with their places (the engine writes
   them at the seed; a day recounts only the cells whose notes changed).
2. **Notes' hidden flags over every row**: 165-185 s for 50M rows in one Python thread; the planet's 2 billion need
   the rows near changed notes found by position, or the files in parallel.
3. **The two cover gaps above** (a relation's quest point when a member way changed; roads crossing a rectangle):
   both need the elements whose geometry meets the marked cells, from the store, added to the cover.
4. **A rectangle city's parts index** spanned every part's whole box (a country: 512 x 512 cells per rectangle) and
   ran out of heap at 8 GB on 28,703 rectangles; now clipped to the city (engine `PolygonIndex(clip=)`, same answers).
   The planet's 128,544 rectangles still need their runs grouped (per plan file) and measured.

### Tier 2's two cover gaps closed (2026-11-17, afternoon; fork P3 of the release-1 build)

The rehearsal's default-setting residues (above) came from what the day's diff does not show. Built:
- **`tilestore context`** gains `--rel-geometry` (each asked relation's member ways from its relation store blob),
  `--vertex-ways` (every way an asked node is a vertex of, with its geometry, from the node's tile) and `--crossing`
  (the ways with a tag key whose segments cross given segments, with their geometry, from the tiles the segments
  cross). Exact against the 11-12 clip: 300 relations' member ways, 799 of 799 vertex ways, 0 of 203 crossings missed.
- **`store_context.DayContext`** asks them at D-1 (before the update) and at D (after it): the relations holding a
  changed way (their member lines marked, a container boxed, any other by the box rule) and their old rows; the
  untouched ways a moved node is a vertex of (their quest points at D-1 and D); the roads crossing a changed
  `over_road` way (AddMaxHeight's `bridgeFilter`) and the bridges crossing a changed road, each crossing a box from the
  road's quest point to the crossing (`crossing_box`), so one rectangle city holds the road's quest and the bridge (an
  area's map data is the ways with a node in its padded box).
- **`world_day` now asks the store context** (G's day never did, so F's container boxes never reached its cover).
- `_quest_points` weighs longitude at the line's own latitude (a fixed 0.63 put a 15.7 km road's half-length point at
  55.6 degrees 700 m off).

**The rehearsal again** (`.scratch/p3/rerun.py` in fork P3's worktree: G's 11-09 seed counts, a fresh clip store and
node index, each day checked against G's own whole count; 12 GB heap), default-setting groups different:

| day | G | P3 | the 32 cities' own counts different (G, P3) |
|---|---|---|---|
| 11-10 | 15 | 3 | 1, 1 |
| 11-11 | 45 | 4 | 3, 1 |
| 11-12 | 66 | 9 | 7, 4 |
| 11-13 | 83 | 9 | 7, 4 |

Every "different" from a moved node and the Praha and Moscow bridges are gone; the residue no longer grows. Left
(11-13), each traced:
- **5 groups, relations changed by their tags alone** (2213778, 2213779 Salzburg and 3252407 Göteborg on 11-08,
  `building:levels` added; 5328319 London, 3458546 München on 11-12): the rehearsal's `clip_keep` keeps a relation
  only with a kept member, so a tags-only change is dropped before the cover. A rehearsal artifact: the planet runs
  without `clip_keep`. Fix if the rehearsal is rerun: keep the diff's relations the D-1 store holds.
- **1, w1577774915 AddHousenumber**: the order effect traced on 11-14 (DESIGN, "The one tier-2 row left, traced").
- **3, not traced: r13409862 AddRoofShape and AddBuildingLevels** (a TUM building multipolygon whose members were
  replaced on 11-12) and **w684910576 AddMaxHeight** (a 15.7 km Moscow trunk road changed on 11-11). Both lie inside a
  rectangle on their day, the store's copies are right (the relation's new member way; the road's nine crossing
  footway and road bridges, each within 10 m of its box), the engine's map data rule includes them (a way with a node
  in the box comes with all its nodes), and yet both recounts lack the quest the whole count has. Needs an engine
  reproduction on that day's read (`days/<D>/t2/new.osm.pbf`).

**Planet day 5172's cover** (answers only inside Europe, from a clip store cut at 11-07; outside it the cover falls back
as before): the rule 128,039 rectangles, 101,595 km2; with F's answers 128,260, 101,887; with P3's too 128,796,
102,475 km2 (+0.6%). Inside Europe P3 added 486 holding relations (7,947 member lines), 3,266 moved-node ways and
1,024 road-under-a-bridge boxes. The planet store holds every element, so the planet adds these everywhere: not
measured; about 1.8% of 5172's changed ways lie in the clip, so a plain scale-up would be tens of thousands of boxes
and lines, mostly small. A day's store questions took about 2.5 min in the rehearsal (D-1 15 s, D 115-135 s).

### Tier 2 per plan file, measured on the planet (2026-11-17, evening; blocker 4)

`world_day.rect_rows` recounts the rectangles group by group instead of in one engine run. A group is one plan
file's rectangle cities, since their cells share the file's parts. A file whose padded area passes
`WORLD_T2_GROUP_KM2` (default no cap) is cut further. Each group is read from the store on its own, and
`WORLD_T2_WORKERS` engines run at a time (default 1). The dumps are ingested in group order, D-1's before D's, so
the place-set numbering does not depend on which engine ends first.

**Exact:** on the rehearsal's 11-13 (clip store generation 4, the day's own cities and parts), 16 groups give the same
5,668,905 rows as the one run, with 0 different (`.scratch/rectgroups/exact.py`). Grouping took 145 s at 4 workers,
the one run 157 s.

**End to end:** the rehearsal's day 11-10 through `world_day.run` with grouping (16 groups, 4 workers, both
reads), from the same 11-09 seed, against the ungrouped run of that day: every state row and all 628,364 counts per
place and quest equal (`.scratch/rectgroups/e2e.py`). Tier 2's engine time there: 245 s.

**The planet, one date** (`.scratch/rectgroups/measure.py all --workers 4 --heap 8`): planet day 5172's rectangles
under the big-polygon rule (128,544 in 127 files, 101,651 km2, 289,864 km2 padded by the 300 m ring), read from
the planet store's generation 15 (11-17) with the planet parts cache (1,069,679 outlines, 5.8 GB, built in 870 s).

| | |
|---|---|
| wall time, 4 engines at a time | 1,220 s |
| reads, one at a time beside the engines | 643 s in all; 7,961 MB of map data |
| engine time summed | 4,684 s (passes 3,603 s, the rest startup: about 20 s an engine) |
| peak heap of the largest group | 6.7 GB (f11, 2,441 rectangles, 287 MB of map data) |
| the most rectangles in one group | f116, 10,286, north Norway: 36 MB of map data, 168 s with others running, 82 s alone |

So **tier 2 on a planet day is about 40 minutes for both dates at 4 workers**, and 8 GB heaps fit with no cap. The
engine's cost follows map data and rectangle count, not area: f116 is 10% of the padded area and 0.5% of the map
data. Not measured: 6 or 8 workers (the engines already use every thread each, so 4 to 1,220 s is close to the
summed time over 4), or the cover's extra P3 boxes the planet would add outside Europe.
