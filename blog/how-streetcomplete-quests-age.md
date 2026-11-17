---
title: How StreetComplete quests age
date: 2026-11-17
status: draft
---

# How StreetComplete quests age

Our counts sometimes go up on a day nobody touched the map. Nothing broke. Some StreetComplete
quests are built to come back: after a few years the app asks again whether the road is still
asphalt, the shop is still open, the bench is still there. We call this **aging**, and
StreetComplete calls it **resurvey**.

This post explains which quests age, how long they wait, and how the app knows you already
checked. Everything below comes from StreetComplete's own source (v64). We count with the app's
code, so the site follows the same rules.

## The short version

- About 70 of StreetComplete's roughly 190 quest types can come back after they are answered. The
  rest only ask while a tag is missing or wrong, and once answered they are gone for good.
- Each aging quest has an interval, from two weeks to 16 years, often depending on the answer
  already on the map.
- The app remembers nothing on your phone. It reads dates that are stored in OpenStreetMap: when
  the object was last edited, and `check_date` tags.
- Confirming an unchanged answer is still an edit. It writes `check_date:<key>=<today>`, and that
  stops the quest for everyone, not just you.

## Three ways a quest can age

A quest is a filter over OSM tags. A quest ages when its filter compares a date with "today minus
some time". As days pass, an object that didn't match starts to match, with no edit at all.

| Kind | What the filter says | Examples |
|---|---|---|
| **A tag is old** | `surface older today -12 years` | surface, lit, kerb height, tactile paving, wheelchair access, diets, payment, capacity, fee, opening hours |
| **The whole object is old** | `older today -2 years` | "Is this still here?", "Is this shop still here?", "What is in this vacant shop now?", "Is the construction finished?" |
| **A date in a tag has passed** | `smoothness:date < today -4 years`, `opening_date < today` | road and path smoothness, construction with an opening date |

## How long each quest waits

How often each interval appears across the quest filters:

| Interval | Uses |
|---|---|
| 16 years | 4 |
| 12 years | 9 |
| 8 years | 30 |
| 6 years | 10 |
| 4 years | 23 |
| 3 years | 2 |
| 2 years | 6 |
| 18 months | 1 |
| 1 year | 5 |
| 6 months | 1 |
| 2 weeks | 1 |

The short ones are for things that change fast: opening hours and vacant shops (1 year), parking
charge (18 months), a building under construction (6 months), a road under construction (2
weeks).

**The answer already on the map often sets the interval.** The answer that is more likely to
change is asked again sooner:

| Quest | Asked again sooner | Asked again later |
|---|---|---|
| Road surface | unpaved: 6 years | paved: 12 years |
| Is this way lit? | `lit=no`: 8 years | `lit=yes`: 16 years |
| Tactile paving | no: 8 years | yes: 12 years |
| Kerb height | raised: 8 years | other kerbs: 12 years |
| Traffic signal sound or vibration | no: 4 years | yes: 8 years |
| Accepts cash | `yes`: 2 years | `no`: 4 years |

The "is this still here?" quest goes by what the object is:

| Object | Asked again after |
|---|---|
| Postbox, clock, ticket machine, picnic table, information board, defibrillator, camera | 4 years |
| Bench, waste basket, toilets, drinking water, recycling container, planter | 6 years |
| Bicycle or motorcycle parking, taxi stand, shelter | 10 years |
| Speed bump, hump, cushion | 14 years |

More of the intervals, quest by quest:

| Interval | Quests |
|---|---|
| 16 years | summit cross; way lit, bus stop lit and pitch lit (when `lit=yes`) |
| 12 years | road, pitch and motorcycle parking surface (paved); kerb height, tactile paving (when yes) |
| 8 years | path, footway, cycleway and sidewalk surface; parking fees; bike parking capacity; smoking; wheelchair access outside; railway crossing barrier; stile type |
| 6 years | road surface (unpaved); air compressor; bike shop pump, repair and second-hand; bike rental capacity; fire hydrant diameter |
| 4 years | bench, bin and shelter at a bus stop; vegan, vegetarian, halal, kosher, gluten-free; camp water, power and shower; summit register; smoothness; motorcycle parking capacity; ramps on steps; accepts cash (when no) |
| 3 years | accepts cards |
| 2 years | internet access; postbox collection times; bicycle repair station services; opening hours signed; accepts cash (when yes); is this shop still here? |
| 1 year | opening hours; what is in this vacant shop now?; drinking water type (disused fountains only) |

