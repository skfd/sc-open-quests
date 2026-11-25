# Repin: moving the engine to a new StreetComplete release

Everything the engine counts with is pinned to one StreetComplete (SC) tag: the vendored source
(`engine/SC-VERSION.txt`), the ports of the custom quests (`engine/PORTED-QUESTS.txt`), the registry
dump (`data/quests/v<tag>.json`), the icons and titles (`docs/icons/`) and the release pins on the
timeline (`docs/data/sc-releases.json`). Moving all of them to a new tag is a **repin**. The scheduled
inputs run's last step, `python run.py check-release`, opens the issue "Repin to StreetComplete vX.Y"
when a stable release is newer than the pin; this is the routine it points at. Expect half a day:
most steps are checks, not typing. The v64.0 repin (2026-10-21) is the worked example.

Work in a worktree (`git worktree add ../sc-open-quests-v<tag> -b sc-v<tag>`); the engine needs a cold
Gradle build there, and `data/notes/`, `data/cities/` are not tracked, so run the counts from main
after merging.

## 1. Checkout and registry dump

```sh
TAG=v64.0
git clone --depth 1 --branch $TAG https://github.com/streetcomplete/StreetComplete.git /c/Users/kk/AppData/Local/Temp/sc-$TAG
cd /c/Users/kk/AppData/Local/Temp/sc-$TAG && git fetch --depth 1 origin tag v63.4   # the old tag, for diffs
```

Then `tools/sc-harness/README.md`, "Reproduce for a new SC tag": drop the two harness files into the
unit-test source set, append the Gradle snippet, run `:app:dumpQuestFilters` into
`data/quests/v<tag>.json`. Since v64 that source set is `androidHostTest`, the task
`testAndroidHostTest`, `OsmNoteQuestType` sits in `quests.note_comments`, and SC's `buildSrc` wants
JDK 25: add the foojay toolchain resolver to the root `settings.gradle.kts` (after `pluginManagement`)
and, without a version, to a new `buildSrc/settings.gradle.kts`, run Gradle itself on a JDK 25
(`~/.gradle/jdks/` after the first resolve). Cold: about 10 minutes plus the Android platform download.

Compare the registries: names added and removed (`data/quests/v<old>.json` against the new dump), and
the library versions in `gradle/libs.versions.toml` (kotlin, kotlinx-datetime, kotlinx-serialization,
osmfeatures, osm-opening-hours, kaml, countryboundaries) against `engine/build.gradle.kts`.

## 2. Vendored source: `engine/sync-sc.ps1`

`./sync-sc.ps1 -ScPath <checkout> -Tag v<tag>` (default tag in the script: update it). It fails, in
this order, on: a pinned port file that changed (step 3 first), a listed file that moved (fix the path
in `$files`; v64 moved `osm/Places.kt` to `osm/places/`, `osm/Things.kt` to `osm/things/`), a patch
line that no longer matches verbatim (read the new file; the patch has to hold or be rewritten:
`clock`, `multiplier`, and since v64 `nolazy`, which exists because SC started caching a filter's
date threshold). Then build. Unresolved references in `src/main/kotlin/sc/` mean a vendored file grew a
dependency: vendor it too if it is plain Kotlin, stub it under `src/main/kotlin/stubs/` if it is UI
(Compose, resources). Keep stubs minimal and say in each which vendored file needs it.

## 3. Ports of the custom quests

Diff every pinned file between tags, logic only (UI, `Form`, `Res.*`, achievements, answers do not
count): `git diff v<old>:<old path> v<tag>:<new path>`. The list is `engine/PORTED-QUESTS.txt`.

- **Generated area ports**: `python engine/port_area_quests.py --sc <checkout> <every name in
  src/main/kotlin/ported/AreaQuests.kt> [new custom quests that read the map data]`. It re-pins them.
  Read the generator's output of a new quest once: an enum it splices into a filter needs vendoring.
- **Hand ports** (`src/main/kotlin/openquests/custom/`): edit by hand to the new logic; filters
  verbatim. New custom quests whose `getApplicableElements` looks at one element at a time go here.
- **Fast twins** (`src/main/kotlin/openquests/fast/`): redo each as "the new port plus its one speed
  change", with `sourceSha256` from the new pin. `CustomQuestsTest` fails until the hashes agree.
  `helper:KerbUtil` pins SC's `osm/kerb/KerbUtil.kt`, which `fastKerbNodes` (`FastKerbs.kt`) copies: if it
  moved, redo that function from the new file. `NodeSetTwinsTest` then holds it and the other node-set twins
  against SC's own code on random map data.
