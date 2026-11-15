package openquests.fast

import openquests.ArrayMapData
import openquests.candidates
import de.westnordost.streetcomplete.data.elementfilter.ElementFilterExpression
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.geometry.ElementPolygonsGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.filter
import de.westnordost.streetcomplete.osm.places.isPlace
import de.westnordost.streetcomplete.osm.things.isThing
import de.westnordost.streetcomplete.util.math.contains
import de.westnordost.streetcomplete.util.math.isInMultipolygon
import kotlin.math.floor

/** Positions by grid cell: [inBounds] gives the index of every position the bounds contain (SC's
 *  BoundingBox.contains), ascending. */
class PointGrid(private val points: List<LatLon>, private val cellDegrees: Double = 0.002) {
    private val cells = HashMap<Long, MutableList<Int>>()

    private fun cell(d: Double) = floor(d / cellDegrees).toInt()
    private fun key(x: Int, y: Int) = gridKey(x, y)

    init {
        for ((i, p) in points.withIndex()) cells.getOrPut(key(cell(p.longitude), cell(p.latitude))) { ArrayList(4) }.add(i)
    }

    fun inBounds(b: BoundingBox): IntArray {
        val x0 = cell(b.min.longitude); val x1 = cell(b.max.longitude)
        val y0 = cell(b.min.latitude); val y1 = cell(b.max.latitude)
        // across the 180th meridian, or more cells than points: look at every point
        if (b.crosses180thMeridian || (x1 - x0 + 1).toLong() * (y1 - y0 + 1) > points.size) {
            return points.indices.filter { points[it] in b }.toIntArray()
        }
        val out = ArrayList<Int>()
        for (x in x0..x1) for (y in y0..y1) cells[key(x, y)]?.let { for (i in it) if (points[i] in b) out.add(i) }
        return out.toIntArray().also { it.sort() }
    }
}

/** The grid cells any of [bounds] touches: [mayHold] is true for every position one of the bounds contains,
 *  and for some others. Across the 180th meridian, or with too many cells, it is true everywhere. */
class NearBounds(bounds: List<BoundingBox>, private val cellDegrees: Double = 0.01) {
    private val everywhere: Boolean
    /** open-addressed cell keys; [EMPTY] for a free slot */
    private val slots: LongArray

    private fun cell(d: Double) = floor(d / cellDegrees).toInt()
    private fun key(x: Int, y: Int) = (x.toLong() shl 32) or (y.toLong() and 0xffffffffL)
    private fun slotOf(key: Long) = ((key * -0x61c8864680b583ebL) ushr 40).toInt() and (slots.size - 1)

    init {
        var cells = 0L
        var wide = false
        for (b in bounds) {
            if (b.crosses180thMeridian) wide = true
            cells += (cell(b.max.longitude) - cell(b.min.longitude) + 1L) * (cell(b.max.latitude) - cell(b.min.latitude) + 1L)
        }
        everywhere = wide || cells > MAX_CELLS
        var size = 16
        if (!everywhere) while (size < cells * 2) size *= 2
        slots = LongArray(size) { EMPTY }
        if (!everywhere) for (b in bounds) {
            for (x in cell(b.min.longitude)..cell(b.max.longitude)) for (y in cell(b.min.latitude)..cell(b.max.latitude)) {
                val k = key(x, y)
                var s = slotOf(k)
                while (slots[s] != EMPTY && slots[s] != k) s = (s + 1) and (slots.size - 1)
                slots[s] = k
            }
        }
    }

    fun mayHold(p: LatLon): Boolean {
        if (everywhere) return true
        val k = key(cell(p.longitude), cell(p.latitude))
        var s = slotOf(k)
        while (true) {
            val v = slots[s]
            if (v == k) return true
            if (v == EMPTY) return false
            s = (s + 1) and (slots.size - 1)
        }
    }

    private companion object {
        const val EMPTY = Long.MIN_VALUE
        const val MAX_CELLS = 2_000_000L
    }
}

/** Every element with a level tag, as SC's getMultiLevelMallGeometries walks them, with its center and
 *  level; one without geometry is left out, as SC's loop skips it. */
class LevelPoints(val positions: List<LatLon>, val levels: List<String>, val anyLevel: Boolean) {
    val grid = PointGrid(positions)
}

/** The level points once per map data. It reads no clock, and AddLevel and AddLevelThing both start from
 *  it: SC's version looks up the geometry of every element with a level tag again for every mall (Moscow's
 *  AddLevelThing 52-86 s). */
val LEVEL_POINTS = PerMapData("level points") { mapData ->
    val positions = ArrayList<LatLon>(); val levels = ArrayList<String>()
    var anyLevel = false
    for (element in mapData) {
        val level = element.tags["level"] ?: continue
        anyLevel = true
        val pos = mapData.getGeometry(element.type, element.id)?.center ?: continue
        positions.add(pos); levels.add(level)
    }
    LevelPoints(positions, levels, anyLevel)
}

/**
 * SC's getMultiLevelMallGeometries (ported/.../level/LevelUtils.kt), with one change: a mall looks only at
 * the level points its bounds contain, from [LEVEL_POINTS], instead of all of them. SC skips the others at
 * its bounds check, and its answer (two different levels inside the mall) does not depend on the order.
 */
private fun getMultiLevelMallGeometries(
    mallGeometries: List<ElementPolygonsGeometry>,
    mapData: MapDataWithGeometry
): List<ElementPolygonsGeometry> {
    val points = LEVEL_POINTS.of(mapData)
    if (!points.anyLevel) return emptyList()

    return mallGeometries.filter { mallGeometry ->
        var level: String? = null
        for (i in points.grid.inBounds(mallGeometry.bounds)) {
            if (!points.positions[i].isInMultipolygon(mallGeometry.polygons)) continue

            if (level != null) {
                if (level != points.levels[i]) return@filter true
            } else {
                level = points.levels[i]
            }
        }
        return@filter false
    }
}

