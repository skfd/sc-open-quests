# Repin: moving the engine to a new StreetComplete release

Everything the engine counts with is pinned to one StreetComplete (SC) tag: the vendored source
(`engine/SC-VERSION.txt`), the ports of the custom quests (`engine/PORTED-QUESTS.txt`), the registry
dump (`data/quests/v<tag>.json`), the icons and titles (`docs/icons/`) and the release pins on the
timeline (`docs/data/sc-releases.json`). Moving all of them to a new tag is a **repin**. The scheduled
update's last step, `python run.py check-release`, opens the issue "Repin to StreetComplete vX.Y"
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

## 5. Site assets and pins

- `python tools/sc_assets.py <checkout>` after the first count wrote the new `docs/data/quests.json`
  (it reads the quest names from there): icons, titles, authors.
- `python run.py check-release` refreshes `docs/data/sc-releases.json`; with the new pin in
  `SC-VERSION.txt` it reports the pin as current and opens nothing.

## 6. Write it down, merge, count

- `engine/README.md` (what changed in the vendoring, stubs, the port list), `DESIGN.md` (a dated
  "Repin to vX.Y" entry: what the release changed for the counts), `HANDOFF.md` status,
  `tools/sc-harness/README.md` (the run's timings and any new gotcha).
- Merge to main, without a data commit on the branch (the daily "data" commits would conflict with
  it in the generated history files). From main, `engine/gradlew installDist` and `test` first (a new
  Kotlin downloads on the first build; don't leave that to the scheduler), then `python run.py count`
  by hand once (each region's newest extract is recounted with the new registry; older ones keep
  their counts, so the break sits at the repin date), `history`, then `publish` via `update`, or let
  the 13:15 run do it. Close the issue with the data commit.
- Or recount everything: `tools/backfill_history.py recount --region <r>` then `merge --region <r>`
  for every region rewrites every published snapshot with the new registry (from the store's extract
  or a history slice), and the series carry one registry with no break, as was done for v64.0 (an
  Ontario snapshot takes about 5 minutes, so it is an overnight job). The site marks a break only where
  two consecutive snapshots differ, so nothing on the site needs changing either way.
