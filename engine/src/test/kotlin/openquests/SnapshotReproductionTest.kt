package openquests

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import org.junit.jupiter.api.Assumptions.assumeTrue
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Recounts the newest extract in the shared store (~/Code/.osm-data, or -PosmData=<dir>) that has
 * a committed snapshot, and checks every city's open and agedOnly counts against that snapshot.
 *
 * Unlike [TorontoRegressionTest], which needs one fixed extract, this survives the store pruning
 * old extracts: any extract that was counted and committed must count the same again. Skipped
 * when no stored extract has a snapshot.
 */
class SnapshotReproductionTest {
    @Test fun `recounting a stored extract reproduces its committed snapshot`() {
        val store = File(System.getProperty("openquests.osmData") ?: "", "ontario")
        val snapshots = File("docs/data/snapshots")
        val pair = store.listFiles { f -> f.name.matches(Regex("""ontario-\d{4}-\d{2}-\d{2}\.osm\.pbf""")) }
            .orEmpty().sortedByDescending { it.name }
            .map { it to File(snapshots, it.name.removePrefix("ontario-").removeSuffix(".osm.pbf") + ".json") }
            .firstOrNull { it.second.isFile }
        assumeTrue(pair != null, "no extract in $store has a snapshot in $snapshots")
        val (pbf, snapshotFile) = pair!!

        val snapshot = Json.parseToJsonElement(snapshotFile.readText()).jsonObject
        val result = count(CountOptions(
            pbf = pbf,
            quests = File("data/quests/v${snapshot["scVersion"]!!.jsonPrimitive.content}.json"),
            cities = File("config/cities.json"),
            out = null,
        ))
        assertEquals(snapshot["asOf"]!!.jsonPrimitive.content, result.meta.extractTimestamp)

        val engine = result.engine
        val c = engine.counts
        val failures = ArrayList<String>()
        var checked = 0
        for ((cityId, city) in snapshot["cities"]!!.jsonObject) {
            val ci = engine.cities.single { it.id == cityId }.index
            for ((name, q) in city.jsonObject["quests"]!!.jsonObject) {
                val qi = engine.quests.indexOfFirst { it.name == name }
                val want = q.jsonObject
                val open = want["open"]!!.jsonPrimitive.long
                val aged = want["agedOnly"]!!.jsonPrimitive.long
                if (c.open(ci, qi) != open || c.agedOnly(ci, qi) != aged)
                    failures += "$cityId/$name: ${c.open(ci, qi)}/${c.agedOnly(ci, qi)}, snapshot $open/$aged"
                checked++
            }
        }
        println("${pbf.name}: $checked city×quest counts checked against ${snapshotFile.name}")
        assertTrue(failures.isEmpty(), failures.take(20).joinToString("\n"))
    }
}
