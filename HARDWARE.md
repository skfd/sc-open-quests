# Hardware for a daily world count

Written 2026-11-06. The goal: every place in the world counted every day, all computing at home, the data
hosted elsewhere (DESIGN.md, "The whole world: measured and proposed"). Prices are USD from web sources of
that week, several of them conflicting, in a memory shortage that moves them monthly. Check before buying.

**In short:** buy nothing until the engine speed-up is measured, because it may be worth as much as a new
computer. Then benchmark before paying. The likely buy is one Ryzen 9 9950X desktop with 64 GB, or two or
three 32 GB Mac minis if quiet and low power matter more. Phones are not worth it.

## The workload

Measured on this laptop (ThinkPad, Ryzen AI 9 HX PRO 370, 12 cores, 24 threads, 88 GB, 2 TB SSD). Call its
speed **1 L**.

| what | measured |
|---|---|
| counting | 5.4 s per million nodes, in town or country |
| the planet | 10-11 billion nodes (estimated), so about 16 L-hours |
| limit | CPU. Two engines at once took 520 s, one took 522 s |
| memory | about 1 GB of heap per million nodes in an area: 7.8M 7 GB, 11.8M 10 GB, 21M 18 GB, 31M 24 GB; 97.5M failed at 41 GB |
| work units | independent files, no shared state, about 1 GB each at 130M nodes |
| daily input | one planet diff, about 110 MB |

**Count hours a day = 16 / (engine speed-up x total L).** The target is 8 hours or less, leaving room for
diffs (1-3 h), publishing (1 h) and a bad day.

| engine speed-up | L needed for 8 hours | what that means |
|---|---|---|
| none | 2.0 | laptop plus 1 L at least, or a new desktop alone with little margin |
| 1.7x | 1.2 | laptop alone falls short; 1 L more is comfortable |
| 2.5x | 0.8 | laptop alone, if it holds speed for hours (not yet tested) |

## Spec: one machine

- **CPU:** 16 cores or more, at least 1.5 L. Sustained all-core speed is what counts; a desktop cooler matters.
- **Memory:** 64 GB. 128 GB is not needed, and it is where prices are worst.
- **Disk:** 4 TB NVMe. 2 TB works. See below.
- **Network:** wired gigabit.
- **OS:** Linux. It runs everything the laptop does without Docker Desktop or Task Scheduler.
- **Uptime:** on all day, on a surge protector. A run that dies restarts its file, so no UPS is needed.

## Spec: many machines

One **coordinator** holds the store, applies diffs, hands out files and publishes. This laptop can do it.
**Workers** only count.

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
| Mac mini M4, 32 GB | 1.0 | about $1,000 (launch list) | 1,000 | about 40 W | Silent; memory is included; needs the job queue |
| Mac mini M4 Pro, 14 cores, 64 GB, 1 TB | 1.45 | about $2,400 (2024 list) | 1,650 | about 60 W | Score 22,285; refurbished is cheaper |
| Ryzen AI Max+ 395 mini PC, 64 GB (GMKtec EVO-X2) | 1.3 | about $1,500 | 1,150 | about 120 W | Memory soldered; prices conflict a lot |
| Ryzen AI Max+ 395, 128 GB (Bosgame M5) | 1.3 | about $2,400 | 1,850 | about 120 W | The extra memory buys no speed here |
| Framework Desktop, 64 GB | 1.3 | about $1,640 | 1,250 | about 120 W | Reported after its price rises |
| **Ryzen 9 9950X desktop, 64 GB, built** | **1.75** | **about $2,200-2,600** | **about 1,350** | **about 200 W** | Score about 27,000; no queue needed; CPU price not confirmed |
| Used EPYC 7702 (64 cores) | 2.5-3.5, a guess | CPU about $500; board and DDR4 not priced | ? | 250-300 W | Loud; many cores may not scale; run several engines |

## Life hacks

