# iPhone widgets blank or timing out (2026-11-28, 01:20-01:45)

- **The owner, 01:20:** "widgets show nothing for some reason". Asked: the iPhone (Scriptable) widgets. Two tiles
  black, two "Couldn't reach the site, and nothing is saved yet." with "request timed out" under it. "are you sure we
  did not break looking up places by name from scriptable or something?" Which copy of `open-quests.js` the phone
  holds: not sure.
- **Checked from this machine, all fine:**
  - The four published copies (11-13/14, 11-16, 11-25) run through the widget repo's `ios/test/preview.js` against the
    live files: Toronto, Berlin, Toronto/Parkdale draw in small, medium, large (the 11-14 copy has no neighbourhoods,
    as expected). Current copy: Toronto 371,884, -1,591 in 4 wk, as of 11-27; Parkdale 1,683.
  - The Android model (`Summary`, `Movers`) on the same live files gives the same numbers.
  - Every URL the script reads answers 200 in under 0.12 s cold (site `data/cities.json`, `quests.json`,
    `parts/toronto.json`, `icons/index.json`; sc-data `latest.json`, `city/toronto.json?v=`, `place/52/...`), with
    phone user agents too. The share-preview Worker runs only for `/` and `/index.html`, so it does not touch the
    data. No file the script reads has grown (quests.json 742 KB since 11-02).
  - Both hosts resolve to the same Cloudflare address (172.64.80.1 and a v6 one). IPv6 not tested: this machine has
    no v6 route.
- **What the message means:** the script falls back to its saved copy on any failure but a 404, so "nothing is saved
  yet" plus "timed out" means a file was being fetched for the first time on the phone (a re-added widget, a new
  parameter, or the 11-25 script's new `world-*` files) and the request did not answer in 20 s. Black tiles in
  Scriptable are usually a widget run iOS ended before it finished. Not settled: needs the phone (HANDOFF, Waiting
  on the owner).
- **The owner, 01:50:** "running script from scriptable itself showed widget preview but for some reason actual widget
  show black fill". So the code, data and network work in the app; the widget run is what fails. Not memory from
  icons (184 PNGs, 96 px, at most 11 KB); quests.json (742 KB) was parsed the same way by every copy since 11-14,
  once a day per widget. Candidates: the first fetches on a widget run taking long enough that iOS ends it (the two
  "timed out" tiles point there), or memory. Test asked: preview each widget's Parameter in the app, then Edit Widget
  so a run needs no network.
- **The owner, about 02:00:** the Parameters are Kyiv and Guelph (both draw here: Kyiv 188,295, +1,073 in 4 wk;
  Guelph 38,337, +165). After previewing both in the app and Edit Widget: "Still black". With every file saved a
  widget run needs no network, so neither time spent on the network nor our files explain it; the sparkline is a
  340-pt image, far under WidgetKit's image limit. A web search found the same on iOS 26: Scriptable widgets blank
  on the home screen while the in-app preview works, other apps' widgets too (Home Assistant); the fixes reported are
  re-adding the widget, a restart, reinstalling the app. Passed to the owner.
- **Built anyway, owner's "Yes, build it":** a widget run shares 10 s of network (`timeoutFor`, `setDeadline` in
  `ios/open-quests.js`); once spent a fetch fails at once and the saved copy is drawn, so a slow network gives the
  saved numbers or "Couldn't reach the site" instead of a run iOS ends. Widget repo 96ef164 (22 Scriptable tests,
  `check.js --no-gradle` all ok), apps page 4807719f0, deployed by the 11:15 `site` run.
