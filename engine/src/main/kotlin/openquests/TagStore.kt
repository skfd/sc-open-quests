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
