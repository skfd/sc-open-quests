"""Generate engine ports of StreetComplete custom quests that need the surrounding map data.

SC keeps its quest classes in androidMain next to their Android forms, so they cannot be vendored as
they are. This script copies a quest's source and keeps only what decides where it applies:

- the imports (minus Android, resources, achievements and the quest-type interfaces),
- everything outside the class (top-level filters and helper functions), verbatim,
- inside the class, every member that is not an override (private filters and helpers), plus
  `override fun getApplicableElements(mapData: MapDataWithGeometry)`, verbatim.

The class becomes `object <Name> : AreaQuest` in SC's own package, so references to helpers in the
same package resolve unchanged. A `getFeature` constructor parameter becomes SC's feature dictionary
as the app wires it (`openquests.custom.ScFeatures`). Any other constructor parameter used by the kept
code is an error.

The output goes to src/main/kotlin/ported/<package path>/<Name>.kt and the quest's upstream file is
pinned in PORTED-QUESTS.txt (sha256 of its LF text), which sync-sc.ps1 checks. When a pinned file
changes at a new SC tag, rerun this script for that quest and recheck it with the oracle
(tools/sc-harness CheckCustomQuests).

    python engine/port_area_quests.py --sc <SC checkout> AddCrossing AddKerbHeight ...
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
PKG_ROOT = "app/src/androidMain/kotlin/de/westnordost/streetcomplete"

DROP_IMPORTS = [
    r"\.R$",
    r"\.resources\.",
    r"\.data\.user\.achievements\.",
    r"\.data\.quest\.AndroidQuest$",
    r"\.data\.osm\.osmquests\.OsmElementQuestType$",
    r"\.screens\.",
    r"^org\.jetbrains\.compose\.",
    r"\.view\.",
    r"\.ui\.",
]

# androidMain files of quest packages that hold only helpers used by the ported quests; copied whole
HELPERS = [
    "quests/ferry/FerryUtils.kt",
    "quests/level/LevelUtils.kt",
    "quests/summit/SummitMarkingsUtil.kt",
    "quests/max_height/MaxHeightUtils.kt",
]

AGE = re.compile(r"\b(older|newer|today)\b|TagOlderThan|RelativeDate")


def lf(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def find_quest_file(sc: Path, name: str) -> Path:
    hits = [p for p in (sc / PKG_ROOT / "quests").rglob(f"{name}.kt")
            if re.search(rf"^class {name}\b", lf(p), re.M)]
    if len(hits) != 1:
        sys.exit(f"{name}: expected one androidMain file declaring class {name}, found {hits}")
    return hits[0]


def declared_in_common_main(sc: Path, target: str) -> bool:
    """False for an import from a quests package whose class is not in commonMain, i.e. an answer
    or form type that lives in androidMain with the quest and is only used by the dropped members."""
    parts = target.split(".")
    if "quests" not in parts:
        return True
    i = next((k for k, p in enumerate(parts) if p[:1].isupper()), None)
    if i is None:
        return True  # a top-level function or value; let the compiler judge
    folder = sc / "app/src/commonMain/kotlin" / "/".join(parts[:i])
    decl = re.compile(rf"\b(class|object|interface|typealias)\s+{parts[i]}\b")
    return folder.is_dir() and any(decl.search(lf(p)) for p in folder.glob("*.kt"))


def matching_brace(text: str, open_idx: int) -> int:
    """Index of the brace closing the one at open_idx, skipping strings, chars and comments."""
    depth, i, n = 0, open_idx, len(text)
    while i < n:
        if text.startswith('"""', i):
            j = text.index('"""', i + 3)
            # a raw string may contain ${...} templates with braces; they balance, so skip them whole
            i = j + 3
            continue
        c = text[i]
        if c == '"':
            i += 1
            while text[i] != '"':
                i += 2 if text[i] == "\\" else 1
            i += 1
            continue
        if c == "'" and text[i + 1:i + 2] != "'":
            j = i + 1
            while text[j] != "'":
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            continue
        if text.startswith("//", i):
            i = text.index("\n", i)
            continue
        if text.startswith("/*", i):
            i = text.index("*/", i) + 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("unbalanced braces")


