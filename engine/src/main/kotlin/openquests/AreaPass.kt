package openquests

import crosby.binary.Osmformat
import de.westnordost.streetcomplete.data.osm.geometry.ElementGeometry
import de.westnordost.streetcomplete.data.osm.geometry.ElementGeometryCreator
import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Relation
import de.westnordost.streetcomplete.data.osm.mapdata.RelationMember
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import de.westnordost.streetcomplete.data.download.tiles.TilePos
import de.westnordost.streetcomplete.data.download.tiles.TilesRect
import de.westnordost.streetcomplete.data.download.tiles.enclosingTilePos
import de.westnordost.streetcomplete.data.download.tiles.enclosingTilesRect
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.util.math.contains
import openquests.custom.AreaQuest
import openquests.fast.FAST_TWINS
import java.util.concurrent.ConcurrentLinkedQueue
import kotlin.math.cos

/** How far around a city's bounding box elements are collected, in metres: more than a z16 tile, so
 *  every tile that touches the city finds all its elements (and, in city mode, the area reaches that
 *  far past the city's bounding box). `-Dopenquests.areaPaddingM=<metres>` sets another ring, for
 *  tests that count small patches (DESIGN.md, "The stream, tier 2"); snapshots use the default. */
val AREA_PADDING_M: Double = System.getProperty("openquests.areaPaddingM")?.toDouble() ?: 1000.0

/** `-Dopenquests.verifyFast=true`: run every port that has a [FAST_TWINS] entry next to its twin and
 *  fail on any difference (slow on whole cities: the ports' quadratic parts run too). */
val VERIFY_FAST = System.getProperty("openquests.verifyFast") == "true"

/** Area quests whose one run is among a city's longest in the traces (DESIGN.md, "The whole area pass
 *  profiled"), started before every other run so none of them starts late and runs on alone. Order
 *  only: counts do not depend on it. */
private val LONG_RUNS = listOf("AddHousenumber", "AddLevelThing", "AddMaxHeight")
private fun longRank(name: String) = LONG_RUNS.indexOf(name).let { if (it < 0) LONG_RUNS.size else it }

/** `-Dopenquests.taskTrace=<file>`: append a tab-separated line per area task (city, task, thread,
 *  start and end in seconds from the city's first task, thread CPU seconds), to see whether a city's
 *  area pass waits on one run or on the CPU. Counts do not change. */
private val TASK_TRACE: java.io.File? = System.getProperty("openquests.taskTrace")?.let { java.io.File(it) }
private val threadMx = java.lang.management.ManagementFactory.getThreadMXBean()

private class Traced(val label: String, val thread: String, val start: Long, val end: Long, val cpu: Long)

private inline fun <T> traced(out: ConcurrentLinkedQueue<Traced>?, label: () -> String, f: () -> T): T {
    if (out == null) return f()
    val t0 = System.nanoTime(); val c0 = threadMx.currentThreadCpuTime
    val r = f()
    out += Traced(label(), Thread.currentThread().name, t0, System.nanoTime(), threadMx.currentThreadCpuTime - c0)
    return r
}

/** The app's download unit (ApplicationConstants.DOWNLOAD_TILE_ZOOM). */
const val AREA_TILE_ZOOM = 16

/** How AreaPass cuts the map data. [CITY], what snapshots use, puts a whole city into one map data:
 *  the app after downloading the whole city, and exactly what tools/sc-harness CheckCustomQuests runs
 *  on (with --dump-elements). [TILES] runs each z16 tile alone, the app's smallest download; quests
 *  about a large containing polygon then see less of it (--area-unit tiles). */
enum class AreaUnit { TILES, CITY }

