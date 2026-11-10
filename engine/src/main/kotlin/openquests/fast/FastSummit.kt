package openquests.fast

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.quests.summit.getHikingPathsAndRoutes
import de.westnordost.streetcomplete.util.math.distanceTo
import de.westnordost.streetcomplete.util.math.distanceToArc
import openquests.candidates
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.max

/**
 * The hiking paths and routes of a map data, from SC's own `getHikingPathsAndRoutes()` (SummitMarkingsUtil.kt,
 * called, not copied; it reads no clock), with a grid over their segments.
 *
 * SC asks of each peak `paths.any { it.polylines.any { peak.position.distanceToArcs(it) <= 10 } }`: every peak
 * against every segment of every path and route. A polyline's `distanceToArcs` is the least `distanceToArc` of
 * its segments (or `distanceTo` its one point), so "the least is at most 10" is "some segment is at most 10".
 * [near] asks exactly that, with SC's own functions and arguments, but only of the segments whose box, padded
 * by [PAD_M], holds the peak. SC's distance is to the great-circle arc, which is within its endpoints' box
 * but for a bulge of under a metre at [LONG_M]; longer segments, and any near a pole or across the
 * antimeridian, are asked of every peak. So the answer is the same for every peak.
 */
class HikingSegments(geometries: List<de.westnordost.streetcomplete.data.osm.geometry.ElementPolylinesGeometry>) {
    private val starts = ArrayList<LatLon>()
    private val ends = ArrayList<LatLon?>()  // null: a polyline of one point, asked by distanceTo
    private val grid = HashMap<Long, IntArrayList>()
    private val always = IntArrayList()

    /** SC's `distanceToArcs` fails on an empty polyline; such a map data is left to SC's code. */
    val hasEmptyPolyline: Boolean

    init {
        var empty = false
        for (g in geometries) for (line in g.polylines) {
            if (line.isEmpty()) { empty = true; continue }
            if (line.size == 1) add(line[0], null)
            else for (i in 0 until line.size - 1) add(line[i], line[i + 1])
        }
        hasEmptyPolyline = empty
    }

    private fun add(a: LatLon, b: LatLon?) {
        val i = starts.size
        starts += a; ends += b
        val bb = b ?: a
        val s = minOf(a.latitude, bb.latitude); val n = maxOf(a.latitude, bb.latitude)
        val w = minOf(a.longitude, bb.longitude); val e = maxOf(a.longitude, bb.longitude)
        val maxLat = max(abs(s), abs(n))
        val cosLat = cos(Math.toRadians(maxLat))
        val lengthM = Math.hypot((n - s) * M_PER_DEG, (e - w) * M_PER_DEG * cosLat)
        if (maxLat > 85.0 || e - w > 180.0 || lengthM > LONG_M) { always.add(i); return }
        val dLat = PAD_M / M_PER_DEG
        val dLon = PAD_M / (M_PER_DEG * cosLat)
        for (x in cell(w - dLon)..cell(e + dLon)) for (y in cell(s - dLat)..cell(n + dLat)) {
            grid.getOrPut(key(x, y)) { IntArrayList() }.add(i)
        }
    }

    private fun exact(p: LatLon, i: Int): Boolean {
        val b = ends[i]
        return if (b == null) p.distanceTo(starts[i]) <= 10 else p.distanceToArc(starts[i], b) <= 10
    }

    /** Whether some path or route passes within 10 m of [p], by SC's own test. */
    fun near(p: LatLon): Boolean {
        grid[key(cell(p.longitude), cell(p.latitude))]?.let { c -> for (k in 0 until c.size) if (exact(p, c[k])) return true }
        for (k in 0 until always.size) if (exact(p, always[k])) return true
        return false
    }

    private fun cell(d: Double) = floor(d / CELL_DEG).toInt()
    private fun key(x: Int, y: Int) = gridKey(x, y)

    companion object {
        const val PAD_M = 50.0
        const val LONG_M = 5000.0
        private const val CELL_DEG = 0.01
        private const val M_PER_DEG = 111_000.0  // a little under the true 111,195: pads a little more
    }
}

class IntArrayList {
    private var a = IntArray(4)
    var size = 0; private set
    fun add(v: Int) { if (size == a.size) a = a.copyOf(size * 2); a[size++] = v }
    operator fun get(i: Int) = a[i]
}

val HIKING_SEGMENTS = PerMapData("hiking paths") { HikingSegments(getHikingPathsAndRoutes(it)) }

/** The body both summit quests share, SC's order kept: the tag tests first, then the paths. */
private fun summitPeaks(
    mapData: MapDataWithGeometry,
    filter: de.westnordost.streetcomplete.data.elementfilter.ElementFilterExpression,
    otherYes: String,
    own: String,
    port: (MapDataWithGeometry) -> Iterable<Element>,
): Iterable<Element> {
    val peaks = mapData.candidates(mapData.nodes, filter).filter { filter.matches(it) }
    if (peaks.isEmpty()) return emptyList()
    val paths = HIKING_SEGMENTS.of(mapData)
    if (paths.hasEmptyPolyline) return port(mapData)
    return peaks.filter { peak ->
        peak.tags[otherYes] == "yes" || peak.tags.containsKey(own) || paths.near((peak as Node).position)
    }
}

/** SC's AddSummitRegister.getApplicableElements (ported/.../AddSummitRegister.kt), the paths asked through
 *  [HikingSegments] instead of all against all. Filter copied verbatim. */
object FastAddSummitRegister : FastTwin {
    override val name = "AddSummitRegister"
    override val usesAge = true
    override val sourceSha256 = "c790121ea6413483fe0fb7baa8022265ad427774a1de49467fdce5b486c3fbe3"
    override val shared = listOf(HIKING_SEGMENTS)

    private val filter by lazy { """
        nodes with
          natural = peak
          and name
          and (!summit:register or summit:register older today -4 years)
    """.toElementFilterExpression() }

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> =
        summitPeaks(mapData, filter, "summit:cross", "summit:register",
            de.westnordost.streetcomplete.quests.summit.AddSummitRegister::getApplicableElements)
}

/** SC's AddSummitCross.getApplicableElements (ported/.../AddSummitCross.kt), as [FastAddSummitRegister]. */
object FastAddSummitCross : FastTwin {
    override val name = "AddSummitCross"
    override val usesAge = true
    override val sourceSha256 = "f27565b3ac2f82f0a722ac353be6a4bad4f78d99e7e143c4510f0cf919a64353"
    override val shared = listOf(HIKING_SEGMENTS)

    private val filter by lazy { """
        nodes with
          natural = peak
          and name
          and (!summit:cross or summit:cross older today -16 years)
    """.toElementFilterExpression() }

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> =
        summitPeaks(mapData, filter, "summit:register", "summit:cross",
            de.westnordost.streetcomplete.quests.summit.AddSummitCross::getApplicableElements)
}
