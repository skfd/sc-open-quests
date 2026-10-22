package openquests

import de.westnordost.streetcomplete.data.osm.geometry.ElementGeometryCreator
import de.westnordost.streetcomplete.data.osm.geometry.ElementPointGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.MutableMapDataWithGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import openquests.custom.ScCountryInfos
import openquests.ported.AREA_QUESTS
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** The quests that ask SC's country metadata (getCountryInfoByLocation). */
class CountryInfoQuestsTest {
    private val toronto = LatLon(43.6532, -79.3832)

    @Test fun `country info for Toronto is SC's CA-ON, CA and default metadata`() {
        assertEquals(listOf("CA-ON", "CA"), ScCountryInfos.countryBoundaries.getIds(toronto))
        val info = ScCountryInfos.getCountryInfoByLocation(toronto)
        assertEquals("CA", info.countryCode)
        assertEquals(listOf("en"), info.officialLanguages) // CA-ON.yml overrides CA.yml (en, fr)
        assertFalse(info.roofsAreUsuallyFlat) // default.yml
        assertFalse(info.isLeftHandTraffic)
        // Gatineau, across the river from Ottawa
        assertEquals(listOf("CA-QC", "CA"), ScCountryInfos.countryBoundaries.getIds(LatLon(45.4765, -75.7013)))
    }

    @Test fun `country info for Montreal and Vancouver reads the province's file first`() {
        val montreal = LatLon(45.5019, -73.5674)
        assertEquals(listOf("CA-QC", "CA"), ScCountryInfos.countryBoundaries.getIds(montreal))
        val qc = ScCountryInfos.getCountryInfoByLocation(montreal)
        assertEquals("CA", qc.countryCode)
        assertEquals(listOf("fr"), qc.officialLanguages) // CA-QC.yml overrides CA.yml (en, fr)
        assertTrue(qc.hasBicycleBoulevard) // CA-QC.yml
        assertFalse(qc.roofsAreUsuallyFlat) // default.yml

        val vancouver = LatLon(49.2827, -123.1207)
        assertEquals(listOf("CA-BC", "CA"), ScCountryInfos.countryBoundaries.getIds(vancouver))
        val bc = ScCountryInfos.getCountryInfoByLocation(vancouver)
        assertEquals(listOf("en"), bc.officialLanguages) // CA-BC.yml
        assertEquals("yellow", bc.centerLineStyle) // CA.yml
    }

    @Test fun `country info for Berlin, Hamburg and Bremen is SC's DE and default metadata`() {
        for (p in listOf(LatLon(52.5163, 13.3777), LatLon(53.5503, 9.9930), LatLon(53.0758, 8.8072))) {
            // SC's countryboundaries data has no German subdivisions (no DE-BE, DE-HH, DE-HB)
            assertEquals(listOf("DE"), ScCountryInfos.countryBoundaries.getIds(p), "$p")
            val info = ScCountryInfos.getCountryInfoByLocation(p)
            assertEquals("DE", info.countryCode)
            assertEquals(listOf("de"), info.officialLanguages) // DE.yml
            assertTrue(info.hasAdvisoryCycleLane) // DE.yml; default.yml says false
            assertFalse(info.roofsAreUsuallyFlat) // default.yml
        }
    }

    private fun mapData(vararg elements: Any): MutableMapDataWithGeometry {
        val md = MutableMapDataWithGeometry()
        val nodes = elements.filterIsInstance<Node>().associateBy { it.id }
        for (n in nodes.values) md.put(n, ElementPointGeometry(n.position))
        for (w in elements.filterIsInstance<Way>()) {
            md.put(w, ElementGeometryCreator().create(w, w.nodeIds.map { nodes.getValue(it).position }))
        }
        md.boundingBox = BoundingBox(43.64, -79.40, 43.66, -79.37)
        return md
    }

    private fun square(firstId: Long, lat: Double, lon: Double, d: Double = 0.0001) = listOf(
        Node(firstId, LatLon(lat, lon)), Node(firstId + 1, LatLon(lat, lon + d)),
        Node(firstId + 2, LatLon(lat + d, lon + d)), Node(firstId + 3, LatLon(lat + d, lon)),
    )

    @Test fun `AddRoofShape asks for buildings with levels, since roofs are not usually flat in Ontario`() {
        val ns = square(1, 43.65, -79.38)
        val building = Way(10, ns.map { it.id } + 1L, mapOf("building" to "yes", "building:levels" to "2"))
        val noLevels = Way(11, ns.map { it.id } + 1L, mapOf("building" to "yes"))
        val got = AREA_QUESTS.getValue("AddRoofShape").getApplicableElements(mapData(*ns.toTypedArray(), building, noLevels))
        assertEquals(listOf(10L), got.map { it.id })
    }

    @Test fun `AddHousenumber asks for a house without an address inside the downloaded area`() {
        val ns = square(1, 43.65, -79.38)
        val house = Way(10, ns.map { it.id } + 1L, mapOf("building" to "house"))
        val ms = square(20, 43.651, -79.38)
        val addressed = Way(30, ms.map { it.id } + 20L, mapOf("building" to "house"))
        val address = Node(40, LatLon(43.65105, -79.37995), mapOf("addr:housenumber" to "1"))
        val got = AREA_QUESTS.getValue("AddHousenumber")
            .getApplicableElements(mapData(*(ns + ms).toTypedArray(), house, addressed, address))
        assertEquals(listOf(10L), got.map { it.id })
    }

    @Test fun `AddCycleway asks for an untagged secondary road`() {
        val a = Node(1, LatLon(43.65, -79.38)); val b = Node(2, LatLon(43.65, -79.379))
        val road = Way(10, listOf(1, 2), mapOf("highway" to "secondary"))
        // edited just now: older cycleway tagging would be asked again (resurvey after 4 years)
        val tagged = Way(11, listOf(1, 2), mapOf("highway" to "secondary", "cycleway:both" to "no"), 1, System.currentTimeMillis())
        val got = AREA_QUESTS.getValue("AddCycleway").getApplicableElements(mapData(a, b, road, tagged))
        assertEquals(listOf(10L), got.map { it.id })
    }
}
