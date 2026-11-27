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
