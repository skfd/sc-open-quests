"""Clip the OSM planet notes dump to regions, all in one pass over the dump. Python standard library only.

  python tools/clip_notes.py <planet-notes-YYMMDD.osn.bz2> --poly <a.poly> --out <a.jsonl> [--poly ... --out ...]
  python tools/clip_notes.py <planet-notes-YYMMDD.osn.bz2> --config <clips.json>

clips.json: {"clips": [{"poly": "config/ontario.poly", "out": "data/notes/....jsonl",
                        "boxes": [[minLon, minLat, maxLon, maxLat], ...]}, ...]}; "boxes" is optional.

The engine models StreetComplete's note quest and its hiding of quests at open-note positions, at any
past time, so every note of a clip is kept, open or closed, with all its comments. A note belongs to a clip
when it is inside the .poly (osmosis semantics: in some outer section and not strictly inside a "!" hole
section; on an edge counts as inside) or inside one of the clip's boxes (inclusive). run.py passes each
region's cities' bounding boxes, padded by 1 km, as boxes: Geofabrik's polys are simplified outlines, and a
border city can stick out of its region's poly by a few metres, so the poly alone could lose a note the
engine looks at (it reads notes inside the city polygons, and counts the open ones in each city's bbox).
A poly across the antimeridian is fine either way it is written: each section is unwrapped to one
continuous run of longitudes (so it may go past +-180), and a note is tested at lon and lon +- 360.

Output is JSONL (UTF-8, LF), one file per clip. Line 1 is a header:
  {"schema":1,"source":<dump name>,"sha256":<of the dump>,"until":<newest comment timestamp in the whole
   dump>,"bbox":[minLon,minLat,maxLon,maxLat],"poly":<poly name>,"notes":<count>[,"boxes":[[...],...]]}
bbox is the poly's outer sections' bounding box (longitudes past +-180 for a poly across the antimeridian);
boxes, when given, are the extra boxes. Then one note per line, ascending id:
  {"id":6,"lat":"35.5170066","lon":"139.6322554","created":"...","comments":[{"action":"opened",
   "timestamp":"...","uid":378532,"text":"..."},...]}
lat/lon are the dump's attribute strings; uid is omitted when the comment is anonymous.

Speed: the dump is ~2.7 GB of XML. It is never parsed whole: regexes over big decompressed blocks find
note headers and comment timestamps (for "until"). A note's position is looked up in a 1-degree grid of
the cells some clip's bounding boxes touch; only notes there get the exact test (point in polygon over the
edges of the note's latitude band), and only notes in some clip go through ElementTree, once however many
clips hold them. Decompression is most of the time, so clipping many regions costs about what one did
(the 2026-10-24 dump, twelve regions: see DESIGN.md). The dump is multi-stream (pbzip2-style), so the
streams could be decompressed in parallel if this ever gets too slow; for now it stays single-threaded.
Actions seen in the dump: opened, commented, closed, reopened, hidden.
"""
from __future__ import annotations

import argparse
import bz2
import hashlib
import json
import math
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run  # noqa: E402

SCHEMA = 1
READ_SIZE = 1 << 20     # compressed bytes per read
BLOCK_SIZE = 16 << 20   # decompressed bytes gathered before scanning

# Text and attribute values cannot hold a raw "<", so these only ever match real tags.
NOTE_HEAD = re.compile(rb'<note id="(\d+)" lat="([^"]+)" lon="([^"]+)"')
COMMENT_TS = re.compile(rb'<comment action="[^"]*" timestamp="([^"]+)"')
NOTE_END = b"</note>"

OUTSIDE, ON_EDGE, INSIDE = 0, 1, 2
SHIFTS = (0.0, 360.0, -360.0)


# --- polygons -------------------------------------------------------------------------------------

def read_poly(path: Path) -> list[tuple[bool, list[tuple[float, float]]]]:
    """Sections of an osmosis .poly as (is_hole, [(lon, lat), ...]), as written."""
    sections: list[tuple[bool, list[tuple[float, float]]]] = []
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    current: list[tuple[float, float]] | None = None
    for ln in lines[1:]:  # the first line is the polygon's name
        if not ln:
            continue
        if ln == "END":
            current = None
            continue
        parts = ln.split()
        if current is not None and len(parts) == 2:
            try:
                current.append((float(parts[0]), float(parts[1])))
                continue
            except ValueError:
                pass
        current = []  # a section name
        sections.append((ln.startswith("!"), current))
    sections = [(hole, pts) for hole, pts in sections if pts]
    if not any(not hole for hole, _ in sections):
        raise ValueError(f"{path}: no coordinates")
    return sections


