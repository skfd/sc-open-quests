package openquests

import de.westnordost.streetcomplete.data.elementfilter.ElementFilterExpression
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import openquests.custom.CUSTOM_QUESTS
import openquests.custom.AreaQuest
import openquests.custom.CustomQuest
import openquests.ported.AREA_QUESTS
import java.io.File

/** Where a quest is enabled, as SC's `enabledInCountries` (util/countryboundaries/Countries.kt). */
sealed interface Countries {
    /** SC: CountryBoundariesImpl.isInAny(position, countries). [regionIds] are the ids the
     *  countryboundaries data gives for a position, e.g. ["CA-ON", "CA"] in Ontario: subdivision
     *  and country are separate ids, and a code in the quest's list matches only an equal id. */
    fun isEnabledIn(regionIds: Collection<String>): Boolean

    data object All : Countries {
        override fun isEnabledIn(regionIds: Collection<String>) = true
    }
    data class AllExcept(val codes: List<String>) : Countries {
        override fun isEnabledIn(regionIds: Collection<String>) = codes.none { it in regionIds }
    }
    data class NoneExcept(val codes: List<String>) : Countries {
        override fun isEnabledIn(regionIds: Collection<String>) = codes.any { it in regionIds }
    }

    companion object {
        fun fromJson(e: JsonElement?): Countries {
            if (e == null || e is JsonNull) return All
            val o = e.jsonObject
            val codes = o["codes"]?.jsonArray?.map { it.jsonPrimitive.content }.orEmpty()
            return when (val type = o["type"]!!.jsonPrimitive.content) {
                "AllCountries" -> All
                "AllCountriesExcept" -> AllExcept(codes)
                "NoCountriesExcept" -> NoneExcept(codes)
                else -> error("unknown enabledInCountries type $type")
            }
        }
    }
}

/** Decides which elements get a quest: SC's element filter for a filter quest, the port of SC's logic
 *  for a ported custom quest (openquests.custom). */
interface QuestMatcher {
    fun includesElementType(type: ElementType): Boolean
    fun matches(element: Element): Boolean
}

private class FilterMatcher(private val filter: ElementFilterExpression) : QuestMatcher {
    override fun includesElementType(type: ElementType) = filter.includesElementType(type)
    override fun matches(element: Element) = filter.matches(element)
}

private class CustomMatcher(private val quest: CustomQuest) : QuestMatcher {
    override fun includesElementType(type: ElementType) = type in quest.elementTypes
    override fun matches(element: Element) = quest.isApplicable(element)
}

/** One entry of the registry dump (tools/sc-harness). [filter] is set for kind "filter" only, [custom]
 *  for a custom quest that has a port; [matcher] for either, and only those quests are counted. */
class QuestDef(
    val index: Int,
    val name: String,
    val order: Int,
    val kind: String,
    val elementFilter: String?,
    val custom: CustomQuest?,
    /** a ported custom quest that needs the surrounding map data; counted by AreaPass */
    val area: AreaQuest?,
    /** the note quest, counted from a notes clip (Engine.notes); false when the run has none */
    val countsNotes: Boolean,
    /** from the dump for a filter quest, from the port for a custom quest (the dump has none) */
    val usesAge: Boolean,
    val defaultDisabled: Boolean,
    val countries: Countries,
    /** as in the dump, for quests.json; null for the note quest, which has no such property */
    val enabledInCountriesJson: JsonElement?,
    val wikiLink: String?,
    /** "nodes", "ways", "relations": what the filter selects, or what the port can return */
    val elementTypes: List<String>,
) {
    val filter: ElementFilterExpression? = elementFilter?.toElementFilterExpression()
    val matcher: QuestMatcher? = filter?.let { FilterMatcher(it) } ?: custom?.let { CustomMatcher(it) }
    val isFilter get() = filter != null
    val isCounted get() = matcher != null || area != null || countsNotes
}

class Registry(val scVersion: String, val scCommit: String, val quests: List<QuestDef>) {
    val filterQuests = quests.filter { it.isFilter }
    /** filter quests, ported custom quests and (with notes) the note quest, in registry order */
    val countedQuests = quests.filter { it.isCounted }

    companion object {
        /** [withNotes]: the run has a notes clip, so the note quest is counted */
        fun load(file: File, withNotes: Boolean = false): Registry {
            val root = Json.parseToJsonElement(file.readText()).jsonObject
            val quests = root["quests"]!!.jsonArray.mapIndexed { i, q ->
                q as JsonObject
                val kind = q.str("kind")!!
                val filterString = if (kind == "filter") q.str("elementFilter") else null
                if (kind == "filter") {
                    requireNotNull(filterString) { "${q.str("name")}: kind filter without elementFilter" }
                    require(q["parsesOk"]?.jsonPrimitive?.booleanOrNull != false) { "${q.str("name")}: parsesOk=false in the dump" }
                }
                val custom = if (kind == "custom") CUSTOM_QUESTS[q.str("name")] else null
                val area = if (kind == "custom") AREA_QUESTS[q.str("name")] else null
                QuestDef(
                    index = i,
                    name = q.str("name")!!,
                    order = q["order"]!!.jsonPrimitive.int,
                    kind = kind,
                    elementFilter = filterString,
                    custom = custom,
                    area = area,
                    countsNotes = withNotes && kind == "note",
                    usesAge = custom?.usesAge ?: area?.usesAge ?: q["usesAge"]?.jsonPrimitive?.boolean ?: false,
                    defaultDisabled = q["defaultDisabled"]?.jsonPrimitive?.boolean ?: false,
                    countries = Countries.fromJson(q["enabledInCountries"]),
                    enabledInCountriesJson = q["enabledInCountries"],
                    wikiLink = q.str("wikiLink"),
                    elementTypes = custom?.elementTypes?.map { it.name.lowercase() + "s" }?.sorted()
                        ?: (q["elementTypes"] as? JsonArray)?.map { it.jsonPrimitive.content }.orEmpty(),
                )
            }
            val names = quests.map { it.name }
            require(names.toSet().size == names.size) { "duplicate quest names in ${file.path}" }
            require((CUSTOM_QUESTS.keys intersect AREA_QUESTS.keys).isEmpty()) { "quests ported twice" }
            val unknownPorts = CUSTOM_QUESTS.keys + AREA_QUESTS.keys - quests.filter { it.kind == "custom" }.map { it.name }.toSet()
            require(unknownPorts.isEmpty()) { "ported quests that are not custom quests in ${file.path}: $unknownPorts" }
            return Registry(root.str("scVersion")!!, root.str("scCommit")!!, quests)
        }
    }
}

internal fun JsonObject.str(key: String): String? =
    (this[key] as? JsonElement)?.takeIf { it !is JsonNull }?.jsonPrimitive?.content
