"""Copy each counted quest's icon and title from a StreetComplete checkout into docs/icons/.

    python tools/sc_assets.py <sc-checkout>      # e.g. C:/Users/kk/AppData/Local/Temp/sc-v63.4

Reads the quest names from docs/data/quests.json, finds each quest's Kotlin class in the checkout,
and follows `override val icon = Res.drawable.quest_<x>` (R.drawable up to v63) to res/graphics/quest/<x>.svg and
`override val title = Res.string.<id>` to the English strings.xml. Writes docs/icons/<x>.svg,
docs/icons/index.json ({"scVersion", "quests": {name: {"icon", "title"}}}) and a copy of SC's
graphics authors.txt. The icons are CC-BY-SA 4.0 (see that file); rerun on every SC version bump.
"""
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "icons"

ICON = re.compile(r"override val icon\s*=\s*R\.drawable\.quest_(\w+)")
TITLE = re.compile(r"override val title\s*=\s*Res\.string\.(\w+)")


def strings(sc: Path) -> dict[str, str]:
    tree = ET.parse(sc / "app/src/commonMain/composeResources/values/strings.xml")
    out = {}
    for s in tree.getroot().iter("string"):
        text = "".join(s.itertext()).strip().strip('"')
        # Android escapes; placeholders become "…" since the site has no element to name
        text = text.replace("\\'", "'").replace('\\"', '"').replace("\\n", " ")
        out[s.get("name")] = re.sub(r"%(\d+\$)?s", "…", text)
    return out


def main(sc: Path) -> None:
    names = [q["name"] for q in json.loads((ROOT / "docs/data/quests.json").read_text("utf-8"))["quests"]]
    sources = {p.stem: p for p in (sc / "app/src").rglob("*.kt") if "/quests/" in p.as_posix()}
    text = strings(sc)
    version = json.loads((ROOT / "docs/data/quests.json").read_text("utf-8")).get("scVersion")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    index, missing = {}, []
    for name in names:
        src = sources.get(name)
        body = src.read_text("utf-8") if src else ""
        icon, title = ICON.search(body), TITLE.search(body)
        entry = {}
        if icon and (svg := sc / "res/graphics/quest" / f"{icon[1]}.svg").exists():
            shutil.copyfile(svg, OUT / svg.name)
            entry["icon"] = svg.name
        if title and title[1] in text:
            entry["title"] = text[title[1]]
        if len(entry) < 2:
            missing.append(f"{name}: {'no source' if not src else 'icon' if 'icon' not in entry else 'title'}")
        if entry:
            index[name] = entry
    shutil.copyfile(sc / "res/graphics/authors.txt", OUT / "authors.txt")
    (OUT / "index.json").write_text(json.dumps({"scVersion": version, "quests": index}, ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(f"{len(index)} of {len(names)} quests, {len(list(OUT.glob('*.svg')))} icons -> {OUT}")
    for m in missing:
        print("  missing", m)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
