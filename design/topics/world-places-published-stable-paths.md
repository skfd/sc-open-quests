## World places published: stable paths (schema 2) (2026-11-21; owner: "lets do the stable urls and proper fix")

This replaces the file layout of "World places published: the files" above. What is published, the counted cities'
rule, the midnight-UTC clock and change points are unchanged. Schema 1 was stopped 39 minutes into its first upload
and no page ever read it.

**Why.** Measured on the publisher's cached daily changes, 11-02 to 11-13: of 110,423 parent files 11,300 to 13,200
hold a child that changed on a day (about 11%), and of 1,018,552 places 30,000 to 37,000 change (about 3%); 166,932
places changed at all in the 12 days. Schema 1 rewrote every parent file daily because the date was in its path and
its content (`date`, `dates`, a sliding 28-day start): about 3.3M writes a month, $15. And a page read its parent's
file for its own last days: a country page downloaded `latest/<date>/world.json`, 2.09 MB, for one entry of 248
(`.scratch/world-publish/page_open.txt`).

**The files.** No path carries a date:

| file | holds | uploaded | Cache-Control |
|---|---|---|---|
| `latest.json` | `schema` 2, `v`, `date`, `first`, `back`, the counted quests, `scVersion`, `overture`, and the two folders | each publish, last | `max-age=300` |
| `place/<id[:2]>/<id>.json` | `id`, `name`, `subtype`, `cc`, `first`, `from` when not 0, and `quests`: the place's whole series as change points `[day, open, aged]` | when its bytes changed | `max-age=86400` |
| `children/<p[:2]>/<parent>.json` | `quests`, the names this file uses, in the world's order; `places`: child id to `{<index into quests>: [open, aged, openBack, agedBack]}` | when its bytes changed | `max-age=86400` |

**The counted cities (2026-11-25).** The world counts each of config/cities.json's cities inside its own boundary
(`osm-<cityId>`), and the same build publishes them: the page reads a city's days from `first` on here, and only the
dates before it from the site's `docs/data/history/<cityId>.json`. `latest.json` then has `city` and `cityParts`.

| file | holds |
|---|---|
| `city/<cityId>.json` | a place file's form: `id`, `name`, `first`, `from` when not 0, `quests` |
| `city-parts/<cityId>.json` | a children file's form over the city's registered parts (config/parts), and `noFile`: the parts with no place file, which have had no quest on any day |
| `cities.json` | `open`: each city's open quests on `date`, over the quests asked there and on by default |
| `city-trends.json` | `open`: the same on every day from `first` |
| `city-quests.json` | a children file's form over the cities, for the compare view |

A part's own days are its place's, `place/<id>`. A quest a file leaves out is 0 where `quests.json` says the site
counts it in the city, and a quest it says is not asked there is not shown. Checked 2026-11-25 against that day's
`docs/data` for every city, part, quest and date: 44,355,752 values, 0 different.

