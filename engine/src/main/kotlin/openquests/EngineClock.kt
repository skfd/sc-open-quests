package openquests

import de.westnordost.streetcomplete.util.ktx.systemClock
import kotlinx.datetime.LocalDate
import kotlinx.datetime.TimeZone
import kotlinx.datetime.atStartOfDayIn
import kotlin.time.Clock
import kotlin.time.Instant

/** The clock the vendored SC code reads (through the `clock` patch in util/ktx/Instant.kt).
 *
 *  [asOf] is "today" for every age filter: the extract's replication timestamp. A thread can
 *  temporarily evaluate at another instant with [at], which is how `agedOnly` re-checks a match
 *  with every `older today -N` test false, in the same pass and without a second parse. */
object EngineClock : Clock {
    @Volatile var asOf: Instant = Instant.fromEpochSeconds(0)
        private set
    private val override = ThreadLocal<Instant?>()

    /** An instant so far back that `x older today -N` (and `x < today`) is false for any date an
     *  OSM element or check date can carry. */
    val LONG_AGO: Instant = LocalDate(1900, 1, 1).atStartOfDayIn(TimeZone.UTC)

    override fun now(): Instant = override.get() ?: asOf

    /** Points SC's clock at this object, evaluating at [instant]. */
    fun install(instant: Instant) {
        asOf = instant
        systemClock = this
    }

    inline fun <T> at(instant: Instant, block: () -> T): T {
        val previous = overrideGet()
        overrideSet(instant)
        try {
            return block()
        } finally {
            overrideSet(previous)
        }
    }

    @PublishedApi internal fun overrideGet(): Instant? = override.get()
    @PublishedApi internal fun overrideSet(i: Instant?) = override.set(i)
}
