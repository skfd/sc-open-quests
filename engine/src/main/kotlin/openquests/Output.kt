package openquests

import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import java.math.BigDecimal
import java.math.RoundingMode

/** Everything a snapshot needs besides the counts. */
class SnapshotMeta(
    val asOf: String,
    val asOfDate: String,
    val timeZone: String,
    val extractTimestamp: String,
    val scVersion: String,
    val scCommit: String,
    val resurveyMultiplier: Double,
    /** what the area quests run on: "city" (one map data per city) or "tiles" (per z16 tile) */
    val areaUnit: String,
    val engineCommit: String?,
    val source: SourceMeta,
    /** the notes clip the run used; null when notes were not modelled */
    val notes: NotesMeta?,
    val runSeconds: Double,
)

class SourceMeta(val url: String?, val lastModified: String?, val sha256: String, val file: String)

/** [open]: notes open at asOf in the clip's region; [showAllNotes]: the app setting the note quest assumes */
class NotesMeta(val source: NotesSource, val open: Int, val showAllNotes: Boolean)

/** Status of a quest in a city, as in DATA-FORMAT.md. */
fun questStatus(q: QuestDef, city: City): String = when {
    !q.isCounted -> "unsupported"
    !q.countries.isEnabledIn(city.countryCodes) -> "not-in-region"
    else -> "counted"
}

/** Every filter quest is computed with SC's own filter and geometry code, every ported custom quest
 *  with a port checked element by element against SC's own class (tools/sc-harness
 *  CheckCustomQuests), the note quest with SC's own note filter on the notes open at asOf; see README
 *  for the remaining differences, none of which is specific to a quest. */
fun questSupport(q: QuestDef): String = if (q.isCounted) "supported" else "unsupported"

// ---- JSON text, written by hand so that key order and number format are fixed --------------------

fun jsonString(s: String?): String = if (s == null) "null" else JsonPrimitive(s).toString()

/** Fixed-point decimal without trailing zeros ("665.9", "12", "0.123"). */
fun decimal(x: Double?, scale: Int): String =
    if (x == null) "null"
    else BigDecimal(x).setScale(scale, RoundingMode.HALF_EVEN).stripTrailingZeros().toPlainString()
        .let { if (it == "-0") "0" else it }

/** Compact JSON of a parsed element with object keys in their original order. */
fun compactJson(e: JsonElement?): String = when (e) {
    null, is JsonNull -> "null"
    is JsonObject -> e.entries.joinToString(",", "{", "}") { (k, v) -> "${jsonString(k)}:${compactJson(v)}" }
    is kotlinx.serialization.json.JsonArray -> e.joinToString(",", "[", "]") { compactJson(it) }
    is JsonPrimitive -> e.toString()
}

/** docs/data/snapshots/<asOfDate>.json. Cities and quests are keyed and sorted by id/name; one
 *  quest per line, so that day-to-day diffs stay readable. */
