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

Windows, Git Bash. The Android SDK, and a JDK the tag's `buildSrc` accepts: JDK 21 from Android Studio
up to v63, JDK 25 since v64 (see the v64.0 run below).

```sh
TAG=v64.0
git clone --depth 1 --branch $TAG https://github.com/streetcomplete/StreetComplete.git /tmp/sc-$TAG
cd /tmp/sc-$TAG
git fetch --depth 1 origin tag v63.4        # the previous pin, for `git diff v63.4 v64.0 -- <file>`
printf 'sdk.dir=C:/Users/kk/AppData/Local/Android/Sdk\n' > local.properties   # forward slashes

# 1. which unit-test source set does this tag use?
ls app/src   # androidHostTest (>= v64)  or  androidUnitTest (<= v63.x)
cp ~/Code/sc-open-quests/tools/sc-harness/{DumpQuestFilters,CheckCustomQuests}.kt \
   app/src/androidHostTest/kotlin/de/westnordost/streetcomplete/   # or androidUnitTest/...
# (<= v63: OsmNoteQuestType was in quests.note_discussion; edit the import in both files)

# 2. append the tasks; on androidUnitTest tags change "testAndroidHostTest" to "testDebugUnitTest"
cat ~/Code/sc-open-quests/tools/sc-harness/build.gradle.kts.snippet >> app/build.gradle.kts

# 3. run (>= v64: on a JDK 25, see below; <= v63: JAVA_HOME="/c/Program Files/Android/Android Studio/jbr")
export JAVA_HOME="$HOME/.gradle/jdks/eclipse_adoptium-25-amd64-windows.2"
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

## v64.0 run (2026-10-21)

- `buildSrc` asks for a JDK 25 toolchain and refuses to run on Gradle's own JVM below 25, so: add
  `plugins { id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0" }` to the root
  `settings.gradle.kts` after the `pluginManagement` block, the same id without a version to a new
  `buildSrc/settings.gradle.kts` (with a `pluginManagement { repositories { gradlePluginPortal() } }`),
  run once on JDK 21 so Gradle downloads JDK 25 into `~/.gradle/jdks/`, then run with `JAVA_HOME` at it.
- Gradle 9.7.1 (wrapper); it fetched Android SDK Platform 37 by itself.
- First build (`:app:compileAndroidHostTestKotlinAndroid` with the whole multiplatform app, cold Gradle 9.7.1
  and the JDK 25 download): 12 min 3 s. The dump itself then takes seconds.
- 193 registry entries: 140 `filter`, 52 `custom`, 1 `note`. All 140 filter strings re-parse. Against
  v63.4: added AddChargingStationMotorcar, AddChargingStationSocket (custom), AddDoctorType,
  AddGeneralAccess, AddLockable, AddMotorcycleParkingSurface, AddParkingCharge, AddVendingMachineType;
  removed AddChargingStationBicycleCapacity, AddChargingStationCapacity, AddPlaygroundAccess,
  AddProhibitedForPedestrians, AddTowerAccess. 57 filters now name relations.
- `questTypeRegistry(mock(), mock(), mock(), mock())` still compiles: the four parameters are the same.

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
 "lat":43.6,"lon":-79.4,"nodes":[1,2,3],"inCity":true}
{"type":"relation","id":7,"tags":{"type":"multipolygon","building":"retail"},
 "members":[{"type":"way","ref":123,"role":"outer"}]}
{"type":"node","id":1,"tags":{},"lat":43.6,"lon":-79.4}
```

- `timestamp` is epoch milliseconds (SC's `timestampEdited`). Leave it out and the element counts as
  edited in 1970, so every `older today -N years` rule matches; the tool warns with a count.
- Nodes need `lat`/`lon`. Untagged nodes (`"tags":{}`) belong in the input whenever a quest looks at
  the map around an element: way nodes for `AddCrossing`, `AddKerbHeight`, `AddEntrance`,
  `AddBarrierOnPath`, ...
- `nodes` (ways) and `members` (relations) list the element's parts. Without `nodes` a way has no node
  ids, so `isClosed` is false.
- `lat`/`lon` on ways and relations is optional, and only a fallback (below).
- `inCity` (optional, `true`/`false`): `false` marks context, an element outside the counted area. It is
  in the map data the quests see, but it is never listed. A line without the field counts as `true`, so
  inputs without it behave as before.
- Bad lines are skipped and counted.

Geometry is built the way the app builds its map data on download (`MapDataControllerImpl`): all
elements go in first, then a node gets a point at its position, and ways and relations get SC's own
`ElementGeometryCreator().create(element, mapData, allowIncomplete = true)`: a polyline or polygon from
their nodes, a relation from whichever member ways are complete. If that gives nothing (nodes missing
from the input, no `nodes`/`members`, too few positions) the element's own `lat`/`lon` becomes a point;
without those it has no geometry. stderr says how many were built, fell back, or have none.

Then each quest's applicable elements are filtered as `OsmQuestController.createQuestsForBBox` does:
an element without geometry is dropped (`getGeometry(...) ?: continue`), and with a bounding box given,
one whose geometry centre lies outside it is dropped (`mayCreateQuest`). Then the `inCity:false` ones.
stderr gives the drops per quest and reason.

```sh
./gradlew --console=plain :app:checkCustomQuests   -PcheckIn=C:/path/elements.jsonl   -PcheckQuests=AddSidewalk,AddOpeningHours   -PcheckBbox=43.58,-79.64,43.86,-79.11   -PcheckOut=C:/path/applicable.tsv
```

- `-PcheckBbox=south,west,north,east` (optional) is the downloaded area. It becomes the map data's
  `boundingBox` and the centre rule above applies. Without it the box covers every `lat`/`lon` in the
  input and nothing is dropped for position.

Output is a sorted TSV with columns `quest`, `type`, `id` (header row included), type `node`/`way`/`relation`. Counts per quest go to
stderr. Unknown quest names fail before the input is read. 6.9 million lines (1.1 GB, Toronto with every
way node) take about 27 s for 13 quests: 12 s to read, 2 s for geometry, 3.4 GB of heap in use (the task
sets 20 GB).

Caveats:

- Date filters use the wall clock, as the app does. Run the port against the same day.
- Country gating is not applied. The app also drops quests outside `enabledInCountries`
  (`OsmQuestController.mayCreateQuest`), e.g. `AddPostboxCollectionTimes` is `NoCountriesExcept(..., "CA", ...)`.
  Default-disabled quests (`AddRoadWidth`, and `AddMaxPhysicalHeight` without AR) are listed anyway.
- The registry is built as the app builds it, except for the AR checker, which is a mock.
  - `getFeature` is SC's feature dictionary over the checkout's presets, in en-CA.
  - `getCountryInfoByLocation` and `getCountryOrSubdivisionCode` read the checkout's `boundaries.ser` with SC's
    `CountryBoundariesImpl`, as `AndroidModule2` wires them. For the metadata, CountryInfos reads
    `country_metadata/*.yml` through Compose resources, which do not load on the unit-test classpath, so its
    `load()` is mirrored: kaml with `strictMode = false`, with `countryCode: XX` prepended, region files
    smallest region first, then `default.yml`. `-PcheckFiles=<dir>` points it at another composeResources
    `files` folder.

  A quest that calls the AR mock inside `getApplicableElements` would throw or return junk; the tool reports a
  quest that throws and exits non-zero. AddRoadWidth, AddMaxPhysicalHeight and AddBarrierOpening use the AR
  checker for `defaultDisabledMessage` only.
- The test fixture at v63.4 (45 elements covering those nine quests, hits and near misses) matched the
  expected list exactly, before and after real geometry came in.
- A second hand-built fixture (67 lines) covers the quests that need the surrounding map: a road crossed
  by a footway at a shared untagged node (`AddCrossing`), a `barrier=kerb` node on a footway and a
  `barrier=kerb` way crossing one (`AddKerbHeight`), a footway ending on an apartments outline and on a
  multipolygon building relation (`AddEntrance`), a fence crossed by a path (`AddBarrierOnPath`), each
  with a near miss; plus an `inCity:false` copy of the crossing, and ways with no / missing nodes for the
  geometry rules (`AddSidewalk`). It matched with and without a bounding box.
- `ElementGeometryCreator` can throw on a degenerate shape (a sliver polygon whose centroid falls off the
  globe). The app does not guard that; here the element counts as having no built geometry, and stderr
  names the first ten.
