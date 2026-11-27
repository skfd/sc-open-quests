## The engine speed-up: built (2026-11-06)

The owner chose to build the steps of "A rewrite in a systems language" first and run the clean engine test
after. All of it is on main; `engine/README.md` has how each part works.

| area | old pass | new pass | old peak heap | new peak heap |
|---|---|---|---|---|
| Bremen, 2026-11-04 | 24.6 s | 15.0 s | 2.7 GB | 2.1 GB |
| Berlin, 2026-11-04 | 81.6 s | 47.2 s | 11.2 GB | 7.8 GB |
| Ontario, 2026-11-05 | 366.5 s | 204.3 s | 35.8 GB | 22.8 GB |

- **About 1.8 times on Ontario, below the 2 to 3 expected.** Not a clean number: the recut ran through every
  timing, and each old run came first, so it may also have read a cold file. The clean test decides.
- **A small heap no longer seems to cost much.** Ontario under `-Xmx16g` took 182 s with a 16.7 GB peak, faster
  than the 204 s at 40 GB, though it ran later and warm. It was 80 s slower before (2026-10-24).
- **What changed:** an area quest with no age test runs once; each run of an age quest is its own task; the fast
  reject (patch `fastreject`) with `TagMap`; `ArrayMapData`, which ends the serial map build (Berlin 12.4 s to
  4.6 s); the main pass skips all resurvey variants of a rejected element, and no longer boxes a Float for each.
- **Same counts:** Bremen, Berlin and Ontario, snapshot and grid, equal the old engine's apart from `runSeconds`
  and `engineCommit`. So does Bremen with `--area-unit tiles`, and Ontario under `-Xmx16g`. Berlin with
  `-Dopenquests.verifyFast=true` passed: all twins equal their ports, and every `usesAge = false` quest gives
  the same result at 1900. All other tests pass. SnapshotReproductionTest and TorontoRegressionTest were skipped.
- **The check earned its keep:** map data in id order moved Bremen's AddHousenumber by one. The quest gives a
  shared address node to the first building that reaches it, so it depends on the order a `HashMap<Long, ...>`
  iterates in, in the app too. `ArrayMapData` keeps that order. Any quest may depend on it, so it must stay.
- **Not done:** the age quests still walk the map data four times; one walk would save more, and patches more of SC's code.
- **What is left in a Berlin run:** about 85% of the machine while quests run, with a tail of about 5 s of 47
  (AddLevelThing). `LongIndex` lookups and the walk over all nodes lead the profile.
