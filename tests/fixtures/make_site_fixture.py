"""Make a stand-in docs/data for the site until the engine's real snapshots land.

    python tests/fixtures/make_site_fixture.py

Writes tests/fixtures/data/ (ten daily snapshots, with an SC version change on the seventh) and
tests/fixtures/data-single/ (one snapshot), each with quests.json, then runs `run.py history` on
both. Quest metadata comes from the real registry dump; the counts are made up (seeded), so the
numbers mean nothing. Preview: python -m http.server, then open /docs/?data=../tests/fixtures/data
"""
import json
import random
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import run  # noqa: E402

CITIES = ["toronto", "ottawa", "mississauga", "hamilton", "london", "kingston", "guelph", "barrie"]
APPROXIMATED = {"AddHousenumber", "AddRoadName"}     # pretend someone wrote these two custom quests
DROPPED_IN_NEW_VERSION = "AddBusStopRef"              # present before the version change only
ADDED_IN_NEW_VERSION = "AddBenchStatusOnBusStop"      # present after it only


def in_canada(rule: dict | None) -> bool:
    rule = rule or {"type": "AllCountries"}
    codes = set(rule.get("codes", []))
    if rule["type"] == "AllCountries":
        return True
    if rule["type"] == "AllCountriesExcept":
        return not codes & {"CA", "CA-ON"}
    return bool(codes & {"CA", "CA-ON"})


def quest_meta(registry: dict) -> dict:
    quests = []
    for q in sorted(registry["quests"], key=lambda q: q["order"]):
        if q["name"] in APPROXIMATED:
            support, status = "approximated", "counted"
        elif q["kind"] == "filter":
            support = "supported"
            status = "counted" if in_canada(q.get("enabledInCountries")) else "not-in-region"
        else:
            support, status = "unsupported", "unsupported"
        quests.append({
            "name": q["name"], "order": q["order"], "kind": q["kind"], "support": support,
            "defaultDisabled": q["defaultDisabled"], "usesAge": bool(q.get("usesAge")),
            "enabledInCountries": q.get("enabledInCountries") or {"type": "AllCountries"},
            "wikiLink": q.get("wikiLink"),
            "status": {c: status for c in CITIES},
        })
    return {"scVersion": registry["scVersion"], "quests": quests}


def snapshots(meta: dict, config: dict, days: int, change_at: int) -> list[dict]:
    rng = random.Random(63)
    cities = {c["id"]: c for c in config["cities"] if c["id"] in CITIES}
    counted = [q for q in meta["quests"] if q["status"][CITIES[0]] == "counted"]
    weight = {q["name"]: rng.lognormvariate(0, 1.4) for q in counted}
    aged_share = {q["name"]: rng.uniform(0.1, 0.6) if q["usesAge"] else 0 for q in counted}
    trend = {q["name"]: rng.uniform(-0.012, 0.004) for q in counted}
    base = {(cid, q["name"]): weight[q["name"]] * (c["population"] or 50000) / 1000 * rng.uniform(0.7, 1.3)
            for cid, c in cities.items() for q in counted}
    out = []
    for day in range(days):
        new = day >= change_at
        as_of = date(2026, 7, 16) + timedelta(days=day)
        snap = {
            "schema": 1, "asOf": f"{as_of.isoformat()}T20:21:30Z", "asOfDate": as_of.isoformat(),
            "timeZone": "America/Toronto", "scVersion": "63.5" if new else "63.4",
            "scCommit": "fixture", "resurveyMultiplier": 1, "engineCommit": "fixture",
            "source": {"url": "https://download.geofabrik.de/north-america/canada/ontario-latest.osm.pbf", "lastModified": f"{as_of.isoformat()} (fixture)",
                       "sha256": f"fixture-{as_of.isoformat()}"},
            "runSeconds": 12.3, "cities": {},
        }
        for cid, c in cities.items():
            scale = (c["population"] or 50000) / 1000
            quests = {}
            for q in counted:
                name = q["name"]
                if (name == DROPPED_IN_NEW_VERSION and new) or (name == ADDED_IN_NEW_VERSION and not new):
                    continue
                b = base[cid, name]
                mapping = round(b * (1 - aged_share[name]) * (1 + trend[name]) ** day)
                aged = round(b * aged_share[name] * (1 + 0.01 * day))
                open_ = mapping + aged
                ways = open_ // 4
                quests[name] = {"open": open_, "nodes": open_ - ways, "ways": ways,
                                "relations": 0, "agedOnly": aged}
            snap["cities"][cid] = {
                "denominators": {"landAreaKm2": round(c["landAreaKm2"], 1),
                                 "population": c["population"],
                                 "taggedNodes": int(scale * 900), "taggedWays": int(scale * 600),
                                 "highwayKm": round(c["landAreaKm2"] * rng.uniform(6, 9), 1)},
                "quests": quests,
            }
        out.append(snap)
    return out



def write(dest: Path, meta: dict, snaps: list[dict], config: dict) -> None:
    """One snapshot per region and date, in <region>/snapshots/, like the engine's per-region runs."""
    shutil.rmtree(dest, ignore_errors=True)
    region_of = {c["id"]: c["region"] for c in config["cities"]}
    for region in sorted(set(region_of.values())):
        run.write_json(dest / region / "quests.json", meta)
        for s in snaps:
            part = {**s, "cities": {cid: c for cid, c in s["cities"].items() if region_of[cid] == region}}
            run.write_json(dest / region / "snapshots" / f"{s['asOfDate']}.json", part, compact=True)
    run.history(dest, run.CITIES_CONFIG)


def main() -> None:
    meta = quest_meta(run.read_json(run.newest_quests_file()))
    config = run.read_json(run.CITIES_CONFIG)
    here = Path(__file__).resolve().parent
    write(here / "data", meta, snapshots(meta, config, days=10, change_at=6), config)
    write(here / "data-single", meta, snapshots(meta, config, days=1, change_at=99), config)


if __name__ == "__main__":
    main()
