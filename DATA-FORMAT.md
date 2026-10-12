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
  "asOf": "2026-07-16T20:21:30Z",     // extract replication timestamp; the "today" used by age filters
  "asOfDate": "2026-07-16",            // asOf in timeZone
  "timeZone": "America/Toronto",
  "scVersion": "63.4",
  "scCommit": "244c6873…",
  "resurveyMultiplier": 1,
  "engineCommit": "<git sha of this repo>",
  "source": { "url": "...", "lastModified": "...", "sha256": "..." },
  "runSeconds": 12.3,
  "cities": {
    "toronto": {
      "denominators": { "landAreaKm2": 665.9, "population": null,
                        "taggedNodes": 0, "taggedWays": 0, "highwayKm": 0.0 },
      "quests": {
        "AddBenchBackrest": {
          "open": 3063,                 // what the app would show at asOf (centre inside the city polygon)
          "nodes": 2931, "ways": 132, "relations": 0,
          "agedOnly": 0                 // of `open`, how many match only because of `older` (0 when !usesAge)
        }
        // only quests with status "counted" in quests.json appear here
      }
    }
  }
}
```

`agedOnly` = matches at `asOf`, minus matches with the clock set so every `older today -N` test is false.
Those elements need a resurvey, not new mapping.

## Quest metadata for the site

`docs/data/quests.json`, rewritten each run from the registry dump:

```jsonc
{ "scVersion": "63.4", "quests": [ {
    "name": "AddBenchBackrest", "order": 12, "kind": "filter|custom|note",
    "support": "supported|approximated|unsupported",
    "defaultDisabled": false, "usesAge": false,
    "enabledInCountries": { "type": "AllCountries" },
    "wikiLink": "Key:backrest",
    "status": { "toronto": "counted|not-in-region|unsupported" }   // per city
} ] }
```

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

`docs/data/cities.json` lists cities with their latest totals, for the selector and comparisons.

Rerunning on the same extract rewrites the same snapshot file byte for byte, apart from `runSeconds` and
`engineCommit`.
