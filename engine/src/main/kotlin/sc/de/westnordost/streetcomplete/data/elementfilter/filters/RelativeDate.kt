package de.westnordost.streetcomplete.data.elementfilter.filters

import de.westnordost.streetcomplete.util.ktx.minusInSystemTimeZone
import de.westnordost.streetcomplete.util.ktx.now
import de.westnordost.streetcomplete.util.ktx.plusInSystemTimeZone
import kotlinx.datetime.DateTimeUnit
import kotlinx.datetime.LocalDate
import kotlinx.datetime.LocalDateTime
import kotlin.math.absoluteValue

interface DateFilter {
    val date: LocalDate
}

/** A date relative to (start of) today (positive: future, negative: past) */
class RelativeDate(val deltaDays: Float) : DateFilter {
    // sc-open-quests patch: computed on every read (as up to v63), so the engine can move the clock
    override val date: LocalDate get() = run {
        val now = LocalDateTime.now()
        val plusHours = (deltaDays * MULTIPLIER * 24).toLong()
        val relativeDateTime = (
            if (plusHours > 0) {
                now.plusInSystemTimeZone(plusHours, DateTimeUnit.HOUR)
            } else {
                now.minusInSystemTimeZone(plusHours.absoluteValue, DateTimeUnit.HOUR)
            }
        )
        relativeDateTime.date
    }

    override fun toString() = "$deltaDays days"

    companion object {
        var MULTIPLIER: Float
            get() = multiplierOverride.get() ?: defaultMultiplier
            set(value) { defaultMultiplier = value }

        /** sc-open-quests patch: a thread can evaluate at another resurvey multiplier (the app's
         *  ResurveyIntervals setting: 0.5, 1 or 2), so that one pass counts all three. */
        val multiplierOverride = ThreadLocal<Float?>()
        @Volatile private var defaultMultiplier: Float = 1f
    }
}

/** A fixed date */
class FixedDate(override val date: LocalDate) : DateFilter {
    override fun toString() = date.toString()
}
