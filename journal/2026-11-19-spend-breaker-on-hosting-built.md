## Spend breaker on hosting: built (2026-11-19, 10:00-10:45; owner: "make sure there is a spent breaker on hosting. 50 bucks a month max")

DESIGN.md "Spend breaker" has the why. `tools/spend_breaker.py` prices R2 (the only billable part) from
GraphQL analytics, trips at $40: latch file plus `sc-data.comentality.com` public access off, publishers
refuse R2 writes until `python tools/spend_breaker.py --reset`. Hourly task `kk-SCOpenQuests-spend`
(`logs/spend.log`); `cloud_publish.py` and `archive_backup.py` call `gate()` before writing. The world
publisher on `world-publish` got a strict gate and a per-run file cap. Tests: `tests/test_spend_breaker.py`.
- **Owner, in the dashboard (no API for these, and the token has no billing access):** Manage Account,
  Billing, Billable Usage, Create budget alert at $10, $25 and $40, so a trip also reaches email. Done by the
  owner, 2026-11-19. If the
  account is ever moved to Workers Paid, set a Workers spending limit there too (Billing, Spend Management).
