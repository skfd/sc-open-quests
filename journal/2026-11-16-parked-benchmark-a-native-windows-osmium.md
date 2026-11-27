## Parked: benchmark a native Windows osmium (owner, 2026-11-16, about 22:30: "lets put benchmarking it into todo")

- **It exists (checked 11-16, about 22:35):** conda-forge builds `osmium-tool` for win-64, versions 1.18.0, 1.19.0 and
  1.19.1 (the latest on every platform; the Docker image is 1.18). Not on MSYS2; osmcode's GitHub releases ship no
  binaries. No conda, mamba, micromamba or pixi is installed here: the install is one micromamba (single exe) or
  pixi, into its own env (no change to the Docker image). Not yet run: whether every command we use works there.
- **Why (as asked):** every osmium time we had went through Docker's mount (reads 4.5x slower, a pass 1.85x), so
  the Rust-vs-osmium figures seemed unfair to osmium. For history work native turned out slower, not faster
  (below); Rust `tilestore at` 1.4 s against native `time-filter` 21-24 s on Berlin.
- **Still to measure:** `fileinfo -e` and `extract -s smart` on a Europe clip (Docker: 19-20 s / 74 s through the
  mount, 4.4 s / 40 s on container disk), warm and cold, when the machine is quiet.
- **Decides:** whether release 2's monthly backfill (`backfill_history.py` slices and cuts) stays on osmium, goes
  native, or moves to Rust. Not before release 1's catch-up.
