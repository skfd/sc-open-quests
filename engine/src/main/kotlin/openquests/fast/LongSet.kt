package openquests.fast

/**
 * A set of ids as plain longs in one array (open addressing, linear probing), for the twins whose SC code
 * asks a `HashSet<Long>` about every node of every way: no object per id put in or asked for. A removed
 * id's place is closed by moving the following ones back, so the set stays as fast after many removals.
 */
class LongSet(expected: Int = 16) {
    private var keys: LongArray
    private var shift: Int
    var size = 0
        private set

    init {
        var bits = 4
        while ((1L shl bits) < expected.toLong() * 2) bits++
        keys = LongArray(1 shl bits) { EMPTY }
        shift = 64 - bits
    }

    private constructor(keys: LongArray, shift: Int, size: Int) : this(0) {
        this.keys = keys; this.shift = shift; this.size = size
    }

    private fun home(id: Long) = ((id * -7046029254386353131L) ushr shift).toInt()

    operator fun contains(id: Long): Boolean {
        val mask = keys.size - 1
        var i = home(id)
        while (true) {
            val k = keys[i]
            if (k == id) return id != EMPTY
            if (k == EMPTY) return false
            i = (i + 1) and mask
        }
    }

    /** true if [id] was not in the set */
    fun add(id: Long): Boolean {
        require(id != EMPTY) { "the id $id cannot be kept" }
        if ((size + 1) * 2 > keys.size) grow()
        val mask = keys.size - 1
        var i = home(id)
        while (true) {
            val k = keys[i]
            if (k == id) return false
            if (k == EMPTY) { keys[i] = id; size++; return true }
            i = (i + 1) and mask
        }
    }

    /** true if [id] was in the set */
    fun remove(id: Long): Boolean {
        if (id == EMPTY) return false
        val mask = keys.size - 1
        var i = home(id)
        while (true) {
            val k = keys[i]
            if (k == EMPTY) return false
            if (k == id) break
            i = (i + 1) and mask
        }
        // close the gap: an id further on moves back into it unless its own place lies after the gap
        var j = i
        while (true) {
            j = (j + 1) and mask
            val k = keys[j]
            if (k == EMPTY) break
            val h = home(k)
            val stays = if (j > i) h > i && h <= j else h > i || h <= j
            if (!stays) { keys[i] = k; i = j }
        }
        keys[i] = EMPTY
        size--
        return true
    }

    fun copy() = LongSet(keys.copyOf(), shift, size)

    private fun grow() {
        val old = keys
        keys = LongArray(old.size * 2) { EMPTY }
        shift--
        size = 0
        for (k in old) if (k != EMPTY) add(k)
    }

    private companion object { const val EMPTY = Long.MIN_VALUE }
}
