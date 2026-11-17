---
title: How StreetComplete quests age
date: 2026-11-17
status: draft
---

# How StreetComplete quests age

Our counts sometimes go up on a day nobody touched the map. Nothing broke. Some StreetComplete
quests are built to come back: after a few years the app asks again whether the road is still
asphalt, the shop is still open, the bench is still there.[^grant] We call this **aging**, and
StreetComplete calls it **resurvey**.

This post explains which quests age, how long they wait, and how the app knows you already
checked. Everything below comes from StreetComplete's own source code, release v64.0. We count
with the app's code, so the site follows the same rules.

## The short version

- 67 of StreetComplete's 192 quest types can come back after they are answered.[^registry][^count]
  The rest only ask while a tag is missing or wrong, and once answered they are gone for good.
- Each aging quest has an interval, from two weeks to 16 years, often depending on the answer
  already on the map.
- The app remembers nothing on your phone. It reads dates that are stored in OpenStreetMap: when
  the object was last edited, and `check_date` tags.[^tag-age]
- Confirming an unchanged answer is still an edit. It writes `check_date:<key>=<today>`, and that
  stops the quest for everyone, not just you.[^update-with]

## Three ways a quest can age

A quest is a filter over OSM tags. A quest ages when its filter compares a date with "today minus
some time".[^filter-syntax] As days pass, an object that didn't match starts to match, with no edit
at all.

| Kind | What the filter says | Examples |
|---|---|---|
| **A tag is old** | `surface older today -12 years` | surface, lit, kerb height, tactile paving, wheelchair access, diets, capacity, fee, opening hours |
| **The whole object is old** | `older today -2 years` | "Is this still here?", "Is this shop still here?", "What is in this vacant shop now?", "Is the construction finished?" |
| **A date in a tag has passed** | `smoothness:date < today -4 years`, `opening_date < today` | road and path smoothness,[^smoothness] construction with an opening date[^building] |

## How long each quest waits

How often each interval appears across the quest filters:[^count]

| Interval | Uses |
|---|---|
| 16 years | 4 |
| 12 years | 9 |
| 8 years | 30 |
| 6 years | 10 |
| 4 years | 22 |
| 2 years | 5 |
| 18 months | 1 |
| 1 year | 5 |
| 6 months | 1 |
| 2 weeks | 1 |

The short ones are for things that change fast: opening hours[^opening-hours] and vacant
shops[^shop-type] (1 year), parking charge (18 months),[^charge] a building under construction (6
months),[^building] a road under construction (2 weeks).[^highway]

**The answer already on the map often sets the interval.** The answer that is more likely to
change is asked again sooner:

| Quest | Asked again sooner | Asked again later |
|---|---|---|
| Road surface | unpaved: 6 years | paved: 12 years[^road-surface] |
| Is this way lit? | `lit=no`: 8 years | `lit=yes`: 16 years[^lit] |
| Tactile paving at a crossing | no: 8 years | yes: 12 years[^tactile] |
| Kerb height | raised: 8 years | other kerbs: 12 years[^kerb] |
| Traffic signal sound | no: 4 years | yes: 8 years[^sound] |
| Ramp on steps | no: 4 years | yes: 8 years[^ramp] |

The "is this still here?" quest goes by what the object is:[^existence]

| Object | Asked again after |
|---|---|
| ATM, phone box, parcel locker, public bookcase, give box, vending machine | 2 years |
| Postbox, clock, ticket machine, picnic table, information board, defibrillator, camera | 4 years |
| Bench, waste basket, toilets, drinking water, recycling container, planter | 6 years |
| Bicycle or motorcycle parking, taxi stand, shelter | 10 years |
| Speed bump, hump, cushion | 14 years |

The main quests at each interval:[^count]

