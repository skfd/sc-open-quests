package openquests

import de.westnordost.streetcomplete.data.osm.geometry.ElementPolylinesGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.util.math.distanceToArcs
import openquests.fast.HikingSegments
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** The summit twins' grid gives SC's answer for every peak: random paths (short and long segments, one-point
 *  polylines) and peaks placed 0-20 m off them, so many land on either side of SC's 10 m. */
class SummitTest {
    @Test fun `the grid answers as SC's all against all`() {
        val r = Random(7)
        fun jitter(p: LatLon, m: Double) = LatLon(p.latitude + (r.nextDouble() * 2 - 1) * m / 111_195.0,
            p.longitude + (r.nextDouble() * 2 - 1) * m / (111_195.0 * Math.cos(Math.toRadians(p.latitude))))
        val paths = (0 until 300).map {
            val start = LatLon(47.3 + r.nextDouble() * 0.4, 10.8 + r.nextDouble() * 0.6)
            val lines = (0 until 1 + r.nextInt(3)).map {
                val n = if (r.nextInt(10) == 0) 1 else 2 + r.nextInt(30)
                val step = if (r.nextInt(8) == 0) 8000.0 else 60.0  // some segments longer than LONG_M
                generateSequence(start) { jitter(it, step) }.take(n).toList()
            }
            ElementPolylinesGeometry(lines, lines[0][0])
        }
        val index = HikingSegments(paths)
        val all = paths.flatMap { it.polylines }.flatten()
        val segs = paths.flatMap { it.polylines }.filter { it.size > 1 }.flatMap { it.zipWithNext() }
        var near = 0
        repeat(20_000) {
            val p = when (it % 4) {
                0 -> LatLon(47.3 + r.nextDouble() * 0.4, 10.8 + r.nextDouble() * 0.6)
                1 -> segs[r.nextInt(segs.size)].let { (a, b) ->  // along a segment, long ones included
                    val t = r.nextDouble()
                    jitter(LatLon(a.latitude + (b.latitude - a.latitude) * t, a.longitude + (b.longitude - a.longitude) * t), 20.0)
                }
                else -> jitter(all[r.nextInt(all.size)], 20.0)
            }
            val sc = paths.any { g -> g.polylines.any { p.distanceToArcs(it) <= 10 } }
            assertEquals(sc, index.near(p), "peak $p")
            if (sc) near++
        }
        assertTrue(near in 2_000..18_000, "a test with both answers: $near near")
    }
}
