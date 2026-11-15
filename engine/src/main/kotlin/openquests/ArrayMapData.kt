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
        if (ids.size < PARALLEL_FROM) {
            for (i in ids.indices) {
                var s = slotOf(ids[i])
                while (slots[s] != 0) s = (s + 1) and mask
                slots[s] = i + 1
            }
        } else {
            // a city's nodes: filled from all threads, each slot claimed by compare-and-set. Which id ends
            // in which slot of a run depends on who came first; what [get] answers does not.
            val chunk = 1 shl 16
            parallelMap(0, (ids.size + chunk - 1) / chunk) { c ->
                for (i in c * chunk until minOf(ids.size, (c + 1) * chunk)) {
                    var s = slotOf(ids[i])
                    while (!SLOT.compareAndSet(slots, s, 0, i + 1)) s = (s + 1) and mask
                }
            }
        }
    }

    private companion object {
        const val PARALLEL_FROM = 1 shl 20
        val SLOT: java.lang.invoke.VarHandle = java.lang.invoke.MethodHandles.arrayElementVarHandle(IntArray::class.java)
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
    /** build the [KeyIndex]es now, on all threads, instead of on the first quest's thread while the others
     *  that want one wait (a whole city; a tile's are small and often not asked for) */
    eagerKeys: Boolean = false,
    /** where each of [nodes] is by id, if the caller has made it already */
    nodeIndex: LongIndex? = null,
) : MapDataWithGeometry {
    private val nodeIndex = nodeIndex ?: LongIndex(LongArray(nodes.size) { nodes[it].id })
    private val wayIndex = LongIndex(LongArray(ways.size) { ways[it].id })
    private val relationIndex = LongIndex(LongArray(relations.size) { relations[it].id })

    override fun getNode(id: Long): Node? {
        val i = nodeIndex[id]
        return if (i < 0) null else nodes[i]
    }

    /** where node [id] is in [nodes], or -1 */
    fun nodePosition(id: Long): Int = nodeIndex[id]

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

    private val nodeKeys by if (eagerKeys) lazyOf(KeyIndex(nodes, parallel = true)) else lazy { KeyIndex(nodes) }
    private val wayKeys by if (eagerKeys) lazyOf(KeyIndex(ways, parallel = true)) else lazy { KeyIndex(ways) }
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
