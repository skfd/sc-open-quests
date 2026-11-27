## Countries in the place index: StreetComplete's, not ours (2026-11-10, evening)

**The problem.** The place index (`docs/places/`, 272 countries) took Overture 2026-10-21.0's `country`
field as shipped; `tools/places.py` reads no perspectives. That files Western Sahara wholly under Morocco
(its "Western Sahara" region overlapping two Moroccan regions), gives Palestine no country (the West Bank
and Gaza are bare `XW`/`XG` stubs), and makes Golan, the Kurils, Senkaku and the Spratlys stubs of their
own. Places with no country are dropped. No counted city is in a disputed area, so no numbers were
affected, only search, the hierarchy and roll-ups. The Map tab's OSM tiles draw a third view.

**The owner's rule:** avoid controversy, and a Western view is no answer; leaning on SC's decisions
completely is fine. So the site files a place where StreetComplete applies a country's rules, and says
so: "Filed where StreetComplete applies that country's rules. This site describes the app; it takes no
position on borders."

**What SC's data says** (`engine/src/main/resources/sc/boundaries.ser`, library
`de.westnordost:countryboundaries:3.0.0`, probed with a throwaway test at 36 points): it follows who
governs. Simferopol `UA-43, RU`, Sevastopol `UA-40, RU` (no plain `UA`, so a UA-only quest is off there;
`UA-43.yml` has Russian banks and uk/ru/crh); Donetsk, Luhansk, Melitopol `UA`; Laayoune, Dakhla `MA`
but Tifariti, east of the berm, `EH`; Ramallah, Gaza `PS`; East Jerusalem, Golan `IL`; Srinagar, Leh
`IN-JK, IN`, Gilgit `PK`, Muzaffarabad `PK-AJK, PK`, Aksai Chin `CN-XJ, CN`, Itanagar `IN-AR, IN`; Pristina
`XK`; Taipei `TW`; Kunashir `RU`; Liancourt `KR`; Halaib `EG`; Woody Island `CN-HI, CN`; North Nicosia,
Kyrenia `CY`; Hargeisa `SO`; Khankendi `AZ`; Sukhumi `GE-AB, GE`; Tskhinvali `GE-SK, GE`; Tiraspol
`MD-SN, MD`; Senkaku, Itu Aba, Bir Tawil nothing.

**Decided (owner, 2026-11-10):**
- **A place goes under every country SC's data names at it.** A code's country is its part before the
  hyphen (`UA-43` is Ukraine), so Crimea is under both Ukraine and Russia. A place SC splits (Overture's
  "Western Sahara" region: `MA` and `EH`) goes under each, tested at several points inside it, not only
  its centre. A place with no code is left out of the tree (owner, later the same evening; this replaces a "no country" group).
- **Country names as SC shows them.** SC names a country by asking the platform's locale data:
  `Locale("en-$countryCode").displayRegion` (`screens/user/edits/CountryDialog.kt`, the per-country
  statistics dialog; the same in `ProfileScreen.kt` and `QuestSelectionScreen.kt`), which is
  `getDisplayCountry` on Android and NSLocale on iOS, both Unicode CLDR, in the phone's language. The
  browser has the same data: `new Intl.DisplayNames(["en"], {type: "region"}).of(code)`, so the site
  names countries there, in English like the rest of the site, and ships no name table. Node's: `PS`
  Palestinian Territories, `EH` Western Sahara, `XK` Kosovo, `TW` Taiwan, `HK` Hong Kong SAR China,
  `MK` North Macedonia, `TR` Türkiye. SC never names a subdivision (`UA-43`), and the top level only
  uses a code's country part. (Owner, 2026-11-10: names, not codes; this replaces "codes only".)
  Regions and everything below keep Overture's names and hierarchy, but see "Below the country
  level" next: that hierarchy is not neutral either.
- **Palestine is named "Palestine"** (owner, 2026-11-10: "just giving palestine a polite name"). Its
  borders stay SC's, like every other country's (Ramallah and Gaza `PS`; East Jerusalem and Golan `IL`).
  The name is CLDR's own short form (`Intl.DisplayNames` with `style: "short"` gives "Palestine" for
  `PS`; the long form is "Palestinian Territories"); every other country keeps the long form, since short
  also gives "US", "UK", "Bosnia". Briefly decided and withdrawn the same evening: Palestine in its 1967
  borders from Overture's `XW` and `XG` polygons (which do include East Jerusalem). Rule kept: borders
  are always SC's.
- The Map tab keeps OSM's tiles; their borders are OSM's and credited as such.

