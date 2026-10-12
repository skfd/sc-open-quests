# sc-harness

Dumps every StreetComplete quest type, in registry order, with its resolved element filter in SC's own
filter syntax, to `data/quests/v<version>.json`. It runs SC's own `questTypeRegistry(...)` on the JVM, so
Kotlin constants spliced into filter strings come out already interpolated.

Files:

- `DumpQuestFilters.kt` — the tool. Drop it into SC's JVM unit-test source set, package
  `de.westnordost.streetcomplete`.
- `CheckCustomQuests.kt` — oracle for ported custom quests, see [below](#checkcustomquests-an-oracle-for-ported-custom-quests).
  Same source set and package.
- `build.gradle.kts.snippet` — the `dumpQuestFilters` and `checkCustomQuests` JavaExec tasks to append to SC's `app/build.gradle.kts`.
  It borrows the unit-test task's classpath, the same way SC's own `printQuestFiltersAsOverpassQL` does on
  master.

Nothing in SC is changed other than adding these files and tasks. The SC checkout is scratch.

## What it emits

```json
{ "scVersion": "63.4", "scCommit": "<sha>", "generatedAt": "...", "questCount": 190,
  "quests": [ { "name": "AddRoadSurface", "order": 169, "ordinal": 135, "kind": "filter",
                "elementFilter": "ways with ...", "usesAge": true, "ageKeywords": ["older","today"],
                "parsesOk": true, "elementTypes": ["ways"], "overpassQL": "...",
                "defaultDisabled": false, "enabledInCountries": {"type": "AllCountries"},
                "wikiLink": "Key:surface", "achievements": ["car","bicyclist"], ... } ] }
```

- `kind`: `filter` (OsmFilterQuestType), `custom` (other OsmElementQuestType), `note` (OsmNoteQuestType).
- `order` is the index in the registry (display/priority order); `ordinal` is SC's stable serialization id.
- `elementFilter` is read from the `protected abstract val elementFilter` getter by reflection. It is the
  original string, not `toString()` of the parsed expression (that prints dates as `-1461.0 days`).
- `parsesOk` re-parses that string with SC's `toElementFilterExpression()`.
- `usesAge` is true when the filter contains `older`, `newer` or `today`; `ageKeywords` says which.
- `enabledInCountries`: `{"type":"AllCountries"}`, `{"type":"AllCountriesExcept","codes":[...]}` or
  `{"type":"NoCountriesExcept","codes":[...]}`. Absent for the note quest.
- Custom quests carry no filter: their filters are private lazies combined with Kotlin logic, and the
  parsed expression no longer holds the source string.
- Anything that needs Android resources (titles, hint text, the default-disabled message) is left out;
  `defaultDisabled` only records whether the message is set.

## Reproduce for a new SC tag

Windows, Git Bash. JDK 21 from Android Studio and the Android SDK.

```sh
TAG=v63.4
git clone --depth 1 --branch $TAG https://github.com/streetcomplete/StreetComplete.git /tmp/sc-$TAG
cd /tmp/sc-$TAG
printf 'sdk.dir=C:/Users/kk/AppData/Local/Android/Sdk\n' > local.properties   # forward slashes

# 1. which unit-test source set does this tag use?
ls app/src   # androidUnitTest (<= v63.x)  or  androidHostTest (newer)
cp ~/Code/sc-open-quests/tools/sc-harness/DumpQuestFilters.kt \
   app/src/androidUnitTest/kotlin/de/westnordost/streetcomplete/   # or androidHostTest/...

# 2. append the task; on androidHostTest tags change "testDebugUnitTest" to "testAndroidHostTest"
cat ~/Code/sc-open-quests/tools/sc-harness/build.gradle.kts.snippet >> app/build.gradle.kts

# 3. run
export JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"
./gradlew --console=plain :app:dumpQuestFilters \
  -PdumpOut="C:/Users/kk/Code/sc-open-quests/data/quests/${TAG}.json"
```

Notes:

- AGP downloads a missing `platforms;android-<compileSdk>` by itself, as long as the SDK's `licenses/`
  folder already has the accepted licence. At v63.4 it fetched Android SDK Platform 36.
- The first build compiles the whole app plus its unit tests and takes a while (see below). Later runs are
  incremental.
- If the dump fails to compile on a new tag, the likely causes are a moved class (`Countries`,
  `OsmNoteQuestType`, `EditTypeAchievement`) or a changed `questTypeRegistry(...)` signature. Match the
  arguments to the tag's `QuestsOverpassPrinter.kt` / `PrintQuestFiltersAsOverpassQL.kt`, which builds
  the registry the same way.
- Without `-PdumpOut` the JSON goes to stdout.
- Don't add `dependsOn(testTask.map { it.classpath })` the way master's task does: on Gradle 8.14 that
  provider carries the test task itself, so the whole unit-test suite runs first (and at v63.4 five
  date-sensitive SC tests fail, e.g. `CheckOpeningHoursSignedTest`, which aborts the build). The classpath
  FileCollection already carries the compile dependencies.
- `elementFilter` keeps the string exactly as SC holds it, including the leading newline and indentation
  of Kotlin raw strings. Trim if you need to; SC's parser doesn't care.

## v63.4 run (2026-10-11)

- First build (`:app:compileDebugUnitTestKotlinAndroid`, cold Gradle 8.14 and caches): 6 min 55 s,
  including the automatic install of Android SDK Platform 36. The dump itself then takes about 10 s.
- 190 registry entries: 138 `filter`, 51 `custom`, 1 `note`. All 138 filter strings re-parse.

## CheckCustomQuests: an oracle for ported custom quests

Custom quests have Kotlin logic on top of their filters, so a hand port can drift. `CheckCustomQuests.kt`
runs SC's real `getApplicableElements(mapData)` (what `OsmQuestController` calls for a downloaded area) of
the named quest types over a set of elements, and lists what each one applies to. Diff that against the
port's output for the same elements.

Install it like the dump: `CheckCustomQuests.kt` next to `DumpQuestFilters.kt`, and the `checkCustomQuests`
task from the snippet into `app/build.gradle.kts`.

Input is JSON lines, one element per line:

```json
{"type":"way","id":123,"version":4,"timestamp":1690000000000,"tags":{"highway":"residential"},
 "lat":43.6,"lon":-79.4,"nodes":[1,2,3]}
```

- `timestamp` is epoch milliseconds (SC's `timestampEdited`). Leave it out and the element counts as
  edited in 1970, so every `older today -N years` rule matches; the tool warns with a count.
- `lat`/`lon` is the quest position. Every element gets an `ElementPointGeometry` there, and the map
  data's bounding box covers them all.
- `nodes` (ways) and `members` (relations, `{"type":"way","ref":1,"role":"outer"}`) are optional. Without
  `nodes` a way has no node ids, so `isClosed` is false.
- Bad lines are skipped and counted.

```sh
./gradlew --console=plain :app:checkCustomQuests \
  -PcheckIn=C:/path/elements.jsonl \
  -PcheckQuests=AddSidewalk,AddOpeningHours \
  -PcheckOut=C:/path/applicable.tsv
```

Output is a sorted TSV with columns `quest`, `type`, `id` (header row included), type `node`/`way`/`relation`. Counts per quest go to
stderr. Unknown quest names fail before the input is read. 2 million elements (500 MB) take about 20 s
in the 12 GB heap the task sets.

Caveats:

- Date filters use the wall clock, as the app does. Run the port against the same day.
- Country gating is not applied. The app also drops quests outside `enabledInCountries`
  (`OsmQuestController.mayCreateQuest`), e.g. `AddPostboxCollectionTimes` is `NoCountriesExcept(..., "CA", ...)`.
  Default-disabled quests (`AddRoadWidth`, and `AddMaxPhysicalHeight` without AR) are listed anyway.
- The registry is built with mocks for `ArSupportChecker`, `getCountryInfoByLocation`,
  `getCountryOrSubdivisionCode` and `getFeature`. A quest that calls one inside `getApplicableElements` would
  throw or return junk; the tool reports a quest that throws and exits non-zero. Checked at v63.4 for
  `AddSidewalk`, `AddOpeningHours`, `AddPostboxCollectionTimes`, `AddRecyclingContainerMaterials`,
  `CheckShopType`, `AddClothingBinOperator`, `AddOnewayAerialway`, `AddRoadWidth`, `AddMaxPhysicalHeight`:
  none does. Only `AddRoadWidth` and `AddMaxPhysicalHeight` take one (the AR checker), and they use it
  only for `defaultDisabledMessage`. Quests built with `getFeature` (`AddPlaceName`, `CheckExistence`,
  `AddIsAmenityIndoor`, ...) or `getCountryInfoByLocation` (`AddHousenumber`, `AddCycleway`, ...) need a
  look before you trust them here.
- The test fixture at v63.4 (45 elements covering those nine quests, hits and near misses) matched the
  expected list exactly.
