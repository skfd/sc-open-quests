package openquests

import crosby.binary.Osmformat
import de.westnordost.streetcomplete.data.osm.geometry.ElementGeometry
import de.westnordost.streetcomplete.data.osm.geometry.ElementGeometryCreator
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Relation
import de.westnordost.streetcomplete.data.osm.mapdata.RelationMember
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import de.westnordost.streetcomplete.util.math.measuredLength
import java.io.Writer
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.atomic.AtomicLongArray
import java.util.stream.IntStream
import kotlin.math.roundToLong

const val NODE = 0
const val WAY = 1
const val RELATION = 2
private val TYPE_NAMES = listOf("node", "way", "relation")

/** Ways that count towards the `highwayKm` denominator: the road network a car or bike quest
 *  could be about. Area highways (`area=yes`) are left out. */
val HIGHWAY_KM_VALUES: Set<String> = listOf(
    "motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "service",
    "living_street",
).let { base -> base + base.filter { it in setOf("motorway", "trunk", "primary", "secondary", "tertiary") }.map { "${it}_link" } }
    .toSet()

/** Counts of one engine pass, indexed by city, quest (index into [Engine.quests]) and type. */
class Counts(val cityCount: Int, val questCount: Int) {
    /** per (city, quest): nodes, ways, relations, agedOnly */
    val perQuest = AtomicLongArray(cityCount * questCount * 4)
    val taggedNodes = AtomicLongArray(cityCount)
    val taggedWays = AtomicLongArray(cityCount)
    /** sum over ways of their length rounded to whole millimetres, so the total is exact and
     *  independent of the order in which threads add */
    val highwayMm = AtomicLongArray(cityCount)

    fun slot(city: Int, quest: Int, kind: Int) = (city * questCount + quest) * 4 + kind
    fun get(city: Int, quest: Int, kind: Int) = perQuest[slot(city, quest, kind)]
    fun open(city: Int, quest: Int) = get(city, quest, NODE) + get(city, quest, WAY) + get(city, quest, RELATION)
    fun agedOnly(city: Int, quest: Int) = get(city, quest, 3)
}

/** Diagnostics of one pass, printed to the log. */
class PassStats {
    /** tagged elements whose centre was computed (any city or none) */
    val located = AtomicLongArray(3)
    /** tagged elements in some city */
    val inCity = AtomicLongArray(3)
    /** tagged elements without SC geometry: way with a missing node or < 2 positions, relation
     *  with no usable member way */
    val noGeometry = AtomicLongArray(3)
    /** SC's ElementGeometryCreator threw (e.g. ways it could not join) */
    val geometryErrors = AtomicLongArray(3)
    /** tagged elements skipped because their bounding box misses every city's */
    val outsideBboxes = AtomicLongArray(3)
    /** tagged relations the app drops on download (ignoreRelation) */
    val ignoredRelations = java.util.concurrent.atomic.AtomicLong()
    val timings = LinkedHashMap<String, Double>()
}

/**
 * One pass over a PBF: every tagged element gets its quest marker position the way the app computes
 * it (SC's ElementGeometryCreator), is assigned to the cities whose polygon contains that position,
 * and is matched against every counted quest (filter quests and ported custom quests) enabled in those
 * cities.
 *
 * The file must be sorted Type_then_ID (Geofabrik, osmium). Stages: relations are scanned first for
 * the ids of their member ways; then nodes (kept as an id -> position index); then ways (member ways
 * of tagged relations keep their node positions); then relations.
 */
class Engine(val registry: Registry, val cities: List<City>) {
    val quests: List<QuestDef> = registry.countedQuests
    private val cityIndex = CityIndex(cities)
    /** enabled[city][quest] */
    val enabled: Array<BooleanArray> = Array(cities.size) { c ->
        BooleanArray(quests.size) { quests[it].countries.isEnabledIn(cities[c].countryCodes) }
    }
    private val questsByType: Array<IntArray> = Array(3) { t ->
        val type = ElementType.entries[t]
        quests.indices.filter { quests[it].matcher?.includesElementType(type) == true }.toIntArray()
    }
    private val geometryCreator = ElementGeometryCreator()

