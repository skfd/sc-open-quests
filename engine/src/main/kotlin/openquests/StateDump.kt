package openquests

import java.io.Closeable
import java.io.File
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Collections
import java.util.concurrent.atomic.AtomicLong
import kotlin.math.pow
import kotlin.math.roundToInt
import kotlin.time.Duration.Companion.days
import kotlin.time.Instant

/**
 * --dump-state: everything the run decides, per (element, quest), for the stream to start from and to be checked
 * against (DESIGN.md, "The stream: its state"). Fixed 24-byte little-endian records, in no order:
 *
 *   key   i64  id * 4 + type (0 node, 1 way, 2 relation)
 *   lat   i32  the quest's position, 1e-7 degrees
 *   lon   i32
 *   quest u16  index into the sidecar's `quests`
 *   flags u8   kind 0: the M_* bits of [matchVariants]; kind 1: the setting's bit, [M_NOW] (the default),
 *              [M_05] or [M_2]; and [HIDDEN] when an open note at asOf hides the position
 *   kind  u8   [MATCH], or [DUE]: not open now at that resurvey setting, open from `due` on (aged-only then)
 *   due   i32  kind DUE: minutes since the epoch from which the quest is open (whole days after asOf); else 0
 *
 * Every match is written whatever the notes say (flag [HIDDEN]), so the stream can hold notes as a layer of
 * its own. Quests waiting for their date: the main pass's at each of the three resurvey settings, by asking the
 * quest at [FAR_DAYS] and then halving the days in between (a quest that only `newer` tests open is not found: it
 * is not open at FAR either); the area quests' at the default setting only and only up to [AREA_DUE_DAYS] ahead
 * (the sidecar's `areaDueDays`), on a small map data round each (AreaPass.dateCandidates).
 *
 * With [places] (the run has parts), `<file>.places` holds a u32 per record, in the same order: the record's place
 * set, the parts holding its position as the engine found them (the counted parts, from the exact position, not
 * the record's rounded one); set 0 is no part. `<file>.places.json` lists the sets as indices into its `parts`,
 * the part ids (DESIGN.md, "Release 1: the world day", step 5).
 */
class StateDump(private val file: File, val places: Boolean = false, private val partIds: List<String> = emptyList()) : Closeable {
    private val channel = FileOutputStream(file).channel
    private val placeChannel = if (places) FileOutputStream(File(file.path + ".places")).channel else null
    /** a thread's records and, aligned with them, their place sets */
    private class Bufs(val rec: ByteBuffer, val place: ByteBuffer)
    private val buffers = Collections.synchronizedList(ArrayList<Bufs>())
    private val local = ThreadLocal.withInitial {
        Bufs(ByteBuffer.allocate(RECORD * 8192).order(ByteOrder.LITTLE_ENDIAN),
             ByteBuffer.allocate(4 * 8192).order(ByteOrder.LITTLE_ENDIAN)).also { buffers += it }
    }
    /** the place sets: run-local part indices, sorted, to a set number; 0 is the empty set */
    private val setIds = java.util.concurrent.ConcurrentHashMap<List<Int>, Int>().also { it[emptyList()] = 0 }
    private val setList = Collections.synchronizedList(arrayListOf<List<Int>>(emptyList()))

    /** the number of the place set [parts] (run-local part indices, any order, repeats allowed) */
    fun placeSet(parts: IntArray): Int {
        if (parts.isEmpty()) return 0
        val key = parts.distinct().sorted()
        setIds[key]?.let { return it }
        synchronized(setList) {
            return setIds.getOrPut(key) { setList.add(key); setList.size - 1 }
        }
    }
    val matches = AtomicLong()
    val dues = AtomicLong()
    /** how many days ahead the area quests were dated (AreaPass, [AREA_DUE_DAYS]); 0: not dated */
    @Volatile var areaDueDays = 0

    fun match(type: Int, id: Long, lat: Double, lon: Double, quest: Int, mask: Int, hidden: Boolean, place: Int = 0) {
        matches.incrementAndGet()
        put(type, id, lat, lon, quest, mask or (if (hidden) HIDDEN else 0), MATCH, 0, place)
    }

    /** [setting] is the variant bit of the resurvey setting the date is for: [M_NOW] (the default), [M_05] or [M_2] */
    fun due(type: Int, id: Long, lat: Double, lon: Double, quest: Int, hidden: Boolean, setting: Int, dueMinute: Int,
            place: Int = 0) {
        dues.incrementAndGet()
        put(type, id, lat, lon, quest, setting or (if (hidden) HIDDEN else 0), DUE, dueMinute, place)
    }

