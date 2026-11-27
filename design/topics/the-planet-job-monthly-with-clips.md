## The planet job, monthly, with clips (2026-10-31, on branch `europe`)

- **`run.py planet`** replaces `weekly`, which stays as its old name. The task is renamed too: from
  `kk-SCOpenQuests-weekly` to `kk-SCOpenQuests-planet`, with its log in `logs/planet.log`. The steps:
  `fetch planet-history`, then `osm-extracts recut`, then the months each clip region lacks, from the
  clip's history cut, then the weekly-cadence regions as before; merge, history, and "data planet <date>".
  The re-cut takes no pipeline lock, and a clip's daily fetch carries on beside it, so it need not keep
  out of the 13:15 window. The task's limit is 14 hours, because the job is two planet passes: the
  rewrite (2-2.5 h) and the re-cut (3-4 h).
- **The months of a clip's regions share one slice.** `backfill_history months` takes several
  `--region`. Regions reading one history file get one `time-filter` per date, counted once per region
  and then deleted. A region on a clip reads `<clip>/<clip>-history-<YYMMDD>.osh.pbf` and does not make
  a clip of its own.
- **Containers: one name per run** (osm-extracts 3413b63). The first Europe re-cut was killed after 8
  minutes by a `recut --from-history` test. Both used the fixed container name `osm-extracts-recut`, and
  the test's cleanup on failure removed the running one. Now each run's container is named
  `<role>-<pid>` and labelled with its role. A run removes only its own container. Leftovers of a role
  are removed only under the lock that role's runs hold, and a `--from-history` pass, which holds no
  planet lock, has a role of its own.
