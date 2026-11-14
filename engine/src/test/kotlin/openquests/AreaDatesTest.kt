package openquests

import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.days
import kotlin.time.Instant

/**
 * --dump-state dates the area quests up to [AREA_DUE_DAYS] ahead (AreaPass.dateCandidates): benches whose
 * CheckExistence (an area quest, six years since the last check) opens now, within the horizon and after it. The
 * date written must be the first day a whole count at that date has the quest open.
 */
class AreaDatesTest {
    private val quests = File("data/quests/v64.1.json")
    private val asOf = Instant.parse("2026-12-01T00:00:00Z")

    private fun count(dir: File, today: Instant, state: File? = null): CountResult {
        val pbf = File(dir, "benches.osm.pbf")
        if (!pbf.exists()) TestPbf().apply {
            val edited = 1_760_000_000L  // 2025-10: the last edit is recent, so only check_date ages (`older today` reads the edit)
            node(52.2001, 7.0001, mapOf("amenity" to "bench", "check_date" to "2020-03-01"), edited)  // open now
            node(52.2003, 7.0003, mapOf("amenity" to "bench", "check_date" to "2021-01-20"), edited)  // opens in about 50 days
            node(52.2005, 7.0005, mapOf("amenity" to "bench", "check_date" to "2020-12-03"), edited)  // in a couple of days
            node(52.2007, 7.0007, mapOf("amenity" to "bench", "check_date" to "2024-05-01"), edited)  // past the horizon
        }.write(pbf)
        val cities = writeTestCities(File(dir, "cities.json"), listOf(TestCity("c", 52.19, 6.99, 52.21, 7.01, listOf("DE"), "UTC")))
        return count(CountOptions(pbf = pbf, quests = quests, cities = cities, out = null, today = today, dumpState = state, baseDir = dir))
    }

    private fun CountResult.open(quest: String): Long =
        engine.counts.open(0, engine.quests.indexOfFirst { it.name == quest })

    private class Rec(val id: Long, val quest: Int, val kind: Int, val due: Int)

    private fun read(f: File): List<Rec> {
        val b = ByteBuffer.wrap(f.readBytes()).order(ByteOrder.LITTLE_ENDIAN)
        val out = ArrayList<Rec>()
        while (b.hasRemaining()) {
            val key = b.long; b.int; b.int
            val quest = b.short.toInt(); b.get(); val kind = b.get().toInt(); val due = b.int
            out += Rec(key shr 2, quest, kind, due)
        }
        return out
    }

    @Test fun `an area quest's date is the first day a whole count has it open`() {
        val dir = Files.createTempDirectory("areadates").toFile()
        val state = File(dir, "state.bin")
        val r = count(dir, asOf, state)
        assertEquals(1, r.open("CheckExistence"))
        val qi = r.engine.quests.indexOfFirst { it.name == "CheckExistence" }
        val dues = read(state).filter { it.quest == qi && it.kind == StateDump.DUE }
        assertEquals(2, dues.size, "the two benches within ${AREA_DUE_DAYS} days, not the one after: ${dues.map { it.id }}")
        assertTrue(File(state.path + ".json").readText().contains("\"areaDueDays\":$AREA_DUE_DAYS"))
        var expectOpen = 1L
        for (d in dues.sortedBy { it.due }) {
            val day = Instant.fromEpochSeconds(d.due * 60L)
            assertTrue(day > asOf && day <= asOf + AREA_DUE_DAYS.days, "$day")
            expectOpen++
            assertEquals(expectOpen - 1, count(dir, day - 1.days).open("CheckExistence"), "the day before $day")
            assertEquals(expectOpen, count(dir, day).open("CheckExistence"), "on $day")
        }
    }
}
