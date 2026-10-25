# Data format

This is the contract between the engine (writes snapshots), the pipeline (keeps the series) and the site
(reads it). All JSON is UTF-8. Dates are ISO-8601. Times are UTC unless a field name says `Local`.

## Inputs

- `data/quests/v<SC>.json`: the quest registry dumped from the StreetComplete build (`tools/sc-harness`).
- `config/regions.json`: `{ "regions": [ { id, name, group, timeZone, poly, source, extract?, url?, cadence? } ] }`.
  A region is one engine run: one time zone, its own cities, its own archive `data/archive/<id>/`. `extract`
  (default: `id`) is the shared-store extract it is counted from: the folder `~/Code/.osm-data/<extract>/`
  and the `osm-extracts fetch <extract>`; `url` is passed as `fetch --url` when osm-extracts does not know
  the extract by name. Several regions may share an extract (a country across time zones, or more cities
  than one run takes); `download` fetches each extract once, and regions sharing one must give the same
  `url`. Today every region is its own Geofabrik extract (`id` = osm-extracts region: ontario, berlin, …).
  `group` heads the city selector ("Ontario", "Germany"); `source` names the extract in the footer; `poly`
  is the region's `.poly` (Geofabrik's, for today's), used to clip notes and the planet history.
  `cadence` is `"daily"` (default) or `"weekly"`. A daily region is counted from its extract by
  `run.py update`; a weekly one has no extract (`extract` and `url` are ignored) and is counted by
  `run.py weekly` from the planet history file: a slice at the file's replication timestamp each week, plus
  the 1st of every month since 2017-01 not yet counted. Its snapshots' `source.url` is null and
  `source.file` is `<id>-history-<YYMMDD>.osh.pbf@<time>`. Today every region is daily.
- `config/cities.json`: `{ "cities": [ { id, name, relation, adminLevel, countryCodes: ["CA","CA-ON"],
  timeZone, population, landAreaKm2, boundary, region } ] }`. `boundary` is a path to an Overpass `out geom`
  relation element; `region` is the region whose extract holds the city, and its `timeZone` must be the
  region's. Adding a city means adding an entry and its boundary file (`tools/add_city.py <relation>`
  makes both; `tools/import_farmland_cities.py` made the ontario-farmland set). The engine gets the
  region's cities only (`data/cities/<region>.json`, cut by `run.py`).
- An `.osm.pbf` extract with timestamps. Its header `osmosis_replication_timestamp` is the snapshot's
  **as-of** time.
