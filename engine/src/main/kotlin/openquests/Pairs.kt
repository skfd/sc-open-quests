package openquests

/**
 * SC's `Iterable<T>.asSequenceOfPairs()` (util/ktx/Collections.kt, the `pairs` patch in sync-sc.ps1): each
 * item with the one after it, in order. SC builds it with `sequence { }`, a coroutine whose state objects
 * and pairs the JIT cannot remove; its geometry code walks every way's positions through it several times,
 * a tenth of a run's allocated bytes. This is a plain iterator giving the same pairs. As with SC's, the
 * source is first read when the first pair is asked for, and each iteration of the sequence reads it anew.
 */
fun <T> pairsOf(source: Iterable<T>): Sequence<Pair<T, T>> = Sequence {
    object : Iterator<Pair<T, T>> {
        private var items: Iterator<T>? = null
        private var first: T? = null
        private var any = false

        private fun items(): Iterator<T> {
            items?.let { return it }
            val it = source.iterator()
            items = it
            any = it.hasNext()
            if (any) first = it.next()
            return it
        }

        override fun hasNext(): Boolean = items().hasNext() && any

        override fun next(): Pair<T, T> {
            if (!hasNext()) throw NoSuchElementException()
            val second = items!!.next()
            @Suppress("UNCHECKED_CAST")
            val pair = (first as T) to second
            first = second
            return pair
        }
    }
}
