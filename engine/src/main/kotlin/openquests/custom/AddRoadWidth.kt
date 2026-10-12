package openquests.custom

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import de.westnordost.streetcomplete.osm.ROADS_ASSUMED_TO_BE_PAVED
import de.westnordost.streetcomplete.osm.maxspeed.MAX_SPEED_TYPE_KEYS
import de.westnordost.streetcomplete.osm.surface.PAVED_SURFACES

/** Port of SC quests/width/AddRoadWidth.kt. getApplicableElements =
 *  mapData.nodes.filter { nodeFilter.matches(it) } + mapData.ways.filter { wayFilter.matches(it) } */
object AddRoadWidth : CustomQuest {
    override val name = "AddRoadWidth"
    override val elementTypes = setOf(ElementType.NODE, ElementType.WAY)
    override val usesAge = false

    private val nodeFilter by lazy { """
       nodes with
         traffic_calming ~ ${ROAD_NARROWERS.joinToString("|")}
         and (!width or source:width ~ ".*estimat.*")
         and (!maxwidth or source:maxwidth ~ ".*estimat.*")
    """.toElementFilterExpression() }

    private val wayFilter by lazy { """
        ways with (
          (
            highway ~ trunk|primary|secondary|tertiary|unclassified|residential|busway
            and (lane_markings = no or lanes < 2)
          ) or (
            highway = residential
            and (
              maxspeed < 33
              or maxspeed = walk
              or ~"${MAX_SPEED_TYPE_KEYS.joinToString("|")}" ~ ".*:(zone)?:?([1-9]|[1-2][0-9]|30)"
            )
            and lane_markings != yes and (!lanes or lanes < 2)
          )
          or highway = living_street
          or highway = service and service = alley
        )
        and area != yes
        and (!width or source:width ~ ".*estimat.*")
        and (traffic_calming !~ ${ROAD_NARROWERS.joinToString("|")} or !maxwidth or source:maxwidth ~".*estimat.*")
        and (surface ~ ${PAVED_SURFACES.joinToString("|")} or highway ~ ${ROADS_ASSUMED_TO_BE_PAVED.joinToString("|")})
        and (access !~ private|no or (foot and foot !~ private|no))
        and foot != no
        and placement != transition
    """.toElementFilterExpression() }

    override fun isApplicable(element: Element): Boolean =
        element is Node && nodeFilter.matches(element) || element is Way && wayFilter.matches(element)
}

private val ROAD_NARROWERS = setOf("choker", "chicane", "choked_table")
