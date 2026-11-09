package openquests

import de.westnordost.streetcomplete.data.elementfilter.AllOf
import de.westnordost.streetcomplete.data.elementfilter.AnyOf
import de.westnordost.streetcomplete.data.elementfilter.BooleanExpression
import de.westnordost.streetcomplete.data.elementfilter.Leaf
import de.westnordost.streetcomplete.data.elementfilter.filters.CombineFilters
import de.westnordost.streetcomplete.data.elementfilter.filters.CompareDateTagValue
import de.westnordost.streetcomplete.data.elementfilter.filters.CompareTagValue
import de.westnordost.streetcomplete.data.elementfilter.filters.ElementFilter
import de.westnordost.streetcomplete.data.elementfilter.filters.HasKey
import de.westnordost.streetcomplete.data.elementfilter.filters.HasTag
import de.westnordost.streetcomplete.data.elementfilter.filters.HasTagValueLike
import de.westnordost.streetcomplete.data.osm.mapdata.Element

/** The bit of [key] in [TagMap.keyBits]. */
private fun keyBit(key: String): Long {
    val h = key.hashCode()
    return 1L shl (h xor (h ushr 6) xor (h ushr 12) xor (h ushr 18))
}

/**
 * An element's tags, read-only once built: keys and values side by side in one array, in the order
 * given, plus [keyBits], one bit per key hash. An element has a few tags and most lookups are for a key
 * it does not have, which [keyBits] answers without touching the array. A plain `Map<String, String>`
 * to SC's code; [KeyReject] uses [keyBits] directly.
 */
class TagMap(capacity: Int) : AbstractMap<String, String>() {
    private var kv = arrayOfNulls<String>(capacity * 2)
    private var used = 0
    /** a set of bits that holds the bit of every key: a bit that is off means no such key */
    var keyBits = 0L
        private set

    /** Adds a tag while building; as in a HashMap, a key given twice keeps the last value. */
    fun add(key: String, value: String) {
        val bit = keyBit(key)
        if (keyBits and bit != 0L) {
            var i = 0
            while (i < used) {
                if (kv[i] == key) { kv[i + 1] = value; return }
                i += 2
            }
        }
        if (used == kv.size) kv = kv.copyOf(maxOf(4, used * 2))
        kv[used] = key
        kv[used + 1] = value
        used += 2
        keyBits = keyBits or bit
    }

    override val size: Int get() = used / 2

    override fun isEmpty() = used == 0

    override fun get(key: String): String? {
        if (keyBits and keyBit(key) == 0L) return null
        var i = 0
        while (i < used) {
            if (kv[i] == key) return kv[i + 1]
            i += 2
        }
        return null
    }

    override fun containsKey(key: String) = get(key) != null

    override val keys: Set<String> get() = object : AbstractSet<String>() {
        override val size get() = this@TagMap.size
        override fun contains(element: String) = containsKey(element)
        override fun iterator() = object : Iterator<String> {
            private var i = 0
            override fun hasNext() = i < used
            override fun next(): String {
                if (i >= used) throw NoSuchElementException()
                return kv[i].also { i += 2 }!!
            }
        }
    }

    override val entries: Set<Map.Entry<String, String>> get() = object : AbstractSet<Map.Entry<String, String>>() {
        override val size get() = this@TagMap.size
        override fun iterator() = object : Iterator<Map.Entry<String, String>> {
            private var i = 0
            override fun hasNext() = i < used
            override fun next(): Map.Entry<String, String> {
                if (i >= used) throw NoSuchElementException()
                return java.util.AbstractMap.SimpleImmutableEntry(kv[i]!!, kv[i + 1]!!).also { i += 2 }
            }
        }
    }
}

/**
 * The fast reject of one [de.westnordost.streetcomplete.data.elementfilter.ElementFilterExpression]
 * (the `fastreject` patch): most of a count is quests asking "is this you?" of an element that holds
 * none of their keys. Worked out once from the expression: clauses of keys, such that an element the
 * expression matches holds at least one key of every clause. An element that fails a clause cannot
 * match, whatever its values or age, so it is rejected without evaluating anything. Anything that can
 * hold without a key (`!a`, `a != b`, `older today -1 years`) gives no clause, and an expression with
 * no clause rejects nothing. [mayMatch] may say yes wrongly but never no wrongly, so counts do not change.
 */
class KeyReject private constructor(
    private val masks: LongArray,
    /** every clause worked out, not only the [MAX_CLAUSES] smallest the masks use ([candidates]) */
    val clauses: List<Set<String>>,
) {

    fun mayMatch(element: Element): Boolean {
        val tags = element.tags
        // an untagged element holds no key, and AreaPass gives it emptyMap(), not a TagMap
        if (tags.isEmpty()) return masks.isEmpty()
        if (tags !is TagMap) return true
        val bits = tags.keyBits
        for (mask in masks) if (bits and mask == 0L) return false
        return true
    }

    companion object {
        private const val MAX_CLAUSES = 6

        fun of(root: BooleanExpression<ElementFilter, Element>?): KeyReject {
            val clauses = if (root == null) emptyList() else clausesOf(root)
            val smallestFirst = clauses.sortedBy { it.size }.take(MAX_CLAUSES)
            return KeyReject(LongArray(smallestFirst.size) { i ->
                smallestFirst[i].fold(0L) { mask, key -> mask or keyBit(key) }
            }, clauses)
        }

        /** every clause must hold for [e] to hold */
        internal fun clausesOf(e: BooleanExpression<ElementFilter, Element>): List<Set<String>> = when (e) {
            is Leaf -> clausesOf(e.value)
            is AllOf -> e.children.flatMap { clausesOf(it) }
            // one child holding is enough, so a clause of the whole must take in one clause of every
            // child, and a child with none leaves the whole with none
            is AnyOf -> {
                val perChild = e.children.map { child -> clausesOf(child).minByOrNull { it.size } }
                if (perChild.any { it == null }) emptyList() else listOf(perChild.flatMapTo(HashSet()) { it!! })
            }
            else -> emptyList() // Not
        }

        private fun clausesOf(f: ElementFilter): List<Set<String>> = when (f) {
            is HasKey -> listOf(setOf(f.key))
            is HasTag -> listOf(setOf(f.key))
            is HasTagValueLike -> listOf(setOf(f.key))
            is CompareTagValue -> listOf(setOf(f.key))
            is CompareDateTagValue -> listOf(setOf(f.key))
            is CombineFilters -> f.filters.flatMap { clausesOf(it) }
            else -> emptyList()
        }
    }
}
