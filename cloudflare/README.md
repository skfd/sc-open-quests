# The site on Cloudflare

`https://street-complete-statistics.comentality.com` is `docs/` deployed as Workers static assets
(`wrangler.jsonc`), with no Worker script. Cloudflare serves a file that matches the path without
running any code, and asset requests are free and unlimited, so no request to the site counts
against Workers Free's 100,000 a day. DESIGN.md, "Hosting on Cloudflare", says why and how.

- **Token:** `~/.config/sc-open-quests/cloudflare.env`, outside the repo, holding
  `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`. It's a user token named "sc-open-quests deploy":
  Workers, R2 and Pages on the one account, plus DNS, Zone read and Workers Routes on comentality.com.
  R2's S3 credentials are derived from it, so there's no second key.
- **Publish, daily:** `run.py update` (and `planet`) runs `python tools/cloud_publish.py` after its git
  push. It syncs `docs/` to the R2 bucket `sc-open-quests`, then runs `wrangler deploy`, which uploads
  the files that changed (first upload 42 s, an unchanged one 20 s). The sync goes first because it
  holds the guard: it refuses a `docs/` that looks partial and deletes at most 2,000 objects a run,
  and a `docs/` it refuses is never deployed. By hand: `python tools/cloud_publish.py [--dry-run]`.
- **Needs:** rclone and node on PATH, and wrangler installed once: `cd cloudflare && npm install`.
- **Headers:** `docs/_headers` (read by Cloudflare, not served) keeps icons and images a day in the
  browser. Everything else is `max-age=0, must-revalidate`: the browser asks each time and gets a
  304 when its copy is current.
- **Limits:** 20,000 files in one deployed version and 25 MiB a file on Workers Free;
  `cloud_publish.py` refuses to deploy past the first.
- **Check:** `python tools/cloud_publish.py --check` fetches every file through the site and compares
  bytes. Cloudflare Web Analytics, which is on for the zone, adds a beacon script to HTML; the check
  takes it out before comparing.
- **The way back:** `wrangler.r2.jsonc` is the earlier shape, a Worker (`src/worker.js`) that serves
  every path from the R2 bucket. The bucket is still kept equal to `docs/`, so this puts it back at
  once (Git Bash):

  ```bash
  cd cloudflare && set -a && . ~/.config/sc-open-quests/cloudflare.env && set +a && npx wrangler deploy --config wrangler.r2.jsonc
  ```

  In that shape every request is a Worker invocation, about 71 for a first city view, so the daily
  cap is spent after about 1,400 of them.
