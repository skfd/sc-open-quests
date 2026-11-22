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
import de.westnordost.streetcomplete.util.math.enlargedBy
import openquests.custom.AreaQuest
import openquests.fast.FAST_TWINS
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.cos
import kotlin.time.Duration.Companion.days

/** How far around a city's bounding box elements are collected, in metres: more than a z16 tile, so
 *  every tile that touches the city finds all its elements (and, in city mode, the area reaches that
 *  far past the city's bounding box). `-Dopenquests.areaPaddingM=<metres>` sets another ring, for
 *  tests that count small patches (DESIGN.md, "The stream, tier 2"); snapshots use the default. */
val AREA_PADDING_M: Double = System.getProperty("openquests.areaPaddingM")?.toDouble() ?: 1000.0

/** `-Dopenquests.areaPass=false` leaves the area quests uncounted: for a file of single elements with a
 *  world-sized "city", where only the quests decided from the element alone mean anything and a map data
 *  of that box would not fit (DESIGN.md, "The stream, step 5"). Snapshots never set it. */
val AREA_PASS: Boolean = System.getProperty("openquests.areaPass")?.toBoolean() ?: true

/** --dump-state: how many days ahead the area quests' dates are looked for (`-Dopenquests.areaDueDays`; 0: none).
 *  An area quest asks a whole map data at once, so the main pass's halving per element over 40 years does not fit:
 *  each age quest runs once more at asOf plus this many days, and every element open then but not now is dated on
 *  a small map data round its z16 tile (DESIGN.md, "Area quests' dates"). A state's area dates are complete up to
 *  that day only (the sidecar's `areaDueDays`): the stream must reseed before. City mode only. */
val AREA_DUE_DAYS: Int = System.getProperty("openquests.areaDueDays")?.toInt() ?: 64

/** the ring round a candidate's z16 tile that its small map data holds, in metres: the tier-2 recounts found
 *  300 m enough to reproduce a whole city's result (DESIGN.md, "The stream, tier 2") */
const val AREA_DUE_RING_M = 300.0

/** SC's `LatLonRaster(mapData.boundingBox, 0.0005)` (AddHousenumber, AddIsAmenityIndoor and their twins)
 *  allocates a slot per 0.0005 degree square of the box, 4 bytes each: 500M slots is 2 GB a raster. A city
 *  whose map data needs more is refused by name instead of dying in a full collection (DESIGN.md, "Where a
 *  cell run's time goes"). `-Dopenquests.maxRasterSlots` sets another limit, for tests. */
val MAX_RASTER_SLOTS: Long = System.getProperty("openquests.maxRasterSlots")?.toLong() ?: 500_000_000L

/** The box for SC's `LatLonRaster(box, 0.0005)` in our twins of its quests. The raster rounds its north
 *  edge up to a whole cell, so a world cell reaching latitude 90 made it build LatLon(90.0000168, ...) and
 *  die (the world count of 2026-11-12, six files). Held two cells short of the pole: a point in the last
 *  0.001 degree (110 m round the pole) is left out of the raster, where nobody has mapped an address or
 *  an amenity. */
fun rasterBox(box: BoundingBox): BoundingBox =
    if (box.max.latitude <= 90.0 - 0.001) box
    else BoundingBox(box.min, de.westnordost.streetcomplete.data.osm.mapdata.LatLon(90.0 - 0.001, box.max.longitude))

fun rasterSlots(box: BoundingBox): Long =
    kotlin.math.ceil((box.max.latitude - box.min.latitude) / 0.0005).toLong() *
        kotlin.math.ceil((box.max.longitude - box.min.longitude) / 0.0005).toLong()

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

/** `-Dopenquests.assembleTrace=true`: a log line per city's map data with the seconds each step of building
 *  it took, to see which steps run on one thread. Counts do not change. */
private val ASSEMBLE_TRACE = System.getProperty("openquests.assembleTrace") == "true"

/** `-Dopenquests.areaCities=<n>`: how many cities' map data are built and counted at once in city mode
 *  (default 1: one after the other). Each holds its own map data, so the heap must have room for n. */