| Interval | Quests |
|---|---|
| 16 years | summit cross; way lit, bus stop lit and pitch lit (when `lit=yes`) |
| 12 years | road, pitch and motorcycle parking surface (paved); kerb height, tactile paving (when yes) |
| 8 years | path, footway, cycleway and sidewalk surface; parking fees; bike parking capacity; smoking; wheelchair access outside; railway crossing barrier; stile type |
| 6 years | road surface (unpaved); air compressor; bike shop pump, repair and second-hand; bike rental capacity; fire hydrant diameter |
| 4 years | bench, bin and shelter at a bus stop; vegan, vegetarian, halal, kosher, gluten-free; camp water, power and shower; summit register; smoothness; motorcycle parking capacity; ramps on steps (when no) |
| 2 years | internet access; postbox collection times; bicycle repair station services; opening hours signed; is this shop still here?[^shop-existence] |
| 1 year | opening hours; what is in this vacant shop now?; drinking water type (disused fountains only)[^drinking] |

**There is a setting for all of this.** In the app's settings, "resurvey intervals" multiplies
every interval: *more often* halves them, *default* keeps them, *less often* doubles
them.[^intervals-setting] Our headline numbers use the default.

**Coming next.** After v64.0, StreetComplete's development branch made two payment quests age too:
"accepts cash" comes back after 2 years when the answer is yes and 4 years when it is no, and
"accepts cards" after 3 years.[^main-payment] That change isn't in a release yet.

## How the app tells that a tag is old

OpenStreetMap does not record when each tag changed, only when the whole object was last edited.
So for "this tag is older than 8 years" StreetComplete counts the tag as old if **either** is
true:[^tag-age]

1. the object was last edited more than 8 years ago, **or**
2. a check date for that key is more than 8 years old. The app reads `check_date:surface`, and
   the older spellings `surface:check_date`, `lastcheck:surface` and
   `last_checked:surface`.[^check-keys]

Two things follow from this.

**Any edit resets the clock for every tag on the object.** If someone adds a name to a road, its
surface counts as freshly checked too, unless the surface has its own check date that is
old.[^tag-age]

**The object-wide `check_date` does not count here.** A plain `check_date=2025-06-01` speaks for
the object as a whole.[^check-keys-object] The "is this still here?" and shop quests read
it;[^existence][^shop-existence] the surface quest doesn't.

## What happens when you answer

| You answer | What the app writes |
|---|---|
| The same as what is on the map | Leaves the value and adds `check_date:<key>=<today>`[^update-with] |
| Something new | Writes the new value; adds or updates a check date only if the object already had one[^update-with] |
| "Yes, it's still here" or "still vacant" | `check_date=<today>` for the whole object[^existence-answer][^shop-type] |
| "No, it's gone" | Removes it from the map[^existence-answer] |

Confirming a value is a real edit, uploaded under your name. It moves the object's timestamp
and sets that key's own date, so the quest stays away for another full interval.

A new value doesn't get a check date unless the object already had one. The app avoids adding
`check_date` tags where the edit itself says enough: the new value is plainly new. Before v32,
the app deleted old check dates in this case; it stopped because that destroyed other surveyors'
data.[^update-with] When it does update a key's check date, it also updates the object's
`check_date` if there is one, so the two never disagree.[^set-for-key]

One side effect: because every edit refreshes the object's timestamp, answering one quest quietly
delays the other aging quests on the same object.[^tag-age] Confirm a road's surface and its
lighting won't be asked for a while either.

## The memory is shared

Because the dates live in OpenStreetMap, the memory is shared by everyone. Confirm a surface on
your phone and the quest disappears for every StreetComplete user, and from our counts the next
day. The one thing kept on the phone is "hide this quest": that stays on your device and never
reaches the map.[^hidden]

## Why we track it separately

A count that goes up is not always bad news. When a town's open quests rise, it might be new
data, or it might be that a batch of benches reached their sixth birthday. We count each aging
quest twice: once as the app would show it today, and once as if nothing could age. The
difference is the resurvey part, drawn in its own colour, so a rise from aging isn't read as
neglect.

## Further reading

