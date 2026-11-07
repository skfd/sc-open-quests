# Hardware for a daily world count

Written 2026-11-06. The goal: every place in the world counted every day, all computing at home, the data
hosted elsewhere (DESIGN.md, "The whole world: measured and proposed"). Prices are USD from web sources of
that week, several of them conflicting, in a memory shortage that moves them monthly. Check before buying.

**In short:** the engine speed-up is measured, about 2.4x with two engines at once (2026-11-07), so a planet is
about 6.5 hours on this laptop, if it holds speed for that long. That was the only open question for the count:
run it for hours before paying for anything. The machine should also serve OSM servers (the owner, 2026-11-06), so
if you buy, buy a tower: the speed-up passed 1.8x, so a used Ryzen 9 5950X is enough, with 64 GB and 4 TB. Benchmark
it first. CI stays on GitHub. Phones are not worth it.

## The workload

Measured on this laptop (ThinkPad, Ryzen AI 9 HX PRO 370, 12 cores, 24 threads, 88 GB, 2 TB SSD). Call its
speed **1 L**.

| what | measured |
|---|---|
| counting | 2.25 s per million nodes with two engines at once (Czechia, 97.5M nodes, 219 s); 5.4 before the speed-up |
| the planet | 10-11 billion nodes (estimated), so about 6.5 L-hours; about 16 before the speed-up |
| limit | CPU, with two engines. One uses 13 of 24 threads, two 18.6 (82% of the machine), three 20.6 (90%), and the third gains 4% |
| memory | peak heap in an area, with room to spare: 7.8M 5 GB, 11.8M 7 GB, 21M 14 GB, 31M 20 GB; each engine needs its own. The old engine at 97.5M failed at 41 GB; the new one is untested there |
| work units | independent files, no shared state, about 1 GB each at 130M nodes |
| daily input | one planet diff, about 110 MB |

**Count hours a day = 16 / (engine speed-up x total L).** The target is 8 hours or less, leaving room for
diffs (1-3 h), publishing (1 h) and a bad day. The speed-up is now about 2.4x, against the 5.4 s behind the 16, so
the last row below is the one that holds.

| engine speed-up | L needed for 8 hours | what that means |
|---|---|---|
| none | 2.0 | laptop plus 1 L at least, or a new desktop alone with little margin |
| 1.7x | 1.2 | laptop alone falls short; 1 L more is comfortable |
| 2.5x | 0.8 | laptop alone, if it holds speed for hours (not yet tested) |

## Spec: one machine

- **CPU:** 16 cores or more, at least 1.5 L. Sustained all-core speed is what counts; a desktop cooler matters.
- **Memory:** 64 GB, as 2x32 GB so two slots stay free. The count does not need 128 GB, and it is where prices
  are worst.
- **Disk:** 4 TB NVMe. 2 TB works for the count alone, not with the OSM servers. See below.
- **Network:** wired gigabit.
- **OS:** Linux. It runs everything the laptop does without Docker Desktop or Task Scheduler.
- **Uptime:** on all day, on a surge protector. A run that dies restarts its file, so no UPS is needed.

## Spec: many machines

One **coordinator** holds the store, applies diffs, hands out files and publishes. This laptop can do it only
with more disk: the store peaks at about 680 GB and it has 260 GB free. **Workers** only count.

| worker | requirement |
|---|---|
| minimum | 8 cores, 32 GB, 100 GB free SSD, wired gigabit, JDK 21 |
| smallest possible | 16 GB, if files are cut to 8M nodes or fewer: about 1,300 files, not 80, and a third cutting stage |
| OS | any: the engine is plain JVM, so Linux, Windows and macOS on ARM should all work |

To build: a small job queue (a worker takes the next file, posts its snapshot, a dead worker's file goes back
in the queue). Gigabit moves the whole planet in 15 minutes, so the network is not a limit; workers can also
keep their files and apply the diff themselves.

**Check before trusting a new kind of worker:** its snapshot must be identical to the laptop's on the same
file. Different CPUs and JVMs should agree, but nothing has tested it.

**A small heap costs time.** Ontario took 261-271 s at 16 GB against 188 s at 40 GB, all of it collection. A
32 GB worker may run below its L; cells that need far less than the heap may not suffer. Not yet measured.

## Disk

| item | size |
|---|---|
| planet history file (monthly rewrite needs a second copy for a while) | 160 + 170 |
| region files | 90 |
| per-region history cuts, for the fast 2017 backfill | 160 |
| archive, notes, Overture, working room | about 100 |
| **total at peak** | **about 680 GB** |

The laptop has 260 GB free. Writing 90 GB a day is about 33 TB a year, well inside a normal SSD's rating.

## Options

L values are estimates from Geekbench 6 multi-core (HX 370 about 15,000), which is not this workload.
Treat them as a shortlist until benchmarked.

