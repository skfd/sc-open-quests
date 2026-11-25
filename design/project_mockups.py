"""Write design/project-mockups.html: three mockups of a general card, 1200x630 each, as inline SVG. Real numbers.

Writes text only: whoever opens the page draws it. Standard library, but for Pillow imported by project_image.
"""
import json
import math
import re
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path

import project_image as P

OUT = P.ROOT / "design" / "project-mockups.html"
W, H = 1200, 630
LAV, ORANGE, GOLD, SOFT, INK = "#9a9aff", "#ff6600", "#ffd666", "#cdcdff", "#141442"
LABELS = {**P.LABELS, "CheckShopExistence": "shops still there?", "AddCycleway": "cycleways",
          "AddTactilePavingCrosswalk": "tactile paving"}


def numbers():
    cities, dates, totals, _ = P.city_numbers()
    defaults = {q["name"] for q in P.load(P.DATA / "quests.json")["quests"] if not q["defaultDisabled"]}
    types, aged = Counter(), Counter()
    for cid in cities:
        h = P.load(P.DATA / "history" / f"{cid}.json")
        i = h["dates"].index(dates[-1])
        for n, v in h["quests"].items():
            if n in defaults:
                types[n] += v["open"][i]
                aged[n] += v["agedOnly"][i]
    assert (sum(types.values()), sum(aged.values())) == totals[-1]
    return cities, dates, totals, types, aged


def t(x, y, s, size, fill="#fff", weight=400, anchor="start"):
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}">{s}</text>')


def split(x, y, total, aged, size=25):
    """A dot, a number, a word, twice, in one line of text so that no font can make them collide."""
    part = lambda colour, n, word: (f'<tspan fill="{colour}">●</tspan> <tspan font-weight="700" fill="#fff">{P.millions(n)}'
                                    f'</tspan> {word}')
    return t(x, y, part(LAV, total - aged, "to map") + "&#160;&#160; " + part(ORANGE, aged, "to resurvey"), size, SOFT)


def icon(name, x, y, size):
    index = P.load(P.ROOT / "docs" / "icons" / "index.json")["quests"]
    svg = (P.ROOT / "docs" / "icons" / index[name]["icon"]).read_text(encoding="utf-8")
    box = re.search(r'viewBox="([^"]+)"', svg).group(1)
    body = re.sub(r"(?s)^.*?<svg\b[^>]*>|</svg>\s*$", "", svg)
    return f'<svg x="{x:g}" y="{y:g}" width="{size}" height="{size}" viewBox="{box}">{body}</svg>'


def hills(dates, totals, height):
    first, last = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
    top = max(a for a, _ in totals)
    xs = [(date.fromisoformat(s) - first).days / (last - first).days * W for s in dates]
    up = [f"{x:.0f},{H - a / top * height:.1f}" for x, (a, _) in zip(xs, totals)]
    low = [f"{x:.0f},{H - (a - g) / top * height:.1f}" for x, (a, g) in zip(xs, totals)]
    return (f'<polygon fill="{ORANGE}" points="{" ".join(up + low[::-1])}"/>'
            f'<polygon fill="{LAV}" points="{" ".join(low)} {W},{H} 0,{H}"/>')


def world(cities, step=4.6):
    cells, points, n = P.places(step)
    if missing := sorted(set(cities) - set(points)):
        raise SystemExit(f"no point for {missing}")
    print(f"{n:,} places, {len(cells):,} dots, {len(points)} cities with a point")
    most, buckets = math.log1p(max(cells.values())), {}
    for (col, row), k in cells.items():
        buckets.setdefault(min(4, int(math.log1p(k) / most * 5)), []).append(
            f"M{(col + (row % 2) / 2) * step:.0f} {row * step * 0.866:.0f}h0")
    out = [f'<path d="{"".join(p)}" stroke="{SOFT}" stroke-opacity="{0.18 + 0.1 * b:.2f}" stroke-width="{1.6 + 0.5 * b:.1f}" '
           'stroke-linecap="round" fill="none"/>' for b, p in sorted(buckets.items())]
    biggest = max(c["open"] for c in cities.values())
    for c in sorted(cities.values(), key=lambda c: -c["open"]):
        x, y = P.xy(*points[c["id"]])
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{1.9 + 4.6 * math.sqrt(c["open"] / biggest):.1f}" '
                   f'fill="{GOLD}" stroke="#2b2b80" stroke-width="1"/>')
    return "".join(out)


