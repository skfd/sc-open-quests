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
- **Reuse the sibling plumbing:**
  - Download, `meta.json` and lock from `toronto-streets-osm`.
  - Skip the run when the extract's `Last-Modified` hasn't changed, so reruns change nothing.
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
- Don't treat open OSM notes as noise. The app hides a quest whose center sits exactly on an open note. This
  is minor, but note it as a known difference until we model it.
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
  - Date filters use the system time zone. Pin `-Duser.timezone=America/Toronto` and record "today".
  - `tag older X` is also true when the *element* hasn't been edited since X, so element age counts as well
    as check dates.
- **Known approximations** still to replace:
  - Way centres are a plain average of their nodes, not SC's centroid or midpoint.
  - Relation centres ignore sub-relations; 776 Ontario relations got no centre.
  - Notes aren't modelled.
- **Licence:** the engine is a GPL-3.0 derivative, so this repo needs a GPL-compatible licence.
