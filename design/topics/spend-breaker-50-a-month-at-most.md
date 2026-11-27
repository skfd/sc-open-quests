## Spend breaker: $50 a month at most (2026-11-19; owner: "make sure there is a spent breaker on hosting. 50 bucks a month max")

Cloudflare has no cap that covers this: spending limits cover Workers and Durable Objects only, and budget
alerts (Billing, Billable Usage) only send email. What can cost money is R2 alone: the site is Workers static
assets on Workers Free (no bill), egress is free, and r2.dev access is off on all three buckets. So
`tools/spend_breaker.py` is the cap.

- **Estimate:** R2 operations by action and storage per bucket from the account's GraphQL analytics, priced
  from the R2 pricing page (read 2026-11-19: Class A $4.50 and Class B $0.36 a million past 1M and 10M free,
  storage $0.015 a GB-month past 10 GB, deletes free). It errs high: an action on neither list is Class A,
  units round up as Cloudflare rounds them, storage is the window's peak, and the window is the stricter of
  the calendar month and the trailing 30 days (the billing period starts on the purchase date). On 11-19:
  35k Class A, 74k Class B, 1.16 GB, $0.
- **Trips at $40,** warns at $20: the gap covers analytics lag, an hourly check and anything it cannot see.
- **A trip** writes a latch (`~/.config/sc-open-quests/spend-breaker.json`) and turns off public access on
  `sc-data.comentality.com`, the one public R2 surface (the bucket keeps its files; readers get a 401,
  which is not billed). Checked live on 11-19 while the bucket was empty: off gave 401 "public access
  disabled", on gave the 404 of a missing key again. The latch holds until the owner runs `--reset`,
  even into a new month. `--reset` refuses while the estimate is still past the line; the trailing 30 days
  can stay there into a new billing period, so `--reset --force` is the owner's override.
- **Publishers ask first:** `gate(planned_class_a=N)` refuses when latched or when the estimate plus N
  more writes reaches the line. `cloud_publish.py` then skips its R2 sync but still deploys the site
  (static assets cost nothing); `archive_backup.py` fails as it does on any error; the world publisher
  (branch `world-publish`) calls it strict, so analytics it cannot read stop it too, and caps a run's files.
- **Hourly:** Task Scheduler `kk-SCOpenQuests-spend`, log in `logs/spend.log`. Not covered: reads while
  the PC is off. 139M uncached reads past the free 10M make $50, so an outage of hours does not get there;
  a Worker cron would close the gap if it ever matters, and a WAF rate-limit rule on the data host would
  cap a flood at the edge.
