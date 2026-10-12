package openquests.custom

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.osm.any
import de.westnordost.streetcomplete.osm.maxspeed.MAX_SPEED_TYPE_KEYS
import de.westnordost.streetcomplete.osm.sidewalk.Sidewalk.INVALID
import de.westnordost.streetcomplete.osm.sidewalk.parseSidewalkSides
import de.westnordost.streetcomplete.osm.surface.UNPAVED_SURFACES

/** Port of SC quests/sidewalk/AddSidewalk.kt. getApplicableElements = mapData.filter { isApplicableTo(it) } */
object AddSidewalk : CustomQuest {
    override val name = "AddSidewalk"
    override val elementTypes = setOf(ElementType.WAY)
    override val usesAge = false

    override fun isApplicable(element: Element): Boolean =
        roadsFilter.matches(element)
        && (untaggedRoadsFilter.matches(element) || element.hasInvalidOrIncompleteSidewalkTags())
}

// streets that may have sidewalk tagging
private val roadsFilter by lazy { """
    ways with
      (
        (
          highway ~ trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|residential|service|busway
          and motorroad != yes
          and expressway != yes
          and foot != no
        )
        or
        (
          highway ~ motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|residential|service|busway
          and (foot ~ yes|designated or bicycle ~ yes|designated)
        )
      )
      and area != yes
      and access !~ private|no
""".toElementFilterExpression() }

// streets that do not have sidewalk tagging yet
private val untaggedRoadsFilter by lazy { """
    ways with
      highway ~ motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|residential
      and !sidewalk and !sidewalk:both and !sidewalk:left and !sidewalk:right
      and (!maxspeed or maxspeed > 9 or maxspeed ~ [A-Z].*)
      and surface !~ ${UNPAVED_SURFACES.joinToString("|")}
      and (
        lit = yes
        or highway = residential
        or ~"${MAX_SPEED_TYPE_KEYS.joinToString("|")}" ~ ".*:(urban|.*zone.*|nsl_restricted)"
        or maxspeed <= 60
        or (foot ~ yes|designated and highway ~ motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link)
      )
      and ~foot|bicycle|bicycle:backward|bicycle:forward !~ use_sidepath
      and ~cycleway|cycleway:left|cycleway:right|cycleway:both !~ separate
""".toElementFilterExpression() }

private fun Element.hasInvalidOrIncompleteSidewalkTags(): Boolean {
    val sides = parseSidewalkSides(tags) ?: return false
    if (sides.any { it == INVALID || it == null }) return true
    return false
}
