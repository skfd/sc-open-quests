package openquests.fast

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.osm.kerb.findAllKerbNodes

/** SC's own `findAllKerbNodes()` (sc/.../osm/kerb/KerbUtil.kt), unchanged, once per map data. It reads no
 *  clock, and AddKerbHeight and AddTactilePavingKerb both start from it in each of their four runs: eight
 *  identical searches per map data (London about 17 s each). */
val KERB_NODES = PerMapData<List<Node>>("kerb nodes") { it.findAllKerbNodes().toList() }

/**
 * SC's AddKerbHeight.getApplicableElements (ported/.../AddKerbHeight.kt), with one change: the kerb nodes
 * come from [KERB_NODES] instead of a search of their own. The same nodes in the same order, so the same
 * result. Filter copied verbatim.
 */
object FastAddKerbHeight : FastTwin {
    override val name = "AddKerbHeight"
    override val usesAge = true
    override val sourceSha256 = "a120e53280b83fec54c7be8a68a1815240d4e6d4f983290a9aaad1b3c4c917d3"
    override val shared = listOf(KERB_NODES)

    private val eligibleKerbsFilter by lazy { """
        nodes with
          !kerb
          or kerb ~ yes|unknown
          or kerb = raised and kerb older today -8 years
          or kerb !~ no|rolled and kerb older today -12 years
    """.toElementFilterExpression() }

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> =
        KERB_NODES.of(mapData).filter { eligibleKerbsFilter.matches(it) }
}

/**
 * SC's AddTactilePavingKerb.getApplicableElements (ported/.../AddTactilePavingKerb.kt), with one change: the
 * kerb nodes come from [KERB_NODES] instead of a search of their own. Filter copied verbatim.
 */
object FastAddTactilePavingKerb : FastTwin {
    override val name = "AddTactilePavingKerb"
    override val usesAge = true
    override val sourceSha256 = "03bea418f2f0756492fc6771858fd6a8f7c0b846cc081b3a758b7ca9ce71c36f"
    override val shared = listOf(KERB_NODES)

    private val eligibleKerbsFilter by lazy { """
        nodes with
          !tactile_paving
          or tactile_paving = unknown
          or tactile_paving = no and tactile_paving older today -8 years
          or tactile_paving = yes and tactile_paving older today -12 years
    """.toElementFilterExpression() }

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> =
        KERB_NODES.of(mapData).filter { eligibleKerbsFilter.matches(it) }
}
