"""Draw design/project-image.png: one picture of the project, from its own data. An illustration; nothing reads it.

- The faint dots: the name layer (docs/places), localities and smaller, by the middle of each place's box.
- The bright dots: the counted cities, larger with more open quests.
- The numbers: quests on by default, summed over the counted cities on the last date all of them have.
- The hills: the same sum on every date all of them have, from zero; orange is resurvey.

Needs Pillow. No browser. Run it in a gap of the world loop (it reads about 100 MB of docs/places).
"""
import glob
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
OUT = ROOT / "design" / "project-image.png"
S = 2                       # pixels per unit; the layout below is 1200x630 units
W, H = 1200, 630
TOP, BOTTOM = (43, 43, 128), (20, 20, 66)
LAVENDER, ORANGE, INK, WHITE = (154, 154, 255), (255, 102, 0), (20, 20, 66), (255, 255, 255)
SOFT, GOLD = (205, 205, 255), (255, 214, 102)
# short labels for the types that may lead; a new leader stops the script rather than going unnamed
LABELS = {"AddPathSurface": "path surfaces", "AddHousenumber": "house numbers", "AddRoadSurface": "road surfaces",
          "AddOpeningHours": "opening hours", "AddSidewalk": "sidewalks"}
MAP_X, MAP_Y, MAP_W = 480, 34, 690
LON0, LAT0, PER_DEG = -170.0, 80.0, MAP_W / 360
HILLS = 128


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def xy(lon, lat):
    return MAP_X + ((lon - LON0) % 360) * PER_DEG, MAP_Y + (LAT0 - lat) * PER_DEG


def font(size, bold=False):
    return ImageFont.truetype("segoeuib.ttf" if bold else "segoeui.ttf", round(size * S))


def millions(n, places=1):
    return f"{n / 1e6:.{places}f}M"


