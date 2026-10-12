# engine

Counts open StreetComplete quests from an OSM PBF extract by running StreetComplete's own element
filter code on a plain JVM. Status: **spike** (12 hardcoded filter quests, Toronto, Ontario extract).

## Licence

`src/main/kotlin/sc/` is StreetComplete source, **GPL-3.0** (licence text copied alongside). Linking it
into this program makes the engine a GPL-3.0 derivative, so this project needs a GPL-3.0-compatible
licence before it is published. The SC files carry no per-file headers upstream; they are copied
byte-for-byte (see the sha256 list in `SC-VERSION.txt`).

## Layout

- `sync-sc.ps1 -ScPath <SC checkout> -Tag v63.4` copies the needed SC `commonMain` files into
  `src/main/kotlin/sc/` (original packages) and writes `SC-VERSION.txt` (tag, commit, file hashes).
  **Patches: none.** The files compile unchanged because the build uses SC's Kotlin (2.4.0),
  kotlinx-datetime (0.8.0) and the kotlinx.serialization plugin (for `@Serializable` on `Element`).
- `src/main/kotlin/openquests/`
  - `Pbf.kt`: PBF blob reading and decoding on `org.openstreetmap.pbf:osmpbf` (protobuf bindings only).
  - `Polygon.kt`: city polygon from ontario-farmland's `cache/boundaries.json`, even-odd test.
  - `Quests.kt`: the spike's quest filters, pasted verbatim from SC v63.4 including their string
    templates.
  - `Spike.kt`: one pass over the file, staged nodes, then ways, then relations, each stage parallel.
- `run-spike.ps1`: runs the installed app and samples peak working set.
- `crosscheck_bench.py`: an independent pyosmium count for two quests, plus a version/timestamp check.

## Build and run

```powershell
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'   # JDK 21
./gradlew.bat installDist
./run-spike.ps1                       # writes out/spike-run.log and out/spike-matches.tsv
python crosscheck_bench.py            # needs out/spike-matches.tsv
```

## Spike approximations (to fix before the numbers go public)

- Element centre is the plain average of the way's nodes. For relations it is the average of member
  nodes and member-way centres; sub-relations are ignored. SC uses polygon centroids and line midpoints.
- `Way.nodeIds` and `Relation.members` are passed empty; no element filter reads them.
- Untagged elements are skipped. At start-up the app checks that no filter matches an untagged element.
- Filters are hardcoded. The real pipeline should take resolved filter strings from SC's quest registry,
  with `enabledInCountries`, default-disabled flags and custom quests.
- The time zone is pinned to `America/Toronto` (`-Duser.timezone`). `older`/`newer` and `RelativeDate`
  use the system zone.
