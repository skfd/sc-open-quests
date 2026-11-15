package openquests

import de.westnordost.streetcomplete.data.elementfilter.AllOf
import de.westnordost.streetcomplete.data.elementfilter.AnyOf
import de.westnordost.streetcomplete.data.elementfilter.BooleanExpression
import de.westnordost.streetcomplete.data.elementfilter.Leaf
import de.westnordost.streetcomplete.data.elementfilter.Not
import de.westnordost.streetcomplete.data.elementfilter.filters.CombineFilters
import de.westnordost.streetcomplete.data.elementfilter.filters.CompareDateTagValue
import de.westnordost.streetcomplete.data.elementfilter.filters.CompareElementAge
import de.westnordost.streetcomplete.data.elementfilter.filters.CompareTagAge
import de.westnordost.streetcomplete.data.elementfilter.filters.CompareTagValue
import de.westnordost.streetcomplete.data.elementfilter.filters.ElementFilter
import de.westnordost.streetcomplete.data.elementfilter.filters.FixedDate
import de.westnordost.streetcomplete.data.elementfilter.filters.HasKey
import de.westnordost.streetcomplete.data.elementfilter.filters.HasKeyLike
import de.westnordost.streetcomplete.data.elementfilter.filters.HasTag
import de.westnordost.streetcomplete.data.elementfilter.filters.HasTagLike
import de.westnordost.streetcomplete.data.elementfilter.filters.HasTagValueLike
import de.westnordost.streetcomplete.data.elementfilter.filters.NotHasKey
import de.westnordost.streetcomplete.data.elementfilter.filters.NotHasKeyLike
import de.westnordost.streetcomplete.data.elementfilter.filters.NotHasTag
import de.westnordost.streetcomplete.data.elementfilter.filters.NotHasTagLike
import de.westnordost.streetcomplete.data.elementfilter.filters.NotHasTagValueLike
import de.westnordost.streetcomplete.data.elementfilter.filters.RegexOrSet
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import java.util.BitSet
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.LongAdder

/** `-Dopenquests.matchCache`: `true` (the default), `false` (every quest asked of every element, as before), or
 *  `verify` (both, and the run stops at the first element on which they differ). */
val MATCH_CACHE: String = System.getProperty("openquests.matchCache") ?: "true"

/**
 * The main pass asks some 140 quests of every tagged element, and most elements are alike in everything a
 * filter can see: a house with an address differs from the next house only in tags no filter names. This
 * remembers, per element type, what the filters decide for each distinct *signature*, and asks SC's
 * matchers only what the signature cannot settle.
 *
 * - A filter's leaves are of two kinds. One reads tags only (`highway ~ a|b`, `!name`, `width < 3`, a date tag
 *   against a fixed date). The other reads the clock, the resurvey setting or the element's own timestamp
 *   (`older`, `newer`, a date tag against `today`): these are *open*.
 * - An element's signature is, for each of its tags whose key some tag leaf names (or some key regex matches),
 *   the key and the *class* of the value: two values are of one class when every tag leaf on that key answers
 *   the same for both. Classes are found by asking SC's own leaves about an element holding just that tag, so
 *   nothing of a leaf is re-implemented here. Two elements of one signature get the same answer from every
 *   tag leaf: a leaf on one key reads that key's value only, and a leaf on a key regex is "some tag" or "no
 *   tag" of a per-tag test, which the signature's tags decide.
 * - For a signature, each filter quest is evaluated once in three values (a tag leaf by SC's `matches` on the
 *   element at hand, an open leaf as unknown): *false* whatever the clock, the setting and the timestamp
 *   (the quest is not asked again), *true* whatever they are (it counts, with the bits [matchVariants] gives
 *   when every variant holds), or *unknown* (the quest is asked of every such element, as before).
 * - Ported custom quests are always asked: what they read is not known here.
 *
 * So a count cannot differ from asking every quest: SC's matcher still gives every answer, once per signature
 * where the answer cannot depend on anything else. `verify` checks that on every element.
 */
class MatchCache(private val quests: List<QuestDef>, private val questsByType: Array<IntArray>) {
    /** what a signature settles: [sure] quests match with [sureMask]; [ask] quests must be asked of the element */
    class Outcome(val sure: IntArray, val sureMask: IntArray, val ask: IntArray)

    private class Key(val id: Int, val leaves: Array<ElementFilter>, val valueFree: Boolean) {
        val classOf = ConcurrentHashMap<String, Int>()
        val patterns = ConcurrentHashMap<BitSet, Int>()
        val nextClass = AtomicInteger()
    }

    private class Signature(val tags: LongArray) {
        private val hash = tags.contentHashCode()
        override fun hashCode() = hash
        override fun equals(other: Any?) = other is Signature && tags.contentEquals(other.tags)
    }

