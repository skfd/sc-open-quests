package openquests

import org.junit.jupiter.api.Assumptions.assumeTrue
import java.io.File
import kotlin.math.abs
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Runs the whole engine on the 2026-07-16 Ontario extract with the clock at 2026-10-11, the day the
 * spike ran (engine/README.md), and compares Toronto with the spike's numbers.
 *
 * The spike centred ways on the average of their nodes and relations on the average of their
 * members; the engine uses SC's centroid / half-length point. So the numbers move a little, and
 * [EXACT] pins what the engine gives now. Skipped when the extract is not on this machine
 * (-Ppbf=<path> to point elsewhere).
 */
class TorontoRegressionTest {
    /** spike, Toronto polygon, clock 2026-10-11 (wall clock, America/Toronto) */
    private val spike = mapOf(
        "AddBenchBackrest" to 3063, "AddBusStopShelter" to 3870, "AddBenchStatusOnBusStop" to 6074,
        "AddRoadSurface" to 27116, "AddWayLit" to 117654, "AddRecyclingType" to 31,
        "AddBuildingLevels" to 346142, "AddFireHydrantType" to 1699, "AddBikeParkingCapacity" to 893,
        "AddBikeParkingCover" to 1210, "AddHandrail" to 1948, "AddStepsRamp" to 495,
    )

    /** the engine's own numbers for the same run: nodes, ways, relations */
    private val EXACT = mapOf<String, List<Long>>(
        "AddBenchBackrest" to listOf(2931, 132, 0),
        "AddBusStopShelter" to listOf(3719, 146, 5),
        "AddBenchStatusOnBusStop" to listOf(5768, 301, 5),
        "AddRoadSurface" to listOf(0, 27116, 0),
        "AddWayLit" to listOf(0, 117651, 0), // spike 117654: net 3 centres moved across the boundary
        "AddRecyclingType" to listOf(31, 0, 0),
        "AddBuildingLevels" to listOf(0, 346028, 114),
        "AddFireHydrantType" to listOf(1699, 0, 0),
        "AddBikeParkingCapacity" to listOf(853, 40, 0),
        "AddBikeParkingCover" to listOf(1183, 27, 0),
        "AddHandrail" to listOf(0, 1948, 0),
        "AddStepsRamp" to listOf(0, 495, 0),
    )

    @Test fun `Toronto spike quests stay within 3 percent of the spike`() {
        val pbf = File(System.getProperty("openquests.pbf") ?: "")
        assumeTrue(pbf.isFile, "Ontario extract not found at $pbf")
        val result = count(CountOptions(
            pbf = pbf,
            quests = File("data/quests/v63.4.json"),
            cities = File("config/cities.json"),
            out = null,
            today = parseToday("2026-10-11"),
        ))
        val engine = result.engine
        val toronto = engine.cities.single { it.id == "toronto" }.index
        val failures = ArrayList<String>()
        for ((name, spikeOpen) in spike) {
            val qi = engine.quests.indexOfFirst { it.name == name }
            val c = engine.counts
            val open = c.open(toronto, qi)
            val ntr = listOf(c.get(toronto, qi, NODE), c.get(toronto, qi, WAY), c.get(toronto, qi, RELATION))
            val diff = (open - spikeOpen) * 100.0 / spikeOpen
            println("%-26s spike %7d  engine %7d  (%+.2f%%)  n/w/r %s  agedOnly %d".format(
                name, spikeOpen, open, diff, ntr, c.agedOnly(toronto, qi)))
            if (abs(diff) > 3.0) failures += "$name: $open vs spike $spikeOpen"
            EXACT[name]?.let { if (it != ntr) failures += "$name: n/w/r $ntr, expected $it" }
        }
        assertTrue(failures.isEmpty(), failures.joinToString("\n"))
        assertEquals("2026-10-11", result.meta.asOfDate)
        assertEquals("2026-07-16T20:21:30Z", result.meta.extractTimestamp)
    }
}