def split_members(body: str) -> list[tuple[str, str]]:
    """Split a class body (text between the braces) into (kind, text) chunks. A member starts at a
    line indented by exactly 4 spaces that does not close something; comment lines go with the
    member after them."""
    lines = body.split("\n")
    chunks: list[list[str]] = []
    pending: list[str] = []      # comment lines at member level, waiting for their member
    in_comment = False           # inside a member-level /* ... */ block
    for line in lines:
        stripped = line.strip()
        indent4 = line.startswith("    ") and not line.startswith("     ")
        if in_comment:
            pending.append(line)
            in_comment = "*/" not in stripped
            continue
        if indent4 and stripped.startswith("//"):
            pending.append(line)
            continue
        if indent4 and stripped.startswith("/*"):
            pending.append(line)
            in_comment = "*/" not in stripped
            continue
        if not stripped and pending:
            pending.append(line)
            continue
        is_start = (indent4 and stripped
                    and not stripped.startswith(("}", ")", "]", '"""', ".", "&&", "||", "+")))
        if is_start:
            chunks.append(pending + [line])
            pending = []
        elif chunks:
            chunks[-1].append(line)
    out = []
    for c in chunks:
        first = next(l for l in c if l.strip() and not l.strip().startswith(("//", "/*", "*")))
        out.append((first.strip(), "\n".join(c).rstrip()))
    return out


def port(sc: Path, name: str) -> tuple[Path, str, str]:
    src_path = find_quest_file(sc, name)
    text = lf(src_path)
    package = re.search(r"^package ([\w.]+)$", text, re.M).group(1)

    m = re.search(rf"^class {name}\b", text, re.M)
    if not m:
        sys.exit(f"{name}: no class header")
    class_start = m.start()
    i = m.end()
    while text[i].isspace():
        i += 1
    params_text = ""
    if text[i] == "(":
        depth, j = 0, i
        while True:
            depth += {"(": 1, ")": -1}.get(text[j], 0)
            if depth == 0:
                break
            j += 1
        params_text, i = text[i + 1:j], j + 1
    open_idx = text.index("{", i)
    close_idx = matching_brace(text, open_idx)
    param_names = re.findall(r"\bval (\w+)\s*:", params_text)

    head, body, tail = text[:class_start], text[open_idx + 1:close_idx], text[close_idx + 1:]
    imports = [l for l in head.split("\n") if l.startswith("import ")]
    imports = [l for l in imports if not any(re.search(p, l[len("import "):]) for p in DROP_IMPORTS)]
    imports = [l for l in imports if declared_in_common_main(sc, l[len("import "):])]
    between = "\n".join(l for l in head.split("\n")[1:] if not l.startswith("import ")).strip()

    kept = []
    overrides = {}
    for first, chunk in split_members(body):
        if first.startswith("override fun getApplicableElements("):
            kept.append(chunk)
        elif first.startswith("override "):
            m2 = re.match(r"override (?:fun|val) (\w+)", first)
            if m2:
                overrides[m2.group(1)] = chunk
        elif first.startswith("companion object"):
            continue
        else:
            kept.append(chunk)
    if not any("override fun getApplicableElements(" in k for k in kept):
        sys.exit(f"{name}: no getApplicableElements found")
    # an override the kept code calls (e.g. getApplicableElements = filter { isApplicableTo(it) }) stays,
    # as a plain member
    for member, chunk in overrides.items():
        if member != "getApplicableElements" and re.search(rf"\b{member}\b", "\n".join(kept) + tail):
            kept.append(chunk.replace(f"override fun {member}", f"fun {member}", 1)
                        .replace(f"override val {member}", f"val {member}", 1))

    kept_text = "\n\n".join(kept) + "\n" + tail + "\n" + between
    # drop imports that only the dropped members used
    def used(imp: str) -> bool:
        leaf = imp.rsplit(".", 1)[1]
        return leaf == "*" or re.search(rf"\b{re.escape(leaf)}\b", kept_text) is not None
    imports = [l for l in imports if used(l[len("import "):])]
    feature_line = ""
    for p in param_names:
        if not re.search(rf"\b{p}\b", kept_text):
            continue
        if p == "getFeature":
            feature_line = ("    private val getFeature: (Element) -> Feature? = ScFeatures::getFeature\n\n")
            imports += ["import de.westnordost.osmfeatures.Feature",
                        "import de.westnordost.streetcomplete.data.osm.mapdata.Element"]
        else:
            sys.exit(f"{name}: kept code uses constructor parameter {p}")
    imports += ["import openquests.custom.AreaQuest"]
    if feature_line:
        imports += ["import openquests.custom.ScFeatures"]
    imports = sorted(set(imports))

    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    rel = src_path.relative_to(sc / PKG_ROOT).as_posix()
    uses_age = bool(AGE.search(kept_text))
    out = (
        f"// GENERATED by engine/port_area_quests.py from StreetComplete {PKG_ROOT}/{rel}\n"
        f"// (sha256 of its LF text {sha}, pinned in engine/PORTED-QUESTS.txt). Do not edit: rerun the script.\n"
        f"// Kept verbatim: the filters, helpers and getApplicableElements(); dropped: the Android UI and\n"
        f"// answer members. StreetComplete is GPL-3.0.\n"
        f"package {package}\n\n"
        + "\n".join(imports) + "\n\n"
        + (between + "\n\n" if between else "")
        + f"object {name} : AreaQuest {{\n"
        f"    override val name = \"{name}\"\n"
        f"    override val usesAge = {'true' if uses_age else 'false'}\n\n"
        + feature_line
        + "\n\n".join(kept) + "\n}\n"
        + tail.rstrip() + ("\n" if tail.strip() else "")
    )
    target = ENGINE / "src/main/kotlin/ported" / package.replace(".", "/") / f"{name}.kt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(out, encoding="utf-8", newline="\n")
    return target, rel, sha