    /** three-valued filter trees, by quest index; null for a quest without a filter */
    private val trees: Array<Tri?> = Array(quests.size) { qi -> quests[qi].filter?.let { compile(it.elementExprRoot) } }

    private val exactLeaves = HashMap<String, MutableList<ElementFilter>>()
    private val regexLeaves = ArrayList<Pair<RegexOrSet, ElementFilter>>()
    private val keys = ConcurrentHashMap<String, Key>()
    private val nextKey = AtomicInteger()
    private val outcomes = Array(3) { ConcurrentHashMap<Signature, Outcome>() }
    private val scratch = ThreadLocal.withInitial { LongArray(64) }

    private val lookups = Array(3) { LongAdder() }
    private val misses = Array(3) { LongAdder() }
    private val asked = Array(3) { LongAdder() }

    init {
        for (q in quests) q.filter?.elementExprRoot?.let { collect(it) }
    }

    private fun collect(e: BooleanExpression<ElementFilter, Element>) {
        when (e) {
            is Leaf -> collect(e.value)
            is AllOf -> e.children.forEach { collect(it) }
            is AnyOf -> e.children.forEach { collect(it) }
            is Not -> e.children.forEach { collect(it) }
            else -> error("unexpected expression ${e::class}")
        }
    }

    private fun collect(f: ElementFilter) {
        if (isOpen(f)) return
        when (f) {
            is HasKey -> exactLeaves.getOrPut(f.key) { ArrayList() } += f
            is NotHasKey -> exactLeaves.getOrPut(f.key) { ArrayList() } += f
            is HasTag -> exactLeaves.getOrPut(f.key) { ArrayList() } += f
            is NotHasTag -> exactLeaves.getOrPut(f.key) { ArrayList() } += f
            is HasTagValueLike -> exactLeaves.getOrPut(f.key) { ArrayList() } += f
            is NotHasTagValueLike -> exactLeaves.getOrPut(f.key) { ArrayList() } += f
            is CompareTagValue -> exactLeaves.getOrPut(f.key) { ArrayList() } += f
            is CompareDateTagValue -> exactLeaves.getOrPut(f.key) { ArrayList() } += f
            is HasKeyLike -> regexLeaves += RegexOrSet.from(f.key) to f
            is NotHasKeyLike -> regexLeaves += RegexOrSet.from(f.key) to f
            is HasTagLike -> regexLeaves += RegexOrSet.from(f.key) to f
            is NotHasTagLike -> regexLeaves += RegexOrSet.from(f.key) to f
            is CombineFilters -> f.filters.forEach { collect(it) }
            is CompareTagAge, is CompareElementAge -> error("open leaf") // isOpen
        }
    }

    private fun key(name: String): Key = keys[name] ?: run {
        val leaves = exactLeaves[name].orEmpty() + regexLeaves.filter { it.first.matches(name) }.map { it.second }
        val made = if (leaves.isEmpty()) UNREFERENCED else Key(
            nextKey.getAndIncrement(), leaves.toTypedArray(),
            leaves.all { it is HasKey || it is NotHasKey || it is HasKeyLike || it is NotHasKeyLike },
        )
        keys.putIfAbsent(name, made) ?: made
    }

    private fun classOf(key: Key, name: String, value: String): Int {
        if (key.valueFree) return 0
        key.classOf[value]?.let { return it }
        val probe = Node(0, ORIGIN, mapOf(name to value))
        val pattern = BitSet(key.leaves.size)
        for (i in key.leaves.indices) if (key.leaves[i].matches(probe)) pattern.set(i)
        val c = key.patterns[pattern] ?: synchronized(key) {
            key.patterns[pattern] ?: key.nextClass.getAndIncrement().also { key.patterns[pattern] = it }
        }
        // a key with free text for values (a name, a width) is not remembered value by value for ever
        if (key.classOf.size < MAX_VALUES) key.classOf[value] = c
        return c
    }

    /** what [e]'s signature settles; null for an element without tags (never matched, and not worth a signature) */
    fun outcome(type: Int, e: Element): Outcome? {
        val tags = e.tags
        if (tags.isEmpty()) return null
        var sig = scratch.get()
        if (sig.size < tags.size) { sig = LongArray(tags.size * 2); scratch.set(sig) }
        var n = 0
        if (tags is TagMap) {
            tags.forEachTag { k, v ->
                val key = key(k)
                if (key !== UNREFERENCED) sig[n++] = (key.id.toLong() shl 32) or classOf(key, k, v).toLong()
            }
        } else {
            for ((k, v) in tags) {
                val key = key(k)
                if (key !== UNREFERENCED) sig[n++] = (key.id.toLong() shl 32) or classOf(key, k, v).toLong()
            }
        }
        // a few tags, in any order: insertion sort
        for (i in 1 until n) {
            val x = sig[i]
            var j = i - 1
            while (j >= 0 && sig[j] > x) { sig[j + 1] = sig[j]; j-- }
            sig[j + 1] = x
        }
        val signature = Signature(sig.copyOf(n))
        lookups[type].increment()
        val map = outcomes[type]
        val known = map[signature]
        val out = known ?: settle(type, e).also {
            misses[type].increment()
            if (map.size < MAX_SIGNATURES) map.putIfAbsent(signature, it)
        }
        asked[type].add(out.ask.size.toLong())
        return out
    }

