"""docs/data/quests.json, the site's quest list, without a city count.

The list is config/site-quests.json (the engine's quests.json with no `status`: names, order, support, countries,
element types; it changes only with a repin or a port) and, for every city of config/cities.json, the `status` that
its country codes give. Until 2026-11-24 the daily city run's engines wrote it, one file a region.

    python tools/site_quests.py build           config/site-quests.json + config/cities.json -> docs/data/quests.json
    python tools/site_quests.py check           say whether docs/data/quests.json is what build would write (exit 1 if not)
    python tools/site_quests.py take FILE       an engine's quests.json -> config/site-quests.json (REPIN.md, step 5)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run  # noqa: E402

BASE = ROOT / "config" / "site-quests.json"


def enabled_in(countries: dict, codes: list[str]) -> bool:
    """Registry.kt, Countries.isEnabledIn: `codes` are a city's countryCodes, e.g. ["CA", "CA-ON"]."""
    listed = set(countries.get("codes") or [])
    kind = countries["type"]
    if kind == "AllCountries":
        return True
    if kind == "AllCountriesExcept":
        return not listed & set(codes)
    if kind == "NoCountriesExcept":
        return bool(listed & set(codes))
    raise ValueError(f"unknown enabledInCountries type {kind}")


def status(quest: dict, city: dict) -> str:
    """Output.kt, questStatus."""
    if quest["support"] == "unsupported":
        return "unsupported"
    return "counted" if enabled_in(quest["enabledInCountries"], city["countryCodes"]) else "not-in-region"


def without_status(doc: dict) -> dict:
    return {**doc, "quests": [{k: v for k, v in q.items() if k != "status"} for q in doc["quests"]]}


def base(path: Path = BASE, archive: Path | None = None) -> dict:
    """The committed list, or a newer version's from the archive (a repin whose list was not taken in yet)."""
    doc = run.read_json(path)
    best = doc
    for p in sorted(archive.glob("*/quests.json")) if archive else []:
        other = run.read_json(p)
        if run.version_tuple(other["scVersion"]) > run.version_tuple(best["scVersion"]):
            best = other
            run.log(f"quests.json: {path.name} is {doc['scVersion']}, {p} is {other['scVersion']} and is used; "
                    f"take it in: python tools/site_quests.py take {p}")
    return without_status(best)


def document(doc: dict, cities: list[dict]) -> dict:
    cities = sorted(cities, key=lambda c: c["id"])
    return {**doc, "quests": [{**q, "status": {c["id"]: status(q, c) for c in cities}} for q in doc["quests"]]}


def build(data_dir: Path = run.DATA_DIR, cities: Path = run.CITIES_CONFIG, path: Path = BASE,
          archive: Path | None = run.ARCHIVE_DIR) -> int:
    """Write data_dir/quests.json. Returns 1 if the file changed."""
    doc = document(base(path, archive), run.read_json(cities)["cities"])
    return int(run.write_text(data_dir / "quests.json", run.quests_json(doc)))


def take(source: Path, path: Path = BASE) -> bool:
    return run.write_text(path, run.quests_json(without_status(run.read_json(source))))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    sub.add_parser("check")
    sub.add_parser("take").add_argument("file", type=Path)
    a = p.parse_args()
    if a.command == "take":
        print("written" if take(a.file) else "unchanged", BASE)
    elif a.command == "build":
        print("written" if build() else "unchanged")
    else:
        want = run.quests_json(document(base(archive=run.ARCHIVE_DIR), run.read_json(run.CITIES_CONFIG)["cities"]))
        same = (run.DATA_DIR / "quests.json").read_text(encoding="utf-8") == want
        print("same" if same else "different")
        return 0 if same else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
