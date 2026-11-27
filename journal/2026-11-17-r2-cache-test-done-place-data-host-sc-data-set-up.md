## R2 cache test done; place-data host `sc-data` set up (2026-11-17, 02:30; owner at the desk)

- **Result (DESIGN.md, "The R2 cache premise: checked"):** a cache HIT is not an R2 read (PNG: 30 fetches,
  1 GetObject); JSON is never cached without a rule (60 of 60 DYNAMIC, all R2 reads); the zone's 4-hour
  Browser Cache TTL raises a lower origin max-age. Scanner bots probed ~30 secret-looking keys within two
  minutes of the certificate. `run.py`'s verdict line misread this (it counts bucket-wide reads).
- **Place-data host:** bucket `sc-open-quests-data` (ENAM, empty) created by Claude; `sc-data.comentality.com`
  attached by the owner, ssl and ownership active. Owner's name choice over `street-complete-data`.
- **Cache Rule "sc-data cache" deployed by Claude in the owner's Chrome** (owner: "use chrome to do it yourself");
  JSON on `sc-data` now MISS then HIT with its own max-age. Test domain removed the same way; the test bucket and
  its objects deleted by API. `sc-open-quests-data` is empty again. Nothing open from this step: `sc-data` is ready
  for the place publish (DESIGN.md, "Place statistics for the whole world").
