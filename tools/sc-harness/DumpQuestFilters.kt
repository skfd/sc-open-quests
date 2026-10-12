package de.westnordost.streetcomplete

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.elementfilter.toOverpassQLString
import de.westnordost.streetcomplete.data.osm.osmquests.OsmElementQuestType
import de.westnordost.streetcomplete.data.osm.osmquests.OsmFilterQuestType
import de.westnordost.streetcomplete.quests.note_discussion.OsmNoteQuestType
import de.westnordost.streetcomplete.quests.questTypeRegistry
import de.westnordost.streetcomplete.util.countryboundaries.AllCountries
import de.westnordost.streetcomplete.util.countryboundaries.AllCountriesExcept
import de.westnordost.streetcomplete.util.countryboundaries.Countries
import de.westnordost.streetcomplete.util.countryboundaries.NoCountriesExcept
import dev.mokkery.mock
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.add
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import java.io.File
import java.time.Instant

/** Dumps every quest type of the registry, in registry order, as JSON: name, kind, the resolved
 *  element filter in StreetComplete's own filter syntax (constants interpolated), country gating,
 *  default-disabled state etc.
 *
 *  System properties: sc.out (output file, else stdout), sc.version, sc.commit */
fun main() {
    val registry = questTypeRegistry(mock(), mock(), mock(), mock())

    val elementFilterGetter = OsmFilterQuestType::class.java
        .getDeclaredMethod("getElementFilter")
        .apply { isAccessible = true }

    val ageRegex = Regex("""\b(older|newer|today)\b""")

    val quests = buildJsonArray {
        registry.forEachIndexed { index, questType ->
            add(buildJsonObject {
                put("name", questType.name)
                put("order", index)
                put("ordinal", registry.getOrdinalOf(questType))
                val kind = when {
                    questType is OsmFilterQuestType<*> -> "filter"
                    questType is OsmElementQuestType<*> -> "custom"
                    questType === OsmNoteQuestType -> "note"
                    else -> "other"
                }
                put("kind", kind)
                put("class", questType::class.qualifiedName)

                if (questType is OsmFilterQuestType<*>) {
                    try {
                        val filterString = elementFilterGetter.invoke(questType) as String
                        put("elementFilter", filterString)
                        val keywords = ageRegex.findAll(filterString).map { it.value }.toSortedSet()
                        put("usesAge", keywords.isNotEmpty())
                        putJsonArray("ageKeywords") { keywords.forEach { add(it) } }
                        try {
                            val expr = filterString.toElementFilterExpression()
                            put("parsesOk", true)
                            putJsonArray("elementTypes") {
                                expr.elementsTypes.map { it.name.lowercase() }.sorted().forEach { add(it) }
                            }
                            put("overpassQL", runCatching { expr.toOverpassQLString() }.getOrNull())
                        } catch (e: Exception) {
                            put("parsesOk", false)
                            put("parseError", e.toString())
                        }
                    } catch (e: Throwable) {
                        put("error", (e.cause ?: e).toString())
                    }
                }

                put("defaultDisabled", questType.defaultDisabledMessage != null)
                put("visibilityEditable", questType.visibilityEditable)
                if (questType is OsmElementQuestType<*>) {
                    put("enabledInCountries", questType.enabledInCountries.toJson())
                    put("changesetComment", questType.changesetComment)
                }
                put("wikiLink", questType.wikiLink)
                putJsonArray("achievements") { questType.achievements.forEach { add(it.id) } }
            })
        }
    }

    val root = buildJsonObject {
        put("scVersion", System.getProperty("sc.version"))
        put("scCommit", System.getProperty("sc.commit"))
        put("generatedAt", Instant.now().toString())
        put("generator", "tools/sc-harness/DumpQuestFilters.kt")
        put("questCount", quests.size)
        put("quests", quests)
    }

    val json = Json { prettyPrint = true }.encodeToString(JsonElement.serializer(), root) + "\n"
    val out = System.getProperty("sc.out")
    if (out.isNullOrBlank()) {
        print(json)
    } else {
        val file = File(out)
        file.parentFile?.mkdirs()
        file.writeText(json)
        System.err.println("Wrote ${quests.size} quest types to ${file.absolutePath}")
    }
}

private fun Countries.toJson(): JsonObject = when (this) {
    is AllCountries -> buildJsonObject { put("type", "AllCountries") }
    is AllCountriesExcept -> buildJsonObject {
        put("type", "AllCountriesExcept")
        putJsonArray("codes") { exceptions.forEach { add(it) } }
    }
    is NoCountriesExcept -> buildJsonObject {
        put("type", "NoCountriesExcept")
        putJsonArray("codes") { exceptions.forEach { add(it) } }
    }
}
