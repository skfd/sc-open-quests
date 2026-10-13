"""Write StreetComplete's stable releases to docs/data/sc-releases.json, for the timeline markers.

    python tools/sc_releases.py

Reads the GitHub releases of streetcomplete/StreetComplete (no token needed: three requests),
keeps the ones that are neither drafts nor prereleases (by flag, or by a tag such as v31.0-beta1 that
GitHub has as a full release), and writes
{"releases": [{"version": "v63.4", "date": "2026-07-28"}, ...]} oldest first.
"""
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "sc-releases.json"
API = "https://api.github.com/repos/streetcomplete/StreetComplete/releases?per_page=100&page={}"


def fetch() -> list[dict]:
    out, page = [], 1
    while True:
        req = urllib.request.Request(API.format(page), headers={"Accept": "application/vnd.github+json",
                                                                "User-Agent": "sc-open-quests"})
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.load(r)
        if not batch:
            return out
        out += batch
        page += 1


def main() -> None:
    stable = sorted((r for r in fetch() if not r["draft"] and not r["prerelease"] and "-" not in r["tag_name"]
                     and r.get("published_at")),
                    key=lambda r: r["published_at"])
    rel = [{"version": r["tag_name"], "date": r["published_at"][:10]} for r in stable]
    OUT.write_text(json.dumps({"releases": rel}, indent=1) + "\n", "utf-8")
    print(f"{len(rel)} stable releases, {rel[0]['version']} {rel[0]['date']} to {rel[-1]['version']} {rel[-1]['date']} -> {OUT}")


if __name__ == "__main__":
    main()
