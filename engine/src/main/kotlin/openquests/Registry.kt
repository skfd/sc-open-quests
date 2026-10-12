package openquests

import de.westnordost.streetcomplete.data.elementfilter.ElementFilterExpression
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
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

/** One entry of the registry dump (tools/sc-harness). [filter] is set for kind "filter" only. */
class QuestDef(
    val index: Int,
    val name: String,
    val order: Int,
    val kind: String,
    val elementFilter: String?,
    val usesAge: Boolean,
    val defaultDisabled: Boolean,
    val countries: Countries,
    /** as in the dump, for quests.json; null for the note quest, which has no such property */
    val enabledInCountriesJson: JsonElement?,
    val wikiLink: String?,
    val elementTypes: List<String>,
) {
    val filter: ElementFilterExpression? = elementFilter?.toElementFilterExpression()
    val isFilter get() = filter != null
}

class Registry(val scVersion: String, val scCommit: String, val quests: List<QuestDef>) {
    val filterQuests = quests.filter { it.isFilter }

    companion object {
        fun load(file: File): Registry {
            val root = Json.parseToJsonElement(file.readText()).jsonObject
            val quests = root["quests"]!!.jsonArray.mapIndexed { i, q ->
                q as JsonObject
                val kind = q.str("kind")!!
                val filterString = if (kind == "filter") q.str("elementFilter") else null
                if (kind == "filter") {
                    requireNotNull(filterString) { "${q.str("name")}: kind filter without elementFilter" }
                    require(q["parsesOk"]?.jsonPrimitive?.booleanOrNull != false) { "${q.str("name")}: parsesOk=false in the dump" }
                }
                QuestDef(
                    index = i,
                    name = q.str("name")!!,
                    order = q["order"]!!.jsonPrimitive.int,
                    kind = kind,
                    elementFilter = filterString,
                    usesAge = q["usesAge"]?.jsonPrimitive?.boolean ?: false,
                    defaultDisabled = q["defaultDisabled"]?.jsonPrimitive?.boolean ?: false,
                    countries = Countries.fromJson(q["enabledInCountries"]),
                    enabledInCountriesJson = q["enabledInCountries"],
                    wikiLink = q.str("wikiLink"),
                    elementTypes = (q["elementTypes"] as? JsonArray)?.map { it.jsonPrimitive.content }.orEmpty(),
                )
            }
            val names = quests.map { it.name }
            require(names.toSet().size == names.size) { "duplicate quest names in ${file.path}" }
            return Registry(root.str("scVersion")!!, root.str("scCommit")!!, quests)
        }
    }
}

internal fun JsonObject.str(key: String): String? =
    (this[key] as? JsonElement)?.takeIf { it !is JsonNull }?.jsonPrimitive?.content
