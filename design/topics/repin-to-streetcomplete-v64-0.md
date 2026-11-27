## Repin to StreetComplete v64.0 (2026-10-21)

- **The operation has a name: repin.** Everything the engine counts with is pinned to one SC tag (the
  vendored source, the ports, the registry dump, icons, release pins); moving them all is a repin, the
  routine is [REPIN.md](REPIN.md). The scheduled update now ends with `run.py check-release`: it
  refreshes `docs/data/sc-releases.json` and opens the GitHub issue "Repin to StreetComplete vX.Y"
  once when a stable release is newer than `engine/SC-VERSION.txt`. It is the one network dependency
  the daily run has besides the extracts, and it cannot fail the run: the data is published first, and
  any error in it is logged and ignored.
- **What v64.0 changed for the counts.** 193 quest types (was 190): added AddDoctorType,
  AddVendingMachineType, AddGeneralAccess (replaces AddPlaygroundAccess and AddTowerAccess),
  AddChargingStationSocket (custom: a charging station without mapped charge points) and
  AddChargingStationMotorcar (the two replace AddChargingStationCapacity and
  AddChargingStationBicycleCapacity), AddParkingCharge, AddMotorcycleParkingSurface, AddLockable; removed
  AddProhibitedForPedestrians. 57 filter quests and three hand-ported ones (AddOpeningHours,
  CheckOpeningHoursSigned, AddPlaceName) now take relations; CheckShopExistence no longer requires a
  name (a nameless shop whose preset has a name counts, so it rises); AddIsAmenityIndoor asks for
  bicycle repair stations too. A removed quest leaves the table (quests.json is the newest registry)
  while its series stays in the history files.
- **What v64.0 changed for the engine.** SC became multiplatform: every quest moved from androidMain
  to commonMain, with a Compose form instead of an Android one, so sync-sc.ps1 and the port generator
  read commonMain, the generator drops Compose imports and annotations, and a `Foo.*` import of a
  quest package stays only when the kept code names Foo. SC started caching a date filter's threshold
  (`by lazy`); that would freeze the engine's movable clock and resurvey multiplier after the first
  evaluation, so a third recorded patch, `nolazy`, makes both getters again. New stubs: Compose's
  `LocaleList` (the phone's locale list is the JVM's default locale, en-CA, so
  `getLanguagesForFeatureDictionary()` gives en-CA, en, null), `DrawableResource` and
  `Res.allDrawableResources` (osm/Feature.kt grew an icon lookup), `ApplicationConstants`
  (`MAX_OSM_TAG_VALUE_LENGTH`; `Element` now requires every tag key and value to be at most 255
  characters, which OSM's API guarantees), `readYamlOrNull`. SC's harness needs a JDK 25 since v64
  (Gradle downloads it: tools/sc-harness/README.md).
- **Checked.** The oracle (SC's own classes on the same map data) gives identical sets for all 52
  custom quests on Guelph (33,389 quests) and, for the first time, on a German city: Bremerhaven
  (20,404; AddCycleway, AddHousenumber and AddRoofShape read DE.yml there). The three fast twins
  match their ports on both. The engine's unit tests pass; TorontoRegressionTest stays on v63.4.json
  on purpose (it regresses the vendored filter and geometry code, not the quest set).
- **Where the break is.** After a repin `run.py count` (also inside `update`'s backfill) recounts
  the newest extract of each region with the new registry and leaves the older ones in the store
  alone, so by default the first v64 snapshot is the newest extract at merge time and the totals chart
  marks the change of the counted set there ("+8 types 64.0"), as it did for the custom quests. **For
  v64.0 there is no such break:** the Canada backfill of the same night (next section) recounted every
  published Ontario and German snapshot with v64.0 too, so every series carries one registry and the
  site's break list, which compares consecutive snapshots, has nothing to mark. The branch carried no
  data commit on purpose: the daily "data" commits would conflict with it in the generated history
  files; the first run from main after the merge made it.
- **Merging `sc-v64` into main** (written while another session had uncommitted province work in
  main): `engine/SC-VERSION.txt` is generated, never hand-merged; after the merge rerun
  `engine/sync-sc.ps1 -ScPath <Temp/sc-v64.0> -Tag v64.0` with whatever the other side added to
  `$resources` (its `CA-*.yml` must exist in the v64 checkout). `sync-sc.ps1`, `engine/README.md`,
  `CountriesTest.kt` and `CountryInfoQuestsTest.kt` hand-merge, both sides are additive. Then, from
  main and before the next 13:15: `engine/gradlew installDist` and `test` (the first build downloads
  Kotlin 2.4.20; do not leave that to the scheduler), `python run.py count`, `history`, and commit the
  data. `tools/sc_assets.py` ran already (the icons commit). Ontario's count went from 196 s to
  245 s: CheckShopExistence now asks the feature dictionary for every nameless place before its age
  filter, as SC does. `gh` under Task Scheduler is unproven; a failure shows as
  "check-release failed (ignored)" in `logs/scheduler.log`.