/**
 * The second half of SC's AddLevel and AddLevelThing: every element matching [filter] and [isCandidate]
 * whose center is inside one of [malls], each once, in the order SC adds them (by mall, then in map order).
 * Three changes that give the same result: a mall looks only at the candidates its bounds contain, from a
 * [PointGrid]; [isCandidate] (SC's isPlace or isThing, the costly part) is asked only of an element
 * inside a mall, not of all of them up front; and an element near no mall at all ([NearBounds]) is left out
 * before anything is asked of it or kept. AddLevelThing's filter holds for almost every node, untagged ones
 * too, so without the last a city's every node went into the lists and the grid for a handful of malls (the
 * longest run of a cell of 14M nodes, and what its run phase waited for).
 */
private fun inMalls(
    mapData: MapDataWithGeometry,
    malls: List<ElementPolygonsGeometry>,
    filter: ElementFilterExpression,
    isCandidate: (Element) -> Boolean,
): List<Element> {
    val elements = ArrayList<Element>(); val positions = ArrayList<LatLon>()
    val near = NearBounds(malls.map { it.bounds })
    // without a key to go by (a filter of `!level` and the like), the map data itself: no copy of it
    val candidates: Iterable<Element> =
        if (mapData is ArrayMapData && filter.keyReject.clauses.isEmpty()) mapData else mapData.candidates(filter)
    for (element in candidates) {
        // a node of this map data is its own geometry (ArrayMapData.getNodeGeometry): no lookup by id
        val pos = if (element is Node && mapData is ArrayMapData) element.position
            else mapData.getGeometry(element.type, element.id)?.center ?: continue
        if (!near.mayHold(pos)) continue
        if (!filter.matches(element)) continue
        elements.add(element); positions.add(pos)
    }
    if (elements.isEmpty()) return emptyList()
    val grid = PointGrid(positions)

    val result = mutableListOf<Element>()
    val done = BooleanArray(elements.size) // added to the result, or inside a mall but no candidate
    for (mallGeometry in malls) {
        for (i in grid.inBounds(mallGeometry.bounds)) {
            if (done[i]) continue
            if (!positions[i].isInMultipolygon(mallGeometry.polygons)) continue

            done[i] = true
            if (isCandidate(elements[i])) result.add(elements[i]) // can only be in one mall
        }
    }
    return result
}

/**
 * SC's AddLevel.getApplicableElements (ported/.../level/AddLevel.kt), with the changes of the local
 * [getMultiLevelMallGeometries] and [inMalls]. Filters copied verbatim.
 */
object FastAddLevel : FastTwin {
    override val name = "AddLevel"
    override val usesAge = false
    override val sourceSha256 = "fc8400e3c912651e6ed2eed9f49bb6e4ad4a33da024c77c2ba64358517eb23c6"
    override val helperSha256 = mapOf("helper:LevelUtils" to "1b18ef4268be0e52598b75ec23d8f657611f5dab2d70cd6602ddf6945dd36a08")
    override val shared = listOf(LEVEL_POINTS)

    private val filter by lazy { """
        nodes with
          !level
          and (name or brand or noname = yes or name:signed = no)
    """.toElementFilterExpression() }

    private val mallFilter by lazy { """
        ways, relations with
          shop = mall
          or aeroway = terminal
          or railway = station
          or amenity = bus_station
          or public_transport = station
    """.toElementFilterExpression() }

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> {
        val mallGeometries = mapData
            .filter { mallFilter.matches(it) }
            .mapNotNull { mapData.getGeometry(it.type, it.id) as? ElementPolygonsGeometry }
        if (mallGeometries.isEmpty()) return emptyList()

        val multiLevelMallGeometries = getMultiLevelMallGeometries(mallGeometries, mapData)
        if (multiLevelMallGeometries.isEmpty()) return emptyList()

        return inMalls(mapData, multiLevelMallGeometries, filter) { it.isPlace() }
    }
}

/**
 * SC's AddLevelThing.getApplicableElements (ported/.../level/AddLevelThing.kt), with the changes of the
 * local [getMultiLevelMallGeometries] and [inMalls]. Filters copied verbatim.
 */
object FastAddLevelThing : FastTwin {
    override val name = "AddLevelThing"
    override val usesAge = false
    override val sourceSha256 = "dce2eb86499d94c8c4f24ee2a38f2e2ac8d0ce101e8c0d05ad5bdc35a476b202"
    override val helperSha256 = mapOf("helper:LevelUtils" to "1b18ef4268be0e52598b75ec23d8f657611f5dab2d70cd6602ddf6945dd36a08")
    override val shared = listOf(LEVEL_POINTS)

    private val filter by lazy { """
        nodes with
          !level
          and (!location or location = indoor)
    """.toElementFilterExpression() }

    private val mallFilter by lazy { """
        ways, relations with
          shop ~ department_store|mall
          or aeroway = terminal
          or railway = station
          or amenity = bus_station
          or public_transport = station
    """.toElementFilterExpression() }

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> {
        val mallGeometries = mapData
            .filter(mallFilter)
            .mapNotNull { mapData.getGeometry(it.type, it.id) as? ElementPolygonsGeometry }
            .toList()
        if (mallGeometries.isEmpty()) return emptyList()

        val multiLevelMallGeometries = getMultiLevelMallGeometries(mallGeometries, mapData)
        if (multiLevelMallGeometries.isEmpty()) return emptyList()

        return inMalls(mapData, multiLevelMallGeometries, filter) { it.isThing() }
    }
}
