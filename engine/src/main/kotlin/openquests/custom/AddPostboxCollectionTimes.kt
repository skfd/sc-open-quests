package openquests.custom

import de.westnordost.osm_opening_hours.parser.toOpeningHoursOrNull
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.osm.opening_hours.isSupported

/** Port of SC quests/postbox_collection_times/AddPostboxCollectionTimes.kt.
 *  getApplicableElements = mapData.filter { isApplicableTo(it) } */
object AddPostboxCollectionTimes : CustomQuest {
    override val name = "AddPostboxCollectionTimes"
    override val elementTypes = setOf(ElementType.NODE)
    override val usesAge = true

    private val filter by lazy { """
        nodes with
          amenity = post_box
          and access !~ private|no
          and collection_times:signed != no
          and (!collection_times or collection_times older today -2 years)
    """.toElementFilterExpression() }

    override fun isApplicable(element: Element): Boolean {
        if (!filter.matches(element)) return false
        val tags = element.tags
        // no collection_times yet -> new survey
        val ct = tags["collection_times"] ?: return true
        // invalid opening_hours rules -> applicable because we want to ask for opening hours again
        // be strict
        val oh = ct.toOpeningHoursOrNull(lenient = false) ?: return true
        // only display supported rules, or ambiguous rules that should be corrected
        return oh.isSupported(allowTimePoints = true, allowAmbiguity = true)
    }
}