- [StreetComplete/Quests](https://wiki.openstreetmap.org/wiki/StreetComplete/Quests), OpenStreetMap
  Wiki: every quest, with a resurvey column kept by volunteers.
- ["Map Maintenance with StreetComplete" final report](https://wiki.openstreetmap.org/wiki/Microgrants/Microgrants_2020/Proposal/Map_Maintenance_with_StreetComplete/Report),
  OpenStreetMap Wiki: how resurvey quests were built.
- ["StreetComplete: summary of re-survey quests and how they will be tagged"](https://lists.openstreetmap.org/pipermail/tagging/2020-August/054959.html),
  OSM tagging mailing list, August 2020. Some details changed since.
- [Key:check_date:surface](https://wiki.openstreetmap.org/wiki/Key:check_date:surface),
  OpenStreetMap Wiki.

## References

[^grant]: ["Map Maintenance with StreetComplete"](https://wiki.openstreetmap.org/wiki/Microgrants/Microgrants_2020/Proposal/Map_Maintenance_with_StreetComplete). *OpenStreetMap Wiki*, Microgrants 2020 proposal. Retrieved 17 November 2026.

[^registry]: StreetComplete. ["QuestTypesRegistry.kt"](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/QuestTypesRegistry.kt). Source code, v64.0. Retrieved 17 November 2026. 192 quest types are registered.

[^count]: Counted by us in the v64.0 source: the quest files whose filter contains `older today` or `< today`, and the intervals written in them. The "is this still here?" quest builds its intervals in code and is listed separately.

[^filter-syntax]: StreetComplete. ["ElementFilterExpression.kt", lines 48–51](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/data/elementfilter/ElementFilterExpression.kt#L48-L51). Source code, v64.0. Retrieved 17 November 2026. The documented `older` and `< today` syntax.

[^tag-age]: StreetComplete. ["ElementFilter.kt", lines 140–152](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/data/elementfilter/filters/ElementFilter.kt#L140-L152). Source code, v64.0. Retrieved 17 November 2026. `CompareTagAge`: the object's last edit, then the key's check dates.

[^update-with]: StreetComplete. ["ResurveyUtils.kt", lines 44–56](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/osm/ResurveyUtils.kt#L44-L56). Source code, v64.0. Retrieved 17 November 2026. `updateWithCheckDate`.

[^smoothness]: StreetComplete. ["AddRoadSmoothness.kt", lines 26–27](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/smoothness/AddRoadSmoothness.kt#L26-L27). Source code, v64.0. Retrieved 17 November 2026.

[^building]: StreetComplete. ["MarkCompletedBuildingConstruction.kt", lines 20–21](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/construction/MarkCompletedBuildingConstruction.kt#L20-L21). Source code, v64.0. Retrieved 17 November 2026.

[^opening-hours]: StreetComplete. ["AddOpeningHours.kt", line 119](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/opening_hours/AddOpeningHours.kt#L119). Source code, v64.0. Retrieved 17 November 2026.

[^shop-type]: StreetComplete. ["CheckShopType.kt", lines 40 and 73](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/shop_type/CheckShopType.kt#L40). Source code, v64.0. Retrieved 17 November 2026. A vacant shop or office, asked again after a year; "still vacant" sets `check_date`.

[^charge]: StreetComplete. ["AddParkingCharge.kt", line 22](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/charge/AddParkingCharge.kt#L22). Source code, v64.0. Retrieved 17 November 2026.

[^highway]: StreetComplete. ["MarkCompletedHighwayConstruction.kt", lines 22–23](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/construction/MarkCompletedHighwayConstruction.kt#L22-L23). Source code, v64.0. Retrieved 17 November 2026.

[^road-surface]: StreetComplete. ["AddRoadSurface.kt", lines 46–47](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/surface/AddRoadSurface.kt#L46-L47). Source code, v64.0. Retrieved 17 November 2026.

[^lit]: StreetComplete. ["AddWayLit.kt", lines 52–53](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/way_lit/AddWayLit.kt#L52-L53). Source code, v64.0. Retrieved 17 November 2026.

[^tactile]: StreetComplete. ["AddTactilePavingCrosswalk.kt", lines 35–36](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/tactile_paving/AddTactilePavingCrosswalk.kt#L35-L36). Source code, v64.0. Retrieved 17 November 2026.

[^kerb]: StreetComplete. ["AddKerbHeight.kt", lines 31–32](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/kerb_height/AddKerbHeight.kt#L31-L32). Source code, v64.0. Retrieved 17 November 2026.

[^sound]: StreetComplete. ["AddTrafficSignalsSound.kt", lines 28–29](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/traffic_signals_sound/AddTrafficSignalsSound.kt#L28-L29). Source code, v64.0. Retrieved 17 November 2026.

[^ramp]: StreetComplete. ["AddStepsRamp.kt", lines 32–33](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/steps_ramp/AddStepsRamp.kt#L32-L33). Source code, v64.0. Retrieved 17 November 2026.

[^existence]: StreetComplete. ["CheckExistence.kt", lines 29–73](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/existence/CheckExistence.kt#L29-L73). Source code, v64.0. Retrieved 17 November 2026. The object groups and their 2, 4, 6, 10 and 14 years; `lastChecked` reads the object's last edit and its `check_date`.

[^shop-existence]: StreetComplete. ["CheckShopExistence.kt", lines 42 and 77](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/shop_type/CheckShopExistence.kt#L42). Source code, v64.0. Retrieved 17 November 2026.

[^drinking]: StreetComplete. ["AddDrinkingWaterType.kt", line 24](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/drinking_water_type/AddDrinkingWaterType.kt#L24). Source code, v64.0. Retrieved 17 November 2026.

[^intervals-setting]: StreetComplete. ["ResurveyIntervals.kt", lines 6–10](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/data/preferences/ResurveyIntervals.kt#L6-L10). Source code, v64.0. Retrieved 17 November 2026.

[^main-payment]: StreetComplete. ["AddAcceptsCash.kt", lines 31–32](https://github.com/streetcomplete/StreetComplete/blob/c994ef37e43652a1fe639b7e3e52ee986a01afe6/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/payment/AddAcceptsCash.kt#L31-L32) and ["AddAcceptsCards.kt", lines 31–32](https://github.com/streetcomplete/StreetComplete/blob/c994ef37e43652a1fe639b7e3e52ee986a01afe6/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/payment/AddAcceptsCards.kt#L31-L32). Source code, development branch as of 16 November 2026. Retrieved 17 November 2026.

[^check-keys]: StreetComplete. ["ResurveyUtils.kt", lines 7–13](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/osm/ResurveyUtils.kt#L7-L13). Source code, v64.0. Retrieved 17 November 2026. `getLastCheckDateKeys`.

[^check-keys-object]: StreetComplete. ["ResurveyUtils.kt", lines 15–22](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/osm/ResurveyUtils.kt#L15-L22). Source code, v64.0. Retrieved 17 November 2026. `LAST_CHECK_DATE_KEYS`: `check_date`, `lastcheck`, `last_checked`, `survey:date`, `survey_date`.

[^existence-answer]: StreetComplete. ["CheckExistence.kt", lines 114–121](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/existence/CheckExistence.kt#L114-L121). Source code, v64.0. Retrieved 17 November 2026.

[^set-for-key]: StreetComplete. ["ResurveyUtils.kt", lines 65–71](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/osm/ResurveyUtils.kt#L65-L71). Source code, v64.0. Retrieved 17 November 2026. `setCheckDateForKey`.

[^hidden]: StreetComplete. ["QuestsHiddenController.kt"](https://github.com/streetcomplete/StreetComplete/blob/v64.0/app/src/commonMain/kotlin/de/westnordost/streetcomplete/data/visiblequests/QuestsHiddenController.kt). Source code, v64.0. Retrieved 17 November 2026.