- **Switching, asked by the owner (11-16, about 22:40: "maybe we can look into switching to it now?").** The install was
  refused by auto mode (downloading and running micromamba): it needs the owner's explicit yes. Timings wait for a
  quiet machine (at 22:40 the store's catch-up and two release-1 jobs held about 46 GB). Every Docker osmium caller:
  - **osm-extracts** (`osm_extracts.py`, `OSMIUM_IMAGE`; shared with the other projects): `apply-changes -H` (the
    planet history kept current: 2-3 h a week through the mount, the biggest gain), clips' `extract -s smart`,
    `check-refs`, `merge`, `extract --with-history`, `time-filter`. Its own change, its own repo, all projects' runs.
  - **here:** `backfill_history.py` (`extract --with-history`, `time-filter`), `add_parts.py` (`getid -r`,
    `export`), `world_cells.py` cut (`extract -s smart`; the storecut from the Rust store replaced it in release 1's
    plan), `tilecheck/atcheck.sh` (test). The Overpass bench runs osmium inside the Overpass container: stays.
  - **How:** one knob per repo (`OSMIUM=docker|native` or a path), default Docker until each command's output is
    shown equal (same file through both: `osmium diff -q`, or byte-equal where the writer is deterministic), then
    the default flipped. Native osmium takes Windows paths, so the `/osm`, `/in`, `/out` mapping goes behind the knob.
    Order: the install and a smoke run of every command above; timings when quiet; here first (small, ours);
    osm-extracts after, its next weekly history update as the proof.
- **Installed and smoke-tested (11-16, 22:45-23:20; owner: pixi via winget, "both repos").** pixi 0.81.0 (winget
  `prefix-dev.pixi`, `%LOCALAPPDATA%\pixi\bin\pixi.exe`); `pixi global install osmium-tool=1.19.1`: launcher
  `~/.pixi/bin/osmium.exe`, the real exe `~/.pixi/envs/osmium-tool/Library/bin/osmium.exe`. Provenance checked:
  the package's sha256 equals anaconda.org's; the feedstock's recipe pins osmcode's v1.19.1 tarball, whose sha256
  matches a fresh download. Docker's image untouched.
  - **Same output, every command** (`.scratch/osmium-native/smoke.sh`, Bremen 11-02 and Berlin's history 261005,
    planet diff 5165): `extract -s smart -b`, `-s complete_ways -p`, `--with-history`, `time-filter`,
    `apply-changes`, `apply-changes -H`, `sort`, `getid -r`, `cat -f osm`, `merge` (pbf + xml), `export
    geojsonseq` all equal by `osmium diff -q` or text; `check-refs -r` equal but for CRLF line ends (parse
    tolerantly if switched).
  - **But native is 2-3x slower on history decodes and diff applies** (the machine was busy, both sides
    alternating, so ratios not absolutes; Docker's times include its mount): Berlin history extract 34 s against
    97 s; `time-filter` 8-12 s against 21-24 s; `apply-changes` 15 s against 42 s; `apply-changes -H` 41 s against
    113 s. Native was faster on the only snapshot extracts run (Bremen, 20 MB: 9.5/10.6 s Docker against 2.8/4.2 s,
    where Docker's start and mount may dominate). Not the file write (to a pipe the same); thread count barely
    matters (`OSMIUM_POOL_THREADS=1` 29-47 s, 4 and 8 about the default); not zlib (uncompressed, native reads
    Berlin's history in about 19 s, the same as compressed; Docker reads it compressed in 9 s). Only round 2 of
    the zlib rerun is clean (a Docker run overlapped round 1). `.scratch/osmium-native/threads.sh`, `zlib.sh`.
  - **Cause unknown.** Three things differ: version (1.18.0 / libosmium 2.22 against 1.19.1 / 2.23.1), platform
    and compiler, allocator. The Rust store's heap problem looked different (there one thread was faster).
    Cheapest discriminator: conda-forge's native `osmium-tool=1.18.0` in a second pixi env, same files.
  - **Not measured:** snapshot work at size (`fileinfo -e`, `extract -s smart` on the 1.75 GB Europe clip) and
    anything planet-sized; "the weekly planet update would get slower" is a projection from Berlin, not shown.
    The earlier "native osmium might be 5-10 s on Berlin" (this evening's Rust-vs-osmium answer) was wrong: 21-24 s.
  - **So nothing switched**, owner's call (asked). Test outputs deleted (5 GB); the three scripts kept. To remove
    the install: `pixi global uninstall osmium-tool`, `winget uninstall prefix-dev.pixi`. A mimalloc build of
    osmium (conda-forge `mimalloc` 3.6.1 has win-64) was refused by auto mode and is not the next step.
- **The owner's answer (11-16, 23:35): "we will have to retest on quiet machine. also please research reports about
  it on github or wherever they host".** The retest is open: `smoke.sh`, `threads.sh`, `zlib.sh` again with no
  store run, catch-up or release-1 job going (check `Get-Process tilestore*,python,java` first), plus the Europe clip
  (`fileinfo -e`, `extract -s smart`) and, if the owner allows its install, native `osmium-tool=1.18.0` beside 1.19.1.
- **Research (11-16, 23:30-23:45): no report anywhere of osmium being slower on Windows**, and no benchmark of it.
  - Searched osmcode/osmium-tool, libosmium and pyosmium issues, both conda-forge feedstocks, all of GitHub and the
    web. Rate-limited partway through GitHub's search, but the later broad searches returned nothing relevant.
  - **Windows is built, not tuned:** the maintainer, in osmium-tool#59, "I personally don't know anything about
    Windows"; Windows issues there are about compiling (#263, #59), never speed.
  - **conda-forge's build is a plain CMake Release build** (`recipe/build.bat`, Ninja, MSVC); no allocator choice,
    so it runs on the default Windows heap.
  - **One concrete lead, for diff applies only:** libosmium 2.23.1 `osm/timestamp.hpp` parses XML timestamps with
    `_mkgmtime` on Windows (`timegm` elsewhere). libosmium#363 found the same call (`timegm`) made XML parsing
    1000x slower on iOS and was closed as the vendor's problem. `.osc` diffs are XML, so `apply-changes` could pay
    this. PBF timestamps are integers, so it cannot explain `time-filter` or `fileinfo -e` on PBF.
  - **General Windows heap evidence, not osmium's:** an LLVM RFC measured the CRT allocator at 38 min against
    mimalloc's 2 min 22 s on a 36-core link; GDAL users reported `free()` of many small allocations slowing more
    than linearly. libosmium allocates per block in its pool threads, so it fits, but is still not shown.
  - libosmium's changelog 2.22 to 2.23.1 names no speed change, so a version regression is unlikely but not ruled
    out (that is what native 1.18.0 would test).
