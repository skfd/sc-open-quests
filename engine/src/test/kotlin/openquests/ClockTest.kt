package openquests

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.util.ktx.now
import de.westnordost.streetcomplete.util.ktx.systemTimeNow
import kotlinx.datetime.LocalDate
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.time.Clock
import kotlin.time.Instant

class ClockTest {
    // last edited 2025-12-01, shop surveyed (check_date) never
    private val shop = Node(1, LatLon(43.65, -79.38), mapOf("shop" to "bakery"), 3,
        Instant.parse("2025-12-01T15:00:00Z").toEpochMilliseconds())
    private val filter = "nodes with shop and shop older today -1 years".toElementFilterExpression()

    @AfterTest fun restore() = EngineClock.install(Clock.System.now())

    @Test fun `vendored code reads the patched clock`() {
        EngineClock.install(parseToday("2026-07-16T20:21:30Z"))
        assertEquals(Instant.parse("2026-07-16T20:21:30Z"), systemTimeNow())
        assertEquals(LocalDate(2026, 7, 16), LocalDate.now())
    }

    @Test fun `older today flips with the clock`() {
        EngineClock.install(parseToday("2026-07-16"))
        assertFalse(filter.matches(shop), "edited 7.5 months before 2026-07-16")
        EngineClock.install(parseToday("2027-01-01"))
        assertTrue(filter.matches(shop), "edited 13 months before 2027-01-01")
    }

    @Test fun `--today date is noon in the system zone`() {
        // America/Toronto in July is UTC-4
        assertEquals(Instant.parse("2026-10-11T16:00:00Z"), parseToday("2026-10-11"))
        assertEquals(Instant.parse("2026-10-11T03:00:00Z"), parseToday("2026-10-11T03:00:00Z"))
    }

    @Test fun `a thread can evaluate at LONG_AGO without moving asOf`() {
        EngineClock.install(parseToday("2027-01-01"))
        assertTrue(filter.matches(shop))
        assertFalse(EngineClock.at(EngineClock.LONG_AGO) { filter.matches(shop) })
        assertTrue(filter.matches(shop))
        // other threads keep seeing asOf
        var seen: Instant? = null
        EngineClock.at(EngineClock.LONG_AGO) {
            Thread { seen = systemTimeNow() }.apply { start(); join() }
        }
        assertEquals(parseToday("2027-01-01"), seen)
    }

    @Test fun `LONG_AGO also falsifies date tags compared with today`() {
        val f = "ways with highway = construction and (!opening_date or opening_date < today)".toElementFilterExpression()
        val w = de.westnordost.streetcomplete.data.osm.mapdata.Way(1, listOf(1L, 2L),
            mapOf("highway" to "construction", "opening_date" to "2026-01-01"))
        EngineClock.install(parseToday("2026-07-16"))
        assertTrue(f.matches(w))
        assertFalse(EngineClock.at(EngineClock.LONG_AGO) { f.matches(w) })
    }
}
