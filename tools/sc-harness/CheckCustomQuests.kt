package de.westnordost.streetcomplete

import de.westnordost.streetcomplete.data.osm.geometry.ElementGeometryCreator
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
import de.westnordost.streetcomplete.util.math.contains
import kotlinx.io.files.SystemFileSystem
import kotlinx.io.buffered
import com.charleskorn.kaml.Yaml
import com.charleskorn.kaml.YamlConfiguration
import de.westnordost.streetcomplete.data.meta.CountryInfo
import de.westnordost.streetcomplete.data.meta.IncompleteCountryInfo
import de.westnordost.streetcomplete.util.countryboundaries.CountryBoundariesImpl
import kotlinx.serialization.decodeFromString
import dev.mokkery.mock
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
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
 *               "tags":{...},"lat":43.6,"lon":-79.4, "nodes":[...], "members":[{"type":"way","ref":1,"role":"outer"}],
 *               "inCity":true}
 *              Nodes need lat/lon. Ways and relations get their geometry as the app builds it, from
 *              their nodes / member ways (ElementGeometryCreator, incomplete relations allowed); their
 *              lat/lon, if given, is only the fallback point when that fails. Elements without any
 *              geometry are skipped, as the app skips them. inCity:false marks context outside the
 *              counted area: such elements feed the quests but are not listed (missing = true).
 *  - sc.quests comma-separated quest type names, e.g. AddSidewalk,AddOpeningHours
 *  - sc.out    TSV output (quest, type, id), sorted; else stdout
 *  - sc.bbox   optional south,west,north,east: the "downloaded" bounding box. Set as the map data's
 *              bounding box, and quests whose geometry centre lies outside it are dropped, as
 *              OsmQuestController.mayCreateQuest does. Without it the box covers all positions and
 *              nothing is dropped for position.
 *  - sc.presets SC's osmfeatures preset directory (default: the checkout's composeResources). The
 *              quests that take getFeature get the app's own: FeatureDictionary over SC's presets,
 *              queried in the JVM's default locale (the task pins en-CA, as the engine does). */
