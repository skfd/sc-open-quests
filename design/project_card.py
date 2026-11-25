"""Write design/project-card.svg: one 1200x630 card for the project, the whole world. An illustration; nothing reads it.

Reads the published files on sc-data (latest.json, children/world.json and the 248 country and dependency files).
Quests on by default, summed over countries and dependencies: their land outlines (the ones the world run counts in)
overlap by about 2,000 km2 in all, 1,867 of it the icefield of CL and AR (2026-11-25), so each place counts once as
far as a rounded number shows. Orange is resurvey. The bars are that sum's net change on each day after `first`.
Standard library only; the PNG beside it is a screenshot.
"""
import json
import re
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "design" / "project-card.svg"
HOST = "https://sc-data.comentality.com/"
W, H = 1200, 630
LAV, ORANGE, SOFT, INK = "#9a9aff", "#ff6600", "#cdcdff", "#141442"
# short labels for the types that may lead; a new leader stops the script rather than going unnamed
LABELS = {"AddRoadSurface": "road surfaces", "AddSidewalk": "sidewalks", "AddRoadName": "road names",
          "AddHousenumber": "house numbers", "AddPathSurface": "path surfaces", "AddCycleway": "cycleways",
          "AddTracktype": "track types", "AddPowerPolesMaterial": "power pole materials"}


def get(path, v=None):
    request = urllib.request.Request(HOST + path + (f"?v={v}" if v else ""), headers={"User-Agent": "curl/8"})
    return json.load(urllib.request.urlopen(request, timeout=60))


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def millions(n):
    return f"{n / 1e6:.1f}M"


def numbers():
    latest = get("latest.json")
    v, first, last = latest["v"], date.fromisoformat(latest["first"]), date.fromisoformat(latest["date"])
    if latest.get("questsFrom"):
        raise SystemExit(f"quests not counted from the first day, so the bars would jump: {latest['questsFrom']}")
    default = {q["name"] for q in load(ROOT / "docs" / "data" / "quests.json")["quests"] if not q["defaultDisabled"]}
    table = get("children/world.json", v)
    types, aged = Counter(), Counter()
    for place in table["places"].values():
        for i, x in place.items():
            q = table["quests"][int(i)]
            if q in default:
                types[q] += x[0]
                aged[q] += x[1]
    with ThreadPoolExecutor(8) as pool:
        files = list(pool.map(lambda i: get(f"place/{i[:2]}/{i}.json", v), table["places"]))
    days = (last - first).days + 1
    totals = [[0, 0] for _ in range(days)]
    for f in files:
        for q, points in f["quests"].items():
            if q not in default:
                continue
            points = [p for p in points if p[0] < days]     # the page's clip rule
            for n, (day, total, old) in enumerate(points):
                until = points[n + 1][0] if n + 1 < len(points) else days
                for k in range(day, until):
                    totals[k][0] += total
                    totals[k][1] += old
    if (sum(types.values()), sum(aged.values())) != tuple(totals[-1]):
        raise SystemExit(f"the table says {sum(types.values()), sum(aged.values())}, the series {totals[-1]}")
    return len(files), first, last, totals, types, aged


def t(x, y, s, size, fill="#fff", weight=400, anchor="start"):
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}">{s}</text>')


def split(x, y, total, aged, size=25):
    """A dot, a number, a word, twice, in one line of text so that no font can make them collide."""
    part = lambda colour, n, word: (f'<tspan fill="{colour}">●</tspan> <tspan font-weight="700" fill="#fff">{millions(n)}'
                                    f'</tspan> {word}')
    return t(x, y, part(LAV, total - aged, "to map") + "&#160;&#160; " + part(ORANGE, aged, "to resurvey"), size, SOFT)


def icon(name, x, y, size):
    index = load(ROOT / "docs" / "icons" / "index.json")["quests"]
    svg = (ROOT / "docs" / "icons" / index[name]["icon"]).read_text(encoding="utf-8")
    box = re.search(r'viewBox="([^"]+)"', svg).group(1)
    body = re.sub(r"(?s)^.*?<svg\b[^>]*>|</svg>\s*$", "", svg)
    return f'<svg x="{x:g}" y="{y:g}" width="{size}" height="{size}" viewBox="{box}">{body}</svg>'


def bars(totals, base, height):
    """The net change of each day after the first. From zero; a falling day stops the script, as it has no place here."""
    net = [b[0] - a[0] for a, b in zip(totals, totals[1:])]
    if min(net) < 0:
        raise SystemExit(f"a day fell, and these bars only go up: {net}")
    step = (W - 96) / len(net)
    return max(net), "".join(
        f'<rect x="{48 + k * step + 3:.1f}" y="{base - n / max(net) * height:.1f}" width="{step - 6:.1f}" '
        f'height="{n / max(net) * height:.1f}" fill="{SOFT}"/>' for k, n in enumerate(net))


def main():
    countries, first, last, totals, types, aged = numbers()
    total, old = totals[-1]
    change = total - totals[0][0]
    day = lambda d: f"{d.day} {d:%b}"
    strong = lambda s: f'<tspan font-weight="700" fill="#fff">{s}</tspan>'
    most, drawn = bars(totals, 568, 88)
    out = [drawn,
           t(48, 80, "Open StreetComplete quests", 36, weight=700),
           t(44, 206, f"{total / 1e6:.0f}M", 118, weight=800),
           t(48, 250, f"around the world on {day(last)} {last.year}", 26, SOFT),
           split(48, 306, total, old, 25),
           t(48, 350, strong(sum(k > 0 for k in types.values())) + " quest types", 25, SOFT),
           t(48, 394, strong(f"{countries}") + " countries and territories", 25, SOFT),
           t(48, 438, strong(("+" if change >= 0 else "−") + millions(abs(change))) + f" since {day(first)}", 25, SOFT)]
    top = types.most_common(6)
    for i, (q, k) in enumerate(top):
        x, y, full = 620, 40 + i * 70, 340
        w, g = k / top[0][1] * full, aged[q] / top[0][1] * full
        out += [icon(q, x, y, 54), t(x + 72, y + 21, LABELS[q], 22),
                f'<rect x="{x + 72}" y="{y + 31}" width="{w - g:.1f}" height="18" fill="{LAV}"/>'
                f'<rect x="{x + 72 + w - g:.1f}" y="{y + 31}" width="{g:.1f}" height="18" fill="{ORANGE}"/>',
                t(W - 48, y + 50, millions(k), 27, weight=700, anchor="end")]
    out += [t(48, 602, f"{day(first)}: {millions(totals[0][0])}", 24, "#fff", 700),
            t(W - 48, 602, f"{day(last)}: {millions(total)}", 24, "#fff", 700, "end"),
            t(W / 2, 602, f"net change per day, at most +{most / 1e3:.0f}k &#160;·&#160; data © OpenStreetMap contributors", 18, SOFT,
              anchor="middle")]
    OUT.write_text(f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, -apple-system, '
                   'Roboto, Helvetica, Arial, sans-serif"><defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
                   '<stop stop-color="#2b2b80"/><stop offset="1" stop-color="#141442"/></linearGradient></defs>'
                   f'<rect width="{W}" height="{H}" fill="url(#bg)"/>{"".join(out)}</svg>\n', encoding="utf-8", newline="\n")
    print(last, countries, totals[0], totals[-1], [(LABELS[q], k, aged[q]) for q, k in top])
    print("by day:", [b[0] - a[0] for a, b in zip(totals, totals[1:])])


if __name__ == "__main__":
    main()