    val counts = Counts(cities.size, quests.size)
    val stats = PassStats()

    /** optional: lines "quest type id version timestampMs city lat lon agedOnly" for these quests */
    var dumpQuests: Set<String> = emptySet()
    private val dumpLines = ConcurrentLinkedQueue<String>()

    /** optional: every tagged element whose quest position is in this city (index into [cities]), as
     *  JSON lines for tools/sc-harness CheckCustomQuests, which runs SC's own quest classes on them */
    var dumpElementsCity: Int = -1
    /** how AreaPass cuts the map data; CITY only for oracle checks */
    var areaUnit: AreaUnit = AreaUnit.TILES
    private val elementLines = ConcurrentLinkedQueue<String>()

    init {
        // Untagged elements are skipped below; make sure no quest would match one. SC itself
        // relies on mayEvaluateToTrueWithNoTags, which is conservative (true for `highway ~ ...`).
        val untagged = listOf(Node(1, LatLon(0.0, 0.0)), Way(1, emptyList()), Relation(1, emptyList()))
        for (q in quests) {
            val matcher = q.matcher ?: continue // area quests see untagged elements too (AreaPass)
            require(untagged.none { matcher.matches(it) }) { "${q.name} matches untagged elements" }
        }
    }

    fun writeDump(w: Writer) {
        w.write("quest\ttype\tid\tversion\ttimestamp_ms\tcity\tlat\tlon\tagedOnly\n")
        dumpLines.sorted().forEach { w.write(it); w.write("\n") }
    }

    /** the area pass's map data of [dumpElementsCity], keyed by "type id"; replaces the main pass's
     *  lines for the same elements and adds the context (untagged way nodes, elements outside) */
    private val areaElementLines = HashMap<String, String>()

    /** JSON lines, sorted by type and id */
    fun writeElements(w: Writer) {
        val byKey = HashMap<String, String>()
        for (l in elementLines) byKey[l.substringBefore(",\"version\"")] = l
        for ((k, l) in areaElementLines) byKey[k] = l
        byKey.values.sortedWith(compareBy({ TYPE_NAMES.indexOf(it.substringAfter("\"type\":\"").substringBefore('"')) },
            { it.substringAfter("\"id\":").substringBefore(',').toLong() }))
            .forEach { w.write(it); w.write("\n") }
    }

    /** AreaPass: the whole map data of the dumped city, each element flagged with whether its quest
     *  position is inside the city polygon (the oracle only reports those) */
    fun dumpAreaElements(city: City, mapData: MapDataWithGeometry) {
        if (city.index != dumpElementsCity) return
        log("area: dumping ${city.id}'s map data, bbox ${mapData.boundingBox}")
        for (e in mapData) {
            val type = e.type.ordinal
            val center = mapData.getGeometry(e.type, e.id)?.center
            val inCity = center != null && city.polygon.contains(center.latitude, center.longitude)
            val line = elementJson(e, type, center, inCity)
            areaElementLines[line.substringBefore(",\"version\"")] = line
        }
    }

    /** AreaPass: one counted quest of area quest [qi] in city [c] */
    fun countArea(c: Int, qi: Int, e: Element, center: LatLon, aged: Boolean) {
        val type = e.type.ordinal
        counts.perQuest.incrementAndGet(counts.slot(c, qi, type))
        if (aged) counts.perQuest.incrementAndGet(counts.slot(c, qi, 3))
        if (quests[qi].name in dumpQuests) {
            dumpLines += "${quests[qi].name}\t${TYPE_NAMES[type]}\t${e.id}\t${e.version}\t${e.timestampEdited}\t" +
                "${cities[c].id}\t${center.latitude}\t${center.longitude}\t$aged"
        }
    }