def card(n, body):
    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, -apple-system, Roboto, '
            f'Helvetica, Arial, sans-serif"><defs><linearGradient id="bg{n}" x1="0" y1="0" x2="0" y2="1"><stop stop-color='
            f'"#2b2b80"/><stop offset="1" stop-color="#141442"/></linearGradient></defs>'
            f'<rect width="{W}" height="{H}" fill="url(#bg{n})"/>{body}</svg>')


def main():
    cities, dates, totals, types, aged = numbers()
    total, old = totals[-1]
    first, last = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
    big, when = f"{total / 1e6:.1f}M", f"{last.day} {last:%b %Y}"
    shown = sum(k > 0 for k in types.values())
    where = f"in {len(cities)} cities on {when}"
    name = "Open StreetComplete quests"

    a = [world(cities), t(48, 74, "Open StreetComplete", 34, weight=700), t(48, 114, "quests", 34, weight=700),
         t(44, 222, big, 112, weight=800), t(48, 262, where, 25, SOFT), split(48, 317, total, old, 23),
         t(48, 364, f'<tspan font-weight="700" fill="#fff">{shown}</tspan> quest types', 25, SOFT),
         t(500, 362, "Most open", 22, SOFT)]
    for i, (q, k) in enumerate(types.most_common(3)):
        x = 500 + i * 228
        a += [icon(q, x, 380, 54), t(x + 66, 406, P.millions(k, 2), 29, weight=700), t(x + 66, 432, LABELS[q], 21, SOFT)]
    a += [hills(dates, totals, P.HILLS), t(48, 606, f"{first:%b %Y}: {P.millions(totals[0][0])}", 25, INK, 700),
          t(W - 48, 606, f"{last:%b %Y}: {big}", 25, INK, 700, "end")]

    b = [hills(dates, totals, 330), t(48, 78, name, 38, weight=700), t(44, 216, big, 124, weight=800),
         t(48, 262, where, 26, SOFT), split(620, 108, total, old, 28),
         t(620, 158, f'<tspan font-weight="700" fill="#fff">{shown}</tspan> quest types', 28, SOFT),
         t(620, 208, f'<tspan font-weight="700" fill="#fff">{P.millions(total - totals[0][0])}</tspan> more than in '
                     f"{first:%b %Y}", 28, SOFT),
         t(48, 598, f"{first:%b %Y}: {P.millions(totals[0][0])}", 28, INK, 700),
         t(W - 48, 598, f"{last:%b %Y}: {big}", 28, INK, 700, "end")]

    c = [t(48, 78, name, 38, weight=700), t(44, 240, big, 124, weight=800), t(48, 286, where, 26, SOFT),
         split(48, 360, total, old, 23), t(48, 412, f'<tspan font-weight="700" fill="#fff">{shown}</tspan> quest types', 25, SOFT),
         t(48, 590, "counted from OpenStreetMap", 22, SOFT)]
    top6 = types.most_common(6)
    for i, (q, k) in enumerate(top6):
        y, x, full = 118 + i * 82, 560, 330
        w, g = k / top6[0][1] * full, aged[q] / top6[0][1] * full
        c += [icon(q, x, y, 60), t(x + 78, y + 24, LABELS[q], 23),
              f'<rect x="{x + 78}" y="{y + 34}" width="{w - g:.1f}" height="20" fill="{LAV}"/>'
              f'<rect x="{x + 78 + w - g:.1f}" y="{y + 34}" width="{g:.1f}" height="20" fill="{ORANGE}"/>',
              t(W - 48, y + 53, P.millions(k, 2), 27, weight=700, anchor="end")]

    titles = ["A. World", "B. Over time", "C. Quest types"]
    page = "".join(f"<h2>{escape(h)}</h2>{card(i, ''.join(body))}" for i, (h, body) in enumerate(zip(titles, (a, b, c))))
    OUT.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, '
                   'initial-scale=1"><title>Project card mockups</title><style>body{margin:12px;background:#f2f2f4;color:#111;'
                   'font-family:system-ui,sans-serif}h2{font-size:16px;margin:18px 0 6px}svg{max-width:100%}body>svg{display:'
                   f'block;width:100%;max-width:900px;height:auto;border-radius:8px}}</style>{page}</html>\n',
                   encoding="utf-8", newline="\n")
    print(OUT, OUT.stat().st_size, [(LABELS[q], k, aged[q]) for q, k in top6])


if __name__ == "__main__":
    main()