**`docs/data`'s own city files end on a set day (2026-11-25 on, `config/city-files.json`'s `until`).** `history/`,
`trends.json`, `compare/`, the region snapshots and `cities.json`'s counts are built from the days up to it, so `run.py
history` writes the same bytes whatever the newest day is, and a new day needs no commit and no deploy of the site:
`run.py site` publishes the place files each day and deploys only when the tree of `docs/` or `config/` is not the one
deployed last (`data/site-deployed.json`). What is still made from `config/`: `quests.json` (a release), `parts/`,
`coverage.json`, the list in `cities.json`.

- The page reads the files for the dates before `latest.json`'s `first`, names and areas. Without sc-data it shows
  them as they are, under their own date. Widgets from before 2026-11-25 stop at that day, also under their own date.
- `until` is the last day published before the change, not the last before `first`, so the change moved no byte of
  `docs/data`, and what is shown without sc-data is as new as it can be without a daily build.
- **To add a city, set `until` on** to a day the world counted it: without any day it has no files, and `history`
  stops and says so. `until` can go on, never back (`history` refuses to lose a published date).
- To undo: revert the commit; the next `run.py site` writes every day since, from the world's counts.

- **Days are numbers.** The published days are every day from `first` through `date` with no gap, so day 0 is
  `first` and a point's `day` needs no date list. `latest.json`'s `questsFrom` (there when not empty) is the day
  number from which the world counts a quest a StreetComplete release added after `first`: before it, no count
  (null, not 0), so a release does not draw a jump or enter a change. The build stops if the gated days have a gap.
- **`v` is the publish's token** (a hash of the date and every file's hash). The page asks for every file but
  `latest.json` as `<path>?v=<v>`. Cloudflare's cache keys on the query string (checked on the bucket: MISS, then
  HIT), so each publish is a new address and yesterday's cached copy is never served for today's `v`. The files
  are cached for a day, not a year: a `v` lives a day, and somebody reading a bare path sees a copy at most a
  day old.
- **A place file is append-only, so the page clips it.** A point whose `day` is past `latest.json`'s `date` is
  ignored. A file built through D+1 and read with D's `latest.json` therefore gives exactly D's numbers
  (`test_a_newer_file_clipped_reads_as_the_older_day`), so files of two publishes can never show a mix.
- **`from`** is the day number a place was first counted (11 to 90 places appear after the first day). Its series
  starts there, so a place counted late no longer waits for the 1st of a month.
- **A children file is a snapshot, not a series:** per child and quest, open and aged on `date` and on `back`
  (`date` minus 28 days, not before `first`). The table needs nothing else, the file stops growing with the
  window (`children/world.json` 0.67 MB against 2.09 MB), and no page reads it for the place itself. It is not
  append-only: for the minutes between an upload's first file and `latest.json`'s five-minute cache running out,
  a table can show the new day's numbers under the old date. Its bytes change when a child changed that day or
  when a child's value 28 days back slid.
- **`latest.json` goes up last.** It carries the new `v`, so no page asks for the new addresses before every file
  is there.
- **A place page reads two world files:** its own `place/` file and, if it has children, `children/<self>`.
  Germany's page: 0.029 MB and 0.065 MB raw, against 2.09 MB and 0.27 MB.

**Only changed files are written and uploaded.** `build` makes every file's text, hashes it, and writes the file
only when the hash differs from the last build's (`work/local.json`); `out` mirrors what the bucket should hold.
`upload` sends the files whose hash differs from `work/bucket.json` (what the bucket holds) with
`rclone copy --files-from --no-traverse --no-check-dest`, so the bucket is never listed. It goes in batches of
50,000 and saves the bucket manifest after each, so a failed upload resumes where it stopped. Files no longer
built are deleted before `latest.json` is written.

**Guards.** A plan past `DAY_CAP` (200,000 files) needs `--full`: a day changes far fewer, and a bigger plan means
the format, the name layer or the quest list changed, or a manifest was lost. `daily` never passes `--full`.
`MAX_UPLOAD` (1.5M) and the spend breaker (strict, with the planned count) stand as before. `check` reads
`latest.json` and a sample of files back over HTTPS with `?v=` and compares bytes with the local files; the
sample is drawn from every file the bucket manifest claims, most of which the last upload skipped, so it sees a
manifest and a bucket that have drifted apart. `daily` runs it after each upload.

**Rollback.** There is no previous folder to point back at. A bad day is undone by building `--through` the day
before and uploading: the files that differ go up again and `latest.json` gets that build's `v`.

**Measured, 2026-11-21.** The first build (through 11-12): 1,018,541 place files and 110,421 children files in
29 minutes; `verify --sample 1500` 0 mismatches over 12 days. The first upload: 1,128,962 files in about 2 h 40 min
at about 120 a second. The day after, through `daily` (11-13): build 6.5 minutes, 34,612 place files and 12,697
children files written (the same counts the cached changes gave), 47,309 files uploaded in 5 minutes, `verify` and
`check` 0 mismatches. So a day is about 47,000 writes, 1.4M a month: about $2 past R2's free million, against $15
plus $4.50 for schema 1. `back` stays at `first` until 11-29; after that a child's value sliding out adds
children files to a day, not yet measured. R2 counts one read per uploaded file as well (rclone checks each
after writing it), far inside the free 10M a month.
