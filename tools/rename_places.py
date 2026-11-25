"""The rename: every stored place id from the GERS-derived one to ours (tools/place_ids.py). Run once, under HOLD.

    python tools/rename_places.py plan  [config|archive|world ...]    what would change; nothing is written
    python tools/rename_places.py apply [config|archive|world ...]    with the hold (.scratch/planet-cut/HOLD) placed
                                                                      and no world day running
Default: all three. What it rewrites:

- **config**: the `id` of every part in config/parts/*.json, and config/dropped-places.json if there is one;
- **archive**: the keys of `parts` and `partsAged` in every data/archive/<region>/snapshots/*.json;
- **world**: in .scratch/planet/world-1101, places.json, place-sets.json, every files/<f>/parts/*.json and every
  counts/<day>/counts.json. Cells (`city:...`) and cities (`osm-...`) keep their names. Rows, counts and outlines are not
  touched: a row holds a place-set number, counts.npz a position in counts.json's `parts`, whose order stays.

Not here, rebuilt from the renamed files instead: docs/places (tools/places.py build), docs/data (run.py history), data/facts
(facts.py cities --force, facts.py world --force, then verify), the bucket (world_publish.py), the checkpoint in R2.

Safety, per file: an id that is neither an old nor a new id of the registry stops the run, and so does a file with
both, so a run that died is run again (a finished file is all new and is left). The new text is translated back and
must equal the old text byte for byte before it replaces it; it is written beside it and renamed over it, so a
hard-linked copy (the checkpoint's) keeps the old text. The outline cache's stamp (parts.cache.json) follows
places.json only if it was current before: an outline's path does not change.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import place_ids  # noqa: E402

PLANET_CUT = ROOT / ".scratch" / "planet-cut"
WORLD = ROOT / ".scratch" / "planet" / "world-1101"
ARCHIVE = ROOT / "data" / "archive"
PARTS = ROOT / "config" / "parts"
DROPPED = ROOT / "config" / "dropped-places.json"

# where an id is in each kind of file: the id is group 2
ID_FIELD = re.compile(r'("id": ?")([0-9a-f]{12})(")')             # "id": "0123456789ab"
KEY = re.compile(r'(")([0-9a-f]{12})("\s*:)')                     # "0123456789ab": ...
STRING = re.compile(r'(")([0-9a-f]{12})(")')                      # any string of twelve hex digits


class Renamer:
    def __init__(self, pairs: dict[str, str]):
        self.new = pairs
        self.old = {n: o for o, n in pairs.items()}
        if len(self.old) != len(pairs):
            raise SystemExit("two old ids have one new id")
        if self.new.keys() & self.old.keys():
            raise SystemExit("an old id is also a new id: the rename could not be told from its result")

    def text(self, text: str, pattern: re.Pattern, what: str) -> tuple[str, int]:
        """the text with its ids renamed, and how many; the same text when it is already renamed"""
        kinds = {"old": 0, "new": 0}
        unknown = []
        for m in pattern.finditer(text):
            i = m.group(2)
            if i in self.new:
                kinds["old"] += 1
            elif i in self.old:
                kinds["new"] += 1
            else:
                unknown.append(i)
        if unknown:
            raise SystemExit(f"{what}: {len(unknown)} ids are in no registry, e.g. {sorted(set(unknown))[:3]}")
        if kinds["old"] and kinds["new"]:
            raise SystemExit(f"{what}: {kinds['old']} old and {kinds['new']} new ids in one file")
        if not kinds["old"]:
            return text, 0
        out = pattern.sub(lambda m: m.group(1) + self.new[m.group(2)] + m.group(3), text)
        back = pattern.sub(lambda m: m.group(1) + self.old[m.group(2)] + m.group(3), out)
        if back != text:
            raise SystemExit(f"{what}: the renamed text does not translate back")
        return out, kinds["old"]


def replace(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".renaming")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def read(path: Path) -> str:
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def jobs(what: str, world: Path, archive: Path, parts: Path) -> list[tuple[Path, re.Pattern]]:
    if what == "config":
        out = [(p, ID_FIELD) for p in sorted(parts.glob("*.json"))]
        return out + ([(DROPPED, ID_FIELD)] if DROPPED.exists() else [])
    if what == "archive":
        return [(p, KEY) for p in sorted(archive.glob("*/snapshots/*.json"))]
    out = [(world / "places.json", ID_FIELD)]
    out += [(p, ID_FIELD) for p in sorted(world.glob("files/*/parts/*.json"))]
    out += [(p, STRING) for p in sorted(world.glob("counts/*/counts.json"))]
    return out + [(world / "place-sets.json", STRING)]


def stamp_of(places: Path) -> dict:
    st = places.stat()
    return {"places": places.name, "size": st.st_size, "mtimeNs": st.st_mtime_ns}


def run(what: list[str], apply: bool, pairs: dict[str, str], world: Path = WORLD, archive: Path = ARCHIVE,
        parts: Path = PARTS) -> dict[str, tuple[int, int]]:
    """{kind: (files changed, ids renamed)}"""
    ren = Renamer(pairs)
    places, side = world / "places.json", world / "parts.cache.json"
    cache_current = ("world" in what and side.exists() and places.exists()
                     and json.loads(side.read_text(encoding="utf-8")).get("stamp") == stamp_of(places))
    todo = {kind: jobs(kind, world, archive, parts) for kind in what}
    result = {}
    # every file of every kind is read and checked before the first is written
    for write in ((False, True) if apply else (False,)):
        for kind, files_of in todo.items():
            files = ids = 0
            for path, pattern in files_of:
                out, n = ren.text(read(path), pattern, str(path))
                if n:
                    files, ids = files + 1, ids + n
                    if write:
                        replace(path, out)
            result[kind] = (files, ids)
    if apply and cache_current:
        d = json.loads(side.read_text(encoding="utf-8"))
        d["stamp"] = stamp_of(places)
        replace(side, json.dumps(d))
    for kind, (files, ids) in result.items():
        print(f"{kind}: {len(todo[kind]):,} files looked at, {files:,} with {ids:,} ids "
              f"{'renamed' if apply else 'to rename'}", flush=True)
    return result


def refuse_beside_the_loop() -> None:
    if (PLANET_CUT / "RUNNING").exists():
        raise SystemExit("a world day is running (.scratch/planet-cut/RUNNING): the rename needs a gap")
    if not (PLANET_CUT / "HOLD").exists():
        raise SystemExit("place .scratch/planet-cut/HOLD first, so no day starts during the rename")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["plan", "apply"])
    ap.add_argument("what", nargs="*", choices=["config", "archive", "world"])
    ap.add_argument("--registry", type=Path, default=place_ids.REGISTRY)
    a = ap.parse_args(argv)
    if a.cmd == "apply":
        refuse_beside_the_loop()
    reg = place_ids.load(a.registry)
    if reg.check():
        raise SystemExit("the registry fails its own check: place_ids.py check")
    pairs = {place_ids.old_id(p.gers): p.id for p in reg.places.values()}
    if len(pairs) != len(reg.places):
        raise SystemExit("two places of the registry had one old id")
    run(a.what or ["config", "archive", "world"], a.cmd == "apply", pairs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
