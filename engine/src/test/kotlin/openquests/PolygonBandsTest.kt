package openquests

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** [Polygon.contains] answers the same whatever the number of latitude bands: the bands a polygon gets for its
 *  segments ([Polygon.bandsFor]), the 4,096 every boundary once had, one band, and no bands at all (every segment
 *  asked for every point). */
class PolygonBandsTest {
    /** the test of [Polygon.contains] over every segment */
    private fun brute(segs: DoubleArray, lat: Double, lon: Double): Boolean {
        var minLat = Double.MAX_VALUE; var maxLat = -Double.MAX_VALUE; var minLon = Double.MAX_VALUE; var maxLon = -Double.MAX_VALUE
        for (i in segs.indices step 4) {
            minLat = minOf(minLat, segs[i], segs[i + 2]); maxLat = maxOf(maxLat, segs[i], segs[i + 2])
            minLon = minOf(minLon, segs[i + 1], segs[i + 3]); maxLon = maxOf(maxLon, segs[i + 1], segs[i + 3])
        }
        if (lat < minLat || lat > maxLat || lon < minLon || lon > maxLon) return false
        var inside = false
        for (s in 0 until segs.size / 4) {
            val y1 = segs[4 * s]; val x1 = segs[4 * s + 1]; val y2 = segs[4 * s + 2]; val x2 = segs[4 * s + 3]
            if ((y1 > lat) != (y2 > lat) && lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1) inside = !inside
        }
        return inside
    }

    private fun segsOf(rings: List<List<Pair<Double, Double>>>): DoubleArray {
        val out = ArrayList<Double>()
        for (r in rings) for (i in r.indices) {
            val a = r[i]; val b = r[(i + 1) % r.size]
            out += a.first; out += a.second; out += b.first; out += b.second
        }
        return out.toDoubleArray()
    }

    private fun rectangle(s: Double, w: Double, n: Double, e: Double) = listOf(s to w, s to e, n to e, n to w)

    /** a ring of [n] points round a centre, its radius jagged so that it folds back in latitude many times */
    private fun star(rnd: Random, n: Int, lat: Double, lon: Double, r: Double) = List(n) {
        val a = 2 * PI * it / n
        val d = r * rnd.nextDouble(0.3, 1.0)
        (lat + d * sin(a)) to (lon + d * cos(a))
    }

    private fun check(name: String, segs: DoubleArray, rnd: Random, points: Int): Int {
        val scaled = Polygon(segs)
        val old = Polygon(segs, bandCount = 4096)
        val one = Polygon(segs, bandCount = 1)
        val odd = Polygon(segs, bandCount = 37)
        val lats = DoubleArray(segs.size / 2) { segs[2 * it] }
        val lons = DoubleArray(segs.size / 2) { segs[2 * it + 1] }
        val h = scaled.maxLat - scaled.minLat; val w = scaled.maxLon - scaled.minLon
        var inside = 0
        fun ask(lat: Double, lon: Double) {
            val want = brute(segs, lat, lon)
            assertEquals(want, scaled.contains(lat, lon), "$name: $lat,$lon with the bands of its segments")
            assertEquals(want, old.contains(lat, lon), "$name: $lat,$lon with 4096 bands")
            assertEquals(want, one.contains(lat, lon), "$name: $lat,$lon with one band")
            assertEquals(want, odd.contains(lat, lon), "$name: $lat,$lon with 37 bands")
            if (want) inside++
        }
        repeat(points) { k ->
            when (k % 5) {
                // anywhere in and a little round the box
                0, 1 -> ask(rnd.nextDouble(scaled.minLat - 0.1 * h - 1e-9, scaled.maxLat + 0.1 * h + 1e-9),
                    rnd.nextDouble(scaled.minLon - 0.1 * w - 1e-9, scaled.maxLon + 0.1 * w + 1e-9))
                // on a vertex's latitude, where a band may begin and the crossing test takes one side
                2 -> ask(lats[rnd.nextInt(lats.size)], rnd.nextDouble(scaled.minLon - 0.1 * w - 1e-9, scaled.maxLon + 0.1 * w + 1e-9))
                // on a vertex itself and next to it by the smallest step
                3 -> {
                    val v = rnd.nextInt(lats.size)
                    ask(lats[v], lons[v]); ask(Math.nextUp(lats[v]), lons[v]); ask(Math.nextDown(lats[v]), Math.nextDown(lons[v]))
                }
                // on the box's own edges and on a band's edge of each count
                else -> {
                    val lon = rnd.nextDouble(scaled.minLon - 1e-9, scaled.maxLon + 1e-9)
                    ask(scaled.minLat, lon); ask(scaled.maxLat, lon); ask(Math.nextUp(scaled.minLat), lon); ask(Math.nextDown(scaled.maxLat), lon)
                    for (bands in listOf(Polygon.bandsFor(segs.size / 4), 37, 4096)) {
                        val edge = scaled.minLat + h / bands * rnd.nextInt(bands + 1)
                        ask(edge, lon); ask(Math.nextUp(edge), lon); ask(Math.nextDown(edge), lon)
                    }
                }
            }
        }
        return inside
    }

