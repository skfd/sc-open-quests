package openquests.custom

import de.westnordost.streetcomplete.data.elementfilter.filters.RelativeDate
import de.westnordost.streetcomplete.data.elementfilter.filters.TagOlderThan
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.quests.recycling_material.RecyclingMaterial

/** Port of SC quests/recycling_material/AddRecyclingContainerMaterials.kt.
 *  getApplicableElements = mapData.filter { isApplicableTo(it) } */
object AddRecyclingContainerMaterials : CustomQuest {
    override val name = "AddRecyclingContainerMaterials"
    override val elementTypes = setOf(ElementType.NODE, ElementType.WAY)
    override val usesAge = true

    private val filter by lazy { """
        nodes, ways with
          amenity = recycling
          and recycling_type = container
          and access !~ private|no
    """.toElementFilterExpression() }

    override fun isApplicable(element: Element): Boolean =
        /* Only recycling containers that do either not have any recycling:* tag yet or
         * haven't been touched for 2 years and are exclusively recycling types selectable in
         * StreetComplete. */
        filter.matches(element) && (
            !element.hasAnyRecyclingMaterials()
            || recyclingOlderThan2Years.matches(element) && !element.hasUnknownRecyclingMaterials()
        )
}

private val recyclingOlderThan2Years =
    TagOlderThan("recycling", RelativeDate(-(365 * 2).toFloat()))

private val allKnownMaterials = RecyclingMaterial.entries.map { "recycling:" + it.value }

private fun Element.hasAnyRecyclingMaterials(): Boolean =
    tags.any { it.key.startsWith("recycling:") && it.value == "yes" }

private fun Element.hasUnknownRecyclingMaterials(): Boolean =
    tags.any {
        it.key.startsWith("recycling:")
        && it.key !in allKnownMaterials
        && it.value == "yes"
    }