- `helper:OsmNoteQuest` (`openquests/NoteQuest.kt`) and `helper:ignoreRelation`
  (`openquests/IgnoreRelation.kt`): diff the SC function, update the port.
- Then `python engine/pin_ports.py --sc <checkout>`: every pin it reports as changed must be a file
  somebody re-checked.

New filter quests cost nothing: the registry dump carries their filters. Removed quests cost nothing
either: old snapshots keep them, the site shows them while the newest registry has them.

## 4. Build, tests, oracle

- `engine/gradlew installDist`, then `engine/gradlew test`. `CountriesTest` and `CustomQuestsTest` read
  the new dump (update the file name in them); `TorontoRegressionTest` stays on `v63.4.json` on
  purpose, it regresses the vendored filter and geometry code, not the quest set.
- **Oracle** (`tools/sc-harness/README.md`, "CheckCustomQuests"): SC's own classes on the same map data
  must give the same quest sets as the ports, element for element, for every custom quest. Run the
  engine on a small city with `--dump-elements`/`--dump-city` and `--dump-matches` (all custom quests),
  then `:app:checkCustomQuests` in the SC checkout with the same `-PcheckBbox` and today, and diff.
  Guelph or Barrie takes minutes; do one German city too (Bremerhaven), the country metadata differs.
- `-Dopenquests.verifyFast=true` with a whole-region run compares each twin with its port.
- `-Dopenquests.matchCache=verify` with a whole-region run asks every quest of every element beside the match
  cache and stops at the first difference. Run it after any change to a custom port: a port's `necessary()` must
  name only filters its `isApplicable` requires, and this is what finds one that does not.

## 5. Site assets and pins

- `python tools/site_quests.py take data/archive/bremen/quests.json` (any engine's `quests.json` of the new
  version; also after a port changes a quest's support), then `build`; commit `config/site-quests.json`.
- `python tools/sc_assets.py <checkout>` after that wrote the new `docs/data/quests.json`
  (it reads the quest names from there): icons, titles, authors.
- `python run.py check-release` refreshes `docs/data/sc-releases.json`; with the new pin in
  `SC-VERSION.txt` it reports the pin as current and opens nothing.
- `python tools/sc_first_release.py <bare clone>` (its docstring has the clone) rewrites
  `docs/data/quest-releases.json`, after `check-release` so the new tag has its date. A quest the file lacks
  counts for all of history under "Only quests the app had then", and `tests/test_first_release.py` fails.
  A quest that replaces or splits an old one goes in `PREDECESSOR` first: read the changelog's new quests.

## 6. Write it down, merge, count

- `engine/README.md` (what changed in the vendoring, stubs, the port list), `DESIGN.md` (a dated
  "Repin to vX.Y" entry: what the release changed for the counts), `HANDOFF.md` status,
  `tools/sc-harness/README.md` (the run's timings and any new gotcha).
- Merge to main, without a data commit on the branch (the daily "data" commits would conflict with
  it in the generated history files). From main, `engine/gradlew installDist` and `test` first (a new
  Kotlin downloads on the first build; don't leave that to the scheduler).
- **Recount forward from the release date** (the owner's rule, 2026-11-16): every region's snapshots from
  the day the release was published to today are recounted with the new registry, from the extracts the
  store still has; nothing older is touched, so the series shows the release as a step on its own date,
  which is what players saw. For each region:
  `python tools/backfill_history.py recount --region <r> --since <release date YYYY-MM-DD>`, then
  `python tools/backfill_history.py merge --region <r>`; then `python run.py history` and `publish` via
  `update`, or let the 12:15 run do it (`docs/data`'s city files end on `config/city-files.json`'s day; the days after
  it are the world's, on sc-data). Close the issue with the data commit. About 10 minutes of counting
  per day recounted for all regions together; no history file is read (none is kept since 2026-11-16).
  **Repin within 14 days of the release:** the store keeps a region's extracts 14 days, and a snapshot
  whose extract is gone is left as counted (the recount names it). The issue is opened by the scheduled run
  the day the release appears.
- Only when a release fixes a quest so badly that the old numbers mislead: recount that quest further back
  on demand, which needs a planet history file downloaded first (`osm_extracts.py fetch planet-history`,
  hours and about 170 GB) and `recount` without `--since` (every published snapshot, from a history slice
  where the extract is gone, as was done for v64.0). The site marks a break only where two consecutive
  snapshots differ, so nothing on the site needs changing either way.
