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
class Polygon(private val segs: DoubleArray /* lat1, lon1, lat2, lon2 repeated */) {
    val minLat: Double; val maxLat: Double; val minLon: Double; val maxLon: Double
    private val bandCount = 4096
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
        /** Reads relation [relationId] from an Overpass `out geom` JSON file: either a bare
         *  relation element (data/boundaries/<id>.json) or a whole response with `elements`
         *  (ontario-farmland's cache/boundaries.json). Fails if its member ways do not form closed
         *  rings. */
        fun fromOverpassJson(file: File, relationId: Long): Polygon {
            val root = Json.parseToJsonElement(file.readText()).jsonObject
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
            return Polygon(segs.toDoubleArray())
        }
    }
}