    @Test fun `a polygon's bands follow its segments`() {
        assertEquals(1, Polygon.bandsFor(0))
        assertEquals(1, Polygon.bandsFor(4))    // a rectangle city
        assertEquals(1, Polygon.bandsFor(7))
        assertEquals(2, Polygon.bandsFor(8))
        assertEquals(4095, Polygon.bandsFor(16383))
        assertEquals(4096, Polygon.bandsFor(16384))
        assertEquals(4096, Polygon.bandsFor(5_000_000))
    }

    @Test fun `contains answers as asking every segment does, for small and large polygons`() {
        val rnd = Random(26)
        var inside = 0
        // rectangles: a tier 2 rectangle city (about 0.006 by 0.009 degrees), a world cell, one at the pole's cap
        inside += check("rectangle city", segsOf(listOf(rectangle(40.750538986704996, 29.949537132515786, 40.756378009342434, 29.95838454264606))), rnd, 20_000)
        inside += check("cell", segsOf(listOf(rectangle(-34.0, 18.0, -33.0, 19.5))), rnd, 20_000)
        inside += check("polar", segsOf(listOf(rectangle(89.0, -180.0, 90.0, 180.0))), rnd, 5_000)
        // a triangle, and a rectangle with a hole and an island in the hole
        inside += check("triangle", segsOf(listOf(listOf(10.0 to 10.0, 10.5 to 10.9, 11.0 to 10.2))), rnd, 20_000)
        inside += check("holed", segsOf(listOf(rectangle(0.0, 0.0, 1.0, 1.0), rectangle(0.2, 0.2, 0.8, 0.8), rectangle(0.4, 0.4, 0.6, 0.6))), rnd, 20_000)
        // jagged rings from a handful of segments to more than fill the 4,096 bands
        for (n in listOf(3, 5, 12, 16, 17, 100, 1_000, 16_384, 40_000)) {
            inside += check("star of $n", segsOf(listOf(star(rnd, n, 43.7, -79.4, 0.3))), rnd, if (n <= 1_000) 20_000 else 4_000)
        }
        // several rings, one inside another and one apart
        inside += check("multi", segsOf(listOf(star(rnd, 2_000, 50.0, 8.0, 0.5), star(rnd, 300, 50.0, 8.0, 0.1), star(rnd, 50, 51.5, 9.0, 0.2))), rnd, 20_000)
        // no height: every segment on one latitude (the band height is 0)
        inside += check("flat", doubleArrayOf(5.0, 1.0, 5.0, 2.0, 5.0, 2.0, 5.0, 1.0), rnd, 2_000)
        // the fixture must not be all outside
        assertTrue(inside > 50_000, "only $inside points inside")
        println("polygon bands: $inside points inside")
    }

    @Test fun `the readers give a polygon the bands of its segments`() {
        // what fromRings gave before, and now a boundary too: the same answers as 4,096 bands
        val rnd = Random(5)
        val ring = star(rnd, 64, 43.7, -79.4, 0.2).let { it + it.first() }
        val fromRings = Polygon.fromRings(listOf(DoubleArray(2 * ring.size) { if (it % 2 == 0) ring[it / 2].first else ring[it / 2].second }))
        val segs = segsOf(listOf(ring.dropLast(1)))
        repeat(20_000) {
            val lat = rnd.nextDouble(43.45, 43.95); val lon = rnd.nextDouble(-79.65, -79.15)
            assertEquals(brute(segs, lat, lon), fromRings.contains(lat, lon), "$lat,$lon")
        }
    }
}