/**
 * Second pass, for the custom quests whose `getApplicableElements(mapData)` needs the surroundings
 * ([openquests.custom.AreaQuest]). It reproduces what the app does after downloading an area
 * (`OsmQuestController.createQuestsForBBox`): one `MapDataWithGeometry` holding what the OSM API's
 * map call returns for the area, every quest's `getApplicableElements()` on it, and `mayCreateQuest`:
 * a result counts only if it has geometry and its position is inside the downloaded bounding box.
 *
 * The area is a city's bounding box padded by [AREA_PADDING_M] ([AreaUnit.CITY]), or one z16 tile
 * ([AreaUnit.TILES]). Its map data is what the API's map call returns for that box: every way with a
 * node in it (with all its nodes, also those outside), every node in it that has tags (untagged nodes
 * not on such a way play no part), every tagged relation with such a way or node as a member. A result
 * counts if its position is inside the box, as mayCreateQuest demands, and in the city's polygon (per
 * tile: in the cities whose polygon holds it), where the quest is enabled. Cities run one after the
 * other with the quests in parallel; tiles run in parallel. The quests whose SC code compares
 * everything with everything run as [FAST_TWINS] on a whole city.
 *
 * Stages over the PBF blobs already in memory: ways (which ways come within [AREA_PADDING_M] of a
 * city's bounding box, as a [CitySets] id; a [BoxGrid] finds the boxes of a point), nodes (those ways' nodes and the tagged nodes nearby, with
 * tags, version and timestamp), relations. Then the tiles: build the map data, run every enabled area
 * quest at asOf and, for an age quest, at the other resurvey settings and [EngineClock.LONG_AGO] for agedOnly.
 */
