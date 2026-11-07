package openquests.fast

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.filter

/**
 * SC's AddAddressStreet.getApplicableElements (ported/.../AddAddressStreet.kt), with one change: whether an
 * address is a member of an associatedStreet or street relation is looked up in a set of those relations'
 * members instead of scanning every member of every such relation. The same members, so the same result;
 * on a whole city the original compares every address with every street relation (Paris 582 s, where
 * France maps streets as associatedStreet relations). Filters copied verbatim.
 */
object FastAddAddressStreet : FastTwin {
    override val name = "AddAddressStreet"
    override val usesAge = false
    override val sourceSha256 = "5656f08b3ebba8650ed90ad99c30492565bdc1d47d84c8dfe48daa907e3ed938"

    private val filter by lazy { """
        nodes, ways, relations with
          (
            (addr:housenumber or addr:housename)
            and !addr:street
            and !addr:place
            and !addr:block_number
            and !addr:block
            and !addr:substreet
            and !addr:parentstreet
          ) or (
            addr:streetnumber
            and !addr:street
            and !addr:substreet
            and !addr:parentstreet
          )
    """.toElementFilterExpression() }

    // #2112 - exclude indirect addr:street
    private val excludedWaysFilter by lazy { """
        ways with
          addr:street and addr:interpolation
    """.toElementFilterExpression() }

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> {
        val excludedWayNodeIds = mapData.ways
            .filter { excludedWaysFilter.matches(it) }
            .flatMapTo(HashSet()) { it.nodeIds }

        // the change: the street relations' members by type, instead of `none { it.contains(...) }`
        val streetMembers = ElementType.entries.associateWith { HashSet<Long>() }
        for (relation in mapData.relations) {
            val type = relation.tags["type"]
            if (type == "associatedStreet" || type == "street") {
                for (member in relation.members) streetMembers.getValue(member.type).add(member.ref)
            }
        }

        val addressesWithoutStreet = mapData.filter { address ->
            filter.matches(address)
            && address.id !in streetMembers.getValue(address.type)
            && address.id !in excludedWayNodeIds
        }

        return addressesWithoutStreet
    }
}