    private fun settle(type: Int, e: Element): Outcome {
        val sure = IntArray(questsByType[type].size)
        val mask = IntArray(sure.size)
        val ask = IntArray(sure.size)
        var ns = 0
        var na = 0
        for (qi in questsByType[type]) {
            val tree = trees[qi]
            when (tree?.eval(e) ?: UNKNOWN) {
                TRUE -> { sure[ns] = qi; mask[ns++] = if (quests[qi].usesAge) M_NOW or M_05 or M_2 else M_NOW }
                UNKNOWN -> ask[na++] = qi
            }
        }
        return Outcome(sure.copyOf(ns), mask.copyOf(ns), ask.copyOf(na))
    }

    fun logStats() {
        for (t in 0..2) {
            val n = lookups[t].sum()
            if (n == 0L) continue
            log("match cache, ${TYPE_NAMES[t]}s: $n elements, ${outcomes[t].size} signatures, ${misses[t].sum()} settled " +
                "(%.2f%%), %.1f quests asked an element (of ${questsByType[t].size})".format(100.0 * misses[t].sum() / n, asked[t].sum().toDouble() / n))
        }
        val named = keys.entries.filter { it.value !== UNREFERENCED }
        log("match cache: ${named.size} keys named by a filter (${keys.size} seen); most values remembered: " +
            named.sortedByDescending { it.value.classOf.size }.take(8)
                .joinToString(", ") { "${it.key} ${it.value.classOf.size} in ${it.value.nextClass.get()} classes" })
    }

    companion object {
        /** signatures remembered per element type; past this an element is settled anew each time */
        const val MAX_SIGNATURES = 2_000_000
        /** values remembered per key; past this a value's class is worked out each time */
        const val MAX_VALUES = 200_000
        private val ORIGIN = LatLon(0.0, 0.0)
        private val UNREFERENCED = Key(-1, emptyArray(), true)

        const val FALSE = 0
        const val TRUE = 1
        const val UNKNOWN = 2

        /** reads more than tags: the clock, the resurvey setting, the element's timestamp */
        private fun isOpen(f: ElementFilter): Boolean = when (f) {
            is CompareTagAge, is CompareElementAge -> true
            is CompareDateTagValue -> f.dateFilter !is FixedDate
            else -> false
        }

        private fun compile(e: BooleanExpression<ElementFilter, Element>?): Tri = when (e) {
            null -> Tri.Const(TRUE)
            is Leaf -> compile(e.value)
            is AllOf -> Tri.All(e.children.map { compile(it) }.toTypedArray())
            is AnyOf -> Tri.Any(e.children.map { compile(it) }.toTypedArray())
            is Not -> Tri.Not(compile(e.children.single()))
            else -> error("unexpected expression ${e::class}")
        }

        private fun compile(f: ElementFilter): Tri = when {
            f is CombineFilters -> Tri.All(f.filters.map { compile(it) }.toTypedArray())
            isOpen(f) -> Tri.Const(UNKNOWN)
            else -> Tri.Tags(f)
        }
    }

    /** a filter tree in three values: SC's AllOf/AnyOf/Not over [FALSE], [TRUE] and [UNKNOWN] */
    private sealed class Tri {
        abstract fun eval(e: Element): Int

        class Const(val value: Int) : Tri() {
            override fun eval(e: Element) = value
        }
        class Tags(val leaf: ElementFilter) : Tri() {
            override fun eval(e: Element) = if (leaf.matches(e)) TRUE else FALSE
        }
        class All(val children: Array<Tri>) : Tri() {
            override fun eval(e: Element): Int {
                var r = TRUE
                for (c in children) when (c.eval(e)) { FALSE -> return FALSE; UNKNOWN -> r = UNKNOWN }
                return r
            }
        }
        class Any(val children: Array<Tri>) : Tri() {
            override fun eval(e: Element): Int {
                var r = FALSE
                for (c in children) when (c.eval(e)) { TRUE -> return TRUE; UNKNOWN -> r = UNKNOWN }
                return r
            }
        }
        class Not(val child: Tri) : Tri() {
            override fun eval(e: Element) = when (child.eval(e)) { FALSE -> TRUE; TRUE -> FALSE; else -> UNKNOWN }
        }
    }
}
