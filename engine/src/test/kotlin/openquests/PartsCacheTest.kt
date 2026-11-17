package openquests

import java.io.File
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** PartsCache: outlines from the cache are the GeoJSON's, bit for bit; a changed or missing source is parsed again. */
class PartsCacheTest {
    private val base: File = Files.createTempDirectory("partscache").toFile()

    private fun geo(name: String, json: String): String {
        File(base, "geo").mkdirs()
        File(base, "geo/$name").writeText(json)
        return "geo/$name"
    }

    private val square = """{"type":"Polygon","coordinates":[[[10.0,50.0],[10.1,50.0],[10.1,50.1],[10.0,50.1],[10.0,50.0]]]}"""
    // a multipolygon with a hole, odd decimals and a Feature wrapper
    private val multi = """{"type":"Feature","properties":{},"geometry":{"type":"MultiPolygon","coordinates":[
        [[[9.123456789,49.987654321],[9.2,49.9876],[9.2,50.05],[9.123456789,49.987654321]]],
        [[[11.0,51.0],[11.3,51.0],[11.3,51.3],[11.0,51.3],[11.0,51.0]],
         [[11.1,51.1],[11.2,51.1],[11.2,51.2],[11.1,51.1]]]]}}"""

    private fun sample(p: Polygon): List<Boolean> {
        val out = ArrayList<Boolean>()
        for (i in 0..120) for (j in 0..120) out += p.contains(49.9 + i * 0.012, 9.0 + j * 0.02)
        return out
    }

    @Test fun `outlines from the cache equal their GeoJSON, and a stale one is parsed again`() {
        val a = geo("a.geojson", square)
        val b = geo("b.geojson", multi)
        File(base, "parts").mkdirs()
        File(base, "parts/c.json").writeText("""{"schema":1,"city":"c","parts":[{"id":"a","geometry":"$a"},{"id":"b","geometry":"$b"}]}""")
        val cacheFile = File(base, "parts.cache")
        PartsCache.build(listOf(File(base, "parts")), base, cacheFile)
        PartsCache.Reader(cacheFile, base).use { r ->
            for (path in listOf(a, b)) {
                val want = Polygon.fromGeoJson(File(base, path))
                val got = r.polygon(path)
                assertEquals(listOf(want.minLat, want.maxLat, want.minLon, want.maxLon), listOf(got.minLat, got.maxLat, got.minLon, got.maxLon))
                assertEquals(sample(want), sample(got))
            }
            assertEquals(2, r.fromCache)
            assertEquals(0, r.parsed)
        }
        // a source rewritten after the build, and one the cache never saw: by default the cache is trusted (its
        // caller keeps it current) and only the unknown one is parsed; with verify both are parsed from GeoJSON
        File(base, a).writeText(multi)
        File(base, a).setLastModified(File(base, a).lastModified() + 5000)
        val c = geo("c.geojson", square)
        PartsCache.Reader(cacheFile, base).use { r ->
            assertEquals(sample(Polygon.fromGeoJson(File(base, c))), sample(r.polygon(c)))
            r.polygon(a)
            assertEquals(1, r.fromCache)
            assertEquals(1, r.parsed)
        }
        PartsCache.Reader(cacheFile, base, verify = true).use { r ->
            assertEquals(sample(Polygon.fromGeoJson(File(base, a))), sample(r.polygon(a)))
            assertEquals(sample(Polygon.fromGeoJson(File(base, c))), sample(r.polygon(c)))
            assertEquals(0, r.fromCache)
            assertEquals(2, r.parsed)
        }
        assertTrue(cacheFile.length() > 20)
    }
}
