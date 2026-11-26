"""Our own place ids: every place has a GUID of ours; Overture's GERS id and the OSM object are attributes of it.

    <overture venv>/python tools/place_ids.py mint --src data/overture/world   the first registry: every place of the pull
    python tools/place_ids.py check                                            the registry against its own rules
    python tools/place_ids.py map --out FILE                                   the old ids (GERS-derived) -> ours, for the rename

The registry is data/place-ids/registry.tsv.gz (not in git: about a million rows), sorted by public id, a row a place:

    guid, id, gers, osm, name, subtype, country, state, successors, since

- `guid` is a random UUID and `id`, its first 12 hex digits, is what files, links and the bucket use. 12 hex because the
  publisher keys places by a 48-bit number and the links stay short; it is checked unique when an id is minted.
- **A GUID never changes and is never used again.** What a release changes is the rest of the row. `gers` is the place's
  Overture id now; a place that ended keeps its last one.
- `state` is `live` or `ended`. An ended place keeps its row for good; `successors` names the places suggested instead
  (public ids, comma-separated). It can become live again: an id Overture drops can come back.
- `since` is the Overture release the place was first registered with.

Random ids cannot be derived a second time, so this file is the only copy of them: back it up to R2 before anything is
built with it (tools/archive_backup.py), and never delete or regenerate it.

**mint makes ids only for an empty registry.** Afterwards a new Overture release comes in by an agent and an operator who
judge each match (HANDOFF.md, "Overture's next release"); nothing here decides that a place is new or the same.
"""
from __future__ import annotations

import argparse
import gzip
import io
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "place-ids" / "registry.tsv.gz"
RELEASES = ROOT / "data" / "place-ids" / "releases"   # tools/overture_release.py: a release's proposals and staged registry
COLUMNS = ("guid", "id", "gers", "osm", "name", "subtype", "country", "state", "successors", "since")
STATES = ("live", "ended")
ID = re.compile(r"[0-9a-f]{12}")


@dataclass
class Inputs:
    """What a place builder reads for one Overture release (`release_inputs`)."""
    release: str
    src: Path        # the pull: division.parquet, division_area.parquet, division_area_outlines.parquet
    registry: Path   # our place ids
    squares: Path    # the small squares left out (tools/small_squares.py)
    live: bool       # the pinned release: the live inputs, which a world build ahead of a switch must not write


def pinned() -> str:
    import json
    return json.loads((ROOT / "config" / "places.json").read_text(encoding="utf-8"))["overture"]


def release_inputs(release: str | None = None) -> Inputs:
    """The pinned release (config/places.json) reads the live inputs: data/overture/world, the live registry,
    config/small-squares.json. Another release, built ahead of a switch (tools/overture_switch.py), reads its own:
    its pull in data/overture/<release>, its staged registry and its squares list in data/place-ids/releases/<release>/."""
    pin = pinned()
    if release is None or release == pin:
        return Inputs(pin, ROOT / "data" / "overture" / "world", REGISTRY, ROOT / "config" / "small-squares.json", True)
    d = RELEASES / release
    if not (d / "registry.tsv.gz").exists():
        raise SystemExit(f"{release} has no staged registry ({d / 'registry.tsv.gz'}): tools/overture_release.py first")
    return Inputs(release, ROOT / "data" / "overture" / release, d / "registry.tsv.gz", d / "small-squares.json", False)


def live_paths() -> list[Path]:
    """What the running site and world read: a build for a release that is not pinned writes none of them."""
    import json
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))["world"]
    return [ROOT / p for p in ("docs/places", "data/overture/world", "config/parts", "config/small-squares.json",
                               "data/place-ids/registry.tsv.gz", ".scratch/world-places/world", world)]


def refuse_live(out: Path, inputs: Inputs) -> None:
    """Stop when a build for a release that is not pinned would write into what the live site or world reads."""
    if inputs.live:
        return
    o = Path(out).resolve()
    for p in live_paths():
        p = p.resolve()
        if o == p or p in o.parents or o in p.parents:
            raise SystemExit(f"{out} is live ({p}); a build for {inputs.release} goes to a new folder")


def old_id(gers: str) -> str:
    """the id a place had before: the first 12 hex digits of its GERS id. Only for the rename and to keep a new id
    from looking like an old one."""
    oid = gers.replace("-", "")[:12].lower()
    if not ID.fullmatch(oid):
        raise ValueError(f"not a GERS id: {gers!r}")
    return oid


def new_guid() -> uuid.UUID:
    return uuid.uuid4()


@dataclass
class Place:
    guid: str
    id: str
    gers: str
    osm: str
    name: str
    subtype: str
    country: str
    state: str = "live"
    successors: tuple[str, ...] = ()
    since: str = ""


def _clean(v: str | None) -> str:
    return re.sub(r"[\t\r\n]+", " ", v or "")


