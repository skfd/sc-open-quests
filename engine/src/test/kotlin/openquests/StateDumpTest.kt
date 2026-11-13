package openquests

import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.time.Duration.Companion.days
import kotlin.time.Duration.Companion.hours
import kotlin.time.Instant

/** --dump-state's records and the search for the day a waiting quest opens (the stream's seed). */
class StateDumpTest {
    @Test fun recordsReadBackFromEveryThread() {
        val f = File.createTempFile("state", ".bin").apply { deleteOnExit() }
        val s = StateDump(f)
        val threads = (0 until 4).map { t ->
            Thread { repeat(10_000) { s.match(WAY, t * 100_000L + it, 43.65, -79.38, 7, M_NOW or M_AGED, hidden = it % 2 == 0) } }
        }
        threads.forEach { it.start() }
        threads.forEach { it.join() }
        s.due(NODE, 5, -33.9, 151.2, 3, hidden = false, setting = M_05, dueMinute = 29_000_000)
        s.close()
        val b = ByteBuffer.wrap(f.readBytes()).order(ByteOrder.LITTLE_ENDIAN)
        assertEquals(40_001 * StateDump.RECORD, b.limit())
        val keys = HashSet<Long>()
        var hidden = 0
        var dues = 0
        while (b.hasRemaining()) {
            val key = b.long; val lat = b.int; val lon = b.int; val quest = b.short.toInt()
            val flags = b.get().toInt(); val kind = b.get().toInt(); val due = b.int
            keys += key
            if (kind == StateDump.DUE) {
                dues++
                assertEquals(listOf(5L * 4 + NODE, -339000000L, 1512000000L, 3L, 29_000_000L), listOf(key, lat.toLong(), lon.toLong(), quest.toLong(), due.toLong()))
                assertEquals(M_05, flags)
            } else {
                assertEquals(listOf(436500000, -793800000, 7), listOf(lat, lon, quest))
                assertEquals(M_NOW or M_AGED, flags and 63)
                if (flags and StateDump.HIDDEN != 0) hidden++
            }
        }
        assertEquals(40_001, keys.size)
        assertEquals(20_000, hidden)
        assertEquals(1, dues)
    }

    @Test fun dueIsTheFirstWholeDayTheTestHolds() {
        val asOf = Instant.parse("2026-11-08T00:00:00Z")
        EngineClock.install(asOf)
        val opens = asOf + 1234.days + 12.hours
        val due = StateDump.dueMinute { EngineClock.now() >= opens }
        // half a day into day 1234: true from day 1235 on
        assertEquals((asOf + 1235.days).epochSeconds / 60, due.toLong())
        assertEquals(-1, StateDump.dueMinute { false })
    }
}
