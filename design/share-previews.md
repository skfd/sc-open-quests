# Share previews: requirements and design (draft for review, 2026-11-23)

Status: **draft**. The text Worker and a first general card are built on branch `share-previews`, not merged
or live. Cards per place are not built. "Owner" marks what the owner said; "proposed" is ours.

## Requirements

1. Every place with numbers gets a text preview on release 1 day (owner).
2. Text previews come from a Worker on Workers Paid, $5 a month (owner agreed; not upgraded yet).
3. **No outlines** on cards (owner, 11-23).
4. The general card needs statistics; the first one is too bland (owner, 11-23). **Settled (owner, 11-25): the world
   card**, `design/project-card.svg`, is the general card. Redrawn monthly and on release day (owner, 11-25); nothing runs it yet.
5. Pictures are pregenerated for chosen places and a missing one is rendered by the Worker: the owner's idea,
   under discussion. The render speed in the Worker is to be tested and recorded (owner).
6. Proposed: the picture never contradicts the text, is never broken, and has a hard spend limit.
7. English only (owner, 11-10). Place names stay as the name layer has them.

## Design under discussion (proposed)

- Text: the Worker, current, follows the link's quest selection.
- Place card: name, parent, the three most-open quest types as icons and words; no total, no change, **no
  percentages**. General card: the world total, rounded and dated.
- `og:image` = `/card/<id>.png`: the R2 copy, else render and store, else the general card.
- One JavaScript SVG template and resvg for both the local batch (Node) and the Worker (WebAssembly).
- Fallback only for known place ids, once each, under a monthly cap. Cards carry a version in their address.
- Release day: countries, regions, our 147 cities (about 4,350). Larger batches only if the fallback fails its trial.

## Measured 2026-11-23

**Scale** (distinct rows of `docs/places`; not every row has numbers). Time and bytes are extrapolated from the
11-10 mockup (0.30 s, 61 KB, native, and it had an outline), not measured on this design.

| level | places | cumulative | one core | size |
|---|---|---|---|---|
| country, dependency | 270 | 270 | 1.4 min | 16 MB |
| region | 3,929 | 4,199 | 21 min | 256 MB |
| county | 38,933 | 43,132 | 3.6 h | 2.6 GB |
| local admin | 21,502 | 64,634 | 5.4 h | 3.9 GB |
| locality | 556,094 | 620,728 | 52 h | 38 GB |
| macrohood | 47,293 | 668,021 | 56 h | 41 GB |
| neighbourhood, microhood | 414,254 | 1,082,275 | 90 h | 66 GB |

**Number drift**, 147 cities, 11-01 to the newest count: median 0.21%, p90 1.45%, 26 over 1%, 2 over 5% (Oshawa
45,478 to 48,649). The figure rounded to thousands differs for 40. Causes (edits, app release) were not separated.

**Card content drift**, the same cities against their newest count:

| card from | same top 3 | same order | all 3 shares the same whole % | largest share move, median / p90 / max |
|---|---|---|---|---|
| 2026-11-01 | 145 of 147 | 143 | 104 | 0.11 / 0.48 / 2.49 points |
| 2026-10-01 | 143 | 138 | 83 | 0.22 / 1.07 / 10.17 |
| 2026-08-01 | 131 | 119 | 52 | 0.42 / 2.00 / 8.20 |

So three icons hold for a month (and mostly a quarter) and percentages do not: hence no percentages.

**Names** as shown (English where the layer has it): 898,117 Latin, 148,028 Cyrillic, 1,061 Greek, 21,373
Chinese/Japanese/Korean, 10,622 Arabic, 2,199 mixed scripts, 875 others (115 of them without letters). Latin,
Cyrillic and Greek are 96.8% of 1,082,275. Countries are all Latin; regions too, but for 3 mixed names. Localities
are 72.5% Latin. Names run to 117 characters; p99 is 31 to 44 by level, so the template must wrap and shrink.

