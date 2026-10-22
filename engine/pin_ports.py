"""Re-pin PORTED-QUESTS.txt against an SC checkout: rewrite every line's sha256 from the file at that tag.

    python engine/pin_ports.py --sc <SC checkout>

Run after the ports are checked against the new tag (REPIN.md): the hand ports under
src/main/kotlin/openquests/custom/, helper:OsmNoteQuest (openquests/NoteQuest.kt) and
helper:ignoreRelation (openquests/IgnoreRelation.kt). port_area_quests.py pins the generated ports
itself, so this only confirms those. Prints the names whose pin changed; a pin that changed for a
quest nobody re-checked is a mistake, not a repin.
"""
import argparse
import hashlib
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
PKG_ROOT = "app/src/commonMain/kotlin/de/westnordost/streetcomplete"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sc", required=True, type=Path, help="StreetComplete checkout at the new tag")
    args = ap.parse_args()
    pins = ENGINE / "PORTED-QUESTS.txt"
    out = []
    for line in pins.read_text(encoding="utf-8").split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            out.append(line)
            continue
        name, path, sha = line.split()
        path = path[3:] if path.startswith("cm:") else path
        text = (args.sc / PKG_ROOT / path).read_bytes().decode("utf-8").replace("\r\n", "\n")
        now = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if now != sha:
            print(f"repinned {name}")
        out.append(f"{name:<31} {path:<72} {now}")
    pins.write_text("\n".join(out), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