    private fun elementJson(e: Element, type: Int, center: LatLon?, inCity: Boolean? = null): String =
        "{\"type\":\"${TYPE_NAMES[type]}\",\"id\":${e.id},\"version\":${e.version},\"timestamp\":${e.timestampEdited}," +
            "\"tags\":${e.tags.entries.sortedBy { it.key }.joinToString(",", "{", "}") { "${jsonString(it.key)}:${jsonString(it.value)}" }}," +
            // way node ids: SC's isArea() (and so getFeature()'s geometry type) needs isClosed
            (if (e is Way) "\"nodes\":${e.nodeIds.joinToString(",", "[", "]")}," else "") +
            (if (e is Relation) "\"members\":${e.members.joinToString(",", "[", "]") {
                "{\"type\":\"${TYPE_NAMES[it.type.ordinal]}\",\"ref\":${it.ref},\"role\":${jsonString(it.role)}}" }}," else "") +
            (if (inCity != null) "\"inCity\":$inCity," else "") +
            (if (center != null) "\"lat\":${center.latitude},\"lon\":${center.longitude}" else "\"geometry\":null") + "}"

    // ---------------------------------------------------------------------------------------------
    // matching

    private fun offer(e: Element, type: Int, cityIdx: IntArray, center: LatLon) {
        if (dumpElementsCity >= 0 && dumpElementsCity in cityIdx) elementLines += elementJson(e, type, center)
        for (qi in questsByType[type]) {
            var anyEnabled = false
            for (c in cityIdx) if (enabled[c][qi]) { anyEnabled = true; break }
            if (!anyEnabled) continue
            val q = quests[qi]
            val matcher = q.matcher!!
            if (!matcher.matches(e)) continue
            // agedOnly: would it still match if no `older today -N` (or `< today`) test could be true?
            val aged = q.usesAge && !EngineClock.at(EngineClock.LONG_AGO) { matcher.matches(e) }
            for (c in cityIdx) {
                if (!enabled[c][qi]) continue
                counts.perQuest.incrementAndGet(counts.slot(c, qi, type))
                if (aged) counts.perQuest.incrementAndGet(counts.slot(c, qi, 3))
                if (q.name in dumpQuests) {
                    dumpLines += "${q.name}\t${TYPE_NAMES[type]}\t${e.id}\t${e.version}\t${e.timestampEdited}\t" +
                        "${cities[c].id}\t${center.latitude}\t${center.longitude}\t$aged"
                }
            }
        }
    }

    private fun locate(type: Int, center: LatLon): IntArray {
        stats.located.incrementAndGet(type)
        val cityIdx = cityIndex.citiesAt(center.latitude, center.longitude)
        if (cityIdx.isNotEmpty()) stats.inCity.incrementAndGet(type)
        return cityIdx
    }

    // ---------------------------------------------------------------------------------------------
    // the pass

    fun run(blobs: List<ByteArray>) {
        val wayStart = lowerBound(blobs, BlockKind.WAYS)
        val relStart = lowerBound(blobs, BlockKind.RELATIONS)
        log("blocks: nodes [0,$wayStart) ways [$wayStart,$relStart) relations [$relStart,${blobs.size})")

        var t0 = System.nanoTime()
        val neededWays = parallelMap(relStart, blobs.size) { i ->
            memberWaysOfTaggedRelations(decodeBlock(blobs[i]).also { require(it.kind() == BlockKind.RELATIONS) })
        }.let { lists ->
            val all = LongArray(lists.sumOf { it.size })
            var k = 0
            for (l in lists) { l.copyInto(all, k); k += l.size }
            all.sort()
            all.distinctSorted()
        }
        timing("relation member scan", t0, "${neededWays.size} member ways of tagged relations")

        t0 = System.nanoTime()
        val nodes = SortedLongMap(parallelMap(0, wayStart) { i ->
            processNodes(decodeBlock(blobs[i]).also { require(it.kind() == BlockKind.NODES) })
        })
        timing("nodes", t0, "${nodes.size} nodes")

        t0 = System.nanoTime()
        val memberWays = SortedIdMap(parallelMap(wayStart, relStart) { i ->
            processWays(decodeBlock(blobs[i]).also { require(it.kind() == BlockKind.WAYS) }, nodes, neededWays)
        })
        timing("ways", t0, "${memberWays.size} member ways kept")

        t0 = System.nanoTime()
        parallelMap(relStart, blobs.size) { i ->
            processRelations(decodeBlock(blobs[i]), memberWays)
        }
        timing("relations", t0, "")

        AreaPass(this, blobs, wayStart, relStart, nodes, memberWays, areaUnit).run()
    }

    private fun timing(stage: String, t0: Long, note: String) {
        val s = (System.nanoTime() - t0) / 1e9
        stats.timings[stage] = s
        log("%-22s %6.1f s  %s".format(stage, s, note))
    }

    private fun memberWaysOfTaggedRelations(b: Osmformat.PrimitiveBlock): LongArray {
        val out = LongList()
        for (g in b.primitivegroupList) for (r in g.relationsList) {
            if (r.keysCount == 0) continue
            var memId = 0L
            for (i in 0 until r.memidsCount) {
                memId += r.getMemids(i)
                if (r.getTypes(i) == Osmformat.Relation.MemberType.WAY) out.add(memId)
            }
        }
        return out.toArray()
    }

    private fun processNodes(b: Osmformat.PrimitiveBlock): Pair<LongArray, LongArray> {
        val ctx = BlockContext(b)
        val ids = LongList()
        val coords = LongList()
        for (g in b.primitivegroupList) {
            if (g.hasDense()) {
                val d = g.dense
                val hasInfo = d.hasDenseinfo()
                val info = d.denseinfo
                val hasKv = d.keysValsCount > 0
                var id = 0L; var lat = 0L; var lon = 0L; var ts = 0L; var kv = 0
                for (i in 0 until d.idCount) {
                    id += d.getId(i); lat += d.getLat(i); lon += d.getLon(i)
                    if (hasInfo) ts += info.getTimestamp(i)
                    val lat7 = ctx.lat7(lat); val lon7 = ctx.lon7(lon)
                    ids.add(id); coords.add(pack(lat7, lon7))
                    if (!hasKv) continue
                    val start = kv
                    while (d.getKeysVals(kv) != 0) kv += 2
                    val end = kv
                    kv++
                    if (end == start) continue
                    val position = LatLon(lat7 / 1e7, lon7 / 1e7)
                    val cityIdx = locate(NODE, position)
                    if (cityIdx.isEmpty()) continue
                    val tags = HashMap<String, String>(end - start)
                    var j = start
                    while (j < end) { tags[ctx.strings[d.getKeysVals(j)]] = ctx.strings[d.getKeysVals(j + 1)]; j += 2 }
                    val version = if (hasInfo) info.getVersion(i) else 1
                    val node = Node(id, position, tags, version, ts * ctx.dateGranularity)
                    for (c in cityIdx) counts.taggedNodes.incrementAndGet(c)
                    offer(node, NODE, cityIdx, position)
                }
            }
            for (n in g.nodesList) {
                val lat7 = ctx.lat7(n.lat); val lon7 = ctx.lon7(n.lon)
                ids.add(n.id); coords.add(pack(lat7, lon7))
                if (n.keysCount == 0) continue
                val position = LatLon(lat7 / 1e7, lon7 / 1e7)
                val cityIdx = locate(NODE, position)
                if (cityIdx.isEmpty()) continue
                val node = Node(n.id, position, tagsOf(n.keysList, n.valsList, ctx.strings),
                    if (n.hasInfo()) n.info.version else 1, n.info.timestamp * ctx.dateGranularity)
                for (c in cityIdx) counts.taggedNodes.incrementAndGet(c)
                offer(node, NODE, cityIdx, position)
            }
        }
        return ids.toArray() to coords.toArray()
    }

    private fun processWays(
        b: Osmformat.PrimitiveBlock,
        nodes: SortedLongMap,
        neededWays: LongArray,
    ): Pair<LongArray, Array<LongArray?>> {
        val ctx = BlockContext(b)
        val keptIds = LongList()
        val keptCoords = ArrayList<LongArray?>()
        var refs = LongArray(2000)
        var coords = LongArray(2000)
        for (g in b.primitivegroupList) for (w in g.waysList) {
            val tagged = w.keysCount > 0
            val needed = neededWays.binarySearch(w.id) >= 0
            if (!tagged && !needed) continue
            val rc = w.refsCount
            if (refs.size < rc) { refs = LongArray(rc * 2); coords = LongArray(rc * 2) }
            var ref = 0L
            var complete = true
            for (i in 0 until rc) {
                ref += w.getRefs(i); refs[i] = ref
                val c = nodes[ref]
                coords[i] = c
                if (c == NO_COORD) complete = false
            }
            if (needed) { keptIds.add(w.id); keptCoords += if (complete) coords.copyOf(rc) else null }
            if (!tagged) continue
            // SC (MapData.getNodePositions): a way with a node missing has no geometry, so no quest
            if (!complete) { stats.noGeometry.incrementAndGet(WAY); continue }
            if (!bboxMayHit(coords, rc)) { stats.outsideBboxes.incrementAndGet(WAY); continue }

            val positions = ArrayList<LatLon>(rc)
            for (i in 0 until rc) positions += LatLon(unpackLat7(coords[i]) / 1e7, unpackLon7(coords[i]) / 1e7)
            val tags = tagsOf(w.keysList, w.valsList, ctx.strings)
            val way = Way(w.id, LongArrayAsList(refs.copyOf(rc)), tags,
                if (w.hasInfo()) w.info.version else 1, w.info.timestamp * ctx.dateGranularity)
            val geometry = geometryOf(WAY) { geometryCreator.create(way, positions) } ?: continue
            val center = geometry.center
            val cityIdx = locate(WAY, center)
            if (cityIdx.isEmpty()) continue
            for (c in cityIdx) counts.taggedWays.incrementAndGet(c)
            if (tags["highway"] in HIGHWAY_KM_VALUES && tags["area"] != "yes") {
                // SC's spherical length (R = 6371 km), as used for the app's own measurements
                val mm = (positions.measuredLength() * 1000).roundToLong()
                for (c in cityIdx) counts.highwayMm.addAndGet(c, mm)
            }
            offer(way, WAY, cityIdx, center)
        }
        return keptIds.toArray() to keptCoords.toTypedArray()
    }

    private fun processRelations(b: Osmformat.PrimitiveBlock, memberWays: SortedIdMap<LongArray>) {
        require(b.kind() == BlockKind.RELATIONS)
        val ctx = BlockContext(b)
        for (g in b.primitivegroupList) for (r in g.relationsList) {
            if (r.keysCount == 0) continue
            val tags = tagsOf(r.keysList, r.valsList, ctx.strings)
            // the app drops these while parsing a download, so no quest is ever on one
            if (ignoreRelation(tags)) { stats.ignoredRelations.incrementAndGet(); continue }
            val members = ArrayList<RelationMember>(r.memidsCount)
            // SC builds relation geometry from member ways only, skipping missing or incomplete ways
            // (allowIncomplete = true in MapDataControllerImpl); node and relation members are ignored.
            val wayGeometries = HashMap<Long, List<LatLon>>()
            var south = 90.0; var north = -90.0; var west = 180.0; var east = -180.0
            var memId = 0L
            for (i in 0 until r.memidsCount) {
                memId += r.getMemids(i)
                val type = when (r.getTypes(i)!!) {
                    Osmformat.Relation.MemberType.NODE -> ElementType.NODE
                    Osmformat.Relation.MemberType.WAY -> ElementType.WAY
                    Osmformat.Relation.MemberType.RELATION -> ElementType.RELATION
                }
                members += RelationMember(type, memId, ctx.strings[r.getRolesSid(i)])
                if (type != ElementType.WAY || memId in wayGeometries) continue
                val coords = memberWays[memId] ?: continue
                val positions = ArrayList<LatLon>(coords.size)
                for (c in coords) {
                    val lat = unpackLat7(c) / 1e7; val lon = unpackLon7(c) / 1e7
                    positions += LatLon(lat, lon)
                    if (lat < south) south = lat; if (lat > north) north = lat
                    if (lon < west) west = lon; if (lon > east) east = lon
                }
                wayGeometries[memId] = positions
            }
            if (wayGeometries.isEmpty()) { stats.noGeometry.incrementAndGet(RELATION); continue }
            if (!cityIndex.bboxMayHit(south, west, north, east)) { stats.outsideBboxes.incrementAndGet(RELATION); continue }
            val relation = Relation(r.id, members, tags,
                if (r.hasInfo()) r.info.version else 1, r.info.timestamp * ctx.dateGranularity)
            val geometry = geometryOf(RELATION) { geometryCreator.create(relation, wayGeometries) } ?: continue
            val center = geometry.center
            val cityIdx = locate(RELATION, center)
            if (cityIdx.isEmpty()) continue
            offer(relation, RELATION, cityIdx, center)
        }
    }

    private inline fun geometryOf(type: Int, create: () -> ElementGeometry?): ElementGeometry? {
        val g = try {
            create()
        } catch (e: RuntimeException) {
            stats.geometryErrors.incrementAndGet(type)
            return null
        }
        if (g == null) stats.noGeometry.incrementAndGet(type)
        return g
    }

    private fun bboxMayHit(coords: LongArray, n: Int): Boolean {
        var s = Int.MAX_VALUE; var nn = Int.MIN_VALUE; var w = Int.MAX_VALUE; var e = Int.MIN_VALUE
        for (i in 0 until n) {
            val lat = unpackLat7(coords[i]); val lon = unpackLon7(coords[i])
            if (lat < s) s = lat; if (lat > nn) nn = lat
            if (lon < w) w = lon; if (lon > e) e = lon
        }
        return cityIndex.bboxMayHit(s / 1e7, w / 1e7, nn / 1e7, e / 1e7)
    }
}

