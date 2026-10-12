# Prior art

Collected 2026-10-11. Searched GitHub, Codeberg (by name, not code search), the OSM wiki, OSM diaries and
the StreetComplete issue tracker for: "StreetComplete statistics", "open quests per city", "quests left",
"quest density", "ElementFilterExpression" ports, "sc-quest", ohsome / tag-completeness dashboards.
Claims marked *(unverified)* were not confirmed this session.

**Bottom line:** nobody publishes *open* StreetComplete quests per city *over time*. starsep comes closest,
for Poland, with today's numbers only. The app's own Kotlin is the best source of filters; nobody has
ported its filter language elsewhere.

## Closest work

- **starsep/StreetCompleteStats**: https://github.com/starsep/StreetCompleteStats, live at
  https://street-complete-stats.starsep.com/.
  - Kotlin + GeoDesk over a Poland `.gol`. 25 quests, filters ported by hand to GeoDesk syntax.
  - Covers every `admin_level=8` city over 20k people and shows solved/all per quest per city.
  - Rebuilt daily; last commit 2026-10-11.
  - Gaps:
    - It selects by the city's **bounding box, not its polygon**.
    - It only shows today's numbers.
    - It covers one country and a hand-picked quest subset.
  - Its gh-pages branch holds about 1,168 daily snapshot commits since 2023. That is a time series nobody
    has charted, and it shows the daily-snapshot approach holds up.
  - *Our edge: polygons, full quest set taken from the app, history, Ontario.*
- **jmizv/sc-quest-stats**: https://codeberg.org/jmizv/sc-quest-stats (mirror at zff.dev).
  - Three hand-written Overpass queries per quest, kept in JSON, giving a static `QUESTS.md` with a
    "Pending" (= open) column.
  - The queries aren't tied to one city.
  - No time series. Inspiration, not reusable.
- **StreetCompleteness**: https://streetcompleteness.haukauntrie.de/.
  - Completion percentage for a few chosen quests in a city you type in. Closed source.
  - It inspired starsep.
  - Returned HTTP 500 on 2026-10-11. *(Unverified whether it's dead or just down.)*

## Different question (solved, not open)

- **wielandb, "Some StreetComplete-Statistics"** (OSM diary, 2022) / StreetCompleteNumbers: solved-quest
  counts for about 5,284 users, by quest type and country.
- **piebro/openstreetmap-statistics**: global edit and contributor counts per editor, including SC.
- **streetcomplete/sc-statistics-service**: PHP. `get_statistics.php?user_id=` returns solved counts per
  user and per country plus ranks. No regional or open-quest data, so it can't serve as a backend.

## Building blocks

- **StreetComplete itself** (https://github.com/streetcomplete/StreetComplete; release v63.4, master
  64.0-beta2 at commit c9b7956).
  - Filter code is in `app/src/commonMain/kotlin/de/westnordost/streetcomplete/data/elementfilter/`
    (`ElementFiltersParser.kt`, `ElementFilterExpression.kt`, `filters/ElementFilter.kt`).
  - `quests/QuestTypesRegistry.kt` lists 192 OSM quests plus the note quest:
    - 140 are `OsmFilterQuestType`, a pure filter string. 21 of these splice Kotlin constants into the
      string, so a regex over the source won't extract them.
    - 52 are custom `OsmElementQuestType`. About 33 need the surrounding elements, about 6 need iD presets
      or NSI, and 2 need country metadata.
  - 26 quests are country-gated (`enabledInCountries`). 34 are disabled by default.
  - About 50 filter quests use `older`/`newer`, which compares the element's last-edit timestamp or its
    `check_date` against `today -N years`. A user setting scales those intervals by 0.5, 1 or 2.
  - Two dev tools are worth reusing:
    - `printQuestFiltersAsOverpassQL` (Gradle task; `androidHostTest/.../PrintQuestFiltersAsOverpassQL.kt`)
      builds the registry and prints each filter quest as Overpass QL, constants resolved.
    - `.github/workflows/generate-quest-list.yml` uploads `quest-list.csv` (quests joined with the wiki
      table) as a CI artifact on every master push.
- **GeoDesk**: builds a `.gol` index from a PBF and does fast polygon selects. Its query syntax is close to
  SC's. starsep uses it. A candidate evaluation engine.
- **ohsome API** (HeiGIT): counts elements matching a filter in a boundary *at past dates*, which is real
  history.
  - Its filter language covers only `k=v`, `k=*`, `!=`, `in()`, `type:`, `geometry:`, `and/or/not`, with
    wildcards from v2. SC filters also use regex values, numeric comparisons, `check_date` dates and
    element age.
  - That makes it a possible backfill for the plain key/value quests and not the engine.
  - **v1 shuts down 2026-11-30.** v2 drops `groupBy/boundary`, so it's one polygon per request.
- **ohsome Quality API / dashboard**: an "attribute completeness" indicator. Ideas for presentation only;
  it doesn't know SC's rules.

## Context from the StreetComplete tracker

- **#869 "Quest density heatmap"** (2018) asked for quests per area "as a service on a separate webpage".
  westnordost: "not really doable technically" (closed). This shows demand.
- **#1874** (2020): SC moved from per-quest Overpass to downloading full data and filtering locally, which
  is the same architecture as ours.
- **#2072**: the OSM wiki's per-quest Overpass Turbo links (wiki "StreetComplete/Quests") are wizard-made and
  some are wrong. Don't use them as a filter source.

## Looked for, found nothing

- No Python, JS or Rust port of `ElementFilterExpression`. Only 2017-era SC forks (OpenSidewalks) turned up.
  Codeberg was not code-searched.
- **SCEE** (https://github.com/Helium314/SCEE), the expert-edition fork with extra quests, has no stats
  tooling. Its quests could be an optional extra set later.
- Osmose, KeepRight, OSMCha, MapRoulette (no SC-derived challenges found), taginfo, OSM-Analytics: none know
  SC quests or fit as a backend. *(Lightly checked.)*

## Sibling projects to borrow from (~/Code)

- `toronto-streets-osm`:
  - Geofabrik Ontario download to `.partial` with sha256, `meta.json`, PID lock (`src/osm_refresh.py`).
  - Daily `docs/history.jsonl` row, rewritten if run again the same day, plus chart (`src/history.py`).
  - `run.py update`, which commits "data YYYY-MM-DD" and pushes `docs/` to Pages.
  - Task Scheduler at 12:30.
- `ontario-farmland`:
  - 48 Ontario municipalities with relation ids, population and wikidata (`cities.json`). Toronto is
    relation **324211, admin_level 6**.
  - Full geometries (`cache/boundaries.json`, not committed); Overpass client `osmslot.py`.
  - Census land areas for denominators (`areas.json`).
- `osm-mayflies/DESIGN.md`: pyosmium pitfalls (use `FileProcessor`; check before reading a deleted node's
  location).

Counts above are from SC master (2026-10-10). At the pinned release v63.4 the build-time dump
(`data/quests/v63.4.json`) gives 138 filter / 51 custom / 1 note quest, 27 country-gated, 34 default-disabled,
48 using `older`.
