package openquests

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.double
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import java.io.File
import kotlin.math.floor

/** Even-odd point-in-polygon test over a set of closed rings, given as loose segments.
 *  Outer and inner rings need no assembly: the crossing parity is right as long as the segments
 *  together form closed rings. Segments are bucketed into latitude bands for speed. */
class Polygon(
    private val segs: DoubleArray, /* lat1, lon1, lat2, lon2 repeated */
    /** latitude bands: [bandsFor] the segments unless given. [contains] answers the same with any number of them
     *  (a segment the test counts lies in the point's band, however high the bands are); only its time differs. */
    private val bandCount: Int = bandsFor(segs.size / 4),
) {
    val minLat: Double; val maxLat: Double; val minLon: Double; val maxLon: Double
    private val bandHeight: Double
    private val bands: Array<IntArray>

    init {
        var a = Double.MAX_VALUE; var b = -Double.MAX_VALUE; var c = Double.MAX_VALUE; var d = -Double.MAX_VALUE
        for (i in segs.indices step 4) {
            a = minOf(a, segs[i], segs[i + 2]); b = maxOf(b, segs[i], segs[i + 2])
            c = minOf(c, segs[i + 1], segs[i + 3]); d = maxOf(d, segs[i + 1], segs[i + 3])
        }
        minLat = a; maxLat = b; minLon = c; maxLon = d
        bandHeight = (maxLat - minLat) / bandCount
        val lists = Array(bandCount) { ArrayList<Int>() }
        for (s in 0 until segs.size / 4) {
            val lo = band(minOf(segs[4 * s], segs[4 * s + 2]))
            val hi = band(maxOf(segs[4 * s], segs[4 * s + 2]))
            for (k in lo..hi) lists[k] += s
        }
        bands = Array(bandCount) { lists[it].toIntArray() }
    }

    private fun band(lat: Double) = floor((lat - minLat) / bandHeight).toInt().coerceIn(0, bandCount - 1)

    fun contains(lat: Double, lon: Double): Boolean {
        if (lat < minLat || lat > maxLat || lon < minLon || lon > maxLon) return false
        var inside = false
        for (s in bands[band(lat)]) {
            val y1 = segs[4 * s]; val x1 = segs[4 * s + 1]; val y2 = segs[4 * s + 2]; val x2 = segs[4 * s + 3]
            if ((y1 > lat) != (y2 > lat) && lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1) inside = !inside
        }
        return inside
    }

    companion object {
        /** The latitude bands of a polygon of [segments] segments: one per four segments, 4,096 at most. A rectangle
         *  city's four segments take one band where the 4,096 once given to every boundary were about 100 KB and
         *  most of the time of making it (a tier 2 phase's rectangles: 50 s summed, over 1 GB in the largest group). */
        fun bandsFor(segments: Int): Int = (segments / 4).coerceIn(1, 4096)

        /** Reads relation [relationId] from an Overpass `out geom` JSON file: either a bare
         *  relation element (data/boundaries/<id>.json) or a whole response with `elements`
         *  (ontario-farmland's cache/boundaries.json). Fails if its member ways do not form closed
         *  rings. */
        fun fromOverpassJson(file: File, relationId: Long, lap: Timing.Lap? = null): Polygon {
            val text = file.readText()
            lap?.to("boundary read")
            val root = Json.parseToJsonElement(text).jsonObject
            lap?.to("boundary parse")
            val candidates = root["elements"]?.jsonArray?.map { it.jsonObject } ?: listOf(root)
            val rel = candidates.firstOrNull {
                it["type"]!!.jsonPrimitive.content == "relation" && it["id"]!!.jsonPrimitive.long == relationId
            } ?: error("${file.path}: no relation $relationId")
            val segs = ArrayList<Double>()
            val endpointDegree = HashMap<Pair<Double, Double>, Int>()
            for (m in rel["members"]!!.jsonArray.map { it.jsonObject }) {
                if (m["type"]!!.jsonPrimitive.content != "way") continue
                val pts = m["geometry"]!!.jsonArray.map {
                    val p = it.jsonObject
                    p["lat"]!!.jsonPrimitive.double to p["lon"]!!.jsonPrimitive.double
                }
                for (i in 0 until pts.size - 1) {
                    segs += pts[i].first; segs += pts[i].second; segs += pts[i + 1].first; segs += pts[i + 1].second
                }
                endpointDegree.merge(pts.first(), 1, Int::plus)
                endpointDegree.merge(pts.last(), 1, Int::plus)
            }
            val open = endpointDegree.values.count { it % 2 == 1 }
            require(open == 0) { "relation $relationId: $open open ring ends" }
            return Polygon(segs.toDoubleArray()).also { lap?.to("boundary polygon") }
        }

        /** Reads a GeoJSON Feature or bare geometry of type Polygon or MultiPolygon (`[lon, lat]`
         *  positions, as `osmium export` writes them; tools/add_parts.py). Every ring, outer or inner,
         *  becomes loose segments. */
        fun fromGeoJson(file: File): Polygon = fromRings(geoJsonRings(file))

        /** The rings of a GeoJSON Polygon or MultiPolygon file, outer and inner alike, in the file's order, each as
         *  lat, lon pairs with its closing point (what [fromRings] takes and PartsCache stores). */
        fun geoJsonRings(file: File): List<DoubleArray> {
            val root = Json.parseToJsonElement(file.readText()).jsonObject
            val geometry = root["geometry"]?.jsonObject ?: root
            val coordinates = geometry["coordinates"]!!.jsonArray
            val polygons = when (val type = geometry["type"]!!.jsonPrimitive.content) {
                "Polygon" -> listOf(coordinates)
                "MultiPolygon" -> coordinates.map { it.jsonArray }
                else -> error("${file.path}: geometry $type, not a Polygon or MultiPolygon")
            }
            val rings = ArrayList<DoubleArray>()
            for (polygon in polygons) for (ring in polygon) {
                val pts = ring.jsonArray
                val r = DoubleArray(2 * pts.size)
                for ((i, p) in pts.withIndex()) {
                    val c = p.jsonArray
                    r[2 * i] = c[1].jsonPrimitive.double
                    r[2 * i + 1] = c[0].jsonPrimitive.double
                }
                val n = r.size
                // closed as a Pair of boxed Doubles compares: Double.equals, by bits
                require(pts.size >= 4 && r[0].toBits() == r[n - 2].toBits() && r[1].toBits() == r[n - 1].toBits()) {
                    "${file.path}: a ring that is not closed"
                }
                rings += r
            }
            require(rings.isNotEmpty()) { "${file.path}: no rings" }
            return rings
        }

        /** A polygon of loose segments from closed rings (lat, lon pairs): each ring's consecutive points as one
         *  segment, rings in order. */
        fun fromRings(rings: List<DoubleArray>): Polygon {
            val segs = DoubleArray(4 * rings.sumOf { it.size / 2 - 1 })
            var k = 0
            for (r in rings) for (i in 0 until r.size / 2 - 1) {
                segs[k++] = r[2 * i]; segs[k++] = r[2 * i + 1]; segs[k++] = r[2 * i + 2]; segs[k++] = r[2 * i + 3]
            }
            return Polygon(segs)
        }
    }
}
