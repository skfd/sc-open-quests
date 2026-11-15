package openquests

import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.util.math.LatLonRaster
import openquests.fast.SparseLatLonRaster
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals

/** [SparseLatLonRaster] must answer as SC's [LatLonRaster] does: the same points, in the same order. */
class SparseLatLonRasterTest {
    private fun check(name: String, box: BoundingBox, cell: Double, seed: Int, points: Int, queries: Int) {
        val r = Random(seed)
        val dense = LatLonRaster(box, cell)
        val sparse = SparseLatLonRaster(box, cell)
        val latSpan = box.max.latitude - box.min.latitude
        var lonSpan = box.max.longitude - box.min.longitude
        if (lonSpan < 0) lonSpan += 360.0
        fun lon(v: Double): Double { var x = v; while (x > 180.0) x -= 360.0; while (x < -180.0) x += 360.0; return x }
        // points in the box, a few clustered in one square, and some outside it (both drop those)
        fun point(spread: Double): LatLon {
            val lat = (box.min.latitude + (r.nextDouble() * (1 + 2 * spread) - spread) * latSpan).coerceIn(-90.0, 90.0)
            return LatLon(lat, lon(box.min.longitude + (r.nextDouble() * (1 + 2 * spread) - spread) * lonSpan))
        }
        val inserted = ArrayList<LatLon>()
        repeat(points) {
            val p = if (it % 7 == 0 && inserted.isNotEmpty()) inserted[r.nextInt(inserted.size)].let { q ->
                LatLon((q.latitude + r.nextDouble() * cell / 3).coerceIn(-90.0, 90.0), q.longitude)
            } else point(0.05)
            inserted += p
            dense.insert(p); sparse.insert(p)
        }
        assertEquals(dense.size, sparse.size, "$name: size")
        repeat(queries) { q ->
            val a = point(0.1); val b = point(0.1)
            // small boxes mostly, a wide one now and then (the sparse raster answers those another way)
            val wide = q % 5 == 0
            val h = if (wide) latSpan * r.nextDouble() else cell * (1 + r.nextInt(4))
            val w = if (wide) lonSpan * r.nextDouble() else cell * (1 + r.nextInt(4))
            val min = LatLon(minOf(a.latitude, 90.0 - h).coerceAtLeast(-90.0), a.longitude)
            val max = LatLon((min.latitude + h).coerceAtMost(90.0), lon(a.longitude + w))
            val query = if (q % 11 == 0) BoundingBox(minOf(a.latitude, b.latitude), a.longitude, maxOf(a.latitude, b.latitude), b.longitude)
                else BoundingBox(min, max)
            assertEquals(dense.getAll(query).toList(), sparse.getAll(query).toList(), "$name: query $q $query")
        }
    }

    @Test fun `a city box`() = check("city", BoundingBox(53.0, 8.4, 53.3, 9.1), 0.0005, 1, 20_000, 3_000)

    @Test fun `a world cell of ten degrees with few points`() =
        check("cell", BoundingBox(40.0, 10.0, 49.9, 19.9), 0.0005, 2, 5_000, 3_000)

    @Test fun `a box across the antimeridian`() =
        check("antimeridian", BoundingBox(-18.0, 177.0, -15.0, -178.5), 0.0005, 3, 5_000, 3_000)

    @Test fun `a box that ends two squares short of the pole`() =
        check("pole", rasterBox(BoundingBox(85.0, -30.0, 90.0, -20.0)), 0.0005, 4, 5_000, 3_000)

    @Test fun `a box at the south pole and the globe's west edge`() =
        check("south", BoundingBox(-90.0, -180.0, -87.0, -170.0), 0.0005, 5, 5_000, 3_000)

    @Test fun `an empty raster and a coarse one`() {
        check("empty", BoundingBox(10.0, 10.0, 11.0, 11.0), 0.0005, 6, 0, 200)
        check("coarse", BoundingBox(10.0, 10.0, 11.0, 11.0), 0.25, 7, 2_000, 500)
    }
}
