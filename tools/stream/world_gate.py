"""A world day's gate (DESIGN.md, "Release 1: the world day", step 6): the world's counts for the 32 European cities'
own outlines (parts `osm-<city>`) against the engine's whole count of the same cities on the Europe clip of the same
instant. Same quests file, same clock, the same notes dump as the world's (each region's clip of it under
W/gate-notes/), the default setting's measures, which the site shows.

  python tools/stream/world_gate.py W D [--clip europe-D.osm.pbf]   (a check by hand; planet_store_day.py calls it)

The bar: over the 32 cities' open quests, and in each city, |world - clip| at most 0.1% of the clip's
(BAR). The seed at 11-01 had 21 of 32 cities equal in every quest and measure and +9 open of 19.2M (HANDOFF,
"The seed's like-for-like gate"); a day is logged beside that."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools/stream"))
import run  # noqa: E402
import storecheck_cities as SCC  # noqa: E402

EUROPE = Path.home() / "Code/.osm-data/europe"
REGIONS = SCC.REGIONS
MEASURES = ["open", "nodes", "ways", "relations", "agedOnly"]
BAR = 0.001


def _log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def world_dump(w: Path) -> Path:
    """the notes dump the world's clips were cut from (each plan file's notes.jsonl header names it)"""
    f0 = json.loads((w / "plan.json").read_text(encoding="utf-8"))["files"][0]["id"]
    with open(w / "files" / f0 / "notes.jsonl", encoding="utf-8") as fh:
        src = json.loads(fh.readline())["source"]
    return run.OSM_DATA_DIR / "notes" / src


def notes_until(w: Path) -> str:
    f0 = json.loads((w / "plan.json").read_text(encoding="utf-8"))["files"][0]["id"]
    with open(w / "files" / f0 / "notes.jsonl", encoding="utf-8") as fh:
        return json.loads(fh.readline())["until"]


def gate_regions() -> list[dict]:
    return [r for r in run.read_json(run.REGIONS_CONFIG)["regions"] if r["id"] in REGIONS]


def gate_clips(w: Path, regions: list[dict] | None = None) -> list[dict]:
    """what clip_notes is asked for each region's gate clip (its config's entries): the region's poly, its cities'
    boxes, out W/gate-notes/<region>.jsonl. One place, so the clips the world's notes refresh cuts in its own pass
    over the dump (world_day.refresh_notes) are the ones `gate_notes` would cut"""
    regions = gate_regions() if regions is None else regions
    return [{"poly": str(ROOT / r["poly"]), "out": str(w / "gate-notes" / f"{r['id']}.jsonl"),
             "boxes": run.note_boxes(r)} for r in regions]


def clip_source(clip: Path) -> str | None:
    """the dump a notes clip was cut from (its header); None when there is no such clip"""
    try:
        with open(clip, encoding="utf-8") as fh:
            return json.loads(fh.readline()).get("source")
    except (OSError, ValueError):
        return None


def gate_notes(w: Path, regions: list[dict], log=_log) -> dict[str, Path]:
    """each region's clip of the world's notes dump, made once (the daily run deletes its own older clips). The
    world's notes refresh makes them in its own pass over the dump; a clip that is missing, or is of another dump
    than the world's (a refresh that stopped half way), is cut here"""
    d = w / "gate-notes"
    d.mkdir(exist_ok=True)
    out = {r["id"]: d / f"{r['id']}.jsonl" for r in regions}
    dump = world_dump(w)
    todo = [r for r in regions if clip_source(out[r["id"]]) != dump.name]
    if todo:
        if not dump.exists():
            raise SystemExit(f"the world's notes dump {dump} is gone: the gate's notes clips cannot be made")
        cfg = d / "clips.json"
        cfg.write_text(json.dumps({"clips": gate_clips(w, todo)}), encoding="utf-8")
        log(f"gate notes: clipping {dump.name} to {', '.join(r['id'] for r in todo)}")
        subprocess.run([sys.executable, str(run.CLIP_NOTES), str(dump), "--config", str(cfg)], check=True, cwd=ROOT)
        cfg.unlink()
    return out


def clip_side(w: Path, clip_pbf: Path, day: str, out: Path, log=_log) -> dict:
    """the engine over the Europe clip of day D for each region's cities: out/<region>/out/snapshots/<D>.json"""
    regions = gate_regions()
    notes = gate_notes(w, regions, log)
    quests = run.newest_quests_file()
    secs = {}
    for r in regions:
        d = out / r["id"]
        if (d / "done").exists():
            continue
        cities = run.region_cities(r).relative_to(ROOT)
        try:
            # a region short of its least heap waits, and after the wait raises run.MemoryBusy with nothing
            # written: the regions before it keep their `done`, and the next gate of this day starts here
            s = SCC.engine(clip_pbf, cities, d, notes[r["id"]], r["timeZone"], quests.relative_to(ROOT),
                           f"{day}T00:00:00Z", min_heap_gb=run.region_min_heap_gb(r), what=f"gate {r['id']}", log=log)
        except subprocess.CalledProcessError:
            log(heap_line(r["id"], engine_heap(d)))  # an engine that died: the heap it had, said before the stop
            raise
        (d / "state.bin").unlink(missing_ok=True)  # the gate compares counts; the rows are not needed
        (d / "done").write_text("", encoding="utf-8")
        secs[r["id"]] = round(s)
        log(f"gate: {r['id']} counted on {clip_pbf.name} in {s:.0f} s")
        log(heap_line(r["id"], engine_heap(d)))
    return secs