| option | L (est.) | price | $ per L | power | note |
|---|---|---|---|---|---|
| Mac mini M6, 12 cores, 32 GB, 512 GB | 1.4 | about $1,499 (worked out from upgrade prices) | 1,070 | not found | Score about 21,000; 32 GB is the most it takes; needs the job queue and disk elsewhere for the store |
| Mac mini M5 Pro, 15 cores, 48 GB, 512 GB | 1.95 | about $2,299 (worked out from upgrade prices) | 1,180 | not found | Score about 29,300; 64 GB is the most it takes; SSD soldered; no sustained test found |
| Ryzen AI Max+ 395 mini PC, 64 GB (GMKtec EVO-X2) | 1.3 | about $1,500 | 1,150 | about 120 W | Memory soldered; prices conflict a lot |
| Ryzen AI Max+ 395, 128 GB (Bosgame M5) | 1.3 | about $2,400 | 1,850 | about 120 W | The extra memory buys no speed here |
| Framework Desktop, 64 GB | 1.3 | about $1,640 | 1,250 | about 120 W | Reported after its price rises |
| **Used Ryzen 9 5950X tower, 64 GB DDR4, 4 TB** | **1.1** | **about $1,450** | **about 1,300** | **about 180 W** | Score from memory; CPU about $280 used, 2x32 GB $459, 4 TB $280-590, the rest a guess of $300; no warranty; no built-in graphics, so it needs a cheap card |
| **Ryzen 9 9950X desktop, 64 GB, built** | **1.4-1.8** | **about $2,200-2,600** | **about 1,350-1,700** | **about 200 W** | Scores found run from 20,550 to 27,000; no queue needed; CPU price not confirmed |
| Used EPYC 7702 (64 cores) | 2.5-3.5, a guess | CPU about $500; board and DDR4 not priced | ? | 250-300 W | Loud; many cores may not scale; run several engines |

The 5950X saves about $900 of cash and gives up 0.3-0.7 L. It alone needs a 1.8x speed-up for 8 hours
(16 / (1.8 x 1.1)); the 9950X needs 1.15-1.45x. Reaching 128 GB costs about $460 more on the 5950X and
$1,000-1,250 on the 9950X.

**Newer chips.** The M5 Pro is the fastest thing here on paper: about 2 L, so 8 hours with no engine speed-up, if
a short benchmark holds for 8 hours on a JVM, which nothing has tested. It stays off the shortlist because of
the OSM servers: 64 GB at most, soldered storage, and software that expects Linux. Zen 6 desktop chips are expected
around the first half of 2027, on AM5, with up to 24 cores in leaks. If they land before the buy, look again.

## Other uses: OSM servers

The owner's choice for what the machine does when it is not counting. Requirements are from each project's own
docs, none measured here.

| job | memory | disk | on 64 GB, 4 TB |
|---|---|---|---|
| Overpass, whole planet | public instance runs on 32 GB; more is cache | 250-300 GB | Fits. A clone takes 4-8 hours, an import 24-48 |
| Planetiler, planet tiles | half the planet file, about 45 GB; 32 GB with `--storage=mmap` | 10x the planet file, about 900 GB while building | Fits. Reported 2-3 hours on 24-32 cores, so longer here |
| Nominatim, whole planet | 128 GB strongly recommended; out-of-memory reports under 64 GB not accepted | 1 TB or more, NVMe | At the floor. Run a region, or add 64 GB first |

- **Disk:** the count (680) plus all three is about 2.9 TB, so 4 TB stops being optional.
- **Sharing the machine:** two engines all but fill it, so nothing heavy should run beside a count. A count of
  8 hours fits inside the owner's working day and leaves the evening free.
- **No local CI (the owner, 2026-11-06).** It stays on GitHub: 94 of 131 repos are public, where hosted Actions
  cost nothing, and paid minutes for the rest should cost little beside running a runner at home.

## Life hacks

**Worth doing**
- **Speed up the engine first.** A 2x gain is worth one new desktop, for nothing.
- **Buy memory inside a computer, or buy DDR4.** 64 GB of DDR5 alone was reported at $1,000-1,250 this year. A
  whole 64 GB mini PC costs about $1,500, and a 32 GB Mac mini about the same. 64 GB of DDR4 is about $460, which
  is what makes the 5950X tower work.
- **Rent before you buy.** Scaleway rents M4 Mac minis (reported about EUR 149 a month, billed hourly, 24-hour
  minimum): one day answers what a Mac does on this workload for a few euros.
- **Use what you can borrow.** Any idle PC with 32 GB is a free worker at night, and can run the benchmark.
- **Refurbished Macs.** Apple's refurbished store is usually about 15% below list. A Mac mini is small and
  quiet enough to run all day in a living room, which a 200 W desktop may not be.
- **Keep the laptop free.** The tower counts and holds the store, and the laptop stays usable.
- **Recount only changed tiles, later.** In Ontario, 1.8% of the nodes sat in tiles touched that day. It could
  cut the count several times over on normal days, and shrinks whatever you need to buy.