def places(step):
    """How many places fall in each cell of a hexagonal grid, and the middle of every counted city's outline box."""
    cells, cities, n = Counter(), {}, 0
    for feature in load(DATA / "coverage.json")["features"]:
        g = feature["geometry"]
        polygons = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        ring = [point for polygon in polygons for point in polygon[0]]
        lons, lats = [point[0] for point in ring], [point[1] for point in ring]
        cities[feature["id"]] = ((min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2)
    for f in glob.glob(str(ROOT / "docs" / "places" / "*" / "*.json")):
        for p in load(f)["places"]:
            lon, lat = (p[4] + p[6]) / 2, (p[5] + p[7]) / 2
            if p[2] < 5 or lat < -56:
                continue
            x, y = xy(lon, lat)
            row = round(y / (step * 0.866))
            cells[round(x / step - (row % 2) / 2), row] += 1
            n += 1
    return cells, cities, n


def city_numbers():
    cities = {c["id"]: c for c in load(DATA / "cities.json")["cities"]}
    quests = [q["name"] for q in load(DATA / "quests.json")["quests"] if not q["defaultDisabled"]]
    hist = {cid: load(DATA / "history" / f"{cid}.json") for cid in cities}
    dates = sorted(set.intersection(*(set(h["dates"]) for h in hist.values())))
    totals, types = [], Counter()
    for d in dates:
        total = aged = 0
        for h in hist.values():
            i = h["dates"].index(d)
            for n in quests:
                v = h["quests"].get(n)
                if v is None:
                    continue
                if v["open"][i] is None or v["agedOnly"][i] is None:
                    raise SystemExit(f"{n} is not counted on {d}: the sum would be short")
                total += v["open"][i]
                aged += v["agedOnly"][i]
                if d == dates[-1]:
                    types[n] += v["open"][i]
        totals.append((total, aged))
    return cities, dates, totals, types


def main():
    cities, dates, totals, types = city_numbers()
    total, aged = totals[-1]
    shown = sum(k > 0 for k in types.values())
    print(len(dates), "dates", dates[0], totals[0], "...", dates[-1], totals[-1], "types", shown, types.most_common(3))
    img = Image.new("RGB", (W * S, H * S))
    d = ImageDraw.Draw(img)
    for y in range(H * S):
        t = y / (H * S)
        d.line([(0, y), (W * S, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM)))

    def text(x, y, s, size, fill=WHITE, bold=False, anchor="ls"):
        d.text((x * S, y * S), s, font=font(size, bold), fill=fill, anchor=anchor)

    def dot(x, y, r, fill):
        d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=fill)

    # the world: places faint, counted cities bright
    step = 4.6
    cells, points, n = places(step)
    print(f"{n:,} places in {len(cells):,} dots; {len(points)} of {len(cities)} cities have a point")
    if missing := sorted(set(cities) - set(points)):
        raise SystemExit(f"no point for {missing}")
    most = math.log1p(max(cells.values()))
    for (col, row), k in cells.items():
        t = math.log1p(k) / most
        fill = tuple(round(a + (b - a) * (0.15 + 0.45 * t)) for a, b in zip(TOP, SOFT))
        dot((col + (row % 2) / 2) * step, row * step * 0.866, 0.7 + 1.1 * t, fill)
    biggest = max(c["open"] for c in cities.values())
    for c in sorted(cities.values(), key=lambda c: -c["open"]):
        x, y = xy(*points[c["id"]])
        r = 1.9 + 4.6 * math.sqrt(c["open"] / biggest)
        dot(x, y, r + 0.7, TOP)
        dot(x, y, r, GOLD)

    # left: the headline and its split
    last = date.fromisoformat(dates[-1])
    icon = Image.open(ROOT / "docs" / "icons" / "png" / "housenumber.png")  # opened early: a missing folder fails here
    icon.close()
    text(48, 74, "Open StreetComplete", 34, bold=True)
    text(48, 114, "quests", 34, bold=True)
    text(44, 222, f"{total / 1e6:.1f}M", 112, bold=True)
    text(48, 262, f"in {len(cities)} cities on {last.day} {last:%b %Y}", 25, SOFT)
    dot(56, 308, 8, LAVENDER)
    text(74, 317, millions(total - aged), 27, bold=True)
    text(150, 317, "to map", 25, SOFT)
    dot(264, 308, 8, ORANGE)
    text(282, 317, millions(aged), 27, bold=True)
    text(346, 317, "to resurvey", 25, SOFT)
    text(48, 364, str(shown), 27, bold=True)
    text(104, 364, "quest types", 25, SOFT)

    # right, under the map: the largest types
    quest_icons = load(ROOT / "docs" / "icons" / "index.json")["quests"]
    text(MAP_X + 20, 362, "Most open", 22, SOFT)
    for i, (name, k) in enumerate(types.most_common(3)):
        x = MAP_X + 20 + i * 228
        png = ROOT / "docs" / "icons" / "png" / quest_icons[name]["icon"].replace(".svg", ".png")
        with Image.open(png) as im:
            im = im.convert("RGBA").resize((54 * S, 54 * S), Image.LANCZOS)
        img.paste(im, (x * S, 380 * S), im)
        text(x + 66, 406, millions(k, 2), 29, bold=True)
        text(x + 66, 432, LABELS[name], 21, SOFT)

    # hills: stacked, from zero, over the full width
    first = date.fromisoformat(dates[0])
    xs = [(date.fromisoformat(s) - first).days / (last - first).days * W for s in dates]
    top = max(t for t, _ in totals)
    up = [(x * S, (H - t / top * HILLS) * S) for x, (t, _) in zip(xs, totals)]
    low = [(x * S, (H - (t - a) / top * HILLS) * S) for x, (t, a) in zip(xs, totals)]
    d.polygon(up + low[::-1], fill=ORANGE)
    d.polygon(low + [(W * S, H * S), (0, H * S)], fill=LAVENDER)
    text(48, 606, f"{first:%b %Y}: {millions(totals[0][0])}", 25, INK, True)
    text(W - 48, 606, f"{last:%b %Y}: {millions(total)}", 25, INK, True, "rs")
    text(W / 2, 606, "counted from OpenStreetMap", 20, INK, anchor="ms")

    img.save(OUT, optimize=True)
    img.resize((400, 210), Image.LANCZOS).save(ROOT / ".scratch" / "project-image-thumb.png")
    print(OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()
