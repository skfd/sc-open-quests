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
- **Spend breaker:** `python tools/spend_breaker.py` (hourly, task `kk-SCOpenQuests-spend`) prices this
  month's R2 use and at $40 turns off `sc-data.comentality.com` and refuses R2 writes until
  `--reset`. `--status` shows the latch and the estimate. DESIGN.md, "Spend breaker".
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

## Share previews (built, not live)

`wrangler.previews.jsonc` is the same site plus one script, `src/site.js`, that runs for `/` and
`/index.html` only and writes a place's `og:title` and `og:description` into the page's head, so a pasted link
shows the place's number (DESIGN.md, "Share previews: a Worker's text for every place"). Every other
path is still a static asset served without it. Tests: `node --test cloudflare/test/preview.test.mjs`,
`node cloudflare/test/parity.mjs` (every city against `docs/data/cities.json`), and locally
`npx wrangler dev --config wrangler.previews.jsonc --port 8791` with
`python cloudflare/test/browser_parity.py` (the page's number against the card's, in a browser).

**To go live, in this order:**

1. **Workers Paid on the account** (the owner; $5 a month). Not before: the script is past Workers
   Free's 10 ms of CPU, and on Free a page view that fails is a broken page.
2. Deploy by hand, Git Bash, from `cloudflare/`:
   `set -a && . ~/.config/sc-open-quests/cloudflare.env && set +a && npx wrangler deploy --config wrangler.previews.jsonc`
3. Check the live site at once; the zone's rewrite rule ("Serve index.html for folder paths") sits in
   front of the script and no local run includes it:
   - `python tools/cloud_publish.py --check` (the home page and every file byte-equal);
   - `curl -s 'https://street-complete-statistics.comentality.com/?city=toronto' | grep og:title` names
     Toronto's number, and so does the same link with `/index.html?city=toronto`;
   - `curl -s 'https://street-complete-statistics.comentality.com/?place=be76926172b2&in=ca/eb1eed766420' | grep og:title`
     names Blind River's number: the fetch from Cloudflare to `sc-data` is the one path no local run
     took, and it fails quietly into the site's own title;
   - `curl -sI 'https://street-complete-statistics.comentality.com/?city=toronto' | grep -i cache-control`
     is `max-age=0, must-revalidate`, as for `/` (the zone must not have raised it);
   - `curl -s -o /dev/null -w '%{http_code}' https://street-complete-statistics.comentality.com/data/nothing.json` is 404;
   - open the site in a browser: a city, a neighbourhood, a world place.
   **If anything is off, put the script-less site back at once:** `npx wrangler deploy` (plain
   `wrangler.jsonc`).
4. Only then make it what the daily run deploys (**until this step the 13:15 run deploys plain
   `wrangler.jsonc` and takes the script off again**, so do steps 2 to 4 in one sitting): copy `wrangler.previews.jsonc` over `wrangler.jsonc`
   (keep the old one as `wrangler.static.jsonc`, the way back), fix the comments, commit.
5. Paste a link into a network's preview checker (Facebook's Sharing Debugger, LinkedIn's Post
   Inspector, or a message to yourself in Slack or Signal).

The preview's cost is Workers', not R2's, so `tools/spend_breaker.py` does not count it: watch the
Worker's requests and CPU time in the dashboard for the first days.