**There is a setting for all of this.** In the app's settings, "resurvey intervals" multiplies
every interval: *more often* halves them, *default* keeps them, *less often* doubles them. Our
headline numbers use the default.

## How the app tells that a tag is old

OpenStreetMap does not record when each tag changed, only when the whole object was last edited.
So for "this tag is older than 8 years" StreetComplete counts the tag as old if **either** is true:

1. the object was last edited more than 8 years ago, **or**
2. a check date for that key is more than 8 years old. The app reads `check_date:surface`, and
   the older spellings `surface:check_date`, `lastcheck:surface` and `last_checked:surface`.

Two things follow from this.

**Any edit resets the clock for every tag on the object.** If someone adds a name to a road, its
surface counts as freshly checked too, unless the surface has its own check date that is old.

**The object-wide `check_date` does not count here.** A plain `check_date=2025-06-01` speaks for
the object as a whole. The "is this still here?" and shop quests read it; the surface quest
doesn't.

## What happens when you answer

| You answer | What the app writes |
|---|---|
| The same as what is on the map | Leaves the value and adds `check_date:<key>=<today>` |
| Something new | Writes the new value; adds or updates a check date only if the object already had one |
| "Yes, it's still here" or "still vacant" | `check_date=<today>` for the whole object |
| "No, it's gone" | Removes it from the map |

Confirming a value is a real edit, uploaded under your name. It moves the object's timestamp
and sets that key's own date, so the quest stays away for another full interval.

A new value doesn't get a check date unless the object already had one. The app avoids adding
`check_date` tags where the edit itself says enough: the new value is plainly new. When it does
update a key's check date, it also updates the object's `check_date` if there is one, so the two
never disagree.

One side effect: because every edit refreshes the object's timestamp, answering one quest quietly
delays the other aging quests on the same object. Confirm a road's surface and its lighting won't
be asked for a while either.

## The memory is shared

Because the dates live in OpenStreetMap, the memory is shared by everyone. Confirm a surface on
your phone and the quest disappears for every StreetComplete user, and from our counts the next
day. The one thing kept on the phone is "hide this quest": that stays on your device and never
reaches the map.

## Why we track it separately

A count that goes up is not always bad news. When a town's open quests rise, it might be new
data, or it might be that a batch of benches reached their sixth birthday. We count each aging
quest twice: once as the app would show it today, and once as if nothing could age. The
difference is the resurvey part, drawn in its own colour, so a rise from aging isn't read as
neglect.

## Further reading

- The source code: [`ResurveyUtils.kt`](https://github.com/streetcomplete/StreetComplete/blob/master/app/src/commonMain/kotlin/de/westnordost/streetcomplete/osm/ResurveyUtils.kt)
  (check dates and what an answer writes),
  [`ElementFilter.kt`](https://github.com/streetcomplete/StreetComplete/blob/master/app/src/commonMain/kotlin/de/westnordost/streetcomplete/data/elementfilter/filters/ElementFilter.kt)
  (how "older" is decided),
  [`ResurveyIntervals.kt`](https://github.com/streetcomplete/StreetComplete/blob/master/app/src/commonMain/kotlin/de/westnordost/streetcomplete/data/preferences/ResurveyIntervals.kt)
  (the setting).
- Why StreetComplete re-asks at all: the 2020 grant proposal
  [Map Maintenance with StreetComplete](https://wiki.openstreetmap.org/wiki/Microgrants/Microgrants_2020/Proposal/Map_Maintenance_with_StreetComplete)
  and its [final report](https://wiki.openstreetmap.org/wiki/Microgrants/Microgrants_2020/Proposal/Map_Maintenance_with_StreetComplete/Report).
- The per-quest list with a resurvey column, kept by volunteers:
  [StreetComplete/Quests](https://wiki.openstreetmap.org/wiki/StreetComplete/Quests).
- How the dates are tagged:
  [summary of re-survey quests](https://lists.openstreetmap.org/pipermail/tagging/2020-August/054959.html)
  on the tagging list (2020; some details changed since) and
  [Key:check_date:surface](https://wiki.openstreetmap.org/wiki/Key:check_date:surface).
