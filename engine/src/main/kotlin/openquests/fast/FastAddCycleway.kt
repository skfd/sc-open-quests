package openquests.fast

import de.westnordost.streetcomplete.data.elementfilter.filters.RelativeDate
import de.westnordost.streetcomplete.data.elementfilter.filters.TagOlderThan
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.meta.CountryInfo
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import de.westnordost.streetcomplete.osm.any
import de.westnordost.streetcomplete.osm.cycleway.Cycleway
import de.westnordost.streetcomplete.osm.cycleway.isAmbiguous
import de.westnordost.streetcomplete.osm.cycleway.parseCyclewaySides
import de.westnordost.streetcomplete.osm.maxspeed.FILTER_IS_IMPLICIT_MAX_SPEED_BUT_NOT_SLOW_ZONE
import de.westnordost.streetcomplete.osm.surface.UNPAVED_SURFACES
import openquests.candidates
import openquests.custom.ScCountryInfos

/**
 * SC's AddCycleway.getApplicableElements (ported/.../AddCycleway.kt): the same roads in the same order,
 * with what does not read the clock done once per map data ([CYCLEWAY_ROADS]) instead of in each of the
 * quest's runs (now, the two other resurvey settings, long ago): the eligible roads, the ones with no
 * cycleway tagging, and for each of the others everything `hasOldInvalidOrAmbiguousCyclewayTags` decides
 * before and after its one test of age. SC's code also finds every eligible road's centre and country
 * before it looks at the road's tags; here only a road whose answer turns on the country is placed (most
 * roads have no cycleway tags, and the function then returns before it reads the country). The country
 * of a position does not change within a run. Filters and the function's steps copied verbatim.
 */
object FastAddCycleway : FastTwin {
    override val name = "AddCycleway"
    override val usesAge = true
    override val sourceSha256 = "d051385015791839920aca800c1c701518a79b8e47429dfa3043c6ce2abe5284"
    override val shared = listOf(CYCLEWAY_ROADS)

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> {
        val roads = CYCLEWAY_ROADS.of(mapData)
        val oldRoadsWithKnownCycleways = ArrayList<Way>()
        for (i in roads.tagged.indices) {
            val way = roads.tagged[i]
            when (roads.verdict[i]) {
                YES -> oldRoadsWithKnownCycleways += way
                // SC: `if (olderThan4Years.matches(this)) return true`, then the ambiguous tags
                IF_OLD -> if (olderThan4Years.matches(way)) oldRoadsWithKnownCycleways += way
                else -> oldRoadsWithKnownCycleways += way // AMBIGUOUS: true once the age test has said no, so true either way
            }
        }
        return roads.missing + oldRoadsWithKnownCycleways
    }
}

// what `hasOldInvalidOrAmbiguousCyclewayTags(...) == true` is for a road with cycleway tagging
private const val YES: Byte = 1              // whatever its age
private const val IF_OLD: Byte = 2           // only if olderThan4Years
private const val AMBIGUOUS: Byte = 3        // old or not: its tags are ambiguous in its country

class CyclewayRoads(
    /** roadsWithMissingCycleway */
    val missing: List<Way>,
    /** the eligible roads for which hasOldInvalidOrAmbiguousCyclewayTags may be true, in the eligible roads' order */
    val tagged: List<Way>,
    val verdict: ByteArray,
)

val CYCLEWAY_ROADS = PerMapData("cycleway roads") { mapData ->
    val eligibleRoads = mapData.candidates(mapData.ways, roadsFilter).filter { roadsFilter.matches(it) }
    val roadsWithMissingCycleway = eligibleRoads.filter { untaggedRoadsFilter.matches(it) }
    val tagged = ArrayList<Way>()
    val verdict = java.io.ByteArrayOutputStream()
    for (way in eligibleRoads) {
        val v = way.verdictOfCyclewayTags(mapData)
        if (v != 0.toByte()) { tagged += way; verdict.write(v.toInt()) }
    }
    CyclewayRoads(roadsWithMissingCycleway, tagged, verdict.toByteArray())
}

/** SC's `hasOldInvalidOrAmbiguousCyclewayTags(countryInfo) == true`, step for step, up to its test of age:
 *  0 if it is false whatever the age. */
private fun Way.verdictOfCyclewayTags(mapData: MapDataWithGeometry): Byte {
    val sides = parseCyclewaySides(tags, false)
    // has no cycleway tagging
    if (sides == null) return 0
    // any cycleway tagging is not known: don't mess with that
    if (sides.any { it?.cycleway?.isUnknown == true }) return 0
    // has any invalid cycleway tags
    if (sides.any { it?.cycleway?.isInvalid == true }) return YES
    // cycleway:<side> = separate is never considered old, because the information about cycleways
    // has moved somewhere else -> to the separately mapped way
    if (sides.any { it?.cycleway == Cycleway.SEPARATE }) return 0
    // or it is older than x years: asked in each run. What follows it:
    // has any ambiguous cycleway tags
    val position = mapData.getWayGeometry(id)?.center
    val countryInfo: CountryInfo? = position?.let { ScCountryInfos.getCountryInfoByLocation(it) }
    if (countryInfo != null) {
        if (sides.any { it?.cycleway?.isAmbiguous(countryInfo) == true }) return AMBIGUOUS
    } else {
        if (sides.any { it?.cycleway == Cycleway.UNSPECIFIED_SHARED_LANE }) return AMBIGUOUS
        // for this, a countryCode is necessary, thus return null if no country code is available
        // (null is not true: the road counts only if it is old)
    }
    return IF_OLD
}

// streets that may have cycleway tagging
private val roadsFilter by lazy { """
    ways with
      highway ~ primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|residential|service|busway|living_street
      and area != yes
      and motorroad != yes
      and expressway != yes
      and bicycle_road != yes
      and cyclestreet != yes
      and bicycle != no
      and bicycle != designated
      and access !~ private|no
""".toElementFilterExpression() }

// streets that do not have cycleway tagging yet
private val untaggedRoadsFilter by lazy { """
    ways with
      (
        highway ~ primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified
        or highway = residential and (maxspeed > 33 or $FILTER_IS_IMPLICIT_MAX_SPEED_BUT_NOT_SLOW_ZONE)
      )
      and !cycleway
      and !cycleway:left
      and !cycleway:right
      and !cycleway:both
      and !sidewalk:bicycle
      and !sidewalk:left:bicycle
      and !sidewalk:right:bicycle
      and !sidewalk:both:bicycle
      and (
        !maxspeed
        or maxspeed > 20
        or $FILTER_IS_IMPLICIT_MAX_SPEED_BUT_NOT_SLOW_ZONE
      )
      and surface !~ ${UNPAVED_SURFACES.joinToString("|")}
      and ~bicycle|bicycle:backward|bicycle:forward !~ use_sidepath
      and sidewalk != separate
""".toElementFilterExpression() }

private val olderThan4Years = TagOlderThan("cycleway", RelativeDate(-(365 * 4).toFloat()))
