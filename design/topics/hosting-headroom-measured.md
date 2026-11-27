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