- A notes clip per region (`tools/clip_notes.py`, one pass over the dump for all regions, in `data/notes/`,
  not committed): the notes of the planet notes dump inside the region's poly (holes subtracted, edges
  included; until 2026-10-24 its bounding box) or inside one of its cities' bounding boxes padded by 1 km,
  open or closed, with every comment. JSON lines; the first is a header
  `{"schema":1,"source":"planet-notes-261011.osn.bz2","sha256":…,"until":"<newest comment in the
  dump>","bbox":[minLon,minLat,maxLon,maxLat],"poly":"ontario.poly","notes":<count>,"boxes":[[…],…]}`
  (`bbox`: the poly's, longitudes past ±180 for a poly across the antimeridian; `boxes`: the padded city
  boxes, absent when none were given), then one note per
  line by id: `{"id":…,"lat":"43.6532100","lon":"-79.3832000","created":…,"comments":[{"action":"opened",
  "timestamp":…,"uid":…,"text":…}]}` (lat/lon as the dump's strings, `uid` absent for anonymous comments).

## Engine output: one snapshot per extract

`data/archive/<region>/snapshots/<asOfDate>.json` (not committed), where `asOfDate` is the extract's
replication date in the cities' time zone (`YYYY-MM-DD`). The engine runs once per region, with
`--out data/archive/<region>`, so each region has its own snapshot of a date, holding only its cities. It
also writes `data/archive/<region>/quests.json`, which `run.py history` merges into `docs/data/quests.json`.
The archive keeps every snapshot and is what `run.py history` reads; `docs/data/<region>/snapshots/` holds
the region's newest one only, a byte-for-byte copy. Until 2026-10-24 every snapshot was in `docs/data`;
`run.py migrate-archive` (also run by `count` and `history`) moves any left there into the archive, and
the snapshots published until then stay in git history.

```jsonc
{
  "schema": 1,
  "asOf": "2026-07-16T20:21:30Z",     // the "today" used by age filters: the extract replication timestamp
  "asOfDate": "2026-07-16",            // asOf in timeZone
  "timeZone": "America/Toronto",
  "extractTimestamp": "2026-07-16T20:21:30Z", // the PBF header's timestamp; differs from asOf only
                                       //   when the engine ran with --today (tests, what-ifs)
  "scVersion": "63.4",
  "scCommit": "244c6873…",
  "resurveyMultiplier": 1,
  "areaUnit": "city",                  // what the area quests ran on: "city" (one map data per city) or
                                       //   "tiles" (per z16 tile); absent before 2026-10-12, when
                                       //   the snapshots held no area quests
  "engineCommit": "<git sha of this repo>",   // null if git is unavailable
  "source": { "url": "...",            // null when the engine got no --source-meta, or for a slice of a
                                       //   planet history file brought up to date with diffs
              "lastModified": "2026-07-16T23:33:11Z",  // the download's Last-Modified, as ISO; or null
              "sha256": "...",         // always: computed by the engine from the PBF it read
              "file": "ontario-2026-07-16.osm.pbf" },  // the PBF's file name
  "notes": { "dump": "planet-notes-261011.osn.bz2", "sha256": "...", // the notes dump the clip came from;
             "until": "2026-10-11T00:02:41Z",   // its newest comment (it must be at or after asOf)
             "open": 21345,                     // notes open at asOf in the clip's region (the poly's bbox
                                                //   until 2026-10-24, then the poly and the city boxes)
             "showAllNotes": false },           // the app setting the note quest assumes (its default)
                                       // null: notes not modelled (no quest hidden, no note quest);
                                       //   absent on snapshots made before 2026-10-12
  "runSeconds": 12.3,
  "cities": {                          // keyed by city id, sorted
    "toronto": {
      "denominators": { "landAreaKm2": 665.93, "population": null,
                        "taggedNodes": 808328, "taggedWays": 782590, "highwayKm": 10808.696 },
      "quests": {                      // keyed by quest name, sorted; one quest per line
        "AddBenchBackrest": {
          "open": 3063,                 // what the app would show at asOf (centre inside the city polygon)
          "nodes": 2931, "ways": 132, "relations": 0,
          "agedOnly": 0                 // of `open`, how many match only because of time (0 when !usesAge)
        },
        "AddBusStopShelter": { "open": 3732, …, "agedOnly": 2058,   // Toronto 2026-10-10
          "open05": 6093, "aged05": 4419, // usesAge quests only: open and agedOnly with the app's resurvey
          "open2": 1674, "aged2": 0 }     //   setting "more often" (multiplier 0.5) and "less often" (2);
                                          //   absent before 2026-10-13
        // OsmNoteQuestType (with notes): "open" is the note quests in the city, nodes/ways/relations 0;
        //   "openAllNotes": with the app's setting "show all notes" (since 2026-10-13)
        // every quest with status "counted" for this city in quests.json appears here, zeros included
        // (127 per city for SC 63.4 in Ontario; ~620 KB per snapshot for 48 cities)
      }
    }
  }
}
```

With notes, a quest whose position truncated to 6 decimals equals an open note's is not counted, as the
app hides it (`OsmQuestController.getBlacklistedPositions`). The note quest counts the open notes in the
city that SC's own filter shows to a user who wrote none of them, with "show all notes" off (the app's
default): a question mark in the first comment, or `#surveyme` in any. See `engine/README.md`, "Notes".

The resurvey setting changes only `older today -N` style tests (`RelativeDate`): every variant runs the
quest's own test again with that multiplier, in the same pass. `open` and `agedOnly` stay the app
default (1); `resurveyMultiplier` in the header is that default.

`agedOnly`, per element: of the elements counted in `open`, those that no longer match when the clock is set
to 1900-01-01, where every `older today -N` test is false. That includes date tags compared with today
(`opening_date < today`, `smoothness:date < today -4 years`). Those elements need a resurvey or a re-check,
not new mapping.

Denominators: `landAreaKm2` and `population` come from the city config (area rounded to 2 decimals).
`taggedNodes` and `taggedWays` count tagged elements whose quest position is in the city. `highwayKm` is
the length of ways tagged `highway` = motorway, trunk, primary, secondary, tertiary, unclassified,
residential, service, living_street, or a `_link` of motorway, trunk, primary, secondary or tertiary,
without `area=yes`, whose position is in the city; great-circle length on a 6371 km sphere (SC's
`measuredLength()`), 3 decimals. See `engine/README.md` for how positions are computed.

