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
