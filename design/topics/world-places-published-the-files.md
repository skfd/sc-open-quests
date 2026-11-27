## World places published: the files (2026-11-19, night; owner: "Yes, build it")

**The layout in this section (schema 1: dated folders, the parent's file read for the place itself) was replaced
on 2026-11-21, before any page read it: "World places published: stable paths (schema 2)", at the end of this
file.** What is published, the counted cities' rule, the clock and change points still hold; the file table, the
`base` and `start` rules, the three-file read and the write count do not.

Release 1's step 7 (above) puts place data on `sc-data.comentality.com` (bucket `sc-open-quests-data`), and
"Place statistics for the whole world" fixed the plan: `place/` monthly, `latest/<parent>` daily, a tiny
`latest.json`. That plan was written for a weekly world with monthly history behind it; release 1 is daily from
2026-11-01 with no history before it. So this section fixes the files for that. `tools/world_publish.py` builds
them into a local folder in the bucket's layout; a separate step uploads it. Nothing is uploaded before release 1
(30 gated days).

**What is published.** Only the 12-hex Overture places (the cells `city:` and the gate's `osm-<city>` stay
private). Only the default resurvey setting (`open`, `agedOnly`), as the owner decided on 11-17. Only days whose
gate passed (`W/days/<D>/gate.json` `ok`), from `first` (2026-11-01) through the newest, with no gaps. Quests by
name. A place is published if the world counted it (it is in `counts/<D>/counts.json` `parts`) and the name layer
(`docs/places/`) has it, since the page reaches a place only through the name layer: 11 counted places of
1,018,483 are not in it and are left out. A place with no file is "not counted"; a quest missing from a place's
file is 0 open, provided the quest is in `latest.json` `quests` and enabled in the place's country
(`quests.json` `enabledInCountries`, as for cities).

**Counted cities stay on their own data.** The page already turns a counted place into `?city=`; world data is
for every other place. If world numbers ever replace a counted city's, they come from the city's own OSM
outline (the world's part `osm-<city>`), never from its name-layer place. The Overture outline differs:
Bratislava −13%, Halifax −2.4%, Cape Breton −2.2% (`tools/world_compare.py`, 2026-11-19).

**The clock is midnight UTC (owner, 2026-11-20: "go with midnight UTC").** When world numbers replace the daily
run's, a city's count for D is the world's at D 00:00Z, for every city. Europe's snapshots already use that clock.
Canada's and Germany's are Geofabrik's at about D 21:21Z, so their numbers move 2.6 h later; the comparison saw
no gap bigger than that window's edits. The world is not cut at the extract time.

**Change points, not columns.** A quest's series is a list of `[i, open, aged]`: from date index `i` the values
are `open` and `aged` until the next point; before the first point both are 0. Most places change on few days, so
this keeps a daily series small, and the same decoder reads both kinds of file.

**Paths carry their version, so every file but one is immutable.** A cached file can never disagree with another:

| file | holds | written | Cache-Control |
|---|---|---|---|
| `latest.json` | `date`, `first`, `base`, every published date, the counted quests, `scVersion`, `overture`, and the two folders below | each publish | `max-age=300` |
| `place/<base>/<id[:2]>/<id>.json` | `id`, `name`, `subtype`, `cc`, `dates` from `first` to `base`, and `quests` as change points | when `base` moves (the 1st), or the first publish | a year, immutable |
| `latest/<date>/<parent[:2]>/<parent>.json` | every child of `parent`: `dates` from `start` to `date`, and `places` (id to quests as change points; a point at index 0 carries the value at `start`) | every publish | a year, immutable |

- **`base`** is the newest 1st of a month that is not after `date` and not before `first`; before any such 1st,
  `first`. **`start`** is the earlier of `base` and `date` minus 28 days, but not before `first`, so a parent's
  file alone gives each child's newest count and its 4-week change, and a place page needs only its own file.
- **The parent** is the place's parent in the name layer: the row's `parentIdx` in its region file, or the
  region for a top row, or the country for a region; a country's parent is `world` (`latest/<date>/world.json`).
  A place in more than one region file is written under each of its parents. 29,525 counted places have a
  parent the world did not count; the parent's file is written anyway, keyed by its id.
- **A place page reads three files:** `latest.json`, its own `place/` file (dates to `base`), and
  `latest/<date>/<parent>` (itself after `base`, and its siblings). Children come from `latest/<date>/<self>`.
  It joins `place` dates up to `base` with `latest` dates after it.
- **Writes:** about 1.02M place files when `base` moves, plus about 110k parent files a day: about 4.3M a month,
  roughly $15 at R2's price, near the owner's agreed $13.5 (the daily files are rewritten whole because the
  paths are versioned; that buys the consistency above). Deletes are free: the upload keeps the previous two
  `latest/<date>/` folders and the previous `place/<base>/` (pages open over the switch), and deletes older ones.
- **The bucket needs a CORS rule** for the site's origin (GET, HEAD); the owner's step, with the upload.