**Worth doing**
- **Speed up the engine first.** A 2x gain is worth one new desktop, for nothing.
- **Buy memory inside a computer.** 64 GB of DDR5 alone was reported at $1,000-1,250 this year. A whole 64 GB
  mini PC costs about $1,500, and a 32 GB Mac mini about $1,000. In this shortage the computer is nearly free.
- **Rent before you buy.** Scaleway rents M4 Mac minis (reported about EUR 149 a month, billed hourly, 24-hour
  minimum): one day answers what a Mac does on this workload for a few euros.
- **Use what you can borrow.** Any idle PC with 32 GB is a free worker at night, and can run the benchmark.
- **Refurbished Macs.** Apple's refurbished store is usually about 15% below list. A Mac mini is small and
  quiet enough to run all day in a living room, which a 200 W desktop may not be.
- **Keep the laptop as coordinator.** The new machine does the counting, and the laptop stays usable.
- **Recount only changed tiles, later.** In Ontario, 1.8% of the nodes sat in tiles touched that day. It could
  cut the count several times over on normal days, and shrinks whatever you need to buy.

**Tempting, but no**
- **Cheap phones.** A 12 GB phone leaves perhaps 6-8 GB of heap, so files of 5M nodes and 2,000+ of them. It
  slows down from heat within minutes under full load, perhaps 0.1-0.2 L (a guess). So 10 phones for 1-2 L, each
  on a charger 24 hours a day (battery swelling is a real risk), on Wi-Fi, with Android killing background
  work. A $1,000 Mac mini beats the lot. Fun as an experiment, not as infrastructure.
- **Raspberry Pis.** Same sums: about 0.2 L at best (a guess), with 16 GB at most.
- **128 GB machines.** Nothing here uses it.
- **GPUs.** The work is hash lookups and tag filters in JVM code, nothing a GPU does well.
- **More disk for speed.** It buys room, not time.

## Order of work

1. **Wait for the cell test.** If cells miss the 0.1% bar, the plan changes.
2. **Build the engine speed-up** and measure it (free).
3. **Run 16 hours on the laptop** to see if it holds speed (free).
4. **Benchmark candidates.** `.scratch/world-spike/cells/col4.osm.pbf`, 11.8M nodes, with this engine and
   quest file: this laptop takes about 100 s. Compare seconds and snapshot. One rented Mac, one borrowed PC.
5. **Work out L needed** from the table above, then buy the cheapest $ per L that fits. Check prices that week.

## Sources

Prices and scores, read 2026-11-06:
[Mac mini M4 Pro scores](https://duelvs.com/mini-pc/apple-mac-mini-2024-m4-pro),
[Mac mini M4 Pro prices](https://www.refurb.me/stats/mac-mini/mac-mini-m4-pro-late-2024),
[9950X and HX 370 scores](https://www.3dtested.com/pc-components/cpus/ryzen-ai-9-hx-375-shines-in-geekbench-6-benchmark-strix-point-has-higher-single-core-performance-than-core-i9-14900hx),
[DDR5 price index](https://www.tomshardware.com/pc-components/ram/ram-price-index-2026-lowest-price-on-ddr5-and-ddr4-memory-of-all-capacities),
[64 GB kits](https://en.gamegpu.com/news/zhelezo/tseny-na-ddr5-vzleteli-za-18-mesyatsev-na-500-i-prevysili-usd1250-za-64-gb),
[Framework Desktop](https://www.tomshardware.com/desktops/gaming-pcs/diy-pc-maker-framework-finally-succumbs-to-ram-apocalypse-is-raising-prices-on-its-desktops-now-starts-at-usd1-139-with-32gb-128gb-up-usd450),
[GMKtec EVO-X2](https://www.tomshardware.com/desktops/mini-pcs/gmktec-evo-x2-ai-mini-pc-review),
[Ryzen AI Max roundup](https://www.layer3labs.io/gear/ryzen-ai-mini-pcs),
[EPYC 7702](https://www.amcompute.com/appraisals/epyc-7702),
[Scaleway via Green Mini](https://www.greenmini.nl/compare/scaleway-alternative/).
From memory, not sourced: the Mac mini M4's price and score, power figures, Apple's refurbished discount.