@dataclass
class Registry:
    places: dict[str, Place] = field(default_factory=dict)  # public id -> place
    by_gers: dict[str, str] = field(default_factory=dict)   # GERS id -> public id, the live places'

    def add(self, p: Place) -> None:
        if p.id in self.places:
            raise ValueError(f"public id {p.id} twice ({self.places[p.id].guid}, {p.guid})")
        if p.state == "live":
            if p.gers in self.by_gers:
                raise ValueError(f"GERS id {p.gers} on two live places ({self.by_gers[p.gers]}, {p.id})")
            self.by_gers[p.gers] = p.id
        self.places[p.id] = p

    def id_of(self, gers: str) -> str:
        """the place's public id. Nothing is minted here: an unknown GERS id stops the build."""
        try:
            return self.by_gers[gers]
        except KeyError:
            raise SystemExit(f"GERS id {gers} is not in the place registry ({REGISTRY}): the release has not been "
                             f"ingested (see HANDOFF.md, Overture)") from None

    def check(self) -> list[str]:
        bad = []
        guids: set[str] = set()
        for pid, p in self.places.items():
            if not ID.fullmatch(p.id) or p.id != p.guid.replace("-", "")[:12]:
                bad.append(f"{pid}: the public id is not the GUID's first 12 digits ({p.guid})")
            if p.guid in guids:
                bad.append(f"{pid}: GUID {p.guid} twice")
            guids.add(p.guid)
            if p.state not in STATES:
                bad.append(f"{pid}: state {p.state!r}")
            for s in p.successors:
                if s not in self.places:
                    bad.append(f"{pid}: successor {s} is not a place")
                elif s == pid:
                    bad.append(f"{pid}: is its own successor")
            if p.state == "live" and p.successors:
                bad.append(f"{pid}: live with successors")
        return bad

    # --- files

    def save(self, path: Path = REGISTRY) -> None:
        """Atomic. Refuses to lose a place that the file on disk has, or to change a GUID of one."""
        if path.exists():
            before = load(path)
            lost = [i for i, p in before.places.items() if i not in self.places or self.places[i].guid != p.guid]
            if lost:
                raise SystemExit(f"{len(lost):,} places would lose their id, e.g. {lost[:3]}: not saved")
        bad = self.check()
        if bad:
            raise SystemExit("not saved:\n  " + "\n  ".join(bad[:10]))
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as z:
            z.write(("\t".join(COLUMNS) + "\n").encode())
            for pid in sorted(self.places):
                p = self.places[pid]
                z.write(("\t".join([p.guid, p.id, p.gers, _clean(p.osm), _clean(p.name), p.subtype, p.country, p.state,
                                    ",".join(p.successors), p.since]) + "\n").encode("utf-8"))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(buf.getvalue())
        os.replace(tmp, path)


def load(path: Path = REGISTRY) -> Registry:
    if not path.exists():
        raise SystemExit(f"{path} is missing: there are no place ids (place_ids.py mint; or the R2 backup)")
    reg = Registry()
    with gzip.open(path, "rt", encoding="utf-8", newline="") as z:
        head = z.readline().rstrip("\n").split("\t")
        if tuple(head) != COLUMNS:
            raise SystemExit(f"{path}: columns {head}")
        for n, line in enumerate(z, 2):
            v = line.rstrip("\n").split("\t")
            if len(v) != len(COLUMNS):
                raise SystemExit(f"{path}, line {n}: {len(v)} fields")
            d = dict(zip(COLUMNS, v))
            d["successors"] = tuple(x for x in d["successors"].split(",") if x)
            reg.add(Place(**d))
    return reg


def mint(rows, release: str, guid=new_guid) -> Registry:
    """A registry of rows (gers, osm, name, subtype, country). A new id is unlike every other and unlike every old id of
    the pull, so that a rename can tell an old id from a new one."""
    rows = list(rows)
    old = {old_id(r[0]) for r in rows}
    if len(old) != len(rows):
        raise SystemExit("two places of the pull share an old id")
    reg = Registry()
    for gers, osm, name, subtype, country in sorted(rows, key=lambda r: r[0]):
        while True:
            g = guid()
            pid = g.hex[:12]
            if pid not in reg.places and pid not in old:
                break
        reg.add(Place(str(g), pid, gers, (osm or "").split("@")[0], _clean(name), subtype or "", country or "",
                      since=release))
    return reg


def read_pull(src: Path) -> list[tuple]:
    """Every division of the pull that has an area: what places.py makes places of."""
    import duckdb
    s = src.as_posix()
    con = duckdb.connect()
    con.execute("SET memory_limit = '2GB'")
    return con.execute(f"""SELECT id, [s.record_id FOR s IN sources IF s.dataset = 'OpenStreetMap' AND s.property = ''][1],
        names."primary", subtype, country FROM read_parquet('{s}/division.parquet')
        WHERE id IN (SELECT division_id FROM read_parquet('{s}/division_area.parquet'))""").fetchall()


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mint")
    m.add_argument("--src", type=Path, required=True)
    m.add_argument("--release", help="default: config/places.json's")
    sub.add_parser("check")
    x = sub.add_parser("map")
    x.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "mint":
        if a.registry.exists():
            raise SystemExit(f"{a.registry} exists: ids are minted once. A later release is ingested by an operator.")
        import json
        release = a.release or json.loads((ROOT / "config" / "places.json").read_text(encoding="utf-8"))["overture"]
        reg = mint(read_pull(a.src), release)
        reg.save(a.registry)
        print(f"{len(reg.places):,} places minted from {a.src} ({release}) into {a.registry}: back it up now")
    elif a.cmd == "check":
        reg = load(a.registry)
        bad = reg.check()
        live = sum(p.state == "live" for p in reg.places.values())
        print(f"{len(reg.places):,} places, {live:,} live; {len(bad)} problems")
        for b in bad[:20]:
            print("  " + b)
        return 1 if bad else 0
    else:
        reg = load(a.registry)
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            for pid, p in sorted(reg.places.items()):
                f.write(f"{old_id(p.gers)}\t{pid}\n")
        print(f"{len(reg.places):,} ids in {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
