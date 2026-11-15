package openquests

import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger

/**
 * The tag strings of a file, each once, by number. The area pass keeps every way's and tagged node's tags
 * for all the cities of a file; as a [TagMap] each, with every block's own copies of "building" and "yes",
 * they were 24M maps, 24M arrays and 13M strings that every marking cycle walked. As numbers in a
 * [TagStore] they are two int arrays, and a [TagMap] is made when a city's map data wants the element.
 */
class TagDict {
    private val ids = ConcurrentHashMap<String, Int>()
    private val next = AtomicInteger()

    fun idOf(s: String): Int = ids[s] ?: ids.computeIfAbsent(s) { next.getAndIncrement() }

    fun strings(): Array<String> {
        val out = arrayOfNulls<String>(next.get())
        for ((s, i) in ids) out[i] = s
        @Suppress("UNCHECKED_CAST")
        return out as Array<String>
    }
}

/** Tags of the elements of one block as [TagDict] numbers, key and value side by side, in the order given. */
class TagChunk(private val dict: TagDict) {
    private val known = HashMap<String, Int>()
    var kv = IntArray(1024)
        private set
    var n = 0
        private set

    private fun put(s: String) {
        if (n == kv.size) kv = kv.copyOf(n * 2)
        kv[n++] = known.getOrPut(s) { dict.idOf(s) }
    }

    fun add(tags: Map<String, String>) {
        if (tags is TagMap) tags.forEachTag { k, v -> put(k); put(v) }
        else for ((k, v) in tags) { put(k); put(v) }
    }

    /** the block's string table, and the [dict] number of each of its strings once it was asked for (-1 before) */
    private var table: Array<String>? = null
    private var tableIds = IntArray(0)

    private fun putAt(strings: Array<String>, place: Int) {
        if (table !== strings) { table = strings; tableIds = IntArray(strings.size).also { it.fill(-1) } }
        var id = tableIds[place]
        if (id < 0) { id = known.getOrPut(strings[place]) { dict.idOf(strings[place]) }; tableIds[place] = id }
        if (n == kv.size) kv = kv.copyOf(n * 2)
        kv[n++] = id
    }

    /** Tags as the file gives them: a key's and its value's places in [strings], the block's string table, side
     *  by side in [keysVals] from [from] until [until]. What [add] of the map of those strings gives, for tags
     *  with no key twice, without a look-up by string for each. */
    fun addPlaces(strings: Array<String>, keysVals: List<Int>, from: Int, until: Int) {
        for (j in from until until) putAt(strings, keysVals[j])
    }

    /** [addPlaces] for keys and values in two lists (a way's) */
    fun addPlaces(strings: Array<String>, keys: List<Int>, vals: List<Int>) {
        for (j in keys.indices) { putAt(strings, keys[j]); putAt(strings, vals[j]) }
    }
}

/** A block's string table and, for one element at a time, where its tags are in it: a way's [keys] and [vals].
 *  One per block, set anew for each way ([TagChunk.addPlaces]). */
class TagPlaces(val strings: Array<String>) {
    var keys: List<Int>? = null
    var vals: List<Int>? = null
    fun of(keys: List<Int>, vals: List<Int>): TagPlaces { this.keys = keys; this.vals = vals; return this }
}

/** The tags of elements 0 until `start.size - 1`: element i's are `kv[start[i] until start[i + 1]]`. */
class TagStore(private val start: IntArray, private val kv: IntArray, private val dict: Array<String>) {
    fun isEmpty(i: Int) = start[i] == start[i + 1]

    fun tagsOf(i: Int): Map<String, String> {
        val from = start[i]; val until = start[i + 1]
        if (from == until) return emptyMap()
        val m = TagMap((until - from) / 2)
        var j = from
        while (j < until) { m.add(dict[kv[j]], dict[kv[j + 1]]); j += 2 }
        return m
    }
}
