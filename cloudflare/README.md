# The site on Cloudflare

`https://street-complete-statistics.comentality.com` is a Worker (`src/worker.js`) that serves every
path from the R2 bucket `sc-open-quests`. The bucket is a copy of `docs/`. DESIGN.md, "Hosting on
Cloudflare", says why and how.

- **Token:** `~/.config/sc-open-quests/cloudflare.env`, outside the repo, holding
  `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`. It's a user token named "sc-open-quests deploy":
  Workers, R2 and Pages on the one account, plus DNS, Zone read and Workers Routes on comentality.com.
  R2's S3 credentials are derived from it, so there's no second key.
- **Data, daily:** `run.py update` (and `planet`) runs `python tools/cloud_publish.py` after its git
  push. It uploads changed files, deletes gone ones (at most 2,000 a run), and refuses a `docs/` that
  looks partial. By hand: `python tools/cloud_publish.py [--dry-run]`.
- **Check:** `python tools/cloud_publish.py --check` fetches every file through the site and compares
  bytes. Cloudflare Web Analytics, which is on for the zone, adds a beacon script to HTML; the check
  takes it out before comparing.
- **The Worker, when `src/worker.js` or `wrangler.jsonc` changes** (Git Bash):

  ```bash
  cd cloudflare && npm install && set -a && . ~/.config/sc-open-quests/cloudflare.env && set +a && npx wrangler deploy
  ```