def copy_helper(sc: Path, rel: str) -> tuple[str, str]:
    """An androidMain helper file of a quest package, copied whole with a header."""
    text = lf(sc / PKG_ROOT / rel)
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    package = re.search(r"^package ([\w.]+)$", text, re.M).group(1)
    target = ENGINE / "src/main/kotlin/ported" / package.replace(".", "/") / Path(rel).name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"// COPIED by engine/port_area_quests.py from StreetComplete {PKG_ROOT}/{rel}\n"
        f"// (sha256 of its LF text {sha}, pinned in engine/PORTED-QUESTS.txt), unchanged below this header.\n"
        + text, encoding="utf-8", newline="\n")
    return rel, sha


def update_pins(entries: dict[str, tuple[str, str]]) -> None:
    pins = ENGINE / "PORTED-QUESTS.txt"
    lines = pins.read_text(encoding="utf-8").split("\n")
    seen = set()
    out = []
    for l in lines:
        parts = l.split()
        if parts and not l.startswith("#") and parts[0] in entries:
            rel, sha = entries[parts[0]]
            out.append(f"{parts[0]:<31} {rel:<72} {sha}")
            seen.add(parts[0])
        else:
            out.append(l)
    while out and not out[-1].strip():
        out.pop()
    for n, (rel, sha) in entries.items():
        if n not in seen:
            out.append(f"{n:<31} {rel:<72} {sha}")
    pins.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sc", required=True, type=Path, help="StreetComplete checkout at the pinned tag")
    ap.add_argument("quests", nargs="+")
    args = ap.parse_args()
    entries = {}
    for name in args.quests:
        target, rel, sha = port(args.sc, name)
        entries[name] = (rel, sha)
        print(f"{name}: {target.relative_to(ENGINE)}")
    for rel in HELPERS:
        entries["helper:" + Path(rel).stem] = copy_helper(args.sc, rel)
    update_pins(entries)
    write_registry()


def write_registry() -> None:
    """src/main/kotlin/ported/AreaQuests.kt: every generated port, by name."""
    root = ENGINE / "src/main/kotlin/ported"
    ports = []
    for f in sorted(root.rglob("*.kt")):
        m = re.search(r"^package ([\w.]+)$", f.read_text(encoding="utf-8"), re.M)
        o = re.search(r"^object (\w+) : AreaQuest", f.read_text(encoding="utf-8"), re.M)
        if m and o:
            ports.append(f"{m.group(1)}.{o.group(1)}")
    body = "".join(f"    {p},\n" for p in sorted(ports, key=lambda p: p.rsplit('.', 1)[1]))
    (root / "AreaQuests.kt").write_text(
        "// GENERATED by engine/port_area_quests.py: every quest port under src/main/kotlin/ported/.\n"
        "package openquests.ported\n\n"
        "import openquests.custom.AreaQuest\n\n"
        "/** Ported custom quests that need the surrounding map data, by name. */\n"
        "val AREA_QUESTS: Map<String, AreaQuest> = listOf<AreaQuest>(\n" + body + ").associateBy { it.name }\n",
        encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
