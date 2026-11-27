## Repin to StreetComplete v64.1 (2026-11-03)

- **What v64.1 changed for the counts.** No quest type added or removed (the registry imports only
  moved: AddAcceptsCards and AddAcceptsCash now live in `quests.payment`). Filters that move:
  - **AddAcceptsCards and AddAcceptsCash ask again with age.** Both share the new
    `PLACES_THAT_REQUIRE_PAYMENT_FILTER` (`osm/PaymentUtils.kt`), so AddAcceptsCards covers every place
    AddAcceptsCash did (fuel, cinemas, hotels, saunas, crafts...), not just food, drink and shops
    (branded places still do not ask for cards). Cards ask again when either payment tag is older than
    3 years; cash when `payment:cash = yes` is older than 2 years, or any `payment:cash` older than 4.
    Both now have `usesAge`, so the engine splits out their aging part by itself. AddAcceptsCards'
    rise is nearly all the wider place list: Ontario +3,385, of which 138 aged. AddAcceptsCash is only
    offered in FI, GB, IS, SE and NL, so it moves London, Amsterdam, Helsinki, Stockholm and Göteborg
    and nothing in Canada. `attraction` with a fee is gone from its list, `alpine_hut` joined it.
  - **`access !~ private|no`** on AddAerialwayBicycleAccess, AddAirCompressor, AddAirConditioning,
    AddAtmCashIn, AddAtmOperator, AddBicyclePump, AddBoatRental, AddClothingBinOperator (hand port),
    AddGritBinSeasonal, AddHairdresserCustomers and AddVendingMachineType: each loses its private
    places, a small drop.
  - **AddOpeningHours** (hand port): `healthcare`, `craft` and `office` join `updateFilterFragment`, so
    such a place is asked again once its `opening_hours` is over a year old, and a place without the
    tag is not asked. The whole rise is aged (Ontario +284).
  - **AddFirewood**: `fuel ~ ".*wood.*"` instead of `fuel = wood`, and shelters with a fireplace. Only
    offered in the Nordic countries, so it moves only Göteborg, Helsinki, København, Oslo and Stockholm.
  - **The note quest**: `#surveyneeded` in a comment makes a note a quest, as `#surveyme` does.
  - AddHousenumber, AddKerbHeight, AddTactilePavingKerb and AddMaxWeight changed only in their forms,
    answers or highlights: re-pinned, ports unchanged. AddBoardType likewise (highlights only).
- **What v64.1 changed for the engine.** SC's own fix for tag lengths in code points (8fe4c925) ships,
  so the `codepoints` patch is dropped and `util/ktx/CharSequence.kt` is vendored; `onepoint` stays (the
  same check is in v64.1). `MapDataXt.kt`'s filter cache takes an atomicfu lock, so the engine depends on
  `org.jetbrains.kotlinx:atomicfu:0.33.0`, SC's version. Kotlin, kotlinx-datetime, serialization,
  osmfeatures, the opening-hours parser, kaml and countryboundaries are unchanged, and so are the
  country metadata, presets and boundaries.
- **Checked.** The oracle gives identical sets for all 52 custom quests: Guelph 33,311 quests and
  Bremerhaven 20,413, both from the 2026-11-02 extracts, with the JVM of each side in the city's time
  zone. AddOpeningHours' new rule was exercised (Guelph's count rises by 4 against v64.0).
  AddClothingBinOperator's `access` line barely was (at most one private container in the two inputs),
  and the oracle does not cover the note quest (`#surveyneeded` has a unit test). 58 engine tests pass
  in the worktree. SnapshotReproductionTest and TorontoRegressionTest were skipped there: the first needs
  the untracked `data/cities/`, the second a pruned extract.
- **What the counts do**, measured in a scratch folder against the published v64.0 snapshot of the
  same extract, with the same notes: Ontario 7,876,687 to 7,880,332 (+0.05%; five quests move: AddAcceptsCards
  46,453 to 49,838, AddOpeningHours +284, AddAirCompressor -11, AddAirConditioning -11, AddGritBinSeasonal
  -2). London +0.10% (AddAcceptsCards 50,797 to 54,166, AddAcceptsCash 69,161 to 69,372 with 226 aged),
  Dublin +0.11%, Lisboa +0.42% (AddAcceptsCards 8,316 to 9,532). So a total barely breaks at the repin,
  and one quest's own line does, by 6 to 15%.
- **Where the break is.** The owner chose no recount: about 5 days of machine time for a move this small.
  Each region's newest extract was recounted with v64.1 at the merge and older snapshots stay on v64.0,
  so the series break there (Canada and Germany 2026-11-02, Europe 2026-11-03). AddAcceptsCards and
  AddAcceptsCash are off by default on the site, so the one visible step is not in a reader's default totals.
- **SnapshotReproductionTest cannot pass between the merge and the first v64.1 count.** It recounts a stored
  snapshot with that snapshot's own registry, but the hand ports are v64.1, so AddOpeningHours,
  AddClothingBinOperator and the note quest may differ from a v64.0 snapshot. Run `test` after
  `run.py count`, or read a failure limited to those quests as expected.

---
