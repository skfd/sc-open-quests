package openquests

/**
 * The seconds of one `timing:` log line: `timing: <group>: <name> <seconds> s, <name> <seconds> s, ...`, the names
 * in the order they were first given. These lines name the time the other log lines leave out (the start-up's
 * parts, the engine's indexes, what a city's area run does besides its quests, the files written); they only read
 * the clock, per phase or per city, never per element. Within a group the names are stretches of wall time that do
 * not overlap, so a group adds up; the one group that is not wall time says so in its name (`over threads`).
 * tools/stream/day_metrics.py reads them (`timing`); no other reader of the log matches a line that starts `timing: `.
 */
class Timing(private val group: String) {
    private val nanos = LinkedHashMap<String, Long>()

    fun add(name: String, n: Long) {
        synchronized(nanos) { nanos[name] = (nanos[name] ?: 0L) + n }
    }

    fun lap() = Lap(this)

    fun line(): String = synchronized(nanos) {
        "timing: $group: " + nanos.entries.joinToString(", ") { "%s %.2f s".format(it.key, it.value / 1e9) }
    }

    /** A clock of one thread: [to] gives the time since the last call (or since the lap was made) to a name. */
    class Lap(private val timing: Timing) {
        private var last = System.nanoTime()

        fun to(name: String) {
            val now = System.nanoTime()
            timing.add(name, now - last)
            last = now
        }

        /** the time since the last call belongs to no name of this group (another group has it) */
        fun skip() { last = System.nanoTime() }
    }
}