    private fun put(type: Int, id: Long, lat: Double, lon: Double, quest: Int, flags: Int, kind: Int, due: Int, place: Int) {
        val bufs = local.get()
        val b = bufs.rec
        if (b.remaining() < RECORD) drain(bufs)
        bufs.place.putInt(place)
        b.putLong(id * 4 + type)
        b.putInt(e7(lat))
        b.putInt(e7(lon))
        b.putShort(quest.toShort())
        b.put(flags.toByte())
        b.put(kind.toByte())
        b.putInt(due)
    }

    /** a thread's records and their place sets, written under one lock so the two files stay aligned */
    private fun drain(bufs: Bufs) {
        val b = bufs.rec
        val pb = bufs.place
        b.flip()
        pb.flip()
        synchronized(channel) {
            while (b.hasRemaining()) channel.write(b)
            if (placeChannel != null) while (pb.hasRemaining()) placeChannel.write(pb)
        }
        b.clear()
        pb.clear()
    }

    override fun close() {
        synchronized(buffers) { buffers.forEach(::drain) }
        channel.close()
        placeChannel?.let { pc ->
            pc.close()
            // the sets as indices into the part ids (a place in several cells is one id)
            val ids = LinkedHashMap<String, Int>()
            val sets = synchronized(setList) { setList.toList() }.map { set ->
                set.map { ids.getOrPut(partIds[it]) { ids.size } }.distinct().sorted()
            }
            File(file.path + ".places.json").writeText(
                "{\"record\":\"u32 place set per record of ${file.name}, in its order\",\"sets\":" +
                    sets.joinToString(",", "[", "]") { it.joinToString(",", "[", "]") } +
                    ",\"parts\":" + ids.keys.joinToString(",", "[", "]") { jsonString(it) } + "}\n")
        }
    }

    /** the sidecar `<file>.json`: what the records mean */
    fun writeSidecar(asOf: Instant, quests: List<String>) {
        File(file.path + ".json").writeText(
            "{\"asOf\":\"$asOf\",\"record\":\"key i64, lat i32, lon i32, quest u16, flags u8, kind u8, due i32\"," +
                "\"matches\":${matches.get()},\"dues\":${dues.get()},\"areaDueDays\":$areaDueDays," +
                "\"quests\":${quests.joinToString(",", "[", "]") { jsonString(it) }}}\n")
    }

    companion object {
        const val RECORD = 24

        /**
         * A coordinate in 1e-7 degrees, rounded, but kept inside the 1e-7 steps whose 6-decimal truncation toward
         * zero is the exact value's, as SC truncates it (`Double.truncate(6)`: `(x * 10.0.pow(6)).toInt()`). So the
         * stream can tell from the record alone whether an open note hides the position (OpenNotes.hides: the
         * truncated position equals a note's): `trunc(e7 / 10)` toward zero is SC's truncated value. At most 1e-7
         * from the exact value, against 0.5e-7 for plain rounding (tools/stream/notes_day.py, DESIGN.md
         * "Release 1: the world day", step 4).
         */
        fun e7(x: Double): Int {
            val r = (x * 1e7).roundToInt()
            val t = (x * 10.0.pow(6)).toInt()
            val (lo, hi) = if (t > 0 || (t == 0 && x >= 0.0)) t * 10 to t * 10 + 9 else t * 10 - 9 to t * 10
            return r.coerceIn(lo, hi)
        }
        const val MATCH = 0
        const val DUE = 1
        const val HIDDEN = 64
        /** how far ahead a waiting quest is looked for */
        const val FAR_DAYS = 40 * 366

        /**
         * The minute (since the epoch) from which [test] holds, in whole days after [EngineClock.asOf], or -1 when it
         * does not hold at FAR_DAYS either. [test] must be false at asOf; it is taken to stay true once true.
         */
        inline fun dueMinute(test: () -> Boolean): Int {
            val asOf = EngineClock.asOf
            if (!EngineClock.at(asOf + FAR_DAYS.days, test)) return -1
            var lo = 0
            var hi = FAR_DAYS
            while (hi - lo > 1) {
                val mid = (lo + hi) ushr 1
                if (EngineClock.at(asOf + mid.days, test)) hi = mid else lo = mid
            }
            return ((asOf + hi.days).epochSeconds / 60).toInt()
        }
    }
}
