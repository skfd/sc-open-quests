package de.westnordost.streetcomplete

import de.westnordost.streetcomplete.data.osm.geometry.ElementPointGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.MutableMapDataWithGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Relation
import de.westnordost.streetcomplete.data.osm.mapdata.RelationMember
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import de.westnordost.streetcomplete.data.osm.osmquests.OsmElementQuestType
import de.westnordost.osmfeatures.FeatureDictionary
import de.westnordost.streetcomplete.quests.questTypeRegistry
import de.westnordost.streetcomplete.util.ktx.getFeature
import kotlinx.io.files.SystemFileSystem
import dev.mokkery.mock
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.double
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import java.io.File
import kotlin.system.exitProcess

/** Oracle for ported custom quests: runs StreetComplete's real getApplicableElements() of the given
 *  quest types over a set of OSM elements and lists which elements each one applies to.
 *
 *  System properties:
 *  - sc.in     JSON lines, one element per line:
 *              {"type":"node"|"way"|"relation","id":1,"version":4,"timestamp":<epoch ms>,
 *               "tags":{...},"lat":43.6,"lon":-79.4, "nodes":[...], "members":[{"type":"way","ref":1,"role":"outer"}]}
 *              lat/lon is the element's quest position; nodes/members are optional.
 *  - sc.quests comma-separated quest type names, e.g. AddSidewalk,AddOpeningHours
 *  - sc.out    TSV output (quest, type, id), sorted; else stdout
 *  - sc.presets SC's osmfeatures preset directory (default: the checkout's composeResources). The
 *              quests that take getFeature get the app's own: FeatureDictionary over SC's presets,
 *              queried in the JVM's default locale (the task pins en-CA, as the engine does). */
