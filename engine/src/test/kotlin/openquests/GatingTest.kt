package openquests

import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import java.io.File
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * A city without countryCodes (a world run's cell) is gated per quest position, as the app gates: here a cell
 * across the Dutch-German border at Enschede and Gronau, with a house and a named bakery on each side.
 * AddHousenumber (an area quest) is off in NL (AllCountriesExcept), AddAcceptsCash (a filter quest) on in NL
 * only (NoCountriesExcept); a typed city keeps gating as a whole.
 */
class GatingTest {
    private val nl = LatLon(52.22, 6.89)
    private val de = LatLon(52.21, 7.06)
    private val quests = File("data/quests/v64.1.json")

    @Test fun `the two positions are on either side of the border in SC's data`() {
        assertTrue("NL" in regionIdsAt(nl), "${regionIdsAt(nl)}")
        assertTrue("DE" in regionIdsAt(de), "${regionIdsAt(de)}")
    }

    private fun run(dir: File, cities: List<TestCity>): CountResult {
        val pbf = File(dir, "border.osm.pbf")
        if (!pbf.exists()) TestPbf().apply {
            for (p in listOf(nl, de)) {
                square(p.latitude, p.longitude, 0.0004, mapOf("building" to "house"))
                node(p.latitude + 0.002, p.longitude + 0.002, mapOf("shop" to "bakery", "name" to "Bakkerij"))
            }
        }.write(pbf)
        val f = writeTestCities(File(dir, "cities-${cities.joinToString("-") { it.id }}.json"), cities)
        return count(CountOptions(pbf = pbf, quests = quests, cities = f, out = null, baseDir = dir))
    }

    private fun CountResult.open(city: String, quest: String): Long =
        engine.counts.open(engine.cities.single { it.id == city }.index, engine.quests.indexOfFirst { it.name == quest })

    private fun CountResult.gate(city: String, quest: String): Byte =
        engine.gate[engine.cities.single { it.id == city }.index][engine.quests.indexOfFirst { it.name == quest }]

    @Test fun `a cell across the border counts each quest only where the app shows it`() {
        val dir = Files.createTempDirectory("gating").toFile()
        val tz = "Europe/Berlin"
        val r = run(dir, listOf(
            TestCity("cell", 52.18, 6.85, 52.25, 7.10, null, tz),
            TestCity("nl", 52.21, 6.87, 52.23, 6.91, null, tz),
            TestCity("de", 52.20, 7.05, 52.22, 7.08, null, tz),
        ))
        // the bbox decides where it can
        assertEquals(Gate.BY_POSITION, r.gate("cell", "AddHousenumber"))
        assertEquals(Gate.BY_POSITION, r.gate("cell", "AddAcceptsCash"))
        assertEquals(Gate.OFF, r.gate("cell", "AddPoliceType"), "Italy only")
        assertEquals(Gate.ON, r.gate("cell", "AddRoadName"), "everywhere but Japan")
        // SC's getContainingIds is conservative in a raster cell the border crosses: such a box is asked per position
        assertTrue(r.gate("nl", "AddHousenumber") != Gate.ON)
        assertTrue(r.gate("de", "AddHousenumber") != Gate.OFF)
        assertTrue(r.gate("de", "AddAcceptsCash") != Gate.ON)
        // the cell counts each side's quest once, as the small cells do
        assertEquals(1, r.open("cell", "AddHousenumber"), "an area quest, gated in the area pass: the German house")
        assertEquals(1, r.open("cell", "AddAcceptsCash"), "a filter quest, gated in the main pass: the Dutch bakery")
        assertEquals(1, r.open("de", "AddHousenumber"))
        assertEquals(0, r.open("de", "AddAcceptsCash"))
        assertEquals(0, r.open("nl", "AddHousenumber"))
        assertEquals(1, r.open("nl", "AddAcceptsCash"))
        // the quests list keeps a by-position quest as counted
        assertEquals("counted", questStatus(r.engine.quests.first { it.name == "AddHousenumber" }, r.engine.cities.first { it.id == "cell" }))
        assertEquals("not-in-region", questStatus(r.engine.quests.first { it.name == "AddPoliceType" }, r.engine.cities.first { it.id == "cell" }))
    }

    @Test fun `typed countryCodes still gate the whole city`() {
        val dir = Files.createTempDirectory("gating").toFile()
        val r = run(dir, listOf(TestCity("cell", 52.18, 6.85, 52.25, 7.10, listOf("DE"), "Europe/Berlin")))
        assertEquals(Gate.ON, r.gate("cell", "AddHousenumber"))
        assertEquals(2, r.open("cell", "AddHousenumber"))
        assertEquals(0, r.open("cell", "AddAcceptsCash"))
        val n = run(dir, listOf(TestCity("cell", 52.18, 6.85, 52.25, 7.10, listOf("NL"), "Europe/Berlin")))
        assertEquals(0, n.open("cell", "AddHousenumber"))
        assertEquals(2, n.open("cell", "AddAcceptsCash"))
    }
}
