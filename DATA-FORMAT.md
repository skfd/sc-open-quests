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
  "engineCommit": "<git sha of this repo>",   // null if git is unavailable
  "source": { "url": "...",            // null when the engine got no --source-meta
              "lastModified": "2026-07-16T23:33:11Z",  // the download's Last-Modified, as ISO; or null
              "sha256": "...",         // always: computed by the engine from the PBF it read
              "file": "ontario-2026-07-16.osm.pbf" },  // the PBF's file name
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
        }
        // every quest with status "counted" for this city in quests.json appears here, zeros included
        // (127 per city for SC 63.4 in Ontario; ~620 KB per snapshot for 48 cities)
      }
    }
  }
}
```

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
against SC's own class), `unsupported` for the other custom quests and the note quest. A quest that becomes
counted is absent (`null` in history) from older snapshots, never 0; the site marks the date where the set
of counted quests changes as a break in totals. `status`:
`unsupported` if the quest is not supported, else `not-in-region` if its `enabledInCountries` excludes the
city's `countryCodes`, else `counted`.

Headline totals on the site exclude `defaultDisabled` quests; the per-quest numbers are still there.

## Series for the site

`docs/data/history/<cityId>.json` is rebuilt from all snapshots on every run:

```jsonc
{ "city": "toronto", "name": "Toronto",
  "dates": ["2026-07-16", "..."],                       // asOfDate, ascending, one per extract
  "meta": [ { "scVersion": "63.4", "resurveyMultiplier": 1 } ],  // parallel to dates, so breaks show
  "quests": { "AddBenchBackrest": { "open": [3063], "agedOnly": [0] } },
  "denominators": { "landAreaKm2": 665.9, "highwayKm": [0.0] } }
```

A city's `dates` holds only the snapshots that contain it. A quest absent from one of them (not counted
under that SC version, or new in a later one) is `null` at that index, never 0. Both files are written by
`run.py history` with sorted keys, so a rerun on the same snapshots changes no bytes.

`docs/data/cities.json` lists cities with their latest totals, for the selector and comparisons:

```jsonc
{ "asOfDate": "2026-07-16", "scVersion": "63.4", "resurveyMultiplier": 1,   // newest snapshot
  "cities": [ {                                                             // sorted by name
    "id": "toronto", "name": "Toronto", "asOfDate": "2026-07-16", "scVersion": "63.4",
    "landAreaKm2": 665.9, "population": null, "highwayKm": 0.0,
    "open": 0,          // headline: counted quests, default-disabled excluded
    "agedOnly": 0,      // of `open`
    "openAll": 0,       // default-disabled included
    "questsCounted": 0
} ] }
```

Per-quest comparisons across cities read the newest snapshot directly.

Rerunning on the same extract rewrites the same snapshot file byte for byte, apart from `runSeconds` and
`engineCommit`.