**Tempting, but no**
- **Cheap phones.** A 12 GB phone leaves perhaps 6-8 GB of heap, so files of 5M nodes and 2,000+ of them. It
  slows down from heat within minutes under full load, perhaps 0.1-0.2 L (a guess). So 10 phones for 1-2 L, each
  on a charger 24 hours a day (battery swelling is a real risk), on Wi-Fi, with Android killing background
  work. A $1,500 Mac mini beats the lot. Fun as an experiment, not as infrastructure.
- **Raspberry Pis.** Same sums: about 0.2 L at best (a guess), with 16 GB at most.
- **128 GB machines.** The count does not use it. Only a planet Nominatim would, and a tower can add it later.
- **GPUs.** Filters and tag walks are 55% of the time, so a perfect port caps at about 2.2x, and it means
  rewriting StreetComplete's own quest code and matching every release. The one part that suits a GPU, "does this
  element hold any of the quest's keys", is what the fast reject does on the CPU. Pbf reading stays on the CPU.
- **More disk for speed.** It buys room, not time.

## Order of work

1. **Wait for the cell test.** If cells miss the 0.1% bar, the plan changes.
2. **Build the engine speed-up** and measure it (free). Done 2026-11-06.
3. **Run the clean engine test** on an idle machine (free). Done 2026-11-07: DESIGN.md, "The clean engine test".
4. **Run 16 hours on the laptop** to see if it holds speed (free).
5. **Benchmark candidates.** `.scratch/world-spike/cells/col4.osm.pbf`, 11.8M nodes, with this engine and
   quest file: this laptop takes about 35 s, alone. Compare seconds and snapshot, with the heap the machine would
   really have. One borrowed 5950X if one can be found.
6. **Work out L needed** from the table above. The speed-up passed 1.8x, so the 5950X tower, if one is bought at
   all. Run two engines on it. Check prices that week.

## Sources

Prices and scores, read 2026-11-06:
[Mac mini M5 Pro scores](https://browser.geekbench.com/macs/mac-mini-2026-15c-cpu-16c-gpu),
[Mac mini M6 and M5 Pro prices](https://www.macworld.com/article/3140334/should-you-buy-a-mac-mini-now-or-wait.html),
[Mac mini upgrade prices](https://www.macworld.com/article/3239233/mac-mini-m5-pro-review-killer-performance-at-a-lethal-price.html),
[Mac mini M6 scores](https://www.ithinkdiff.com/m6-mac-mini-review-roundup-what-critics-are-saying/),
[9950X scores, lower](https://www.tweaktown.com/news/101464/apples-new-m4-max-beats-intels-core-ultra-9-285k-amd-ryzen-9950x-in-geekbench-6-run/index.html),
[Zen 6 desktop](https://www.digitalcitizen.life/amd-confirms-zen-6-ryzen-desktop-and-mobile-families-for-am5-and-fp10/),
[9950X and HX 370 scores](https://www.3dtested.com/pc-components/cpus/ryzen-ai-9-hx-375-shines-in-geekbench-6-benchmark-strix-point-has-higher-single-core-performance-than-core-i9-14900hx),
[DDR5 price index](https://www.tomshardware.com/pc-components/ram/ram-price-index-2026-lowest-price-on-ddr5-and-ddr4-memory-of-all-capacities),
[64 GB kits](https://en.gamegpu.com/news/zhelezo/tseny-na-ddr5-vzleteli-za-18-mesyatsev-na-500-i-prevysili-usd1250-za-64-gb),
[Framework Desktop](https://www.tomshardware.com/desktops/gaming-pcs/diy-pc-maker-framework-finally-succumbs-to-ram-apocalypse-is-raising-prices-on-its-desktops-now-starts-at-usd1-139-with-32gb-128gb-up-usd450),
[GMKtec EVO-X2](https://www.tomshardware.com/desktops/mini-pcs/gmktec-evo-x2-ai-mini-pc-review),
[Ryzen AI Max roundup](https://www.layer3labs.io/gear/ryzen-ai-mini-pcs),
[EPYC 7702](https://www.amcompute.com/appraisals/epyc-7702),
[Scaleway via Green Mini](https://www.greenmini.nl/compare/scaleway-alternative/),
[used 5950X](https://yomotherboard.com/?p=467699),
[64 GB DDR4](https://datacenterdisk.com/ram/ddr4/64gb),
[4 TB NVMe](https://datacenterdisk.com/best/4tb-nvme-ssd),
[Nominatim](https://git.openstreetmap.org/nominatim.git/blob_plain/87a8c246:/docs/admin/Installation.md),
[Overpass](https://wiki.openstreetmap.org/wiki/Overpass_API/install),
[Planetiler](https://www.github.com/onthegomap/planetiler/blob/main/PLANET.md),
[Planetiler with mmap](https://newreleases.io/project/github/onthegomap/planetiler/release/v0.4.0),
[GitHub Actions pricing](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/).
From memory, not sourced: the 5950X's score, power figures, Apple's refurbished discount.