**Below the country level: Overture's view is one unlabelled view (checked 2026-11-10, evening).**
The owner: "there is no neutral overture; there could also be problems at this level". Overture's
schema has the toggles (`perspectives` with `mode` accepted_by/disputed_by and `countries`, on
`division` and `division_boundary`; `hierarchies` as a list of parent chains), but release
2026-10-21.0 fills none of them: 0 of 4,700,999 divisions have `perspectives`, every division has
exactly one hierarchy, and 0 of 87,536 boundaries have `perspectives`; only 47 country-level boundary
lines carry `is_disputed` (Kashmir and Aksai Chin, Golan, Gaza and the West Bank, Kosovo, Western
Sahara, Abyei, Halaib and Bir Tawil, Essequibo, Cyprus's buffer zone, and others). So nothing was
toggled wrongly, but there is nothing to toggle: the parent chains and the polygons below a country are
Overture's single choice, unmarked. Where it can disagree with SC:
- *A place whose Overture chain leads to a country SC does not name there.* Crimea's places sit under
  "Autonomous Republic of Crimea" under Ukraine; under Russia (where SC also files them) Overture has no
  region for them. Moroccan-held Western Sahara has Overture's "Western Sahara" region overlapping
  Laayoune-Sakia El Hamra and Dakhla-Oued Ed-Dahab; SC splits the land `MA`/`EH`. Golan is Overture's
  `XH` stub; SC says `IL`.
- *Names.* Overture's primary name is mostly OSM's `name` tag, which is also what SC shows a player.

**Decided (owner, 2026-11-10, evening):**
- **A disputed place goes under both.** "It is just search in a tree structure", so a duplicate costs
  nothing. Disputed is mechanical: SC names two countries at the place (Crimea: `UA-43, RU`), or SC and
  Overture name different countries (Overture's chain says Morocco where SC says `EH`). The place then
  appears under every one of those countries, each time inside its Overture region and below, so
  Crimea's places sit in the same Crimea region under Ukraine and under Russia. Undisputed places follow
  SC, which there agrees with Overture.
- **Overture's placeholder "countries" are not countries** (Claude's default, not yet confirmed: the
  `X?` codes, e.g. `XW` West Bank, `XG` Gaza Strip, `XH` Golan, `XU` Kunashir, `XD` Senkaku). They have no
  CLDR name and are no claimant; their places go under SC's countries, or are left out where SC
  names none (Senkaku). So they never make a place disputed.
- **No source we lean on files the Golan under Syria** (checked 2026-11-10): SC says `IL`; Overture's
  stub is named "Golan Subdistrict" (the Israeli district) with no perspective; its Wikidata item
  (Q5423040, the district, not Q83210 the Golan Heights) has country Israel only. Wikidata is no claims
  source either: Kunashir has JP and RU but Iturup and Shikotan only RU; Gaza lists historical
  occupiers. Overture's `X?` stubs are not all disputed: Saba, Sint Eustatius and Jan Mayen are among
  them. Syria for the Golan, or Japan for the southern Kurils, would be a hand-written claims list, the
  kind of position the owner ruled out with Palestine's borders.
  Rechecked the same evening at the owner's question: 2026-10-21.0 is Overture's newest release; its
  docs (docs.overturemaps.org, schema `perspectives`) describe the mechanism (a map for country X = the
  features with no perspective, plus those `accepted_by` X, minus those `disputed_by` X) and name no
  place that has one; the release fills it nowhere, names included (0 of 513,892 divisions with name
  rules). Around the Golan: Katzrin and Majdal Shams are in the `XH` stub, 4 of the 47 `is_disputed`
  boundaries ring it, and the UNDOF buffer zone (old Quneitra) and Syrian Hermon are under Syria. SC at the
  buffer zone is unchecked.
- **Every perspective at once (owner, 2026-11-10):** "toggle them different ways so that we show smaller
  places in each bigger place a perspective can put it". The index takes every parent chain in
  `hierarchies` and every division whatever its `perspectives`, and files a place under each parent any
  of them gives, alongside SC's countries. A no-op on 2026-10-21.0 (one chain each, no perspectives
  anywhere, the Golan included), so it changes nothing today and fills in by itself if a release
  populates them; the monthly Overture diff should report when one does.
- **Names are OSM's** where the division has an OSM relation: its `name` tag, what SC shows a player;
  Overture's name only where Overture has no OSM source. English stays shown first as today.
- **A world total, if there ever is one, counts each place once**, not once per country it is under.

**Other touchy things, decided (owner, 2026-11-10, late evening):**
- **No home-made romanisation.** "I don't think we should bake our own anglification." `places.py`'s
  Cyrillic tables (BGN/PCGN simplified, chosen by the filing country, so Crimea would get two spellings)
  go. English names come from sources only: Overture's `en` (mostly OSM `name:en`), then the Wikidata
  English label of the division's `wikidata` item; with neither, the local name is shown as it is, as for
  every other script today. Measured on the world's divisions: 289,516 with a Cyrillic primary name,
  196,526 of them with no Overture `en`, 130,716 of those with a Wikidata item (how many of those have
  an English label is unmeasured).
- **Places SC files under no country are left out of the tree** (owner: "they do not appear in tree
  search, is it ok?": yes). Senkaku, the Spratlys, Bir Tawil and the like: no country heading, no
  label to word. The measurement lists them; anything populated among them comes back to the owner.
- **Never flags.** The site shows none and never will (no official emoji flag for Kosovo, Taiwan's
  hidden on iPhones sold in China, Western Sahara's is Polisario's).
- **Fine as they are:** `aka` names such as "Kiev" for Kyiv are only searched, never shown; names in
  occupied areas are OSM's own practice; Hong Kong and Macao keep CLDR's long names; counting uses land
  polygons, so sea claims never matter; time zones are tzdb's, which follows practice.

**To build (nothing built yet):** an engine command that maps points to SC's codes (about a million
lookups); OSM `name` tags for the divisions with an OSM relation (from the planet already on disk); `places.py` files by those codes instead of Overture's `country`; a test pinning the probed
points (Crimea under both, Tifariti under `EH`, Senkaku left out); the note on the about page and
beside the country level; a first measurement of how many places move.