def engine_heap(d: Path) -> dict:
    """a gate region's heap, read off its engine's log (d/log.txt): run.engine_heap_of; {} with no log"""
    try:
        return run.engine_heap_of((d / "log.txt").read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}


def heap_line(region: str, h: dict) -> str:
    """'gate heap: europe-central given 27,648 MB, peak 27,189 MB (98% of it)'. A line of its own: the
    'gate: <region> counted ... in N s' line is read whole by day_metrics.GATE."""
    given, peak = h.get("given MB"), h.get("peak MB")
    said = f"given {given:,} MB" if given is not None else "given: not in the engine's log"
    if peak is not None:
        said += f", peak {peak:,} MB" + (f" ({peak / given:.0%} of it)" if given else "")
    elif h.get("out of memory"):
        said += ", died of OutOfMemoryError before it logged a peak"
    else:
        said += ", no peak logged (the engine did not end)"
    return f"gate heap: {region} {said}"


def clip_heap(out: Path) -> dict:
    """every gate region's heap from the logs under `out`, also of the regions counted by an earlier run of this
    day's gate: what gate.json keeps as "clip heap" """
    return {r: h for r in REGIONS if (h := engine_heap(out / r))}


def compare(w: Path, day: str, out: Path) -> dict:
    """the world's counts at D (W/counts/<D>/) for each city's outline against the clip's snapshots"""
    cd = w / "counts" / day
    meta = json.loads((cd / "counts.json").read_text(encoding="utf-8"))
    if meta.get("clock", f"{day}T00:00:00Z")[:10] != day:
        raise SystemExit(f"{cd} is at {meta.get('clock')}, not {day}")
    z = np.load(cd / "counts.npz")
    mi = [meta["measures"].index(m) for m in MEASURES]
    pidx = {p: i for i, p in enumerate(meta["parts"])}
    want = {}
    for r in REGIONS:
        snap = out / r / "out" / "snapshots" / f"{day}.json"
        for cid, c in json.loads(snap.read_text(encoding="utf-8"))["cities"].items():
            want[cid] = {q: tuple(v[m] for m in MEASURES) for q, v in c["quests"].items()}
    missing = sorted(c for c in want if f"osm-{c}" not in pidx)
    ids = {pidx[f"osm-{cid}"]: cid for cid in want if f"osm-{cid}" in pidx}
    sel = np.isin(z["part"], list(ids))
    world = defaultdict(dict)
    for p, q, m in zip(z["part"][sel].tolist(), z["quest"][sel].tolist(), z["m"][sel][:, mi].tolist()):
        world[ids[p]][meta["quests"][q]] = tuple(m)
    zero = (0,) * len(MEASURES)
    cities, tot_c, tot_w, worst = {}, 0, 0, 0.0
    for cid in sorted(want):
        a, b = want[cid], world.get(cid, {})
        diff = {q: (a.get(q, zero), b.get(q, zero)) for q in set(a) | set(b) if a.get(q, zero) != b.get(q, zero)}
        oa, ob = sum(v[0] for v in a.values()), sum(v[0] for v in b.values())
        rel = abs(ob - oa) / oa if oa else float(ob != 0)
        worst = max(worst, rel)
        cities[cid] = {"open clip": oa, "open world": ob, "rel": rel, "quests differing": len(diff),
                       "examples": {q: [list(x), list(y)] for q, (x, y) in sorted(diff.items())[:6]}}
        tot_c += oa
        tot_w += ob
    rel_tot = abs(tot_w - tot_c) / tot_c if tot_c else 1.0
    equal = sum(1 for c in cities.values() if not c["quests differing"])
    ok = not missing and rel_tot <= BAR and worst <= BAR and len(want) == 32
    return {"day": day, "ok": ok, "bar": BAR, "cities": len(want), "equal": equal, "missing": missing,
            "open clip": tot_c, "open world": tot_w, "rel": rel_tot, "worst city rel": worst, "per city": cities}


def gate(w: Path, day: str, clip_pbf: Path, out: Path, log=_log) -> dict:
    t = time.time()
    secs = clip_side(w, clip_pbf, day, out, log)
    res = compare(w, day, out)
    res["clip seconds"] = secs
    res["clip heap"] = clip_heap(out)  # per region: the heap given and the peak, MB (kept with the day's gate.json)
    res["seconds"] = round(time.time() - t)
    (out / "gate.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    log(f"gate {day}: {'PASS' if res['ok'] else 'FAIL'}; {res['equal']} of {res['cities']} cities equal in every quest "
        f"and measure; open quests clip {res['open clip']:,}, world {res['open world']:,} "
        f"({res['open world'] - res['open clip']:+,}); worst city {res['worst city rel']:.5%}; missing {res['missing']}")
    for cid, c in res["per city"].items():
        if c["quests differing"]:
            log(f"  {cid}: open {c['open clip']:,} / {c['open world']:,}; {c['quests differing']} quests: "
                f"{json.dumps(c['examples'])[:300]}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("world", type=Path)
    ap.add_argument("day")
    ap.add_argument("--clip", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    clip = a.clip or EUROPE / f"europe-{a.day}.osm.pbf"
    res = gate(a.world, a.day, clip, a.out or a.world / "gate" / a.day)
    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