// -------------------------------------------------------------------------------------------------
// helpers

internal fun LongArray.distinctSorted(): LongArray {
    if (isEmpty()) return this
    var n = 1
    for (i in 1 until size) if (this[i] != this[n - 1]) this[n++] = this[i]
    return copyOf(n)
}

internal fun tagsOf(keys: List<Int>, vals: List<Int>, strings: Array<String>): Map<String, String> {
    val m = HashMap<String, String>(keys.size * 2)
    for (i in keys.indices) m[strings[keys[i]]] = strings[vals[i]]
    return m
}

class LongList {
    private var a = LongArray(8000); private var n = 0
    fun add(v: Long) { if (n == a.size) a = a.copyOf(n * 2); a[n++] = v }
    fun toArray() = a.copyOf(n)
}

/** Read-only List<Long> over a LongArray, so a Way's nodeIds need not box every id up front. */
class LongArrayAsList(private val a: LongArray) : AbstractList<Long>(), RandomAccess {
    override val size get() = a.size
    override fun get(index: Int): Long = a[index]
}

/** Sorted id -> value lookup over per-block arrays in file order (ids ascending across blocks). */
class SortedIdMap<T : Any>(blocks: List<Pair<LongArray, Array<T?>>>) {
    private val nonEmpty = blocks.filter { it.first.isNotEmpty() }
    private val firstIds = LongArray(nonEmpty.size) { nonEmpty[it].first[0] }
    val size: Long = nonEmpty.sumOf { it.first.size.toLong() }

    operator fun get(id: Long): T? {
        var bi = firstIds.binarySearch(id)
        if (bi < 0) bi = -bi - 2
        if (bi < 0) return null
        val (ids, values) = nonEmpty[bi]
        val i = ids.binarySearch(id)
        return if (i >= 0) values[i] else null
    }
}

fun <T> parallelMap(from: Int, until: Int, f: (Int) -> T): List<T> =
    IntStream.range(from, until).parallel().mapToObj { f(it) }.toList()

/** First blob index whose kind is >= [kind]; kinds are monotonic in a Type_then_ID sorted file. */
fun lowerBound(blobs: List<ByteArray>, kind: BlockKind): Int {
    var lo = 0; var hi = blobs.size
    while (lo < hi) {
        val mid = (lo + hi) ushr 1
        if (decodeBlock(blobs[mid]).kind() < kind) lo = mid + 1 else hi = mid
    }
    return lo
}

fun log(msg: String) = System.err.println(msg)
