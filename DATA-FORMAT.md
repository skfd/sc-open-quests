# Data format

This is the contract between the engine (writes snapshots), the pipeline (keeps the series) and the site
(reads it). All JSON is UTF-8. Dates are ISO-8601. Times are UTC unless a field name says `Local`.

## Inputs

- `data/quests/v<SC>.json`: the quest registry dumped from the StreetComplete build (`tools/sc-harness`).
- `config/cities.json`: `{ "cities": [ { id, name, relation, adminLevel, countryCodes: ["CA","CA-ON"],
  timeZone, population, landAreaKm2, boundary } ] }`. `boundary` is a path to an Overpass `out geom`
  relation element. Adding a city means adding an entry and its boundary file
  (`tools/import_farmland_cities.py` makes both for the ontario-farmland set).
- An `.osm.pbf` extract with timestamps. Its header `osmosis_replication_timestamp` is the snapshot's
  **as-of** time.
- A notes clip (`tools/clip_notes.py`, in `data/notes/`, not committed): the notes of the planet notes dump
  inside `config/ontario.poly`'s bounding box, open or closed, with every comment. JSON lines; the first is
  a header `{"schema":1,"source":"planet-notes-261011.osn.bz2","sha256":…,"until":"<newest comment in the
  dump>","bbox":[minLon,minLat,maxLon,maxLat],"poly":"ontario.poly","notes":<count>}`, then one note per
  line by id: `{"id":…,"lat":"43.6532100","lon":"-79.3832000","created":…,"comments":[{"action":"opened",
  "timestamp":…,"uid":…,"text":…}]}` (lat/lon as the dump's strings, `uid` absent for anonymous comments).

## Engine output: one snapshot per extract

`docs/data/snapshots/<asOfDate>.json`, where `asOfDate` is the extract's replication date in the cities'
time zone (`YYYY-MM-DD`).

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
  "source": { "url": "...",            // null when the engine got no --source-meta
              "lastModified": "2026-07-16T23:33:11Z",  // the download's Last-Modified, as ISO; or null
              "sha256": "...",         // always: computed by the engine from the PBF it read
              "file": "ontario-2026-07-16.osm.pbf" },  // the PBF's file name
  "notes": { "dump": "planet-notes-261011.osn.bz2", "sha256": "...", // the notes dump the clip came from;
             "until": "2026-10-11T00:02:41Z",   // its newest comment (it must be at or after asOf)
             "open": 21345,                     // notes open at asOf in the clip's region
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

`docs/data/quests.json`, rewritten each run from the registry dump:

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

Headline totals on the site exclude `defaultDisabled` quests; the per-quest numbers are still there.

## Tile grids for heatmaps

`data/grid/<asOfDate>.json.gz` (gzipped, not committed: about 0.5 MB each, 152k cells on 2026-10-10), written with the snapshot when
the engine gets `--grid`: `{"asOfDate":…,"zoom":14,"quests":{"AddBenchBackrest":[[x,y,n],…]}}`. Each cell is
a z14 slippy-map tile (SC's `enclosingTilePos`) and the number of that quest's counted quests whose
position is in it, summed over the cities (what `open` counts: default multiplier, notes applied). Quests
by name, cells by x then y; a quest with nothing counted is absent.

## Series for the site

`docs/data/history/<cityId>.json` is rebuilt from all snapshots on every run:

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
  "dates": ["2026-07-16"],                                                  // every snapshot, ascending
  "cities": [ {                                                             // sorted by name
    "id": "toronto", "name": "Toronto", "asOfDate": "2026-07-16", "scVersion": "63.4",
    "landAreaKm2": 665.9, "population": null, "highwayKm": 0.0,
    "open": 0,          // headline: counted quests, default-disabled excluded
    "agedOnly": 0,      // of `open`
    "openAll": 0,       // default-disabled included
    "questsCounted": 0,
    "trend": [0],       // `open` on each of `dates`; null where the city wasn't counted
    "trendAll": [0]     // the same for `openAll`
} ] }
```

Per-quest comparisons across cities read the newest snapshot directly.

Rerunning on the same extract rewrites the same snapshot file byte for byte, apart from `runSeconds` and
`engineCommit`.