## Quest metadata for the site

`docs/data/quests.json`, rewritten each run by `run.py history` from the regions' `quests.json` (the
newest registry; `status` holds every region's cities):

```jsonc
{ "scVersion": "63.4", "scCommit": "244c6873…", "quests": [ {   // registry order, one quest per line
    "name": "AddBenchBackrest", "order": 12, "kind": "filter|custom|note",
    "support": "supported|approximated|unsupported",
    "defaultDisabled": false, "usesAge": false,
    "enabledInCountries": { "type": "AllCountries" },  // or {"type":"AllCountriesExcept"|"NoCountriesExcept",
                                                       //   "codes":[...]}; the note quest has none in SC
                                                       //   and gets {"type":"AllCountries"}
    "wikiLink": "Key:backrest",                        // may be null
    "elementTypes": ["nodes", "ways"],                 // what the filter selects, or what a per-element
                                                       //   custom port can return; [] for area quests
                                                       //   (engine/README.md), other custom and note
    "status": { "toronto": "counted|not-in-region|unsupported" }   // per city, keyed by id, sorted
} ] }
```

`support`: `supported` for every filter quest (SC's own filter and geometry code; the differences left
in `engine/README.md` are not quest-specific) and every ported custom quest (checked element for element
against SC's own class) and the note quest when the run had notes, `unsupported` otherwise. A quest that becomes
counted is absent (`null` in history) from older snapshots, never 0; the site marks the date where the set
of counted quests changes as a break in totals. `status`:
`unsupported` if the quest is not supported, else `not-in-region` if its `enabledInCountries` excludes the
city's `countryCodes`, else `counted`.

The site's totals count the quests the reader ticks; by default those are the ones without `defaultDisabled`.
The per-quest numbers are always there.

## Tile grids for heatmaps

`data/grid/<region>/<asOfDate>.json.gz` (gzipped, not committed: about 0.5 MB each, 152k cells on 2026-10-10), written with the snapshot when
the engine gets `--grid`: `{"asOfDate":…,"zoom":14,"quests":{"AddBenchBackrest":[[x,y,n],…]}}`. Each cell is
a z14 slippy-map tile (SC's `enclosingTilePos`) and the number of that quest's counted quests whose
position is in it, summed over the cities (what `open` counts: default multiplier, notes applied). Quests
by name, cells by x then y; a quest with nothing counted is absent.

## Series for the site

`docs/data/history/<cityId>.json` is rebuilt from all regions' snapshots in the archive on every run:

```jsonc
{ "city": "toronto", "name": "Toronto",
  "dates": ["2026-07-16", "..."],                       // asOfDate, ascending, one per extract
  "meta": [ { "scVersion": "63.4", "resurveyMultiplier": 1, "areaUnit": "city", "notes": true } ],
                                                        //   parallel to dates, so breaks show; areaUnit only
                                                        //   where the snapshot has it, notes only where true
  "quests": { "AddBenchBackrest": { "open": [3063], "agedOnly": [0] } },
  "denominators": { "landAreaKm2": 665.9, "highwayKm": [0.0] } }
```

A city's `dates` holds only the snapshots that contain it. A quest absent from one of them (not counted
under that SC version, or new in a later one) is `null` at that index, never 0. Both files are written by
`run.py history` with sorted keys, so a rerun on the same snapshots changes no bytes.

`docs/data/cities.json` lists cities with their latest totals, for the selector and comparisons:

```jsonc
{ "asOfDate": "2026-07-16", "scVersion": "63.4", "resurveyMultiplier": 1,   // newest snapshot
  "dates": ["2026-07-16"],                       // every snapshot date of any region, ascending, once each
  "regions": [ { "id": "ontario", "name": "Ontario", "group": "Ontario", "source": "Geofabrik Ontario" } ],
                                                  // config/regions.json, in its order
  "cities": [ {                                   // sorted by name
    "id": "toronto", "name": "Toronto", "region": "ontario", "asOfDate": "2026-07-16", "scVersion": "63.4",
    "landAreaKm2": 665.9, "population": null, "highwayKm": 0.0,
    "open": 0,          // headline: counted quests, default-disabled excluded
    "agedOnly": 0,      // of `open`
    "openAll": 0,       // default-disabled included
    "questsCounted": 0,
    "trend": [0],       // `open` on each of `dates`; null where the city wasn't counted
    "trendAll": [0]     // the same for `openAll`
} ] }
```

`docs/data/compare/<quest>.json` holds one quest's open count in every city, each from the city's newest
snapshot (the one `cities.json`'s `asOfDate` names), for the compare view's per-quest ranking:

```jsonc
{ "quest": "AddBenchBackrest", "open": { "toronto": 3186, "victoria": 732 } }   // keyed by city id, sorted
```

A city whose newest snapshot lacks the quest is absent; a quest in no city's newest snapshot has no file,
which the site reads as no count anywhere. About 2 KB per quest at 115 cities; the compare view fetches
the picked quest's file only. Written by `run.py history` like the history files, stale ones deleted.

Rerunning on the same extract rewrites the same snapshot file byte for byte, apart from `runSeconds` and
`engineCommit`.

## Places and parts (contract, 2026-10-24; being built)

The name layer and the neighbourhood counts (DESIGN.md, "Places: naming the world, counting on
request"). Agreed before the work was split, so the builders, the engine and the site meet here.

- **Place id**: the first 12 hex digits of the Overture GERS id, dashes removed
  (`087cbb33-e54d-...` → `087cbb33e54d`). The build fails if two places share one. The same id is the
  name shards' key, the `?place=` of the site, the issue form's field and a part's key in a snapshot.
  The full GERS id is kept where the place is defined (shard field `g` is not stored; the parts registry
  stores it).
- **Overture release** is pinned like the SC version: `config/places.json`
  `{ "overture": "2026-10-21.0" }`; moving it is a deliberate commit, not an automatic one.
- **Name layer**, `docs/places/` (committed, published). Only divisions that have a `division_area`.
  - `docs/places/index.json`: `{ "schema": 1, "overture": "2026-10-21.0", "countries": [ { "id", "name",
    "cc", "bbox": [xmin, ymin, xmax, ymax], "regions": [ { "id", "name", "file": "<cc>/<id>.json",
    "n": <places in the file> } ] } ] }`, countries by name, regions by name. Places a country has
    outside every region (or a country without regions) are in a region entry with `"id": "_"` and
    `"name": null`, file `<cc>/_.json`.
  - `docs/places/<cc>/<regionId>.json`: `{ "schema": 1, "region": "<id>", "places": [ [id, name, st,
    parent, xmin, ymin, xmax, ymax, en, counted] ] }`. `st` the subtype code: 0 country, 1 dependency,
    2 region, 3 county, 4 localadmin, 5 locality, 6 borough, 7 macrohood, 8 neighborhood, 9 microhood.
    `parent` the index of the parent in this file's `places`, or -1 for the region itself (the nearest
    ancestor that has an area, from `hierarchies`, when `parent_division_id` has none). bbox rounded to
    4 decimals. `en` the English name when it differs from `names.primary`, else null. `counted` the
    city id in config/cities.json when the place is a counted city, `"<city>/<placeId>"` when it is a
    counted part, else null. Parents come before children.
- **Parts registry**, `config/parts/<city>.json` (committed): `{ "schema": 1, "city": "<id>", "overture":
  "2026-10-21.0", "parts": [ { "id": "<placeId>", "gers": "<full id>", "name", "en", "subtype",
  "osm": "r123" | "w456", "geometry": "data/boundaries/parts/<city>/<osm>.geojson" } ] }`.
  A part is an Overture division under the city in `hierarchies`, of subtype borough, locality,
  macrohood, neighborhood or microhood, **whose source is an OSM relation or way** (the owner chose OSM
  only: Esri Community Maps parts are left out). The geometry comes from OSM itself, cut from the
  region's own extract (osmium, Docker image `name-ru-repair-osmium`), not Overture's copy.
- **Part counts in a snapshot**: inside the city, `cities.<id>.parts`: `{ "<placeId>": { "<Quest>":
  <open> } }`, open quests at resurvey ×1 only (the `open` of the city's quest), quests with 0 left out,
  parts with nothing open kept as `{}`. A quest counts in a part when its position (the same centre
  the city test uses) is inside the part's polygon; parts overlap, so a quest can count in several.
  Area quests and the note quest the same way, from the city's own run: a part has no map data of its
  own. Adding parts changes no number outside `parts`.
- **Published part names**: `docs/data/parts/<city>.json`: `{ "schema": 1, "city", "parts": [ { "id",
  "name", "en", "subtype", "bbox" } ] }`, written by `run.py history` from the registry.
- No monthly history for parts yet: the newest snapshot only, until a backfill recounts with parts.
