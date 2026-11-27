## Parked: the world's monthly backfill on several machines (owner, 2026-11-24: "parking this idea for now, will return when less busy")

- **Asked 11-21:** what a second machine needs, and whether the world's monthly backfill (release 2) can be
  distributed. Nothing built or changed.
- **Answer: yes.** Months share no state (each is a full count at its date, unlike the daily loop's chain), and the
  128 plan files share none either: 118 months x 128 files, about 15,100 independent jobs. One coordinator cuts the
  history file once into the 128 files with history (DESIGN.md, "For the monthly history": 171 GB in, about 160 GB
  out, 8-10 h estimated); a worker slices one file at a date, counts it and returns the counts.
- **A worker:** HARDWARE.md's 8 cores, 32 GB, 100 GB SSD, JDK 21 predates the plan files; a full-size file ran at a
  30 GB heap, so 48-64 GB or the big files kept on the big machine. About 20 days of this laptop in all by
  HARDWARE.md's 2.25 s per million nodes (not remeasured since the 11-15 speed-ups).
- **Missing:** the history cut's rehearsal (`--with-history` has no `smart`; exact on a Germany snapshot, not on a
  history clip), a job queue, a check that another CPU or JVM gives the same counts (the cities' monthly points can
  be the oracle), the slicer's choice (osmium or Rust, parked above), and the Windows-only pieces (`.exe`, `.bat`,
  `schtasks`, `tasklist`, the memory probe; the seed's scripts live in `.scratch`).
- **First step on return:** rehearse the history cut on one region.
