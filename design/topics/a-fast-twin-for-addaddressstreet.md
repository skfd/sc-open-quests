## A fast twin for AddAddressStreet (2026-11-07)

Paris took a quarter of a day's engine time on one quest. SC's AddAddressStreet asks, for every address,
whether any `associatedStreet` or `street` relation lists it, by scanning every member of every such relation;
France maps its streets that way. `openquests/fast/FastAddAddressStreet.kt` looks the members up in a set:
the same members, so the same result.

- **Checked:** `-Dopenquests.verifyFast=true` on Paris and Toulouse (europe-2026-11-06) ran SC's port next to the
  twin and found no difference; the twin's snapshot equals the published one in every field of all 183 quests.
- **Speed:** Paris's area pass 473 s to 22 s, Toulouse 79 s to 7 s, on the engine after the 2026-11-06 speed-up.
  The quest drops out of the slowest three in both. The planet estimate's worst known cell goes with it.
