package openquests

import de.westnordost.streetcomplete.data.osm.geometry.ElementGeometry
import de.westnordost.streetcomplete.data.osm.geometry.ElementPointGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Relation
import de.westnordost.streetcomplete.data.osm.mapdata.Way

/** Where each of [ids] (distinct) is in the array: an open-addressed table of positions, without
 *  boxing a key or an object per entry. */
class LongIndex(private val ids: LongArray) {
    private val shift: Int
    /** position + 1, 0 for a free slot */
    private val slots: IntArray

    init {
        var bits = 4
        while ((1L shl bits) < ids.size * 2L) bits++
        shift = 64 - bits
        slots = IntArray(1 shl bits)
        val mask = slots.size - 1
        for (i in ids.indices) {
            var s = slotOf(ids[i])
            while (slots[s] != 0) s = (s + 1) and mask
            slots[s] = i + 1
        }
    }

    private fun slotOf(id: Long) = ((id * -7046029254386353131L) ushr shift).toInt()

    /** the position of [id], or -1 */
    operator fun get(id: Long): Int {
        val mask = slots.size - 1
        var s = slotOf(id)
        while (true) {
            val i = slots[s] - 1
            if (i < 0) return -1
            if (ids[i] == id) return i
            s = (s + 1) and mask
        }
    }
}

/**
 * The positions of [ids], in insertion order, in the order a `HashMap<Long, ...>` filled with them
 * iterates: by bucket, and in a bucket by insertion. Some of SC's quests depend on that order (in
 * AddHousenumber, the first building to reach a shared address node takes it), so [ArrayMapData] keeps
 * the app's order, or counts move. A bin of 8 or more is a tree in a HashMap and may differ inside; on
 * OSM ids they all but never occur.
 */
fun hashMapOrder(ids: LongArray): IntArray {
    var capacity = 16L
    while (ids.size > capacity * 3 / 4) capacity *= 2
    val mask = capacity - 1
    val keys = LongArray(ids.size) { i ->
        val h = (ids[i] xor (ids[i] ushr 32)).toInt()
        ((((h xor (h ushr 16)).toLong() and 0xffffffffL) and mask) shl 32) or i.toLong()
    }
    java.util.Arrays.parallelSort(keys)
    return IntArray(keys.size) { keys[it].toInt() }
}

/**
 * The map data of one area, read-only, which is all a quest asks of it. SC's
 * `MutableMapDataWithGeometry` keeps six `HashMap<Long, ...>`, which on a whole city cost more than the
 * elements and have to be filled on one thread. This is lists and [LongIndex]es, built from any number
 * of threads, and a node's geometry, its position, is made when asked for. Elements must be distinct,
 * in [hashMapOrder].
 */
class ArrayMapData(
    override val boundingBox: BoundingBox,
    override val nodes: List<Node>,
    override val ways: List<Way>,
    private val wayGeometries: List<ElementGeometry?>,
    override val relations: List<Relation>,
    private val relationGeometries: List<ElementGeometry?>,
) : MapDataWithGeometry {
    private val nodeIndex = LongIndex(LongArray(nodes.size) { nodes[it].id })
    private val wayIndex = LongIndex(LongArray(ways.size) { ways[it].id })
    private val relationIndex = LongIndex(LongArray(relations.size) { relations[it].id })

    override fun getNode(id: Long): Node? {
        val i = nodeIndex[id]
        return if (i < 0) null else nodes[i]
    }

    override fun getWay(id: Long): Way? {
        val i = wayIndex[id]
        return if (i < 0) null else ways[i]
    }

    override fun getRelation(id: Long): Relation? {
        val i = relationIndex[id]
        return if (i < 0) null else relations[i]
    }

    override fun getNodeGeometry(id: Long): ElementPointGeometry? = getNode(id)?.let { ElementPointGeometry(it.position) }

    override fun getWayGeometry(id: Long): ElementGeometry? {
        val i = wayIndex[id]
        return if (i < 0) null else wayGeometries[i]
    }

    override fun getRelationGeometry(id: Long): ElementGeometry? {
        val i = relationIndex[id]
        return if (i < 0) null else relationGeometries[i]
    }

    private val nodeKeys by lazy { KeyIndex(nodes) }
    private val wayKeys by lazy { KeyIndex(ways) }
    private val relationKeys by lazy { KeyIndex(relations) }

    /** the [KeyIndex] of [list] if it is this map data's own nodes, ways or relations ([candidates]) */
    fun keyIndexOf(list: Collection<*>): KeyIndex? = when {
        list === nodes -> nodeKeys
        list === ways -> wayKeys
        list === relations -> relationKeys
        else -> null
    }

    override fun iterator(): Iterator<Element> =
        (nodes.asSequence() + ways.asSequence() + relations.asSequence()).iterator()
}
