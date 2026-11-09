package de.westnordost.streetcomplete.util.ktx

import kotlinx.datetime.LocalDate
import kotlinx.datetime.LocalDateTime
import kotlinx.datetime.Month
import kotlinx.datetime.TimeZone
import kotlinx.datetime.toLocalDateTime
import kotlin.time.Clock
import kotlin.time.Instant

/** Convert to local date (disregarding any time passed since start of day) */
fun Instant.toLocalDate(): LocalDate = toLocalDateTime().date

/** Convert to local date time, using current system default timezone */
fun Instant.toLocalDateTime(): LocalDateTime = toLocalDateTime(systemTimeZone())

/** sc-open-quests patch: the zone behind every "system default timezone" read in the vendored code:
 *  a thread's override first, so that one run can count cities in different zones. */
fun systemTimeZone(): TimeZone = systemTimeZoneOverride.get() ?: TimeZone.currentSystemDefault()
val systemTimeZoneOverride = ThreadLocal<TimeZone?>()

/** Shortcut for Clock.System.now() */
fun systemTimeNow(): Instant = systemClock.now()

/** sc-open-quests patch: the clock behind [systemTimeNow], settable so that age filters can be
 *  evaluated at an extract's timestamp instead of the wall clock. */
var systemClock: Clock = Clock.System

/** Current system time in epoch milliseconds */
fun nowAsEpochMilliseconds(): Long = systemTimeNow().toEpochMilliseconds()

/** 🤪 */
fun isApril1st(): Boolean {
    val now = systemTimeNow().toLocalDate()
    return now.day == 1 && now.month == Month.APRIL
}