fun main() {
    val inPath = System.getProperty("sc.in")?.takeIf { it.isNotBlank() }
        ?: fail("sc.in (-PcheckIn) is required")
    val questNames = System.getProperty("sc.quests").orEmpty()
        .split(',').map { it.trim() }.filter { it.isNotEmpty() }
    if (questNames.isEmpty()) fail("sc.quests (-PcheckQuests) is required")

    // resolve quest names before reading a possibly huge input
    // getFeature as the app wires it (AndroidModule2): { featureDictionaryLazy.value.getFeature(it) }
    val presets = System.getProperty("sc.presets")?.takeIf { it.isNotBlank() }
        ?: "src/commonMain/composeResources/files/osmfeatures/default"
    val brands = File(presets).resolveSibling("brands").path
    val featureDictionary by lazy {
        System.err.println("feature dictionary: $presets (+ $brands), locale ${java.util.Locale.getDefault().toLanguageTag()}")
        FeatureDictionary.create(SystemFileSystem, presets, brands)
    }
    val registry = questTypeRegistry(mock(), mock(), mock(), { featureDictionary.getFeature(it) })
    val byName = registry.associateBy { it.name }
    val unknown = questNames.filter { it !in byName }
    if (unknown.isNotEmpty()) fail("unknown quest types: ${unknown.joinToString()}")
    val notElementQuests = questNames.filter { byName[it] !is OsmElementQuestType<*> }
    if (notElementQuests.isNotEmpty()) fail("not OSM element quest types: ${notElementQuests.joinToString()}")
    val questTypes = questNames.distinct().map { byName.getValue(it) as OsmElementQuestType<*> }

    val mapData = MutableMapDataWithGeometry()
    val interner = HashMap<String, String>()
    fun intern(s: String): String = if (s.length > 32) s else interner.getOrPut(s) { s }

    var minLat = Double.POSITIVE_INFINITY
    var minLon = Double.POSITIVE_INFINITY
    var maxLat = Double.NEGATIVE_INFINITY
    var maxLon = Double.NEGATIVE_INFINITY
    var read = 0
    var skipped = 0
    var noTimestamp = 0
    val started = System.currentTimeMillis()

    File(inPath).bufferedReader().useLines { lines ->
        lines.forEachIndexed { lineIndex, line ->
            if (line.isBlank()) return@forEachIndexed
            try {
                val o = Json.parseToJsonElement(line).jsonObject
                val type = o.getValue("type").jsonPrimitive.content
                val id = o.getValue("id").jsonPrimitive.long
                val version = o["version"]?.jsonPrimitive?.int ?: 1
                val timestamp = o["timestamp"]?.jsonPrimitive?.long
                if (timestamp == null) noTimestamp++
                val tags = (o["tags"] as? JsonObject)?.let { t ->
                    val m = HashMap<String, String>(t.size * 4 / 3 + 1)
                    for ((k, v) in t) m[intern(k)] = intern((v as JsonPrimitive).content)
                    m
                } ?: emptyMap()
                val pos = LatLon(o.getValue("lat").jsonPrimitive.double, o.getValue("lon").jsonPrimitive.double)
                val ts = timestamp ?: 0L
                val element: Element = when (type) {
                    "node" -> Node(id, pos, tags, version, ts)
                    "way" -> Way(id, (o["nodes"] as? JsonArray)?.map { it.jsonPrimitive.long } ?: emptyList(), tags, version, ts)
                    "relation" -> Relation(id, (o["members"] as? JsonArray)?.map {
                        val m = it.jsonObject
                        RelationMember(
                            ElementType.valueOf(m.getValue("type").jsonPrimitive.content.uppercase()),
                            m.getValue("ref").jsonPrimitive.long,
                            intern(m["role"]?.jsonPrimitive?.content.orEmpty())
                        )
                    } ?: emptyList(), tags, version, ts)
                    else -> throw IllegalArgumentException("unknown type '$type'")
                }
                mapData.put(element, ElementPointGeometry(pos))
                if (pos.latitude < minLat) minLat = pos.latitude
                if (pos.latitude > maxLat) maxLat = pos.latitude
                if (pos.longitude < minLon) minLon = pos.longitude
                if (pos.longitude > maxLon) maxLon = pos.longitude
                read++
                if (read % 500_000 == 0) System.err.println("  read $read elements")
            } catch (e: Exception) {
                skipped++
                if (skipped <= 10) System.err.println("line ${lineIndex + 1} skipped: $e")
            }
        }
    }
    interner.clear()
    if (read > 0) mapData.boundingBox = BoundingBox(minLat, minLon, maxLat, maxLon)

    System.err.println("Read $read elements in ${(System.currentTimeMillis() - started) / 1000}s" +
        (if (skipped > 0) ", skipped $skipped bad lines" else ""))
    if (noTimestamp > 0) {
        System.err.println("WARNING: $noTimestamp elements have no timestamp; they count as edited in 1970, " +
            "so every 'older today -N years' resurvey rule matches them")
    }

    data class Row(val quest: String, val type: String, val id: Long)
    val rows = ArrayList<Row>()
    val failed = ArrayList<String>()
    for (questType in questTypes) {
        val t = System.currentTimeMillis()
        try {
            val keys = questType.getApplicableElements(mapData)
                .mapTo(HashSet()) { it.type to it.id }
            keys.mapTo(rows) { (type, id) -> Row(questType.name, type.name.lowercase(), id) }
            System.err.println("${questType.name}\t${keys.size}\t(${System.currentTimeMillis() - t} ms)")
        } catch (e: Throwable) {
            failed.add(questType.name)
            System.err.println("${questType.name}\tFAILED: $e")
            e.printStackTrace()
        }
    }

    rows.sortWith(compareBy<Row>({ it.quest }, { it.type }, { it.id }))
    val out = System.getProperty("sc.out")
    val writer = if (out.isNullOrBlank()) System.out.bufferedWriter() else {
        File(out).absoluteFile.parentFile?.mkdirs()
        File(out).bufferedWriter()
    }
    writer.use { w ->
        w.write("quest\ttype\tid\n")
        for (r in rows) w.write("${r.quest}\t${r.type}\t${r.id}\n")
    }
    if (!out.isNullOrBlank()) System.err.println("Wrote ${rows.size} rows to ${File(out).absolutePath}")

    if (failed.isNotEmpty()) {
        System.err.println("FAILED quest types: ${failed.joinToString()}")
        exitProcess(1)
    }
}

private fun fail(message: String): Nothing {
    System.err.println(message)
    exitProcess(2)
}