val AREA_CITIES: Int = System.getProperty("openquests.areaCities")?.toInt() ?: 1

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
    /** every node of the file, from the main pass: with each one's version and time and the tagged ones' tags */
    private val nodes: NodeStore,
    private val unit: AreaUnit = AreaUnit.TILES,
    /** the dictionary of the tag strings in [nodes] */
    private val tagDict: TagDict = TagDict(),
) {
    private val nodeIndex get() = nodes
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
            // a world cell may reach a pole or the antimeridian: the ring's width is taken at 85 degrees at
            // most, and the box stays on the globe (in 1e-7 degrees, 180 already fills most of an Int)
            val dLon = AREA_PADDING_M / (111_320.0 * cos(Math.toRadians(minOf(85.0, maxOf(kotlin.math.abs(p.minLat), kotlin.math.abs(p.maxLat))))))
            south[c.index] = (maxOf(-90.0, p.minLat - dLat) * 1e7).toInt(); north[c.index] = (minOf(90.0, p.maxLat + dLat) * 1e7).toInt()
            west[c.index] = (maxOf(-180.0, p.minLon - dLon) * 1e7).toInt(); east[c.index] = (minOf(180.0, p.maxLon + dLon) * 1e7).toInt()
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

    /** The area pass's ways as columns, sorted by id: way i's nodes are `refs[refStart[i] until refStart[i + 1]]`. */
    private class WayCols(
        val ids: LongArray, val versions: IntArray, val timestamps: LongArray, val cities: IntArray,
        val refStart: IntArray, val refs: LongArray, val tags: TagStore,
    ) {
        val size get() = ids.size
        fun refCount(i: Int) = refStart[i + 1] - refStart[i]
    }

    /** the ways of one block, as [collectWay] is given them */
    class WayChunk(dict: TagDict) {
        var n = 0
        var ids = LongArray(256); var versions = IntArray(256); var timestamps = LongArray(256); var cities = IntArray(256)
        var refEnd = IntArray(256); var tagEnd = IntArray(256)
        var refs = LongArray(2048); var refCount = 0
        val tags = TagChunk(dict)
        fun add(id: Long, version: Int, timestamp: Long, set: Int, t: Map<String, String>) {
            if (n == ids.size) {
                val m = n * 2
                ids = ids.copyOf(m); versions = versions.copyOf(m); timestamps = timestamps.copyOf(m); cities = cities.copyOf(m)
                refEnd = refEnd.copyOf(m); tagEnd = tagEnd.copyOf(m)
            }
            tags.add(t)
            ids[n] = id; versions[n] = version; timestamps[n] = timestamp; cities[n] = set
            refEnd[n] = refCount; tagEnd[n] = tags.n
            n++
        }
        fun ref(id: Long) {
            if (refCount == refs.size) refs = refs.copyOf(refCount * 2)
            refs[refCount++] = id
        }
    }

    private fun wayColumnsOf(chunks: List<WayChunk>): WayCols {
        val n = chunks.sumOf { it.n }
        val refTotal = chunks.sumOf { it.refCount.toLong() }
        val tagTotal = chunks.sumOf { it.tags.n.toLong() }
        require(refTotal <= Int.MAX_VALUE && tagTotal <= Int.MAX_VALUE) { "area: $refTotal way nodes, $tagTotal tag strings: over what one file may hold" }
        val ids = LongArray(n); val versions = IntArray(n); val timestamps = LongArray(n); val cities = IntArray(n)
        val refStart = IntArray(n + 1); val refs = LongArray(refTotal.toInt())
        val tagStart = IntArray(n + 1); val kv = IntArray(tagTotal.toInt())
        var at = 0; var refAt = 0; var tagAt = 0
        for (c in chunks) {
            c.ids.copyInto(ids, at, 0, c.n); c.versions.copyInto(versions, at, 0, c.n)
            c.timestamps.copyInto(timestamps, at, 0, c.n); c.cities.copyInto(cities, at, 0, c.n)
            for (i in 0 until c.n) { refStart[at + i + 1] = refAt + c.refEnd[i]; tagStart[at + i + 1] = tagAt + c.tagEnd[i] }
            c.refs.copyInto(refs, refAt, 0, c.refCount); c.tags.kv.copyInto(kv, tagAt, 0, c.tags.n)
            at += c.n; refAt += c.refCount; tagAt += c.tags.n
        }
        return WayCols(ids, versions, timestamps, cities, refStart, refs, TagStore(tagStart, kv, tagDict.strings()))
    }
    /** A node plays a part in the area pass if a way of some city area has it, or if it has tags; the others
     *  (untagged, on no such way) are in no map data and place no relation, as when they were not kept.
     *  [neededBits]: a bit per node of [nodes], set for the nodes of the ways of [ways]. */
    private val neededBits = java.util.concurrent.atomic.AtomicLongArray(nodes.count / 64 + 1)
    private fun isNeeded(position: Int) = neededBits.get(position ushr 6) and (1L shl (position and 63)) != 0L
    private fun markNeeded(position: Int) {
        val word = position ushr 6; val bit = 1L shl (position and 63)
        if (neededBits.get(word) and bit == 0L) neededBits.getAndUpdate(word) { it or bit }
    }

    /** per tagged node ([NodeStore.tagged]), its [CitySets] id */
    private lateinit var taggedCities: IntArray

    /** the [CitySets] id a relation gets from member node [id]: its boxes if it plays a part, else none */
    private fun memberNodeSet(id: Long): Int {
        val p = nodes.indexOf(id)
        if (p < 0) return 0
        val k = nodes.taggedIndexOf(p)
        if (k >= 0) return taggedCities[k]
        return if (isNeeded(p)) nodes.coords[p].let { setAt(unpackLat7(it), unpackLon7(it)) } else 0
    }

    /** the position of member node [id] if it is in some map data (on a way of a city area, or tagged in a
     *  city's box), else -1 */
    private fun memberNodeAt(id: Long): Int {
        val p = nodes.indexOf(id)
        if (p < 0) return -1
        if (isNeeded(p)) return p
        val k = nodes.taggedIndexOf(p)
        return if (k >= 0 && taggedCities[k] != 0) p else -1
    }

    private class RelRec(val id: Long, val members: List<RelationMember>, val tags: Map<String, String>, val version: Int, val timestamp: Long, val cities: Int)

    private lateinit var ways: WayCols               // sorted by id
    /** packed coordinates of the member ways of tagged relations, from the main pass */
    private lateinit var memberWays: SortedIdMap<LongArray>
    private lateinit var wayIds: LongArray
    private lateinit var relations: List<RelRec>
    private val geometryCreator = ElementGeometryCreator()

    /** [wayChunks]: the ways of each way block in the file's order, as the main pass handed them to [collectWay]. */
    fun run(memberWays: SortedIdMap<LongArray>, wayChunks: MutableList<WayChunk>) {
        if (areaQuests.isEmpty()) return
        if (!AREA_PASS) { log("area pass skipped (-Dopenquests.areaPass=false): the ${areaQuests.size} area quests are not counted"); return }
        this.memberWays = memberWays
        require(wayChunks.size == relStart - wayStart) { "area: ${wayChunks.size} way blocks collected of ${relStart - wayStart}" }
        var t0 = System.nanoTime()
        ways = wayColumnsOf(wayChunks)
        wayChunks.clear()
        wayIds = ways.ids
        timing("area: ways", t0, "${ways.size} ways touch a city area")

        t0 = System.nanoTime()
        require(nodes.keep) { "the area pass needs the main pass's nodes kept" }
        taggedCities = IntArray(nodes.tagged.size)
        parallelMap(0, (taggedCities.size + 65535) / 65536) { c ->
            for (k in c * 65536 until minOf(taggedCities.size, (c + 1) * 65536)) {
                val coord = nodes.coords[nodes.tagged[k]]
                taggedCities[k] = setAt(unpackLat7(coord), unpackLon7(coord))
            }
        }
        timing("area: nodes", t0, "${nodes.tagged.size} tagged nodes placed (of ${nodes.count} nodes)")

        t0 = System.nanoTime()
        relations = parallelMap(relStart, blobs.size) { collectRelations(decodeBlock(blobs[it])) }.flatten()
        timing("area: relations", t0, "${relations.size} tagged relations")
        // nothing reads the file's blocks after this: let go of them (a file's worth of memory while the cities run)
        (blobs as? MutableList<ByteArray>)?.clear()

        if (unit == AreaUnit.TILES) { runTiles(); return }
        fun one(c: City) {
            // with --dump-elements, only the dumped city
            if (engine.dumpElementsCity >= 0 && c.index != engine.dumpElementsCity) return
            val t0 = System.nanoTime()
            val enabledQuests = areaQuests.filter { engine.enabled[c.index][it] }
            if (enabledQuests.isEmpty()) return
            val mapData = buildMapData(c.index)
            val built = (System.nanoTime() - t0) / 1e9
            countCity(c, mapData, enabledQuests)
            engine.stats.timings["area: ${c.id}"] = (System.nanoTime() - t0) / 1e9
            log("area: %-18s %6.1f s  (map data %.1f s: %d nodes, %d ways, %d relations)".format(
                c.id, (System.nanoTime() - t0) / 1e9, built, mapData.nodes.size, mapData.ways.size, mapData.relations.size))
        }
        if (AREA_CITIES <= 1 || cities.size == 1) for (c in cities) one(c)
        else {
            // several cities under way at once: a city's runs keep few threads busy for most of its time
            // (it waits for its longest run), so the next city's fill the rest. Counts do not depend on it.
            t0 = System.nanoTime()
            val next = AtomicInteger()
            val failure = java.util.concurrent.atomic.AtomicReference<Throwable>()
            val drivers = List(minOf(AREA_CITIES, cities.size)) { d ->
                Thread({
                    while (failure.get() == null) {
                        val i = next.getAndIncrement()
                        if (i >= cities.size) break
                        try { logTogether { one(cities[i]) } } catch (t: Throwable) { failure.compareAndSet(null, t) }
                    }
                }, "area-city-$d").apply { start() }
            }
            drivers.forEach { it.join() }
            failure.get()?.let { throw it }
            timing("area: cities", t0, "${cities.size} cities, $AREA_CITIES at once")
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
            val keys = LongArray(ways.refCount(i))
            var n = 0
            for (j in ways.refStart[i] until ways.refStart[i + 1]) {
                val c = nodeIndex[ways.refs[j]]
                if (c != NO_COORD) keys[n++] = tileKey(unpackLat7(c), unpackLon7(c))
            }
            keys.copyOf(n).also { it.sort() }.distinctSorted()
        }
        val buckets = HashMap<Long, Bucket>()
        fun bucket(k: Long) = buckets.getOrPut(k) { Bucket() }
        for (i in 0 until ways.size) for (k in wayTiles[i]) if (isCityTile(k)) bucket(k).ways.add(i)
        for (t in nodes.tagged.indices) {
            if (taggedCities[t] == 0) continue
            val i = nodes.tagged[t]
            val k = tileKey(unpackLat7(nodes.coords[i]), unpackLon7(nodes.coords[i]))
            if (isCityTile(k)) bucket(k).nodes.add(i)
        }
        for (i in relations.indices) {
            val keys = HashSet<Long>()
            for (m in relations[i].members) when (m.type) {
                ElementType.WAY -> wayIds.binarySearch(m.ref).let { if (it >= 0) wayTiles[it].forEach { k -> keys += k } }
                ElementType.NODE -> memberNodeAt(m.ref).let {
                    if (it >= 0) keys += tileKey(unpackLat7(nodes.coords[it]), unpackLon7(nodes.coords[it]))
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
            val mapData = assemble(box, b.ways.toArray().distinct().toIntArray(), b.nodes.toArray().distinct().toIntArray(),
                b.relations.toArray().distinct().map { relations[it] })
            for (qi in questIndices) countIn(mapData, box, qi, cityIndexes = null)
        }
        timing("area: quests", t0, "${questIndices.size} quests in ${tiles.size} tiles")
    }

    private val cityIndex = CityIndex(cities)

    /** The runs of one area quest: at asOf; for an age quest also at the resurvey multipliers 0.5 and 2
     *  (see [matchVariants]) and at LONG_AGO for agedOnly. A quest with no age test gives the same result
     *  at any clock, so it has no agedOnly and runs once. */
    private enum class Run { NOW, AT_05, AT_2, LONG_AGO, AHEAD }

    /** with --dump-state in city mode an age quest also runs at asOf + [AREA_DUE_DAYS] ([Run.AHEAD]): its dates */
    private val dating = engine.state != null && AREA_DUE_DAYS > 0 && unit == AreaUnit.CITY

    private fun runsOf(qi: Int): List<Run> = when {
        !engine.quests[qi].usesAge -> listOf(Run.NOW)
        dating -> Run.entries
        else -> Run.entries - Run.AHEAD
    }

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
            Run.AHEAD -> EngineClock.at(EngineClock.asOf + AREA_DUE_DAYS.days) { quest.getApplicableElements(mapData).toList() }
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
    ): List<Candidate> {
        val now = results.getValue(Run.NOW)
        val at05 = results[Run.AT_05].orEmpty()
        val at2 = results[Run.AT_2].orEmpty()
        val candidates = candidatesOf(mapData, box, qi, cityIndexes, now, results[Run.AHEAD].orEmpty())
        if (now.isEmpty() && at05.isEmpty() && at2.isEmpty()) return candidates
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
        return candidates
    }

    /** An element that area quest [qi] gives at asOf + [AREA_DUE_DAYS] and not at asOf, in city [city]: its day is
     *  looked for by [dateCandidates]. */
    private class Candidate(val qi: Int, val element: Element, val pos: LatLon, val city: Int)

    /** the [Run.AHEAD] results not in [now], with geometry, inside [box], in a city where [qi] is enabled */
    private fun candidatesOf(
        mapData: MapDataWithGeometry, box: BoundingBox, qi: Int, cityIndexes: List<Int>?, now: List<Element>, ahead: List<Element>,
    ): List<Candidate> {
        if (ahead.isEmpty()) return emptyList()
        val nowKeys = now.mapTo(HashSet()) { it.type to it.id }
        val out = ArrayList<Candidate>()
        val seen = HashSet<Pair<ElementType, Long>>()
        for (e in ahead) {
            val k = e.type to e.id
            if (k in nowKeys || !seen.add(k)) continue
            val pos = mapData.getGeometry(e.type, e.id)?.center ?: continue
            if (pos !in box) continue
            val inCities = cityIndexes?.filter { cities[it].polygon.contains(pos.latitude, pos.longitude) }
                ?: cityIndex.citiesAt(pos.latitude, pos.longitude).toList()
            var ids: List<String>? = null
            for (c in inCities) if (engine.enabledAt(c, qi) { ids ?: regionIdsAt(pos).also { ids = it } }) out += Candidate(qi, e, pos, c)
        }
        return out
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


    fun newWayChunk() = WayChunk(tagDict)

    /** The padded city boxes that hold a node of the way whose nodes' packed coordinates are [coords] (a node
     *  the file lacks is [NO_COORD]), as a [citySets] id: 0 when the way is in no city's map data. */
    fun citySetOf(coords: LongArray, n: Int): Int {
        var set = 0
        for (i in 0 until n) {
            val c = coords[i]
            if (c != NO_COORD) set = citySets.union(set, setAt(unpackLat7(c), unpackLon7(c)))
        }
        return set
    }

    /** A way of some city's map data ([set] from [citySetOf], not 0), from the main pass's read of its block:
     *  kept with all its nodes, each of which then plays a part ([at]: its place in [nodes], or -1). */
    fun collectWay(out: WayChunk, id: Long, version: Int, timestamp: Long, set: Int, refs: LongArray, at: IntArray, n: Int, tags: Map<String, String>) {
        for (i in 0 until n) {
            out.ref(refs[i])
            if (at[i] >= 0) markNeeded(at[i])
        }
        out.add(id, version, timestamp, set, tags)
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
                    ElementType.WAY -> wayIds.binarySearch(memId).let { if (it >= 0) ways.cities[it] else 0 }
                    ElementType.NODE -> memberNodeSet(memId)
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
    // area quests' dates (--dump-state)

    /**
     * The day each of [candidates] opens, found on a small map data: the candidate's z16 tile with a ring of
     * [AREA_DUE_RING_M], as the API's map call returns it (every way of the city's with a node in the tiles the ring
     * reaches, with all its nodes; the tagged nodes and tagged relations there). The SC port (not its fast twin) is
     * asked at asOf and at asOf + [AREA_DUE_DAYS]: where that disagrees with the whole city's runs the element stays
     * undated (counted). Then the days in between are halved, the candidates of a tile and quest together, one run
     * per distinct middle day. Each date is a [StateDump.due] row at the default setting.
     */
    private fun dateCandidates(city: City, candidates: List<Candidate>) {
        engine.state?.areaDueDays = AREA_DUE_DAYS
        if (candidates.isEmpty()) return
        val t0 = System.nanoTime()
        fun key(lat7: Int, lon7: Int) = tileKey(lat7, lon7)
        val byTile = candidates.groupBy { key((it.pos.latitude * 1e7).toInt(), (it.pos.longitude * 1e7).toInt()) }
        fun ringOf(k: Long): BoundingBox =
            TilePos((k shr 32).toInt(), k.toInt()).asBoundingBox(AREA_TILE_ZOOM).enlargedBy(AREA_DUE_RING_M)
        val needed = HashSet<Long>()
        val tilesOf = byTile.keys.associateWith { k ->
            ringOf(k).enclosingTilesRect(AREA_TILE_ZOOM).asTilePosSequence()
                .map { (it.x.toLong() shl 32) or (it.y.toLong() and 0xffffffffL) }.toList().also { needed += it }
        }
        // the city's records in the needed tiles, as runTiles buckets them
        val inCity = citySets.membersOf(city.index)
        val wayTiles: List<LongArray> = parallelMap(0, ways.size) { i ->
            if (!inCity[ways.cities[i]]) return@parallelMap LongArray(0)
            val keys = LongArray(ways.refCount(i))
            var n = 0
            for (j in ways.refStart[i] until ways.refStart[i + 1]) {
                val c = nodeIndex[ways.refs[j]]
                if (c == NO_COORD) continue
                val k = key(unpackLat7(c), unpackLon7(c))
                if (k in needed) keys[n++] = k
            }
            keys.copyOf(n).also { it.sort() }.distinctSorted()
        }
        val buckets = HashMap<Long, Bucket>()
        fun bucket(k: Long) = buckets.getOrPut(k) { Bucket() }
        for (i in 0 until ways.size) for (k in wayTiles[i]) bucket(k).ways.add(i)
        for (t in nodes.tagged.indices) {
            if (!inCity[taggedCities[t]]) continue
            val i = nodes.tagged[t]
            val k = key(unpackLat7(nodes.coords[i]), unpackLon7(nodes.coords[i]))
            if (k in needed) bucket(k).nodes.add(i)
        }
        for (i in relations.indices) {
            if (!inCity[relations[i].cities]) continue
            val keys = HashSet<Long>()
            for (m in relations[i].members) when (m.type) {
                ElementType.WAY -> wayIds.binarySearch(m.ref).let { if (it >= 0) wayTiles[it].forEach { k -> keys += k } }
                ElementType.NODE -> memberNodeAt(m.ref).let {
                    if (it >= 0) key(unpackLat7(nodes.coords[it]), unpackLon7(nodes.coords[it])).let { k -> if (k in needed) keys += k }
                }
                ElementType.RELATION -> {}
            }
            for (k in keys) bucket(k).relations.add(i)
        }
        val groups = byTile.entries.toList()
        val zone = engine.zones[city.index]
        val dated = AtomicInteger(); val undated = AtomicInteger(); val runs = AtomicInteger()
        parallelMap(0, groups.size) { gi ->
            EngineZone.at(zone) {
                val (k, cs) = groups[gi]
                val w = java.util.TreeSet<Int>(); val n = java.util.TreeSet<Int>(); val r = java.util.TreeSet<Int>()
                for (t in tilesOf.getValue(k)) buckets[t]?.let { b ->
                    b.ways.toArray().forEach { w += it }; b.nodes.toArray().forEach { n += it }; b.relations.toArray().forEach { r += it }
                }
                val small = assemble(ringOf(k), w.toIntArray(), n.toIntArray(), r.map { relations[it] })
                dateIn(small, cs, dated, undated, runs)
            }
        }
        log("area dates: %-18s %d candidates in %d tiles: %d dated, %d undated (the small map data disagreed at asOf or at +%d days); %d runs, %.1f s".format(
            city.id, candidates.size, groups.size, dated.get(), undated.get(), AREA_DUE_DAYS, runs.get(), (System.nanoTime() - t0) / 1e9))
        engine.stats.timings["area dates: ${city.id}"] = (System.nanoTime() - t0) / 1e9
    }

    /** the candidates [cs] of one small map data, dated by halving (see [dateCandidates]) */
    private fun dateIn(small: MapDataWithGeometry, cs: List<Candidate>, dated: AtomicInteger, undated: AtomicInteger, runs: AtomicInteger) {
        for ((qi, qcs) in cs.groupBy { it.qi }) {
            val port = engine.quests[qi].area!!
            fun keysAt(day: Int): Set<Pair<ElementType, Long>> {
                runs.incrementAndGet()
                return EngineClock.at(EngineClock.asOf + day.days) { port.getApplicableElements(small).mapTo(HashSet()) { it.type to it.id } }
            }
            val now = keysAt(0)
            val ahead = keysAt(AREA_DUE_DAYS)
            val live = qcs.filter { (it.element.type to it.element.id).let { k -> k in ahead && k !in now } }
            undated.addAndGet(qcs.size - live.size)
            val lo = IntArray(live.size)
            val hi = IntArray(live.size) { AREA_DUE_DAYS }
            while (true) {
                val open = live.indices.filter { hi[it] - lo[it] > 1 }
                if (open.isEmpty()) break
                for ((mid, idx) in open.groupBy { (lo[it] + hi[it]) ushr 1 }) {
                    val set = keysAt(mid)
                    for (i in idx) if ((live[i].element.type to live[i].element.id) in set) hi[i] = mid else lo[i] = mid
                }
            }
            for ((i, c) in live.withIndex()) {
                engine.dueArea(c.qi, c.element, c.pos, ((EngineClock.asOf + hi[i].days).epochSeconds / 60).toInt())
                dated.incrementAndGet()
            }
        }
    }

    // ---------------------------------------------------------------------------------------------
    // per city

    private fun buildMapData(city: Int): MapDataWithGeometry {
        // the raster's squares start at the box's corner, and SC's point-in-polygon test counts some points
        // outside a polygon (on a vertex's latitude) as inside, so which squares a query reads moves counts:
        // the box cannot be cut down to the data without changing them (DESIGN.md, "The whole planet, made
        // ready"). Too large a box is refused instead.
        val box = bbox(city)
        val slots = rasterSlots(box)
        require(slots <= MAX_RASTER_SLOTS) {
            "area: ${cities[city].id}'s box spans %.2f by %.2f degrees, a LatLonRaster of %,d slots (at most %,d): cut it smaller".format(
                box.max.latitude - box.min.latitude, box.max.longitude - box.min.longitude, slots, MAX_RASTER_SLOTS)
        }
        val inCity = citySets.membersOf(city)
        // the city's ways and tagged nodes, read off int columns
        val wayCities = ways.cities
        var n = 0
        for (set in wayCities) if (inCity[set]) n++
        val areaWays = IntArray(n)
        n = 0
        for (i in wayCities.indices) if (inCity[wayCities[i]]) areaWays[n++] = i
        n = 0
        for (set in taggedCities) if (inCity[set]) n++
        val tagged = IntArray(n)
        n = 0
        for (t in taggedCities.indices) if (inCity[taggedCities[t]]) tagged[n++] = nodes.tagged[t]
        return assemble(box, areaWays, tagged, relations.filter { inCity[it.cities] }, parallel = true)
    }

    /** Map data of the ways at [areaWays] (indices into [ways]) with all their nodes, the nodes at [taggedNodes]
     *  (indices into [nodes]; both ascending) and [areaRelations] (member way geometry from the main pass), with
     *  SC's own geometry for each. */
    private fun assemble(
        box: BoundingBox, areaWays: IntArray, taggedNodes: IntArray, areaRelations: List<RelRec>,
        parallel: Boolean = false,
    ): MapDataWithGeometry {
        fun <T> each(n: Int, f: (Int) -> T): List<T> = if (parallel) parallelMap(0, n, f) else (0 until n).map(f)
        fun eachDo(n: Int, f: (Int) -> Unit) {
            if (parallel) java.util.stream.IntStream.range(0, n).parallel().forEach { f(it) } else for (i in 0 until n) f(i)
        }
        // -Dopenquests.assembleTrace=true: a line per city's map data with the seconds of each step
        val steps = if (ASSEMBLE_TRACE && parallel) StringBuilder() else null
        var stepStart = System.nanoTime()
        fun step(name: String) {
            if (steps == null) return
            val now = System.nanoTime()
            steps.append(" %s %.2f".format(name, (now - stepStart) / 1e9))
            stepStart = now
        }

        // the tagged nodes, then every node of a way, each where it first comes; a way's node that is not
        // in the file stays out, and the way has no geometry
        val refs = each(areaWays.size) { i ->
            val w = areaWays[i]
            val found = IntArray(ways.refCount(w))
            var n = 0
            var at = -1
            for (j in ways.refStart[w] until ways.refStart[w + 1]) {
                at = nodes.indexOfAfter(ways.refs[j], at)
                if (at >= 0) found[n++] = at
            }
            if (n == found.size) found else found.copyOf(n)
        }
        step("refs")
        val nodeOrder = firstSeen(taggedNodes, refs, nodes.count)
        val distinct = nodeOrder.size
        step("firstSeen")
        val inHashOrder = hashMapOrder(LongArray(distinct) { nodes.ids[nodeOrder[it]] })
        step("nodeOrder")
        // each node's id as it is made: read on the threads that make the nodes, not once more on one
        val mapNodeIds = LongArray(distinct)
        val mapNodes = each(distinct) { i ->
            val n = nodeOrder[inHashOrder[i]]
            val c = nodes.coords[n]
            val id = nodes.ids[n]
            mapNodeIds[i] = id
            Node(id, LatLon(unpackLat7(c) / 1e7, unpackLon7(c) / 1e7), nodes.tagsOf(n), nodes.versions[n], nodes.timestampOf(n))
        }

        // where each node is in mapNodes: a way's geometry takes its nodes' own positions instead of a second
        // object per node of every way (a city's 25M)
        step("nodes")
        val nodeLookup = LongIndex(mapNodeIds)
        step("nodeLookup")

        val wayOrder = hashMapOrder(LongArray(areaWays.size) { ways.ids[areaWays[it]] })
        val relationOrder = hashMapOrder(LongArray(areaRelations.size) { areaRelations[it].id })
        step("wayOrder")

        // each way and its geometry put where it belongs by the thread that made it (a pair each and two lists
        // read off the pairs on one thread were a tenth of a city's map data time)
        val wayArray = arrayOfNulls<Way>(areaWays.size)
        val wayGeometryArray = arrayOfNulls<ElementGeometry>(areaWays.size)
        eachDo(areaWays.size) { i ->
            val w = areaWays[wayOrder[i]]
            val from = ways.refStart[w]; val count = ways.refCount(w)
            val way = Way(ways.ids[w], LongArrayAsList(ways.refs, from, count), ways.tags.tagsOf(w), ways.versions[w], ways.timestamps[w])
            val positions = ArrayList<LatLon>(count)
            var complete = true
            for (j in from until from + count) {
                val at = nodeLookup[ways.refs[j]]
                if (at < 0) { complete = false; break }
                positions += mapNodes[at].position
            }
            // SC (MapData.getNodePositions): a way with a node missing has no geometry
            wayArray[i] = way
            wayGeometryArray[i] = if (complete) safeGeometry { geometryCreator.create(way, positions) } else null
        }

        step("ways")
        val relationGeometries = each(areaRelations.size) { i ->
            val r = areaRelations[relationOrder[i]]
            relationCache?.get(r.id)?.get() ?: relationWithGeometry(r).also {
                relationCache?.put(r.id, java.lang.ref.SoftReference(it))
            }
        }
        step("relations")
        @Suppress("UNCHECKED_CAST")
        val wayList = (wayArray as Array<Way>).asList()
        val wayGeometryList = wayGeometryArray.asList()
        step("lists")
        return ArrayMapData(box, mapNodes, wayList, wayGeometryList,
            relationGeometries.map { it.first }, relationGeometries.map { it.second }, eagerKeys = parallel, nodeIndex = nodeLookup).also {
            step("indexes")
            if (steps != null) log("area: map data of ${mapNodes.size} nodes, ${wayList.size} ways:$steps")
        }
    }

    /** A relation and SC's geometry of it, from all its member ways (the main pass's [memberWays], whole, wherever
     *  they lie): nothing of it depends on the city, so it is the same for every city that holds the relation. */
    private fun relationWithGeometry(r: RelRec): Pair<Relation, ElementGeometry?> {
        val relation = Relation(r.id, r.members, r.tags, r.version, r.timestamp)
        val geometries = HashMap<Long, List<LatLon>>()
        for (m in r.members) {
            if (m.type != ElementType.WAY || m.ref in geometries) continue
            val coords = memberWays[m.ref] ?: continue
            geometries[m.ref] = coords.map { LatLon(unpackLat7(it) / 1e7, unpackLon7(it) / 1e7) }
        }
        return relation to if (geometries.isEmpty()) null else safeGeometry { geometryCreator.create(relation, geometries) }
    }

    /** Each relation's [relationWithGeometry], kept for the run. A world day's tier 2 runs thousands of small
     *  rectangle cities over one file, and a long relation (a coastline, a boundary, a route) is in hundreds of them:
     *  made anew for each, it was 96 to 100% of such a run (2026-11-14: f31, 2,234 rectangles, 932 of 959 s). Soft
     *  references: the heap may take them back, and the relation is made again. -Dopenquests.relationCache=false
     *  turns it off. */
    private val relationCache: java.util.concurrent.ConcurrentHashMap<Long, java.lang.ref.SoftReference<Pair<Relation, ElementGeometry?>>>? =
        if (System.getProperty("openquests.relationCache", "true").toBoolean()) java.util.concurrent.ConcurrentHashMap() else null

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
        val candidates = parallelMap(0, questIds.size) { k ->
            val qi = questIds[k]
            traced(trace, { "(tally) ${engine.quests[qi].name}" }) {
                tally(mapData, box, qi, listOf(city.index), done.getValue(qi).associate { it.run to it.elements })
            }
        }.flatten()
        if (dating) dateCandidates(city, candidates)
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

/** The numbers of [first] and then of each of [rest], each once, where it first comes; all in 0 until [limit]. */
internal fun firstSeen(first: IntArray, rest: List<IntArray>, limit: Int): IntArray {
    val total = first.size.toLong() + rest.sumOf { it.size.toLong() }
    require(total <= Int.MAX_VALUE) { "$total nodes asked of one map data: over what it may hold" }
    // a bit per number of the range costs limit / 8 bytes to clear: for a city, less than sorting; for a tile of
    // a few hundred nodes of a whole file's, far more
    return if (total >= limit / FIRST_SEEN_BITS_FROM) firstSeenByBits(first, rest, limit, total.toInt())
    else firstSeenBySort(first, rest, total.toInt())
}

/** [firstSeen] marks numbers in a bit set when it is asked for at least a 1/this of the range */
private const val FIRST_SEEN_BITS_FROM = 256

internal fun firstSeenByBits(first: IntArray, rest: List<IntArray>, limit: Int, total: Int): IntArray {
    val seen = LongArray((limit + 63) ushr 6)
    val out = IntArray(total)
    var n = 0
    for (p in first) {
        val bit = 1L shl (p and 63)
        if (seen[p ushr 6] and bit == 0L) { seen[p ushr 6] = seen[p ushr 6] or bit; out[n++] = p }
    }
    for (r in rest) for (p in r) {
        val bit = 1L shl (p and 63)
        if (seen[p ushr 6] and bit == 0L) { seen[p ushr 6] = seen[p ushr 6] or bit; out[n++] = p }
    }
    return if (n == total) out else out.copyOf(n)
}

internal fun firstSeenBySort(first: IntArray, rest: List<IntArray>, total: Int): IntArray {
    val wanted = IntArray(total)
    var filled = 0
    first.copyInto(wanted, filled); filled += first.size
    for (r in rest) { r.copyInto(wanted, filled); filled += r.size }
    val byNumber = LongArray(wanted.size) { (wanted[it].toLong() shl 32) or it.toLong() }
    java.util.Arrays.parallelSort(byNumber)
    var distinct = 0
    var previous = -1L
    for (key in byNumber) {
        if (key ushr 32 != previous) byNumber[distinct++] = key and 0xffffffffL
        previous = key ushr 32
    }
    val firstAt = byNumber.copyOf(distinct)
    java.util.Arrays.parallelSort(firstAt)
    return IntArray(distinct) { wanted[firstAt[it].toInt()] }
}

/** Growable int list. */
private class IntList {
    private var a = IntArray(16); private var n = 0
    fun add(v: Int) { if (n == a.size) a = a.copyOf(n * 2); a[n++] = v }
    fun toArray() = a.copyOf(n)
}
