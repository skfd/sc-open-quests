package openquests

/**
 * Each city's elements, from the elements' [CitySets] ids: made once for all the cities, where [scan] reads every
 * element's id for each city (a tier 2 phase's rectangles: 587 s summed for the ways, tagged nodes and relations).
 * City c's are `items[start[c] until start[c + 1]]`, in the elements' order, so each city's list is what [scan]
 * gives it. Two int arrays: 4 bytes for each (city, element) pair and for each city.
 */
class CityElements private constructor(private val start: IntArray, private val items: IntArray) {
    /** how many (city, element) pairs it holds */
    val size: Int get() = items.size

    /** the bytes of its two arrays */
    val bytes: Long get() = 4L * (start.size + items.size) + 32

    fun count(city: Int): Int = start[city + 1] - start[city]

    /** city [city]'s elements, a new array each time */
    fun of(city: Int): IntArray = items.copyOfRange(start[city], start[city + 1])

    companion object {
        /** the (city, element) pairs of [setIds], an element's [CitySets] id each */
        fun pairs(sets: CitySets, setIds: IntArray): Long {
            val perSet = IntArray(sets.size)
            for (id in setIds) perSet[id]++
            var total = 0L
            for (id in perSet.indices) if (perSet[id] != 0) total += perSet[id].toLong() * sets[id].size
            return total
        }

        /**
         * The index of the elements whose set ids are [setIds] (element i's is `setIds[i]`), for [cityCount] cities.
         * An element stands in its cities' lists as `values[i]`, or as i without [values]. Counted, then filled, the
         * elements in order: a city's list ascends as the elements (and their values) do. Null when the pairs are
         * more than one array holds: the caller then reads the ids for each city, as [scan] does.
         */
        fun of(sets: CitySets, cityCount: Int, setIds: IntArray, values: IntArray? = null): CityElements? {
            // the ids are final: every set an element has is in [sets] by now
            val perSet = IntArray(sets.size)
            for (id in setIds) perSet[id]++
            val counts = LongArray(cityCount)
            for (id in perSet.indices) if (perSet[id] != 0) for (c in sets[id]) counts[c] += perSet[id].toLong()
            val total = counts.sum()
            if (total > Int.MAX_VALUE - 16) return null
            val start = IntArray(cityCount + 1)
            for (c in 0 until cityCount) start[c + 1] = start[c] + counts[c].toInt()
            val at = start.copyOf(cityCount)
            val items = IntArray(total.toInt())
            for (i in setIds.indices) {
                val id = setIds[i]
                if (id == 0) continue
                val v = if (values == null) i else values[i]
                if (id <= cityCount) items[at[id - 1]++] = v // CitySets: the set {c} is c + 1
                else for (c in sets[id]) items[at[c]++] = v
            }
            return CityElements(start, items)
        }

        /** City [city]'s elements read off every element's set id, as before the index: its way back
         *  (`-Dopenquests.areaIndex=false`) and what its tests hold it against. [inCity]: [CitySets.membersOf] the city. */
        fun scan(inCity: BooleanArray, setIds: IntArray, values: IntArray? = null): IntArray {
            var n = 0
            for (set in setIds) if (inCity[set]) n++
            val out = IntArray(n)
            n = 0
            for (i in setIds.indices) if (inCity[setIds[i]]) out[n++] = if (values == null) i else values[i]
            return out
        }
    }
}
