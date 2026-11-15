package openquests

import de.westnordost.streetcomplete.data.elementfilter.ElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.MapData

/**
 * The positions of the elements of one list of [ArrayMapData] (its nodes, ways or relations) by tag
 * key, ascending. Built once per list, the first time a quest asks ([ArrayMapData.keyIndexOf]).
 */
class KeyIndex(elements: List<Element>, parallel: Boolean = false) {
    private val byKey: Map<String, IntArray>

    init {
        fun listsOf(from: Int, until: Int): HashMap<String, Positions> {
            val lists = HashMap<String, Positions>()
            for (i in from until until) {
                val tags = elements[i].tags
                if (tags.isEmpty()) continue
                for (key in tags.keys) lists.getOrPut(key) { Positions() }.add(i)
            }
            return lists
        }
        if (!parallel) byKey = listsOf(0, elements.size).mapValuesTo(HashMap()) { it.value.toArray() }
        else {
            // the list in pieces on all threads, then each key's positions joined in the pieces' order: ascending
            val chunk = 1 shl 16
            val pieces = parallelMap(0, (elements.size + chunk - 1) / chunk) { c ->
                listsOf(c * chunk, minOf(elements.size, (c + 1) * chunk))
            }
            val sizes = HashMap<String, Int>()
            for (p in pieces) for ((k, v) in p) sizes[k] = (sizes[k] ?: 0) + v.size
            val out = HashMap<String, IntArray>(sizes.size * 2)
            val filled = HashMap<String, Int>(sizes.size * 2)
            for ((k, n) in sizes) { out[k] = IntArray(n); filled[k] = 0 }
            for (p in pieces) for ((k, v) in p) {
                val at = filled.getValue(k)
                v.copyInto(out.getValue(k), at)
                filled[k] = at + v.size
            }
            byKey = out
        }
    }

    fun positions(key: String): IntArray = byKey[key] ?: EMPTY

    /** the ascending positions of the elements that hold at least one of [keys] */
    fun positionsOfAny(keys: Collection<String>): IntArray {
        if (keys.size == 1) return positions(keys.first())
        val all = IntArray(keys.sumOf { positions(it).size })
        var n = 0
        for (key in keys) positions(key).let { it.copyInto(all, n); n += it.size }
        all.sort()
        var distinct = 0
        for (i in all.indices) if (i == 0 || all[i] != all[i - 1]) all[distinct++] = all[i]
        return all.copyOf(distinct)
    }

    private class Positions {
        private var a = IntArray(4); private var n = 0
        fun add(v: Int) { if (n == a.size) a = a.copyOf(n * 2); a[n++] = v }
        fun toArray() = a.copyOf(n)
        val size get() = n
        fun copyInto(to: IntArray, at: Int) { a.copyInto(to, at, 0, n) }
    }

    private companion object { val EMPTY = IntArray(0) }
}

/**
 * Candidates by key: of [list] (this map data's nodes, ways or relations), the elements that hold a key
 * of one of [expr]'s clauses ([KeyReject.clauses]), in [list]'s order. Every element [expr] matches is
 * among them, for the reason [KeyReject] is exact: it holds at least one key of every clause. So
 * `candidates(list, f).filter { f.matches(it) && ... }` gives what `list.filter { ... }` gives, without
 * walking the elements that hold none of the keys. The clause with the fewest elements is used. Any
 * other list or map data, or an expression with no clause, gives [list] itself.
 */
fun <T : Element> MapData.candidates(list: Collection<T>, expr: ElementFilterExpression): List<T> {
    val index = (this as? ArrayMapData)?.keyIndexOf(list)
    val clauses = expr.keyReject.clauses
    if (index == null || clauses.isEmpty()) return list as? List<T> ?: list.toList()
    // keyIndexOf knows only this map data's own lists, which are lists
    val elements = list as List<T>
    val clause = clauses.minBy { c -> c.sumOf { index.positions(it).size } }
    val positions = index.positionsOfAny(clause)
    return object : AbstractList<T>(), RandomAccess {
        override val size get() = positions.size
        override fun get(index: Int): T = elements[positions[index]]
    }
}

/** [candidates] over the whole map data, in its iteration order (nodes, then ways, then relations), for a
 *  scan like `mapData.filter { expr.matches(it) && ... }` or SC's `mapData.filter(expr)`. */
fun MapData.candidates(expr: ElementFilterExpression): List<Element> =
    if (this !is ArrayMapData || expr.keyReject.clauses.isEmpty()) toList()
    else candidates(nodes, expr) + candidates(ways, expr) + candidates(relations, expr)