fun main() {
    val inPath = System.getProperty("sc.in")?.takeIf { it.isNotBlank() }
        ?: fail("sc.in (-PcheckIn) is required")
    val questNames = System.getProperty("sc.quests").orEmpty()
        .split(',').map { it.trim() }.filter { it.isNotEmpty() }
    if (questNames.isEmpty()) fail("sc.quests (-PcheckQuests) is required")
    val bbox = System.getProperty("sc.bbox")?.takeIf { it.isNotBlank() }?.let { s ->
        val v = s.split(',').map { it.trim().toDoubleOrNull() }
        if (v.size != 4 || v.any { it == null }) fail("sc.bbox (-PcheckBbox) must be south,west,north,east, got '$s'")
        val (south, west, north, east) = v.map { it!! }
        if (south > north) fail("sc.bbox: south $south is north of north $north")
        BoundingBox(south, west, north, east)
    }

    // resolve quest names before reading a possibly huge input
    // getFeature as the app wires it (AndroidModule2): { featureDictionaryLazy.value.getFeature(it) }
    val presets = System.getProperty("sc.presets")?.takeIf { it.isNotBlank() }
        ?: "src/commonMain/composeResources/files/osmfeatures/default"
    val brands = File(presets).resolveSibling("brands").path
    val featureDictionary by lazy {
        System.err.println("feature dictionary: $presets (+ $brands), locale ${java.util.Locale.getDefault().toLanguageTag()}")
        FeatureDictionary.create(SystemFileSystem, presets, brands)
    }
    // getCountryInfoByLocation and getCountryOrSubdivisionCode as the app wires them (AndroidModule2):
    // { countryInfos.get(countryBoundaries, it) } and { countryBoundaries.getIds(it).firstOrNull() },
    // over the checkout's boundaries.ser and country_metadata/ (CountryInfos reads them through
    // Compose resources, which do not load here, so its load() is mirrored below with SC's kaml setup)
    val files = File(System.getProperty("sc.files")?.takeIf { it.isNotBlank() } ?: "src/commonMain/composeResources/files")
    val countryBoundaries by lazy {
        SystemFileSystem.source(kotlinx.io.files.Path(File(files, "boundaries.ser").path)).buffered().use {
            CountryBoundariesImpl(de.westnordost.countryboundaries.CountryBoundaries.deserializeFrom(it))
        }
    }
    val yaml = Yaml(configuration = YamlConfiguration(strictMode = false))
    val incompleteInfos = java.util.concurrent.ConcurrentHashMap<String, java.util.Optional<IncompleteCountryInfo>>()
    fun loadInfo(regionCode: String): IncompleteCountryInfo? = incompleteInfos.getOrPut(regionCode) {
        val f = File(files, "country_metadata/$regionCode.yml")
        java.util.Optional.ofNullable(if (!f.isFile) null else
            yaml.decodeFromString<IncompleteCountryInfo>("countryCode: ${regionCode.split("-").first()}\n" + f.readText()))
    }.orElse(null)
    val getCountryInfoByLocation: (LatLon) -> CountryInfo = { pos ->
        CountryInfo(countryBoundaries.getIds(pos).mapNotNull { loadInfo(it) } + loadInfo("default")!!)
    }
    val registry = questTypeRegistry(
        mock(),
        getCountryInfoByLocation,
        { countryBoundaries.getIds(it).firstOrNull() },
        { featureDictionary.getFeature(it) },
    )
    val byName = registry.associateBy { it.name }
    val unknown = questNames.filter { it !in byName }
    if (unknown.isNotEmpty()) fail("unknown quest types: ${unknown.joinToString()}")
    val notElementQuests = questNames.filter { byName[it] !is OsmElementQuestType<*> }
    if (notElementQuests.isNotEmpty()) fail("not OSM element quest types: ${notElementQuests.joinToString()}")
    val questTypes = questNames.distinct().map { byName.getValue(it) as OsmElementQuestType<*> }

    val mapData = MutableMapDataWithGeometry()
    val interner = HashMap<String, String>()
    fun intern(s: String): String = if (s.length > 32) s else interner.getOrPut(s) { s }

    // lat/lon given on way and relation lines: the fallback point if no geometry can be built
    val wayFallback = HashMap<Long, LatLon>()
    val relationFallback = HashMap<Long, LatLon>()
    // elements whose line said inCity:false (context only, never listed)
    val outside = mapOf(
        ElementType.NODE to HashSet<Long>(),
        ElementType.WAY to HashSet<Long>(),
        ElementType.RELATION to HashSet<Long>(),
    )
    var sawInCity = false

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
                val tags = (o["tags"] as? JsonObject)?.takeIf { it.isNotEmpty() }?.let { t ->
                    val m = HashMap<String, String>(t.size * 4 / 3 + 1)
                    for ((k, v) in t) m[intern(k)] = intern((v as JsonPrimitive).content)
                    m
                } ?: emptyMap()
                val lat = o["lat"]?.jsonPrimitive?.double
                val lon = o["lon"]?.jsonPrimitive?.double
                val pos = if (lat != null && lon != null) LatLon(lat, lon) else null
                val ts = timestamp ?: 0L
                val element: Element = when (type) {
                    "node" -> Node(id, pos ?: throw IllegalArgumentException("node without lat/lon"), tags, version, ts)
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
                val inCity = o["inCity"]?.jsonPrimitive?.booleanOrNull
                if (o.containsKey("inCity")) sawInCity = true
                if (inCity == false) outside.getValue(element.type).add(id)
                // a node's geometry is its position, as the app makes it; ways and relations below,
                // once all nodes are in
                when (element) {
                    is Node -> mapData.put(element, ElementPointGeometry(element.position))
                    is Way -> { mapData.putElement(element); if (pos != null) wayFallback[id] = pos }
                    is Relation -> { mapData.putElement(element); if (pos != null) relationFallback[id] = pos }
                }
                if (pos != null) {
                    if (pos.latitude < minLat) minLat = pos.latitude
                    if (pos.latitude > maxLat) maxLat = pos.latitude
                    if (pos.longitude < minLon) minLon = pos.longitude
                    if (pos.longitude > maxLon) maxLon = pos.longitude
                }
                read++
                if (read % 500_000 == 0) System.err.println("  read $read elements")
            } catch (e: Exception) {
                skipped++
                if (skipped <= 10) System.err.println("line ${lineIndex + 1} skipped: $e")
            }
        }
    }
    interner.clear()
    System.err.println("Read $read elements in ${(System.currentTimeMillis() - started) / 1000}s" +
        (if (skipped > 0) ", skipped $skipped bad lines" else ""))
    if (noTimestamp > 0) {
        System.err.println("WARNING: $noTimestamp elements have no timestamp; they count as edited in 1970, " +
            "so every 'older today -N years' resurvey rule matches them")
    }

    // geometry of ways and relations as MapDataControllerImpl builds it on download
    val geometryStarted = System.currentTimeMillis()
    val creator = ElementGeometryCreator()
    var built = 0
    var fellBack = 0
    var noGeometry = 0
    var threw = 0
    // SC's own creator; it can throw on degenerate shapes (e.g. a sliver polygon whose centroid lands
    // off the globe). The app does not guard that; here it counts as "could not build"
    fun createOrNull(element: Element) = try {
        creator.create(element, mapData, true)
    } catch (e: Exception) {
        threw++
        if (threw <= 10) System.err.println("geometry of ${element.type.name.lowercase()} ${element.id} failed: $e")
        null
    }
    for (way in mapData.ways) {
        val g = (if (way.nodeIds.isNotEmpty()) createOrNull(way) else null)
            ?: wayFallback[way.id]?.let { fellBack++; ElementPointGeometry(it) }
        if (g == null) noGeometry++ else if (g !is ElementPointGeometry) built++
        mapData.putGeometry(ElementType.WAY, way.id, g)
    }
    for (relation in mapData.relations) {
        val g = (if (relation.members.isNotEmpty()) createOrNull(relation) else null)
            ?: relationFallback[relation.id]?.let { fellBack++; ElementPointGeometry(it) }
        if (g == null) noGeometry++ else if (g !is ElementPointGeometry) built++
        mapData.putGeometry(ElementType.RELATION, relation.id, g)
    }
    wayFallback.clear()
    relationFallback.clear()
    System.err.println("Geometry for ${mapData.ways.size} ways and ${mapData.relations.size} relations in " +
        "${(System.currentTimeMillis() - geometryStarted) / 1000}s: $built built, $fellBack fell back to " +
        "lat/lon, $noGeometry have none" +
        (if (threw > 0) " ($threw threw in ElementGeometryCreator)" else "") +
        Runtime.getRuntime().let { "; heap in use ${(it.totalMemory() - it.freeMemory()) shr 20} MB" })

    mapData.boundingBox = bbox ?: if (read > 0 && minLat <= maxLat) BoundingBox(minLat, minLon, maxLat, maxLon) else null
    if (sawInCity) System.err.println("inCity: ${outside.values.sumOf { it.size }} elements are context only")

    data class Row(val quest: String, val type: String, val id: Long)
    val rows = ArrayList<Row>()
    val failed = ArrayList<String>()
    for (questType in questTypes) {
        val t = System.currentTimeMillis()
        try {
            val keys = questType.getApplicableElements(mapData)
                .mapTo(HashSet()) { it.type to it.id }
            var dropNoGeometry = 0
            var dropOutsideBbox = 0
            var dropOutsideCity = 0
            var listed = 0
            for ((type, id) in keys) {
                // OsmQuestController.createQuestsForBBox: getGeometry(...) ?: continue, then mayCreateQuest
                val geometry = mapData.getGeometry(type, id)
                if (geometry == null) { dropNoGeometry++; continue }
                if (bbox != null && !bbox.contains(geometry.center)) { dropOutsideBbox++; continue }
                if (id in outside.getValue(type)) { dropOutsideCity++; continue }
                rows.add(Row(questType.name, type.name.lowercase(), id))
                listed++
            }
            val drops = listOfNotNull(
                "$dropNoGeometry no geometry".takeIf { dropNoGeometry > 0 },
                "$dropOutsideBbox outside bbox".takeIf { dropOutsideBbox > 0 },
                "$dropOutsideCity outside city".takeIf { dropOutsideCity > 0 },
            )
            System.err.println("${questType.name}\t$listed\t(${System.currentTimeMillis() - t} ms)" +
                (if (drops.isNotEmpty()) "\tdropped ${drops.joinToString()}" else ""))
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
