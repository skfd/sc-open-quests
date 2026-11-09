package openquests

import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.util.ktx.systemTimeZoneOverride
import kotlinx.datetime.TimeZone
import openquests.custom.ScCountryInfos

/** Where a quest counts in a city: nowhere, everywhere, or decided at each quest's position. */
object Gate {
    const val OFF: Byte = 0
    const val ON: Byte = 1
    const val BY_POSITION: Byte = 2
}

/**
 * How [countries] (a quest's enabledInCountries) gates [city]. A city with typed `countryCodes` is ON or
 * OFF as a whole, as it always was. A city without them (a world run's cell, which may cross a border) is
 * gated the way the app gates a quest: OsmQuestController skips a quest type whose countries do not meet
 * the downloaded bbox, then mayCreateQuest asks `countryBoundaries.isInAny(position, enabledInCountries)`
 * of each quest. The city's bbox decides it alone when one region holds the whole box or none touches
 * it; otherwise each quest's position is asked, with [regionIdsAt].
 */
fun gateOf(city: City, countries: Countries): Byte {
    city.countryCodes?.let { return if (countries.isEnabledIn(it)) Gate.ON else Gate.OFF }
    val p = city.polygon
    val b = ScCountryInfos.boundaries
    val containing by lazy { b.getContainingIds(minLongitude = p.minLon, minLatitude = p.minLat, maxLongitude = p.maxLon, maxLatitude = p.maxLat) }
    val intersecting by lazy { b.getIntersectingIds(minLongitude = p.minLon, minLatitude = p.minLat, maxLongitude = p.maxLon, maxLatitude = p.maxLat) }
    return when (countries) {
        Countries.All -> Gate.ON
        is Countries.AllExcept -> when {
            countries.codes.none { it in intersecting } -> Gate.ON
            countries.codes.any { it in containing } -> Gate.OFF
            else -> Gate.BY_POSITION
        }
        is Countries.NoneExcept -> when {
            countries.codes.any { it in containing } -> Gate.ON
            countries.codes.none { it in intersecting } -> Gate.OFF
            else -> Gate.BY_POSITION
        }
    }
}

/** The region ids SC's countryboundaries data gives at [p] (e.g. [CA-ON, CA]): what [Countries.isEnabledIn] takes. */
fun regionIdsAt(p: LatLon): List<String> = ScCountryInfos.boundaries.getIds(longitude = p.longitude, latitude = p.latitude)

/** The time zone the vendored SC code reads as "the system default" (the `zone` patch, util/ktx/Instant.kt). */
object EngineZone {
    /** runs [block] with [zone] as the current thread's zone; null leaves the thread's zone as it is */
    inline fun <T> at(zone: TimeZone?, block: () -> T): T {
        if (zone == null) return block()
        val previous = systemTimeZoneOverride.get()
        systemTimeZoneOverride.set(zone)
        try {
            return block()
        } finally {
            systemTimeZoneOverride.set(previous)
        }
    }
}
