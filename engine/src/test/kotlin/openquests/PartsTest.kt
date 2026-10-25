package openquests

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import java.io.File
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Parts (neighbourhoods): the city's open quests split by position, nothing else changed. */
class PartsTest {
    // ManyCitiesTest's synthetic cities: squares of 0.01 degrees from (43.70, -79.40)
    private val s = 43.70; private val w = -79.40

    private fun square(file: File, south: Double, west: Double, north: Double, east: Double, hole: Boolean = false) {
        fun ring(a: Double, b: Double, c: Double, d: Double) =
            listOf(b to a, d to a, d to c, b to c, b to a).joinToString(",", "[", "]") { "[${it.first},${it.second}]" }
        val rings = listOf(ring(south, west, north, east)) +
            (if (hole) listOf(ring(south + .0008, west + .0008, south + .0016, west + .0016)) else emptyList())
        file.writeText("""{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":${rings.joinToString(",", "[", "]")}}}""")
    }

    @Test fun `parts count the city's open quests by position and change nothing else`() {
        val dir = Files.createTempDirectory("parts").toFile()
        val helper = ManyCitiesTest()
        val cities = helper.syntheticCities(File(dir, "cities.json"), 1, 2)
        val pbf = File(dir, "synthetic.osm.pbf").also { helper.writeSyntheticPbf(it, 1, 2) }
        val geo = File(dir, "geo").also { it.mkdirs() }
        // whole: the city c0-0 itself; house: around its house (centroid s+.0032, w+.0032); bench: the
        // bench at (s+.008, w+.008), overlapping whole; holed: house's square with a hole over the house;
        // next: inside the neighbouring city c0-1, registered under c0-0
        square(File(geo, "whole.geojson"), s, w, s + .01, w + .01)
        square(File(geo, "house.geojson"), s + .002, w + .002, s + .0045, w + .0045)
        square(File(geo, "holed.geojson"), s + .002, w + .002, s + .0045, w + .0045, hole = true)
        square(File(geo, "bench.geojson"), s + .0075, w + .0075, s + .0085, w + .0085)
        square(File(geo, "next.geojson"), s, w + .01, s + .01, w + .02)
        val parts = File(dir, "parts").also { it.mkdirs() }
        File(parts, "c0-0.json").writeText("""{"schema": 1, "city": "c0-0", "overture": "test", "parts": [
            {"id": "aaaaaaaaaaaa", "geometry": "geo/whole.geojson"}, {"id": "bbbbbbbbbbbb", "geometry": "geo/house.geojson"},
            {"id": "cccccccccccc", "geometry": "geo/bench.geojson"}, {"id": "dddddddddddd", "geometry": "geo/next.geojson"},
            {"id": "eeeeeeeeeeee", "geometry": "geo/holed.geojson"}]}""")
        val quests = File("data/quests/v64.0.json")
        fun run(withParts: Boolean) = count(CountOptions(pbf = pbf, quests = quests, cities = cities, out = null,
            baseDir = dir, parts = if (withParts) parts else null))
        val plain = run(false)
        val result = run(true)
        val e = result.engine
        assertEquals(5, e.parts.size)

        // every count of the city is what it is without parts
        for (c in e.cities.indices) for (qi in e.quests.indices) for (slot in 0 until 10)
            assertEquals(plain.engine.counts.get(c, qi, slot), e.counts.get(c, qi, slot))

        val snapshot = Json.parseToJsonElement(snapshotJson(result.meta, e)).jsonObject["cities"]!!.jsonObject
        val without = Json.parseToJsonElement(snapshotJson(plain.meta, plain.engine)).jsonObject["cities"]!!.jsonObject
        assertNull(snapshot["c0-1"]!!.jsonObject["parts"], "a city without a registry has no parts key")
        val city = snapshot["c0-0"]!!.jsonObject
        assertEquals(without["c0-0"]!!.jsonObject["quests"], city["quests"])
        val got = city["parts"]!!.jsonObject.mapValues { (_, v) -> v.jsonObject.mapValues { it.value.jsonPrimitive.long } }
        val cityOpen = city["quests"]!!.jsonObject.mapValues { it.value.jsonObject["open"]!!.jsonPrimitive.long }.filterValues { it > 0 }
        assertTrue(cityOpen.isNotEmpty())
        assertEquals(cityOpen, got["aaaaaaaaaaaa"], "the part that is the whole city has the city's numbers")
        assertEquals(1, got["bbbbbbbbbbbb"]!!["AddHousenumber"], "the house is in its part")
        assertEquals(null, got["eeeeeeeeeeee"]!!["AddHousenumber"], "and not in that part's hole")
        assertEquals(null, got["bbbbbbbbbbbb"]!!["AddBenchBackrest"])
        assertTrue(got["cccccccccccc"]!!.isNotEmpty(), "the bench's quests count in the overlapping part")
        assertEquals(null, got["cccccccccccc"]!!["AddHousenumber"])
        assertEquals(emptyMap(), got["dddddddddddd"], "a part counts only its own city's quests")
        for ((_, q) in got) for ((name, n) in q) assertTrue(n <= cityOpen.getValue(name))
    }
}
