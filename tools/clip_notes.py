"""Clip the OSM planet notes dump to a region's bounding box. Python standard library only.

  python tools/clip_notes.py <planet-notes-YYMMDD.osn.bz2> --poly <region.poly> --out <clip.jsonl>

The engine models StreetComplete's note quest and its hiding of quests at open-note positions, at any
past time, so every note in the bbox is kept, open or closed, with all its comments. The test is the
.poly file's bounding box only (inclusive), not the polygon.

Output is JSONL (UTF-8, LF). Line 1 is a header:
  {"schema":1,"source":<dump name>,"sha256":<of the dump>,"until":<newest comment timestamp in the whole
   dump>,"bbox":[minLon,minLat,maxLon,maxLat],"poly":<poly name>,"notes":<count>}
then one note per line, ascending id:
  {"id":6,"lat":"35.5170066","lon":"139.6322554","created":"...","comments":[{"action":"opened",
   "timestamp":"...","uid":378532,"text":"..."},...]}
lat/lon are the dump's attribute strings; uid is omitted when the comment is anonymous.

Speed: the dump is ~2.7 GB of XML. It is never parsed whole: regexes over big decompressed blocks find
note headers (bbox test on lat/lon) and comment timestamps (for "until"), and only notes in the bbox go
through ElementTree. Decompression is ~85% of the time (the 2026-10 dump: 83 s to decompress alone, 197 s
for a whole run on a busy machine, ~230 MB peak memory). The dump is multi-stream (pbzip2-style), so the
streams could be decompressed in parallel if this ever gets too slow; for now it stays single-threaded.
Actions seen in the dump: opened, commented, closed, reopened, hidden.
"""
from __future__ import annotations

import argparse
import bz2
import hashlib
import json
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


def poly_bbox(path: Path) -> tuple[float, float, float, float]:
    """(minLon, minLat, maxLon, maxLat) of an osmosis .poly, ignoring hole sections (names starting with !)."""
    lons, lats = [], []
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    hole = False
    for ln in lines[1:]:  # the first line is the polygon's name
        if not ln:
            continue
        if ln == "END":
            hole = False
            continue
        parts = ln.split()
        if len(parts) == 2:
            try:
                lon, lat = float(parts[0]), float(parts[1])
            except ValueError:
                pass
            else:
                if not hole:
                    lons.append(lon)
                    lats.append(lat)
                continue
        hole = ln.startswith("!")  # a section name
    if not lons:
        raise ValueError(f"{path}: no coordinates")
    return min(lons), min(lats), max(lons), max(lats)


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


def clip(dump: Path, bbox: tuple[float, float, float, float]) -> tuple[list[dict], str, str, int]:
    """Notes in bbox (by id), the dump's sha256, its newest comment timestamp and its note count."""
    min_lon, min_lat, max_lon, max_lat = bbox
    sha = hashlib.sha256()
    notes: list[dict] = []
    until = b""
    total = 0
    for buf in blocks(dump, sha):
        heads = 0
        for m in NOTE_HEAD.finditer(buf):
            heads += 1
            if not (min_lat <= float(m[2]) <= max_lat and min_lon <= float(m[3]) <= max_lon):
                continue
            start = m.start()
            tag_end = buf.index(b">", m.end())
            end = tag_end + 1 if buf[tag_end - 1] == ord("/") else buf.index(NOTE_END, tag_end) + len(NOTE_END)
            notes.append(parse_note(buf[start:end]))
        if heads != buf.count(b"<note "):
            raise ValueError(f"{dump.name}: a <note> start tag is not in the expected attribute order")
        stamps = COMMENT_TS.findall(buf)
        if len(stamps) != buf.count(b"<comment "):
            raise ValueError(f"{dump.name}: a <comment> start tag is not in the expected attribute order")
        if stamps:
            until = max(until, max(stamps))
        total += heads
    notes.sort(key=lambda n: n["id"])
    return notes, sha.hexdigest(), until.decode("ascii"), total


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
    ap.add_argument("--poly", type=Path, required=True, help="osmosis .poly; its bounding box is the clip")
    ap.add_argument("--out", type=Path, required=True, help="output .jsonl")
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    bbox = poly_bbox(a.poly)
    notes, sha, until, total = clip(a.dump, bbox)
    header = {"schema": SCHEMA, "source": a.dump.name, "sha256": sha, "until": until, "bbox": list(bbox),
              "poly": a.poly.name, "notes": len(notes)}
    write_clip(a.out, header, notes)
    run.log(f"{a.out.name}: {len(notes)} of {total} notes, until {until}, in {time.monotonic() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
