"""The city pages' data out of the world's counts: what the daily city run counts, read from the world instead.

`snapshots` writes, for each gated day of the world, one snapshot per region in the shape of data/archive's
(DATA-FORMAT.md), under data/archive-world/<region>/snapshots/<D>.json: a city is its `osm-<city>` part of
`counts/<D>`, a neighbourhood its place, as the world counts it (HANDOFF, "City neighbourhoods on the world's counts":
not cut at the city line). Day D is the world's clock, D 00:00Z. The world keeps no row for a 0, so a quest the city
counts (tools/site_quests.py, `status`) and the world has no row for is 0; a registered part with no row is there,
empty. The folder is made from the world's counts (backed up, data/facts) and can be deleted.

`build` writes the site's data files (run.py history) with those days from the world's first on, the city run's before.

    python tools/world_cities.py snapshots [--world W] [--out O] [--force]
    python tools/world_cities.py build --data-dir DIR [--out O]     never docs/data without --live
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import run  # noqa: E402
import site_quests  # noqa: E402
import world_compare  # noqa: E402  (reads the .npz without its whole matrix)
import world_publish  # noqa: E402  (which days are gated)

MEASURES = ["open", "nodes", "ways", "relations", "agedOnly"]
AGE_MEASURES = ["open05", "aged05", "open2", "aged2"]   # only a quest that uses an age has them (the engine's rule)


def rows_of(day_dir: Path, wanted: set[str]) -> tuple[list[str], dict[str, dict[str, list[int]]]]:
    """(measures, {part: {quest: its measures}}) of the wanted parts; a part the day lacks or has no row of is absent"""
    meta = json.loads((day_dir / "counts.json").read_text(encoding="utf-8"))
    ids = {i: p for i, p in enumerate(meta["parts"]) if p in wanted}
    npz = day_dir / "counts.npz"
    part = world_compare.npz_member(npz, "part.npy", mmap=False)
    rows = np.flatnonzero(np.isin(part, np.fromiter(ids, dtype=part.dtype, count=len(ids))))
    owner, quest = part[rows], world_compare.npz_member(npz, "quest.npy", mmap=False)[rows]
    cols = [world_compare.m_rows(npz, rows, i) for i in range(len(meta["measures"]))]
    out: dict[str, dict[str, list[int]]] = {}
    for p, q, *values in zip(owner.tolist(), quest.tolist(), *(c.tolist() for c in cols)):
        out.setdefault(ids[p], {})[meta["quests"][q]] = values
    missing = {w for w in wanted if w.startswith("osm-")} - set(meta["parts"])
    if missing:
        raise RuntimeError(f"{day_dir}: cities the world does not count: {sorted(missing)}")
    return meta["measures"], out


def city_entry(city: dict, quests: list[dict], measures: list[str], counts: dict, registry: dict | None) -> dict:
    """A city's entry of a snapshot. quests: the site's quest list."""
    def cell(q: dict, row: list[int] | None) -> dict:
        values = dict(zip(measures, row)) if row else {}
        return {m: values.get(m, 0) for m in MEASURES + (AGE_MEASURES if q["usesAge"] else [])}

    mine = counts.get(f"osm-{city['id']}", {})
    counted = {q["name"]: q for q in quests if site_quests.status(q, city) == "counted"}
    stray = {q: r for q, r in mine.items() if q not in counted and r[measures.index("open")]}
    if stray:
        run.log(f"{city['id']}: open quests of kinds not asked there, left out: {sorted(stray)}")
    entry = {
        "denominators": {"landAreaKm2": round(city["landAreaKm2"], 2), "population": city.get("population")},
        "quests": {name: cell(q, mine.get(name)) for name, q in sorted(counted.items())},
    }
    if registry is not None:
        def part(pid: str, measure: str) -> dict[str, int]:
            at = measures.index(measure)
            return {q: r[at] for q, r in sorted(counts.get(pid, {}).items()) if q in counted and r[at]}
        pids = sorted(p["id"] for p in registry["parts"])
        entry["parts"] = {pid: part(pid, "open") for pid in pids}
        entry["partsAged"] = {pid: part(pid, "agedOnly") for pid in pids}
    return entry


def day_snapshots(day_dir: Path, day: str, cities: list[dict], regions: list[dict], quest_list: dict,
                  registries: dict[str, dict]) -> dict[str, dict]:
    """{region: snapshot} of one world day"""
    wanted = {f"osm-{c['id']}" for c in cities} | {p["id"] for r in registries.values() for p in r["parts"]}
    measures, counts = rows_of(day_dir, wanted)
    out = {}
    for region in regions:
        mine = sorted((c for c in cities if c.get("region") == region["id"]), key=lambda c: c["id"])
        if not mine:
            continue
        out[region["id"]] = {
            "schema": 1, "asOf": f"{day}T00:00:00Z", "asOfDate": day, "timeZone": region["timeZone"],
            "scVersion": quest_list["scVersion"], "scCommit": quest_list["scCommit"], "resurveyMultiplier": 1,
            "areaUnit": "city", "source": {"world": day}, "notes": {"showAllNotes": False},
            "cities": {c["id"]: city_entry(c, quest_list["quests"], measures, counts, registries.get(c["id"]))
                       for c in mine},
        }
    return out


def snapshots(world: Path, out: Path, force: bool = False, cities_config: Path = run.CITIES_CONFIG,
              parts_dir: Path = run.PARTS_CONFIG) -> int:
    """Write the gated days that are not there yet, or are older than their counts. Returns the days written."""
    cities, regions = run.read_json(cities_config)["cities"], run.regions()
    quest_list = site_quests.base(archive=run.ARCHIVE_DIR)
    registries = {p.stem: run.read_json(p) for p in sorted(parts_dir.glob("*.json"))}
    days = world_publish.gated_days(world)
    done = 0
    for day in days:
        src = world / "counts" / day
        files = {r["id"]: out / r["id"] / "snapshots" / f"{day}.json" for r in regions
                 if any(c.get("region") == r["id"] for c in cities)}
        made = (src / "counts.npz").stat().st_mtime
        if not force and all(f.exists() and f.stat().st_mtime >= made for f in files.values()):
            continue
        for region, snap in day_snapshots(src, day, cities, regions, quest_list, registries).items():
            run.write_json(files[region], snap, compact=True)
            files[region].touch()
        done += 1
        run.log(f"world cities: {day}")
    for stale in out.glob("*/snapshots/*.json"):   # a day un-gated, or a region gone
        if stale.stem not in days:
            stale.unlink()
    return done


def build(data_dir: Path, out: Path) -> int:
    return run.history(data_dir, archive=run.ARCHIVE_DIR, parts_dir=run.PARTS_CONFIG, world=out,
                       places=ROOT / "docs" / "places")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("snapshots")
    s.add_argument("--world", type=Path, default=world_publish.WORLD)
    s.add_argument("--force", action="store_true")
    b = sub.add_parser("build")
    b.add_argument("--data-dir", type=Path, required=True)
    b.add_argument("--live", action="store_true")
    for p in (s, b):
        p.add_argument("--out", type=Path, default=run.WORLD_ARCHIVE)
    a = ap.parse_args(argv)
    if a.command == "snapshots":
        run.log(f"world cities: {snapshots(a.world, a.out, a.force)} day(s) written")
        return 0
    if a.data_dir.resolve() == run.DATA_DIR.resolve() and not a.live:
        raise SystemExit("docs/data is the site: --live says so")
    build(a.data_dir, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