def unwrap(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """A ring as one continuous run of longitudes: no edge spans more than 180 degrees, so a ring across
    the antimeridian goes past +-180 instead of jumping. A ring around a pole (it ends 360 degrees from
    where it started) is closed over that pole."""
    out = [pts[0]]
    for lon, lat in pts[1:]:
        prev = out[-1][0]
        while lon - prev > 180:
            lon -= 360
        while lon - prev < -180:
            lon += 360
        out.append((lon, lat))
    if abs(out[-1][0] - out[0][0]) > 180:
        pole = 90.0 if sum(lat for _, lat in out) > 0 else -90.0
        out += [(out[-1][0], pole), (out[0][0], pole)]
    return out


class Ring:
    """One unwrapped poly section, its edges bucketed by latitude band for the point test."""

    def __init__(self, pts: list[tuple[float, float]]):
        pts = unwrap(pts)
        if pts[0] != pts[-1]:
            pts.append(pts[0])
        self.min_lon = min(p[0] for p in pts)
        self.max_lon = max(p[0] for p in pts)
        self.min_lat = min(p[1] for p in pts)
        self.max_lat = max(p[1] for p in pts)
        edges = [(x0, y0, x1, y1) for (x0, y0), (x1, y1) in zip(pts, pts[1:]) if (x0, y0) != (x1, y1)]
        span = self.max_lat - self.min_lat
        self.bands = max(1, min(len(edges), 4096)) if span > 0 else 1
        self.band_h = span / self.bands if span > 0 else 1.0
        self.edges: list[list[tuple[float, float, float, float]]] = [[] for _ in range(self.bands)]
        for e in edges:
            lo, hi = self._band(min(e[1], e[3])), self._band(max(e[1], e[3]))
            for b in range(lo, hi + 1):
                self.edges[b].append(e)

    def _band(self, lat: float) -> int:
        return min(self.bands - 1, max(0, int((lat - self.min_lat) / self.band_h)))

    def locate(self, lon: float, lat: float) -> int:
        """OUTSIDE, ON_EDGE or INSIDE, trying lon and lon +- 360."""
        if not self.min_lat <= lat <= self.max_lat:
            return OUTSIDE
        for s in SHIFTS:
            x = lon + s
            if self.min_lon <= x <= self.max_lon:
                where = self._locate(x, lat)
                if where:
                    return where
        return OUTSIDE

    def _locate(self, x: float, y: float) -> int:
        inside = False
        for x0, y0, x1, y1 in self.edges[self._band(y)]:
            if min(y0, y1) <= y <= max(y0, y1) and min(x0, x1) <= x <= max(x0, x1):
                cross = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
                if abs(cross) <= 1e-12 * max(1.0, abs(x1 - x0) + abs(y1 - y0)):
                    return ON_EDGE
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                inside = not inside
        return INSIDE if inside else OUTSIDE


class Clip:
    """One output: a poly, extra boxes, where it goes, and the notes found for it."""

    def __init__(self, poly: Path, out: Path, boxes: list[list[float]] | None = None):
        self.poly, self.out = poly, out
        sections = read_poly(poly)
        self.outers = [Ring(pts) for hole, pts in sections if not hole]
        self.holes = [Ring(pts) for hole, pts in sections if hole]
        self.boxes = [tuple(float(v) for v in b) for b in boxes or []]
        for b in self.boxes:
            if len(b) != 4 or b[0] > b[2] or b[1] > b[3]:
                raise ValueError(f"{out.name}: a box is [minLon, minLat, maxLon, maxLat], not {list(b)}")
        self.bbox = (min(r.min_lon for r in self.outers), min(r.min_lat for r in self.outers),
                     max(r.max_lon for r in self.outers), max(r.max_lat for r in self.outers))
        self.notes: list[dict] = []

    def prefilter(self) -> list[tuple[float, float, float, float]]:
        """Boxes that hold everything this clip keeps."""
        return [(r.min_lon, r.min_lat, r.max_lon, r.max_lat) for r in self.outers] + list(self.boxes)

    def contains(self, lon: float, lat: float) -> bool:
        for x0, y0, x1, y1 in self.boxes:
            if y0 <= lat <= y1 and any(x0 <= lon + s <= x1 for s in SHIFTS):
                return True
        if not any(r.locate(lon, lat) for r in self.outers):
            return False
        return not any(r.locate(lon, lat) == INSIDE for r in self.holes)


def poly_bbox(path: Path) -> tuple[float, float, float, float]:
    """(minLon, minLat, maxLon, maxLat) of an osmosis .poly's outer sections, unwrapped."""
    return Clip(path, Path("-")).bbox


def cell(lon: float, lat: float) -> int:
    """The 1-degree grid cell of a position; longitudes wrap."""
    return (math.floor(lat) + 90) * 360 + (math.floor(lon) + 180) % 360


def grid(clips: list[Clip]) -> dict[int, list[Clip]]:
    """Cell -> the clips whose prefilter boxes touch it."""
    cells: dict[int, list[Clip]] = {}
    for c in clips:
        mine: set[int] = set()
        for x0, y0, x1, y1 in c.prefilter():
            lons = range(math.floor(x0), math.floor(x1) + 1)
            if len(lons) >= 360:
                lons = range(-180, 180)
            for la in range(math.floor(max(y0, -90)), math.floor(min(y1, 90)) + 1):
                for lo in lons:
                    mine.add(cell(lo, la))
        for k in mine:
            cells.setdefault(k, []).append(c)
    return cells


# --- the dump -------------------------------------------------------------------------------------

def decompressed(path: Path, sha):
    """Yield decompressed bytes of a (possibly multi-stream) .bz2, feeding the raw bytes to sha."""
    dec, fed = bz2.BZ2Decompressor(), False
    with open(path, "rb") as f:
        while raw := f.read(READ_SIZE):
            sha.update(raw)
            while raw:
                fed = True
                out = dec.decompress(raw)
                if out:
                    yield out
                if dec.eof:
                    raw = dec.unused_data
                    dec, fed = bz2.BZ2Decompressor(), False
                else:
                    raw = b""
    if fed and not dec.eof:
        raise EOFError(f"{path}: truncated bz2 stream")


def blocks(path: Path, sha):
    """Yield runs of whole notes (each ending at a </note>), then whatever trails the last one."""
    pending: list[bytes] = []
    size = 0
    for out in decompressed(path, sha):
        pending.append(out)
        size += len(out)
        if size < BLOCK_SIZE:
            continue
        buf = b"".join(pending)
        cut = buf.rfind(NOTE_END)
        if cut < 0:
            pending, size = [buf], len(buf)
            continue
        cut += len(NOTE_END)
        yield buf[:cut]
        pending, size = [buf[cut:]], len(buf) - cut
    yield b"".join(pending)


def parse_note(xml: bytes) -> dict:
    el = ET.fromstring(xml)
    comments = []
    for c in el.iter("comment"):
        item = {"action": c.get("action"), "timestamp": c.get("timestamp")}
        if c.get("uid") is not None:
            item["uid"] = int(c.get("uid"))
        item["text"] = c.text or ""
        comments.append(item)
    return {"id": int(el.get("id")), "lat": el.get("lat"), "lon": el.get("lon"),
            "created": el.get("created_at"), "comments": comments}


def clip(dump: Path, clips: list[Clip]) -> tuple[str, str, int]:
    """Fill each clip's notes (by id); returns the dump's sha256, its newest comment timestamp and its
    note count."""
    cells = grid(clips)
    sha = hashlib.sha256()
    until = b""
    total = 0
    for buf in blocks(dump, sha):
        heads = 0
        for m in NOTE_HEAD.finditer(buf):
            heads += 1
            lat, lon = float(m[2]), float(m[3])
            near = cells.get(cell(lon, lat))
            if not near:
                continue
            hits = [c for c in near if c.contains(lon, lat)]
            if not hits:
                continue
            start = m.start()
            tag_end = buf.index(b">", m.end())
            end = tag_end + 1 if buf[tag_end - 1] == ord("/") else buf.index(NOTE_END, tag_end) + len(NOTE_END)
            note = parse_note(buf[start:end])
            for c in hits:
                c.notes.append(note)
        if heads != buf.count(b"<note "):
            raise ValueError(f"{dump.name}: a <note> start tag is not in the expected attribute order")
        stamps = COMMENT_TS.findall(buf)
        if len(stamps) != buf.count(b"<comment "):
            raise ValueError(f"{dump.name}: a <comment> start tag is not in the expected attribute order")
        if stamps:
            until = max(until, max(stamps))
        total += heads
    for c in clips:
        c.notes.sort(key=lambda n: n["id"])
    return sha.hexdigest(), until.decode("ascii"), total


def write_clip(out: Path, header: dict, notes: list[dict]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for obj in (header, *notes):
            f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.replace(tmp, out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dump", type=Path, help="planet-notes-YYMMDD.osn.bz2")
    ap.add_argument("--poly", type=Path, action="append", default=[], help="osmosis .poly (repeatable)")
    ap.add_argument("--out", type=Path, action="append", default=[], help="output .jsonl, one per --poly")
    ap.add_argument("--config", type=Path, help='{"clips": [{"poly", "out", "boxes"?}, ...]}')
    a = ap.parse_args(argv)
    if len(a.poly) != len(a.out):
        ap.error("give one --out per --poly")
    clips = [Clip(p, o) for p, o in zip(a.poly, a.out)]
    if a.config:
        clips += [Clip(Path(c["poly"]), Path(c["out"]), c.get("boxes")) for c in run.read_json(a.config)["clips"]]
    if not clips:
        ap.error("nothing to clip: give --poly/--out or --config")
    outs = [c.out.resolve() for c in clips]
    if len(set(outs)) != len(outs):
        ap.error("two clips write the same --out")
    t0 = time.monotonic()
    sha, until, total = clip(a.dump, clips)
    for c in clips:
        header = {"schema": SCHEMA, "source": a.dump.name, "sha256": sha, "until": until, "bbox": list(c.bbox),
                  "poly": c.poly.name, "notes": len(c.notes)}
        if c.boxes:
            header["boxes"] = [list(b) for b in c.boxes]
        write_clip(c.out, header, c.notes)
        run.log(f"{c.out.name}: {len(c.notes)} of {total} notes, until {until}")
    run.log(f"{a.dump.name}: {len(clips)} clip(s) in {time.monotonic() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
