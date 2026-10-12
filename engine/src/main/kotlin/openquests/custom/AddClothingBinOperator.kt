package openquests.custom

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.Node

/** Port of SC quests/clothing_bin_operator/AddClothingBinOperator.kt.
 *  getApplicableElements = mapData.nodes.filter { filter.matches(it) && it.tags.hasNoOtherRecyclingTags() } */
object AddClothingBinOperator : CustomQuest {
    override val name = "AddClothingBinOperator"
    override val elementTypes = setOf(ElementType.NODE)
    override val usesAge = false

    /* not the complete filter, see below: we want to filter out additionally all elements that
       contain any recycling:* = yes that is not shoes or clothes but this can not be expressed
       in the elements filter syntax */
    private val filter by lazy { """
        nodes with amenity = recycling and recycling_type = container
         and recycling:clothes = yes
         and !operator and !name and !brand
         and operator:signed != no
         and brand:signed != no
    """.toElementFilterExpression() }

    override fun isApplicable(element: Element): Boolean =
        element is Node && filter.matches(element) && element.tags.hasNoOtherRecyclingTags()

    private fun Map<String, String>.hasNoOtherRecyclingTags(): Boolean =
        entries.none { (key, value) ->
            key.startsWith("recycling:")
            && key != "recycling:shoes"
            && key != "recycling:clothes"
            && value == "yes"
        }
}
