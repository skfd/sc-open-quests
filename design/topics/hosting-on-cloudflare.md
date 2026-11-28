## Hosting on Cloudflare (2026-11-10)

The owner chose to move the whole site to Cloudflare, not just the data, at
`https://street-complete-statistics.comentality.com`. This replaces the plan in "Hosting headroom:
measured", where the site stayed on Pages with `DATA` pointing at R2. The reason is the same: GitHub
Pages' 1 GB cap and a git history that grows about 10 KB per city per day. `cloudflare/README.md`
has the commands.

- **Shape:** a Worker serves every path from the R2 bucket `sc-open-quests` through a binding. The
  page and its data share an origin, so there's no CORS and no change to `app.js`. "/" and "…/"
  serve `index.html`. A missing file is a real 404 with `no-store`, never `index.html`. Responses
  carry Content-Type by extension, `Cache-Control: public, max-age=300` and the object's ETag, and
  `If-None-Match` and `If-Modified-Since` get a 304. Cloudflare compresses JSON with Brotli on the way
  out. The Worker has no `workers.dev` URL; the custom domain made its own DNS record.
- **Upload:** `tools/cloud_publish.py` runs rclone over R2's S3 API, with credentials derived from the
  one API token (access key = token id, secret = SHA-256 of the value). It uses `--checksum`, deletes
  files gone from `docs/` (old snapshots leave daily) up to 2,000 a run, and refuses a `docs/` that
  lacks `index.html`, `app.js` or `data/cities.json`, or holds under half the bucket's count.
  First upload: 4,836 files, 133 MB, 2 min 10 s. An unchanged rerun takes seconds.
- **Checked 2026-11-10:** all 4,836 files are byte-equal over HTTPS once the Web Analytics beacon is
  taken out. The zone has Cloudflare Web Analytics on, which injects one script into HTML; that's the
  owner's zone-wide setting, left as it is. Toronto, Berlin, Montreal and London load in headless
  Chromium with no page errors and no failed requests.
- **Daily:** `run.py update` and `planet` sync to R2 after the git push. A failure is logged as
  "cloud publish FAILED" and doesn't stop the run, because Pages is still the fallback. Since 2026-11-25
  `run.py site`, the world loop's last step, does both once a new day of the world is gated. `docs/` stays
  in git for now: the dual write is what makes Pages a fallback.
- **The flip:** after one scheduled run has uploaded by itself (from Task Scheduler, reading the token
  file), the old address `skfd.github.io/sc-open-quests/` gets a redirect that keeps path, query and
  hash, so shared links still reproduce their view. It's served from a separate Pages branch, because
  `main:/docs` is also what R2 copies. The revert is pointing Pages back at `main:/docs`. Later, once
  the week has held, the daily data can leave git history (the reason for the move).

### Static assets, no script (2026-11-10, built on `assets-switch`; live after the flip)

The owner wants the site to survive being posted somewhere busy; so far it has no readers. As a
Worker reading R2, every request was an invocation: about 71 for a first city view, so Workers Free's
100,000 a day ran out after about 1,400 of them, and past it readers get an error until midnight UTC.

- **Shape:** `cloudflare/wrangler.jsonc` deploys `docs/` as Workers static assets with no `main` (until
  2026-11-27; since then it carries the share-preview script for `/` and `/index.html` only, on Workers Paid,
  and this shape is `wrangler.static.jsonc`).
  A path that matches a file is served without running code, and Cloudflare bills no asset request,
  so nothing a reader does counts against the cap. There is no script on purpose: with one, a path
  that matches nothing (a favicon, a scanner's `/wp-login.php`) would still run it. Without one such
  a path is an empty 404.
- **Publish:** `tools/cloud_publish.py` syncs R2 first, then runs `wrangler deploy`, which uploads
  the files that changed: 42 s for all 4,836, 20 s when nothing changed. The R2 bucket stays equal
  to `docs/`. It's the way back (`wrangler.r2.jsonc`), and its object count is what the partial-site
  guard compares against.
- **What changed for the reader:** nothing in the bytes (all 4,836 files compare equal on a local
  `wrangler dev`). Data is `max-age=0, must-revalidate` where it was five minutes; `app.js` already
  asks with `no-cache`, so that is the same in practice. `docs/_headers` keeps icons and images a
  day. JSON's Content-Type has no charset. The page declares the StreetComplete mark as its icon.
- **The first switch looped on `/` (2026-11-11), fixed the same night.** The comentality.com zone has a
  URL Rewrite rule for the blog, "Serve index.html for folder paths", that turns every path ending in `/`
  into `…/index.html` before a Worker or its assets see it (`wrangler tail` on the R2 Worker showed `/`
  arriving as `/index.html`). The assets' `auto-trailing-slash` answered `/index.html` with 307 to `/`,
  and the rule rewrote that again. Now `html_handling: "none"` serves files at their exact path only,
  and `docs/_redirects` (`/ /index.html 200`) serves `/` whether or not the rule stays; `/vendor/` and
  other folders are a 404, as they were in practice. `cloud_publish.py --check` fetches `/` too, since
  every file had compared equal while `/` was broken.
- **Limits now:** 20,000 files in a version and 25 MiB a file. `docs/` is 4,836, of which 4,202 are
  the name layer and don't grow with cities; a city adds about two.
- **Not shown before the switch:** production serving. The trial Worker had no route. A full
  `--check` after the switch should pass and leave the Worker's invocation count where it was.