fun snapshotJson(meta: SnapshotMeta, engine: Engine): String {
    val sb = StringBuilder()
    sb.append("{\n")
    sb.append("  \"schema\": 1,\n")
    sb.append("  \"asOf\": ${jsonString(meta.asOf)},\n")
    sb.append("  \"asOfDate\": ${jsonString(meta.asOfDate)},\n")
    sb.append("  \"timeZone\": ${jsonString(meta.timeZone)},\n")
    sb.append("  \"extractTimestamp\": ${jsonString(meta.extractTimestamp)},\n")
    sb.append("  \"scVersion\": ${jsonString(meta.scVersion)},\n")
    sb.append("  \"scCommit\": ${jsonString(meta.scCommit)},\n")
    sb.append("  \"resurveyMultiplier\": ${decimal(meta.resurveyMultiplier, 2)},\n")
    sb.append("  \"areaUnit\": ${jsonString(meta.areaUnit)},\n")
    sb.append("  \"engineCommit\": ${jsonString(meta.engineCommit)},\n")
    sb.append("  \"source\": { \"url\": ${jsonString(meta.source.url)}, \"lastModified\": ${jsonString(meta.source.lastModified)}, ")
    sb.append("\"sha256\": ${jsonString(meta.source.sha256)}, \"file\": ${jsonString(meta.source.file)} },\n")
    sb.append("  \"notes\": ")
    sb.append(meta.notes?.let { n ->
        "{ \"dump\": ${jsonString(n.source.source)}, \"sha256\": ${jsonString(n.source.sha256)}, " +
            "\"until\": ${jsonString(n.source.until.toString())}, \"open\": ${n.open}, \"showAllNotes\": ${n.showAllNotes} }"
    } ?: "null")
    sb.append(",\n")
    sb.append("  \"runSeconds\": ${decimal(meta.runSeconds, 1)},\n")
    sb.append("  \"cities\": {\n")
    val counts = engine.counts
    val cities = engine.cities.sortedBy { it.id }
    cities.forEachIndexed { ci, city ->
        val c = city.index
        sb.append("    ${jsonString(city.id)}: {\n")
        sb.append("      \"denominators\": { \"landAreaKm2\": ${decimal(city.landAreaKm2, 2)}, ")
        sb.append("\"population\": ${city.population ?: "null"}, ")
        sb.append("\"taggedNodes\": ${counts.taggedNodes[c]}, \"taggedWays\": ${counts.taggedWays[c]}, ")
        sb.append("\"highwayKm\": ${decimal(counts.highwayMm[c] / 1e6, 3)} },\n")
        sb.append("      \"quests\": {\n")
        val counted = engine.quests.indices.filter { engine.enabled[c][it] }.sortedBy { engine.quests[it].name }
        counted.forEachIndexed { k, qi ->
            sb.append("        ${jsonString(engine.quests[qi].name)}: { ")
            sb.append("\"open\": ${counts.open(c, qi)}, ")
            sb.append("\"nodes\": ${counts.get(c, qi, NODE)}, \"ways\": ${counts.get(c, qi, WAY)}, ")
            sb.append("\"relations\": ${counts.get(c, qi, RELATION)}, ")
            sb.append("\"agedOnly\": ${counts.agedOnly(c, qi)}")
            val q = engine.quests[qi]
            if (q.usesAge) {
                sb.append(", \"open05\": ${counts.get(c, qi, OPEN_05)}, \"aged05\": ${counts.get(c, qi, AGED_05)}")
                sb.append(", \"open2\": ${counts.get(c, qi, OPEN_2)}, \"aged2\": ${counts.get(c, qi, AGED_2)}")
            }
            if (q.countsNotes) sb.append(", \"openAllNotes\": ${counts.get(c, qi, ALL_NOTES)}")
            sb.append(" }")
            sb.append(if (k < counted.size - 1) ",\n" else "\n")
        }
        val parts = engine.partsOfCity[c].map { engine.parts[it] }.sortedBy { it.id }
        if (parts.isEmpty()) sb.append("      }\n")
        else {
            // DATA-FORMAT.md, "Places and parts": open at resurvey x1, quests with 0 left out
            sb.append("      },\n")
            sb.append("      \"parts\": {\n")
            parts.forEachIndexed { k, part ->
                val open = counted.filter { engine.partOpen[part.index * engine.quests.size + it] > 0 }
                sb.append("        ${jsonString(part.id)}: {")
                sb.append(open.joinToString(", ", " ", " ") {
                    "${jsonString(engine.quests[it].name)}: ${engine.partOpen[part.index * engine.quests.size + it]}"
                }.takeIf { open.isNotEmpty() } ?: "")
                sb.append("}")
                sb.append(if (k < parts.size - 1) ",\n" else "\n")
            }
            sb.append("      }\n")
        }
        sb.append(if (ci < cities.size - 1) "    },\n" else "    }\n")
    }
    sb.append("  }\n")
    sb.append("}\n")
    return sb.toString()
}

/** docs/data/quests.json: every registry entry in registry order, one per line. */
fun questsJson(registry: Registry, cities: List<City>): String {
    val sortedCities = cities.sortedBy { it.id }
    val sb = StringBuilder()
    sb.append("{\n")
    sb.append("  \"scVersion\": ${jsonString(registry.scVersion)},\n")
    sb.append("  \"scCommit\": ${jsonString(registry.scCommit)},\n")
    sb.append("  \"quests\": [\n")
    registry.quests.forEachIndexed { i, q ->
        val countries = q.enabledInCountriesJson?.takeIf { it !is JsonNull }?.let { compactJson(it) }
            ?: "{\"type\":\"AllCountries\"}" // the note quest has no enabledInCountries: shown everywhere
        sb.append("    { \"name\": ${jsonString(q.name)}, \"order\": ${q.order}, \"kind\": ${jsonString(q.kind)}, ")
        sb.append("\"support\": ${jsonString(questSupport(q))}, \"defaultDisabled\": ${q.defaultDisabled}, ")
        sb.append("\"usesAge\": ${q.usesAge}, \"enabledInCountries\": $countries, ")
        sb.append("\"wikiLink\": ${jsonString(q.wikiLink)}, ")
        sb.append("\"elementTypes\": ${q.elementTypes.joinToString(",", "[", "]") { jsonString(it) }}, ")
        sb.append("\"status\": {")
        sb.append(sortedCities.joinToString(", ", " ", " ") { "${jsonString(it.id)}: ${jsonString(questStatus(q, it))}" })
        sb.append("} }")
        sb.append(if (i < registry.quests.size - 1) ",\n" else "\n")
    }
    sb.append("  ]\n")
    sb.append("}\n")
    return sb.toString()
}