**World**, 2026-11-21, default quests: 576,477,431 open (28,576,252 of them resurvey), +1,394,585 since 11-01. A sum
of the 248 entries of `children/world.json`: overlaps and gaps not measured; DESIGN.md wants each place once.

**Live site**, one fetch each: `/` 0.23 s and `/?city=toronto` 0.47 s to first byte (no Worker yet), a place file
0.33 s. A `Range` request got 200 and the whole page (9,676 bytes on the wire). `twitter:card` is 1.4 KB into our page.

## Looked up 2026-11-23

- **Workers Paid:** 10M requests and 30M CPU-ms a month included, then $0.30 and $0.02 a million; 30 s of CPU a
  request by default; 128 MB of memory including WebAssembly; 64 MiB script; 1 s startup; `waitUntil` 30 s
  ([pricing](https://developers.cloudflare.com/workers/platform/pricing/),
  [limits](https://developers.cloudflare.com/workers/platform/limits/)).
- **Static files: 100,000 on Paid, not 20,000.** The old cap that ruled out static cards goes away with the $5: 9,339
  files plus 43,132 would fit. R2 is still needed if the Worker stores what it renders.
- **R2:** $4.50 a million writes, $0.36 a million reads, $0.015 a GB-month; 1M, 10M and 10 GB free
  ([pricing](https://developers.cloudflare.com/r2/pricing/)).
- **A render at 300 ms CPU** costs $0.000006 past the allowance: 20,000 is 6M CPU-ms (inside the 30M), all 1.08M about
  $6.50. A slower WebAssembly render scales this. `spend_breaker.py` does not see Workers.
- **resvg-wasm** 2.6.2, MPL-2.0, 2.5 MB unpacked; fonts as buffers. Workers and WOFF2 support are not stated.
- **Facebook:** image at most 8 MB, 1200x630 recommended, page answered "within a few seconds", tags in the first
  1 MB; images cached by address. **Slack:** fetches with `Range`, caches about 30 minutes. **X:** its page refused the
  fetch (402). No per-network image timeout was found.
- **Noto packages** (all weights and subsets, so upper bounds): Arabic 1.9 MB, SC 75, JP 84, KR 52.

## Render speed in the Worker: NOT MEASURED YET

`cloudflare/bench/run.py` is written and has not been run: on 11-23 the world loop was running, and benchmarks beside
it are barred (a build beside it stopped its day that night). The script refuses to start beside the loop or the city
task. It times six names (short, long, Cyrillic, Arabic, CJK, CJK with no font) at 1200 and 600 wide, first and
repeat, with bytes and memory. Local time is this PC's, not Cloudflare's: it gives the order of magnitude, the shapes
and the memory. CPU on Cloudflare needs a deployed trial on Paid. Proposed pass mark: median at most 1 s, first at
most 3 s, well under 128 MB.

| case | first | median | max | bytes | memory |
|---|---|---|---|---|---|
| (to fill from `out/results.json`) | | | | | |

## Also to test in a gap

- `Range`, `HEAD` and gzip requests to the rewritten page; the Worker's memory with India's 3.6 MB name file.
- Batch speed and PNG size of the real card in Node; wrapping of 117 characters.
- Two requests for one missing card at once; a failed render falls to the general card.
- The world total with each place once.

## Questions for the next review

1. Cards on static files (now possible to 100,000) or on R2 (needed for the fallback)?
2. Is a place card with no total, outline or percentages interesting enough? That is the price of no mismatch.
3. Is the fallback worth its fonts and caps if 43,132 pregenerated cards take 3.6 core-hours?
4. CJK and Arabic names: carry fonts, or the general card?
5. A monthly cap on fallback renders (proposed 20,000), and should `spend_breaker.py` learn Workers?
6. Card refresh: monthly or quarterly?
7. ~~The site's wording for the world.~~ "Open StreetComplete quests around the world" (owner, 11-25).