class AreaPass(
    private val engine: Engine,
    private val blobs: List<ByteArray>,
    private val wayStart: Int,
    private val relStart: Int,
    private val nodeIndex: SortedLongMap,
    /** packed coordinates of the member ways of tagged relations, from the main pass */
    private val memberWays: SortedIdMap<LongArray>,
    private val unit: AreaUnit = AreaUnit.TILES,
) {
    private val cities = engine.cities

    /** quest indices (into engine.quests) of the area quests */
    private val areaQuests = engine.quests.indices.filter { engine.quests[it].area != null }

    // padded city boxes, in 1e-7 degrees
    private val south = IntArray(cities.size); private val north = IntArray(cities.size)
    private val west = IntArray(cities.size); private val east = IntArray(cities.size)
    init {
        for (c in cities) {
            val p = c.polygon
            val dLat = AREA_PADDING_M / 111_320.0
            val dLon = AREA_PADDING_M / (111_320.0 * cos(Math.toRadians(maxOf(kotlin.math.abs(p.minLat), kotlin.math.abs(p.maxLat)))))
            south[c.index] = ((p.minLat - dLat) * 1e7).toInt(); north[c.index] = ((p.maxLat + dLat) * 1e7).toInt()
            west[c.index] = ((p.minLon - dLon) * 1e7).toInt(); east[c.index] = ((p.maxLon + dLon) * 1e7).toInt()
        }
    }

    fun bbox(city: Int) = BoundingBox(south[city] / 1e7, west[city] / 1e7, north[city] / 1e7, east[city] / 1e7)

    /** which padded city boxes an element is in, as a [CitySets] id (0: none) */
    private val citySets = CitySets(cities.size)
    private val boxGrid = BoxGrid(south, west, north, east)
    /** the set ids of points in two or more boxes, by grid cell and which of the cell's candidates hold the point */
    private val cellSets = java.util.concurrent.ConcurrentHashMap<Long, Int>()

    /** The padded city boxes holding the point, as a [citySets] id. */
    private fun setAt(lat7: Int, lon7: Int): Int {
        val cell = boxGrid.cellOf(lat7, lon7)
        if (cell < 0) return 0
        val candidates = boxGrid.candidatesInCell(cell) ?: return 0
        fun holds(i: Int) = lat7 in south[i]..north[i] && lon7 in west[i]..east[i]
        if (candidates.size > MAX_LOCAL) {
            return citySets.idOf(candidates.filter { holds(it) }.toIntArray())
        }
        var local = 0L; var single = -1; var hits = 0
        for (k in candidates.indices) if (holds(candidates[k])) { local = local or (1L shl k); single = candidates[k]; hits++ }
        return when (hits) {
            0 -> 0
            1 -> single + 1 // CitySets: the set {c} is c + 1
            else -> cellSets.getOrPut((cell.toLong() shl MAX_LOCAL) or local) {
                citySets.idOf(candidates.filterIndexed { k, _ -> local and (1L shl k) != 0L }.toIntArray())
            }
        }
    }

    private class WayRec(val id: Long, val refs: LongArray, val tags: Map<String, String>, val version: Int, val timestamp: Long, val cities: Int)
    private class NodeRec(val id: Long, val coord: Long, val tags: Map<String, String>, val version: Int, val timestamp: Long, val cities: Int)
    private class RelRec(val id: Long, val members: List<RelationMember>, val tags: Map<String, String>, val version: Int, val timestamp: Long, val cities: Int)

    private lateinit var ways: List<WayRec>          // sorted by id
    private lateinit var wayIds: LongArray
    private lateinit var nodes: List<NodeRec>        // sorted by id
    private lateinit var nodeIds: LongArray
    private lateinit var relations: List<RelRec>
    private val geometryCreator = ElementGeometryCreator()

    fun run() {
        if (areaQuests.isEmpty()) return
        var t0 = System.nanoTime()
        ways = parallelMap(wayStart, relStart) { collectWays(decodeBlock(blobs[it])) }.flatten()
        wayIds = LongArray(ways.size) { ways[it].id }
        val needed = LongArray(ways.sumOf { it.refs.size }).also { a ->
            var k = 0
            for (w in ways) { w.refs.copyInto(a, k); k += w.refs.size }
            a.sort()
        }.distinctSorted()
        timing("area: ways", t0, "${ways.size} ways touch a city area, ${needed.size} way nodes")

        t0 = System.nanoTime()
        nodes = parallelMap(0, wayStart) { collectNodes(decodeBlock(blobs[it]), needed) }.flatten()
        nodeIds = LongArray(nodes.size) { nodes[it].id }
        timing("area: nodes", t0, "${nodes.size} nodes")

        t0 = System.nanoTime()
        relations = parallelMap(relStart, blobs.size) { collectRelations(decodeBlock(blobs[it])) }.flatten()
        timing("area: relations", t0, "${relations.size} tagged relations")

        if (unit == AreaUnit.TILES) { runTiles(); return }
        for (c in cities) {
            // with --dump-elements, only the dumped city
            if (engine.dumpElementsCity >= 0 && c.index != engine.dumpElementsCity) continue
            t0 = System.nanoTime()
            val enabledQuests = areaQuests.filter { engine.enabled[c.index][it] }
            if (enabledQuests.isEmpty()) continue
            val mapData = buildMapData(c.index)
            val built = (System.nanoTime() - t0) / 1e9
            countCity(c, mapData, enabledQuests)
            engine.stats.timings["area: ${c.id}"] = (System.nanoTime() - t0) / 1e9
            log("area: %-18s %6.1f s  (map data %.1f s: %d nodes, %d ways, %d relations)".format(
                c.id, (System.nanoTime() - t0) / 1e9, built, mapData.nodes.size, mapData.ways.size, mapData.relations.size))
        }
        if (VERIFY_FAST) log("area: fast twins matched their ports on ${verifiedTwins.get()} map data runs")
    }

    // ---------------------------------------------------------------------------------------------
    // tiles

    private fun tileKey(lat7: Int, lon7: Int): Long {
        val t = LatLon(lat7 / 1e7, lon7 / 1e7).enclosingTilePos(AREA_TILE_ZOOM)
        return (t.x.toLong() shl 32) or (t.y.toLong() and 0xffffffffL)
    }

    /** the z16 tiles that intersect some city's (unpadded) bounding box */
    private val cityTileRects: List<TilesRect> = cities.map {
        BoundingBox(it.polygon.minLat, it.polygon.minLon, it.polygon.maxLat, it.polygon.maxLon).enclosingTilesRect(AREA_TILE_ZOOM)
    }

    private fun isCityTile(key: Long): Boolean {
        val x = (key shr 32).toInt(); val y = key.toInt()
        return cityTileRects.any { x in it.left..it.right && y in it.top..it.bottom }
    }

    private class Bucket { val ways = IntList(); val nodes = IntList(); val relations = IntList() }

    private fun runTiles() {
        // a tile's quests run once for every city it touches, so they have one zone
        require(engine.zones.all { it == null }) { "--area-unit tiles needs every city in the JVM's time zone" }
        var t0 = System.nanoTime()
        // the tiles each way has a node in (the API's map call returns a way for each of them)
        val wayTiles: List<LongArray> = parallelMap(0, ways.size) { i ->
            val w = ways[i]
            val keys = LongArray(w.refs.size)
            var n = 0
            for (r in w.refs) {
                val c = nodeIndex[r]
                if (c != NO_COORD) keys[n++] = tileKey(unpackLat7(c), unpackLon7(c))
            }
            keys.copyOf(n).also { it.sort() }.distinctSorted()
        }
        val buckets = HashMap<Long, Bucket>()
        fun bucket(k: Long) = buckets.getOrPut(k) { Bucket() }
        for (i in ways.indices) for (k in wayTiles[i]) if (isCityTile(k)) bucket(k).ways.add(i)
        for (i in nodes.indices) {
            val n = nodes[i]
            if (n.tags.isEmpty() || n.cities == 0) continue
            val k = tileKey(unpackLat7(n.coord), unpackLon7(n.coord))
            if (isCityTile(k)) bucket(k).nodes.add(i)
        }
        for (i in relations.indices) {
            val keys = HashSet<Long>()
            for (m in relations[i].members) when (m.type) {
                ElementType.WAY -> wayIds.binarySearch(m.ref).let { if (it >= 0) wayTiles[it].forEach { k -> keys += k } }
                ElementType.NODE -> nodeIds.binarySearch(m.ref).let {
                    if (it >= 0) keys += tileKey(unpackLat7(nodes[it].coord), unpackLon7(nodes[it].coord))
                }
                ElementType.RELATION -> {}
            }
            for (k in keys) if (isCityTile(k)) bucket(k).relations.add(i)
        }
        val tiles = buckets.keys.sorted()
        timing("area: tiles", t0, "${tiles.size} non-empty z$AREA_TILE_ZOOM tiles touch a city")

        t0 = System.nanoTime()
        val questIndices = areaQuests.filter { qi -> cities.indices.any { engine.enabled[it][qi] } }
        parallelMap(0, tiles.size) { ti ->
            val key = tiles[ti]
            val b = buckets.getValue(key)
            val box = TilePos((key shr 32).toInt(), key.toInt()).asBoundingBox(AREA_TILE_ZOOM)
            val mapData = assemble(box, b.ways.toArray().distinct().map { ways[it] }, b.nodes.toArray().distinct().map { nodes[it] },
                b.relations.toArray().distinct().map { relations[it] })
            for (qi in questIndices) countIn(mapData, box, qi, cityIndexes = null)
        }
        timing("area: quests", t0, "${questIndices.size} quests in ${tiles.size} tiles")
    }

    private val cityIndex = CityIndex(cities)

    /** The runs of one area quest: at asOf; for an age quest also at the resurvey multipliers 0.5 and 2
     *  (see [matchVariants]) and at LONG_AGO for agedOnly. A quest with no age test gives the same result
     *  at any clock, so it has no agedOnly and runs once. */
    private enum class Run { NOW, AT_05, AT_2, LONG_AGO }

    private fun runsOf(qi: Int): List<Run> = if (engine.quests[qi].usesAge) Run.entries else listOf(Run.NOW)

    /** Area quest [qi] on [mapData] in one [run]. The clocks are the current thread's, so the runs of
     *  one quest may go on different threads. */
    private fun runQuest(mapData: MapDataWithGeometry, qi: Int, run: Run): List<Element> {
        val port = engine.quests[qi].area!!
        val quest = FAST_TWINS[port.name] ?: port
        return when (run) {
            Run.NOW -> {
                // a quest may return an element twice (AddMaxHeight: a tunnel that is also below a bridge);
                // the app keys quests by element, so it is one quest
                val now = quest.getApplicableElements(mapData).distinctBy { it.type to it.id }
                if (VERIFY_FAST) {
                    val keys = now.mapTo(HashSet()) { it.type to it.id }
                    if (quest !== port) verifyTwin(port, mapData, keys)
                    if (!engine.quests[qi].usesAge) verifyNoAge(port, quest, mapData, keys)
                }
                now
            }
            Run.AT_05 -> Resurvey.at(Resurvey.HALF) { quest.getApplicableElements(mapData).toList() }
            Run.AT_2 -> Resurvey.at(Resurvey.DOUBLE) { quest.getApplicableElements(mapData).toList() }
            Run.LONG_AGO -> EngineClock.at(EngineClock.LONG_AGO) { quest.getApplicableElements(mapData).toList() }
        }
    }

    /** Runs area quest [qi] on [mapData] (bounded by [box]), one run after the other, and counts it. */
    private fun countIn(mapData: MapDataWithGeometry, box: BoundingBox, qi: Int, cityIndexes: List<Int>?) {
        tally(mapData, box, qi, cityIndexes, runsOf(qi).associateWith { runQuest(mapData, qi, it) })
    }

    /** Counts every result of [results], the runs of area quest [qi], whose position is in [box] in the
     *  cities whose polygon holds it, where [qi] is enabled; [cityIndexes]: only these cities (city mode). */
    private fun tally(
        mapData: MapDataWithGeometry, box: BoundingBox, qi: Int, cityIndexes: List<Int>?, results: Map<Run, List<Element>>,
    ) {
        val now = results.getValue(Run.NOW)
        val at05 = results[Run.AT_05].orEmpty()
        val at2 = results[Run.AT_2].orEmpty()
        if (now.isEmpty() && at05.isEmpty() && at2.isEmpty()) return
        val then = results[Run.LONG_AGO]?.mapTo(HashSet()) { it.type to it.id }
        val masks = LinkedHashMap<Pair<ElementType, Long>, Int>()
        val elements = HashMap<Pair<ElementType, Long>, Element>()
        fun mark(es: List<Element>, bit: Int, agedBit: Int) {
            for (e in es) {
                val k = e.type to e.id
                elements.putIfAbsent(k, e)
                masks[k] = (masks[k] ?: 0) or bit or (if (then == null || k in then) 0 else agedBit)
            }
        }
        mark(now, M_NOW, M_AGED)
        mark(at05, M_05, M_AGED_05)
        mark(at2, M_2, M_AGED_2)
        for ((k, mask) in masks) {
            val e = elements.getValue(k)
            // OsmQuestController: no geometry, no quest; then mayCreateQuest: inside the downloaded bbox
            val g = mapData.getGeometry(e.type, e.id) ?: continue
            val pos = g.center
            if (pos !in box) continue
            val inCities = cityIndexes?.filter { cities[it].polygon.contains(pos.latitude, pos.longitude) }
                ?: cityIndex.citiesAt(pos.latitude, pos.longitude).toList()
            var ids: List<String>? = null
            for (c in inCities) if (engine.enabledAt(c, qi) { ids ?: regionIdsAt(pos).also { ids = it } }) engine.countArea(c, qi, e, pos, mask)
        }
    }

    private fun verifyTwin(port: AreaQuest, mapData: MapDataWithGeometry, twin: Set<Pair<ElementType, Long>>) {
        val original = port.getApplicableElements(mapData).mapTo(HashSet()) { it.type to it.id }
        check(original == twin) {
            "fast twin of ${port.name} differs from the port in ${mapData.boundingBox}: " +
                "only port ${(original - twin).take(5)}, only twin ${(twin - original).take(5)}"
        }
        verifiedTwins.incrementAndGet()
    }
    val verifiedTwins = java.util.concurrent.atomic.AtomicLong()

    /** a quest that says it has no age test must not care about the clock: [runsOf] relies on it */
    private fun verifyNoAge(port: AreaQuest, quest: AreaQuest, mapData: MapDataWithGeometry, now: Set<Pair<ElementType, Long>>) {
        val then = EngineClock.at(EngineClock.LONG_AGO) {
            quest.getApplicableElements(mapData).mapTo(HashSet()) { it.type to it.id }
        }
        check(then == now) { "${port.name} has usesAge = false but depends on the clock in ${mapData.boundingBox}" }
    }

    private fun timing(stage: String, t0: Long, note: String) {
        val s = (System.nanoTime() - t0) / 1e9
        engine.stats.timings[stage] = s
        log("%-22s %6.1f s  %s".format(stage, s, note))
    }

    // ---------------------------------------------------------------------------------------------
    // collection


    private fun collectWays(b: Osmformat.PrimitiveBlock): List<WayRec> {
        require(b.kind() == BlockKind.WAYS)
        val ctx = BlockContext(b)
        val out = ArrayList<WayRec>()
        for (g in b.primitivegroupList) for (w in g.waysList) {
            val rc = w.refsCount
            val refs = LongArray(rc)
            var ref = 0L
            var set = 0
            for (i in 0 until rc) {
                ref += w.getRefs(i); refs[i] = ref
                val c = nodeIndex[ref]
                if (c != NO_COORD) set = citySets.union(set, setAt(unpackLat7(c), unpackLon7(c)))
            }
            if (set == 0) continue
            out += WayRec(w.id, refs, fitTags("area", "way", w.id, tagsOf(w.keysList, w.valsList, ctx.strings)),
                if (w.hasInfo()) w.info.version else 1, w.info.timestamp * ctx.dateGranularity, set)
        }
        return out
    }

    private fun collectNodes(b: Osmformat.PrimitiveBlock, needed: LongArray): List<NodeRec> {
        require(b.kind() == BlockKind.NODES)
        val ctx = BlockContext(b)
        val out = ArrayList<NodeRec>()
        for (g in b.primitivegroupList) {
            if (g.hasDense()) {
                val d = g.dense
                val hasInfo = d.hasDenseinfo()
                val info = d.denseinfo
                val hasKv = d.keysValsCount > 0
                var id = 0L; var lat = 0L; var lon = 0L; var ts = 0L; var kv = 0
                // ids ascend within a block, and so do the needed ids: walk both
                var p = needed.lowerBoundIndex(d.getId(0))
                for (i in 0 until d.idCount) {
                    id += d.getId(i); lat += d.getLat(i); lon += d.getLon(i)
                    if (hasInfo) ts += info.getTimestamp(i)
                    var start = kv; var end = kv
                    if (hasKv) {
                        while (d.getKeysVals(kv) != 0) kv += 2
                        end = kv; kv++
                    }
                    while (p < needed.size && needed[p] < id) p++
                    val isNeeded = p < needed.size && needed[p] == id
                    val lat7 = ctx.lat7(lat); val lon7 = ctx.lon7(lon)
                    if (!isNeeded && end == start) continue
                    val set = setAt(lat7, lon7)
                    if (!isNeeded && set == 0) continue
                    val tags = if (end == start) emptyMap() else TagMap((end - start) / 2).also { m ->
                        var j = start
                        while (j < end) { m.add(ctx.strings[d.getKeysVals(j)], ctx.strings[d.getKeysVals(j + 1)]); j += 2 }
                    }
                    out += NodeRec(id, pack(lat7, lon7), fitTags("area", "node", id, tags), if (hasInfo) info.getVersion(i) else 1,
                        ts * ctx.dateGranularity, set)
                }
            }
            for (n in g.nodesList) {
                val lat7 = ctx.lat7(n.lat); val lon7 = ctx.lon7(n.lon)
                val set = setAt(lat7, lon7)
                val isNeeded = needed.binarySearch(n.id) >= 0
                if (!isNeeded && (n.keysCount == 0 || set == 0)) continue
                out += NodeRec(n.id, pack(lat7, lon7), fitTags("area", "node", n.id, tagsOf(n.keysList, n.valsList, ctx.strings)),
                    if (n.hasInfo()) n.info.version else 1, n.info.timestamp * ctx.dateGranularity, set)
            }
        }
        return out
    }

    private fun collectRelations(b: Osmformat.PrimitiveBlock): List<RelRec> {
        require(b.kind() == BlockKind.RELATIONS)
        val ctx = BlockContext(b)
        val out = ArrayList<RelRec>()
        for (g in b.primitivegroupList) for (r in g.relationsList) {
            if (r.keysCount == 0) continue
            val tags = tagsOf(r.keysList, r.valsList, ctx.strings)
            if (ignoreRelation(tags)) continue // dropped by the app on download
            val members = ArrayList<RelationMember>(r.memidsCount)
            var set = 0
            var memId = 0L
            for (i in 0 until r.memidsCount) {
                memId += r.getMemids(i)
                val type = when (r.getTypes(i)!!) {
                    Osmformat.Relation.MemberType.NODE -> ElementType.NODE
                    Osmformat.Relation.MemberType.WAY -> ElementType.WAY
                    Osmformat.Relation.MemberType.RELATION -> ElementType.RELATION
                }
                members += RelationMember(type, memId, ctx.strings[r.getRolesSid(i)])
                set = citySets.union(set, when (type) {
                    ElementType.WAY -> wayIds.binarySearch(memId).let { if (it >= 0) ways[it].cities else 0 }
                    ElementType.NODE -> nodeIds.binarySearch(memId).let { if (it >= 0) nodes[it].cities else 0 }
                    ElementType.RELATION -> 0
                })
            }
            if (set == 0) continue
            out += RelRec(r.id, members, fitTags("area", "relation", r.id, tags),
                if (r.hasInfo()) r.info.version else 1, r.info.timestamp * ctx.dateGranularity, set)
        }
        return out
    }

    // ---------------------------------------------------------------------------------------------
    // per city

    private fun buildMapData(city: Int): MapDataWithGeometry {
        val inCity = citySets.membersOf(city)
        return assemble(bbox(city), ways.filter { inCity[it.cities] },
            nodes.filter { inCity[it.cities] && it.tags.isNotEmpty() }, relations.filter { inCity[it.cities] },
            parallel = true)
    }

    /** Map data of [areaWays] with all their nodes, [taggedNodes] and [areaRelations] (member way
     *  geometry from the main pass), with SC's own geometry for each. */
    private fun assemble(
        box: BoundingBox, areaWays: List<WayRec>, taggedNodes: List<NodeRec>, areaRelations: List<RelRec>,
        parallel: Boolean = false,
    ): MapDataWithGeometry {
        fun <T> each(n: Int, f: (Int) -> T): List<T> = if (parallel) parallelMap(0, n, f) else (0 until n).map(f)

        // the tagged nodes, then every node of a way, each where it first comes; a way's node that is not
        // in the file stays out, and the way has no geometry
        val refs = each(areaWays.size) { i ->
            val r = areaWays[i].refs
            val found = IntArray(r.size)
            var n = 0
            for (id in r) {
                val at = nodeIds.binarySearch(id)
                if (at >= 0) found[n++] = at
            }
            if (n == r.size) found else found.copyOf(n)
        }
        val wanted = IntArray(taggedNodes.size + refs.sumOf { it.size })
        var filled = 0
        for (n in taggedNodes) wanted[filled++] = nodeIds.binarySearch(n.id)
        for (r in refs) { r.copyInto(wanted, filled); filled += r.size }
        val byNode = LongArray(wanted.size) { (wanted[it].toLong() shl 32) or it.toLong() }
        java.util.Arrays.parallelSort(byNode)
        var distinct = 0
        var previous = -1L
        for (key in byNode) {
            if (key ushr 32 != previous) byNode[distinct++] = key and 0xffffffffL
            previous = key ushr 32
        }
        val firstAt = byNode.copyOf(distinct)
        firstAt.sort()
        val nodeOrder = IntArray(distinct) { wanted[firstAt[it].toInt()] }
        val inHashOrder = hashMapOrder(LongArray(distinct) { nodes[nodeOrder[it]].id })
        val mapNodes = each(distinct) { i ->
            val n = nodes[nodeOrder[inHashOrder[i]]]
            Node(n.id, LatLon(unpackLat7(n.coord) / 1e7, unpackLon7(n.coord) / 1e7), n.tags, n.version, n.timestamp)
        }

        val wayOrder = hashMapOrder(LongArray(areaWays.size) { areaWays[it].id })
        val relationOrder = hashMapOrder(LongArray(areaRelations.size) { areaRelations[it].id })

        val wayGeometries = each(areaWays.size) { i ->
            val w = areaWays[wayOrder[i]]
            val way = Way(w.id, LongArrayAsList(w.refs), w.tags, w.version, w.timestamp)
            val positions = ArrayList<LatLon>(w.refs.size)
            var complete = true
            for (r in w.refs) {
                val c = nodeIndex[r]
                if (c == NO_COORD) { complete = false; break }
                positions += LatLon(unpackLat7(c) / 1e7, unpackLon7(c) / 1e7)
            }
            // SC (MapData.getNodePositions): a way with a node missing has no geometry
            way to if (complete) safeGeometry { geometryCreator.create(way, positions) } else null
        }

        val relationGeometries = each(areaRelations.size) { i ->
            val r = areaRelations[relationOrder[i]]
            val relation = Relation(r.id, r.members, r.tags, r.version, r.timestamp)
            val geometries = HashMap<Long, List<LatLon>>()
            for (m in r.members) {
                if (m.type != ElementType.WAY || m.ref in geometries) continue
                val coords = memberWays[m.ref] ?: continue
                geometries[m.ref] = coords.map { LatLon(unpackLat7(it) / 1e7, unpackLon7(it) / 1e7) }
            }
            relation to if (geometries.isEmpty()) null else safeGeometry { geometryCreator.create(relation, geometries) }
        }
        return ArrayMapData(box, mapNodes, wayGeometries.map { it.first }, wayGeometries.map { it.second },
            relationGeometries.map { it.first }, relationGeometries.map { it.second })
    }

    private inline fun safeGeometry(create: () -> ElementGeometry?): ElementGeometry? =
        try { create() } catch (e: RuntimeException) { null }

    private fun countCity(city: City, mapData: MapDataWithGeometry, questIndices: List<Int>) {
        val box = mapData.boundingBox!!
        engine.dumpAreaElements(city, mapData)
        // every run is its own task: the runs known to be long first, then the age quests' (four runs each),
        // then the rest; a run left for last holds up the whole city
        val tasks = questIndices.sortedWith(compareBy({ longRank(engine.quests[it].name) }, { !engine.quests[it].usesAge }))
            .flatMap { qi -> runsOf(qi).map { qi to it } }
        class Done(val qi: Int, val run: Run, val elements: List<Element>, val seconds: Double)
        fun runTask(task: Pair<Int, Run>): Done {
            val t0 = System.nanoTime()
            val elements = runQuest(mapData, task.first, task.second)
            return Done(task.first, task.second, elements, (System.nanoTime() - t0) / 1e9)
        }
        // the searches twins share start first; a run that needs one is taken only once it is done, so no
        // thread sits waiting for a search another thread is doing
        fun sharedOf(qi: Int) = FAST_TWINS[engine.quests[qi].area!!.name]?.shared.orEmpty()
        val shared = tasks.flatMap { sharedOf(it.first) }.distinct()
        val ordered = tasks
        val needs = ordered.map { t -> sharedOf(t.first).map { shared.indexOf(it) }.toIntArray() }
        val sharedDone = BooleanArray(shared.size)
        val sharedSeconds = DoubleArray(shared.size)
        val trace = if (TASK_TRACE != null) ConcurrentLinkedQueue<Traced>() else null
        val traceT0 = System.nanoTime()
        val zone = engine.zones[city.index]
        val done = parallelWhenReady(shared.size + ordered.size,
            ready = { k -> k < shared.size || needs[k - shared.size].all { sharedDone[it] } }) { k -> EngineZone.at(zone) {
            if (k < shared.size) traced(trace, { "(shared) ${shared[k].name}" }) {
                val t0 = System.nanoTime()
                shared[k].of(mapData)
                sharedSeconds[k] = (System.nanoTime() - t0) / 1e9
                sharedDone[k] = true
                null
            } else ordered[k - shared.size].let { task ->
                traced(trace, { "${engine.quests[task.first].name} ${task.second}" }) { runTask(task) }
            }
        } }.filterNotNull().groupBy { it.qi }
        val questIds = done.keys.toList()
        parallelMap(0, questIds.size) { k ->
            val qi = questIds[k]
            traced(trace, { "(tally) ${engine.quests[qi].name}" }) {
                tally(mapData, box, qi, listOf(city.index), done.getValue(qi).associate { it.run to it.elements })
            }
        }
        if (trace != null) synchronized(TASK_TRACE!!) {
            TASK_TRACE.appendText(trace.joinToString("") {
                "%s\t%s\t%s\t%.3f\t%.3f\t%.3f\n".format(city.id, it.label, it.thread,
                    (it.start - traceT0) / 1e9, (it.end - traceT0) / 1e9, it.cpu / 1e9)
            })
        }
        val seconds = done.map { (qi, runs) -> qi to runs.sumOf { it.seconds } }
        for ((qi, s) in seconds.sortedByDescending { it.second }.take(3)) if (s >= 1.0) {
            log("  %-30s %6.1f s".format(engine.quests[qi].name, s))
            engine.stats.timings["area: ${city.id} ${engine.quests[qi].name}"] = s
        }
        for ((k, s) in sharedSeconds.withIndex()) if (s >= 1.0) {
            log("  %-30s %6.1f s".format("(shared) ${shared[k].name}", s))
            engine.stats.timings["area: ${city.id} shared ${shared[k].name}"] = s
        }
    }
}

/** AreaPass caches the city set of a point by grid cell and a bit per candidate box of the cell, for
 *  cells of up to this many candidates (cell index above, at most 2^18 cells, below 2^63). */
private const val MAX_LOCAL = 24

/** Index of the first element >= [v] in this sorted array. */
private fun LongArray.lowerBoundIndex(v: Long): Int {
    var lo = 0; var hi = size
    while (lo < hi) { val mid = (lo + hi) ushr 1; if (this[mid] < v) lo = mid + 1 else hi = mid }
    return lo
}

/** Growable int list. */
private class IntList {
    private var a = IntArray(16); private var n = 0
    fun add(v: Int) { if (n == a.size) a = a.copyOf(n * 2); a[n++] = v }
    fun toArray() = a.copyOf(n)
}
