package openquests

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import kotlinx.datetime.TimeZone
import java.io.File
import java.nio.file.Files
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.time.Clock
import kotlin.time.Instant

/**
 * The `zone` patch: a city's age filters run in its own time zone, the same as in a JVM started in that zone.
 * asOf is 2026-10-23T20:20:51Z: already the 24th in Auckland (UTC+13), still the 23rd in Los Angeles (UTC-7).
 */
class ZoneTest {
    private val asOf = Instant.parse("2026-10-23T20:20:51Z")
    private val zones = listOf("Pacific/Auckland", "America/Los_Angeles", "Europe/Moscow")
    private val jvmDefault = java.util.TimeZone.getDefault()

    @AfterTest fun restore() {
        java.util.TimeZone.setDefault(jvmDefault)
        EngineClock.install(Clock.System.now())
    }

    private fun inJvmZone(id: String, block: () -> Unit) {
        java.util.TimeZone.setDefault(java.util.TimeZone.getTimeZone(id))
        try { block() } finally { java.util.TimeZone.setDefault(jvmDefault) }
    }

    /** last edited every hour from 3 days before to 3 days after asOf minus one year */
    private val edits = (-72..72).map { asOf.toEpochMilliseconds() - 365L * 86_400_000 + it * 3_600_000L }

    @Test fun `an override evaluates as a JVM in that zone does`() {
        val filter = "nodes with shop and shop older today -1 years".toElementFilterExpression()
        fun results() = edits.map { filter.matches(Node(1, LatLon(0.0, 0.0), mapOf("shop" to "bakery"), 1, it)) }
        EngineClock.install(asOf)
        val byZone = zones.associateWith { z ->
            var plain: List<Boolean>? = null
            inJvmZone(z) { plain = results() }
            var overridden: List<Boolean>? = null
            inJvmZone("UTC") { overridden = EngineZone.at(TimeZone.of(z)) { results() } }
            assertEquals(plain, overridden, z)
            overridden!!
        }
        assertNotEquals(byZone.getValue("Pacific/Auckland"), byZone.getValue("America/Los_Angeles"),
            "a day apart at asOf, so the threshold moves")
    }

    @Test fun `cities in different zones count in one run as each counts alone in its own zone`() {
        val dir = Files.createTempDirectory("zones").toFile()
        val pbf = File(dir, "zones.osm.pbf")
        // two adjacent cities in Berlin, each with a fire hydrant whose diameter sign was last edited every 2 hours
        // around asOf minus 6 years (AddFireHydrantDiameter: `fire_hydrant:diameter:signed older today -6 years`)
        val cities = listOf(
            TestCity("auckland", 52.50, 13.40, 52.51, 13.41, listOf("DE"), "Pacific/Auckland"),
            TestCity("la", 52.50, 13.41, 52.51, 13.42, listOf("DE"), "America/Los_Angeles"),
        )
        TestPbf(asOf.epochSeconds).apply {
            for (c in cities) for (h in -60..60 step 2) {
                val ts = asOf.epochSeconds - (6 * 365.25 * 86_400).toLong() + h * 3_600L
                node(c.s + 0.001 + (h + 60) * 0.00005, c.w + 0.005,
                    mapOf("emergency" to "fire_hydrant", "fire_hydrant:type" to "pillar", "fire_hydrant:diameter:signed" to "no"), ts)
            }
        }.write(pbf)
        val quests = File("data/quests/v64.1.json")
        fun run(cs: List<TestCity>, name: String) =
            count(CountOptions(pbf = pbf, quests = quests, cities = writeTestCities(File(dir, "$name.json"), cs), out = null, baseDir = dir))

        var both: CountResult? = null
        inJvmZone("UTC") { both = run(cities, "both") }
        val e = both!!.engine
        val qi = e.quests.indexOfFirst { it.name == "AddFireHydrantDiameter" }
        val slots = e.counts.perQuest.length() / (e.counts.cityCount * e.counts.questCount)
        val opens = cities.map { c ->
            var alone: CountResult? = null
            inJvmZone(c.timeZone) { alone = run(listOf(c), c.id) }
            val a = alone!!.engine
            val aq = a.quests.indexOfFirst { it.name == "AddFireHydrantDiameter" }
            val ci = e.cities.single { it.id == c.id }.index
            for (slot in 0 until slots) assertEquals(a.counts.get(0, aq, slot), e.counts.get(ci, qi, slot), "${c.id} slot $slot")
            e.counts.open(ci, qi)
        }
        assertNotEquals(opens[0], opens[1], "the two zones see a different threshold: $opens")
    }
}
