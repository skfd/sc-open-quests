## Idea: a phone widget for daily progress (owner, 2026-11-10)

Not planned and nothing built. The owner's idea: a home-screen widget showing the graph of one quest, or of
a city or neighbourhood, so an active StreetComplete player sees the day's progress at a glance.

What the data gives it today, and what it lacks:

- **City and quest series exist**: `docs/data/history/<cityId>.json` has every quest's `open` per date.
  It is too big for a widget (Toronto 177 KB; `cities.json` 314 KB), so a widget wants its own small
  file per city, something like the last 30 days of `open` and of a few quests.
- **Neighbourhood counts exist but aren't published as a series**: the archived daily snapshots carry
  `parts` since 2026-10-28 (Toronto: 218 parts, 10 days so far), and the site shows the newest only. A
  per-part series file is a new output of `run.py history`, no recount needed for the days since then.
- **Freshness is the weak point for "daily"**: one count a day from an extract, published around 13:00
  local, and on 11-10 Toronto's newest date was 11-08 (11-04 is missing). A player would see
  yesterday's or older edits, never today's.
- **It measures the place, not the player**: the count moves with everyone's edits and with aging
  (`agedOnly`), and per-user stats are a non-goal. A widget of "my solves today" would be a different
  source (changesets with `StreetComplete:quest_type`).
- **Request budget**: every widget refresh is a Worker request against the 100,000 a day, for data that
  changes once a day, so the widget's file must be cacheable for hours (unlike `app.js`'s `no-cache`
  fetches). Any Worker change waits for the flip.

Open, for the owner when it comes up: the platform (a native Android or iOS widget, or just a small JSON
or image address that generic widget apps such as KWGT or Scriptable can show, which needs no app of
ours); and which view comes first (city total, one quest, or a neighbourhood).

### Widget: decided (owner, 2026-11-11, evening), its own repo `~/Code/sc-open-quests-widget`

- **A native Android app on Google Play**, "Open Quests for StreetComplete", package
  `com.comentality.openquests` (permanent after the first upload). No Play developer account yet: a
  personal account made now must run a closed test with 12 testers for 14 days before production, so
  plan that before release.
- **Place only**: the big number is the place's open quests from this site's data, "as of <date>". The
  live "my answers today" line (the public OSM API returns `StreetComplete:quest_type` on changesets,
  checked) was offered and declined; the per-user non-goal stands.
- **First view: a city, optionally one quest type**, read from the live `data/history/<cityId>.json`
  (Toronto 36 KB brotli on the wire, ETag, `max-age=300`, checked 11-11). No pipeline change needed for
  v1. Neighbourhoods wait for a per-part series file; the small cacheable widget file waits for the R2
  data subdomain.
- **Defaults stated, not objected to**: Kotlin + Glance, graph drawn on the device (theme and size
  follow the widget), refresh once or twice a day after the ~13:00 publish with conditional requests,
  daily tail only with a missing day drawn as a gap, sizes 2x1 (number + 4-week chip), 4x2 (+ stacked
  map/resurvey sparkline), 4x3 (+ top three quests), tap opens the place on the site, tone follows the
  trend (as the share-card idea).
- **Load on this site**: every refresh is a Worker request against the 100,000 a day until the R2 data
  subdomain exists; two a day per widget is fine for thousands of installs, not for a hit.
