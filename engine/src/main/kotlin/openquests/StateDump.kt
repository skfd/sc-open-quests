package openquests

import java.io.Closeable
import java.io.File
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Collections
import java.util.concurrent.atomic.AtomicLong
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
 * its own. Quests waiting for their date are found for the main pass's quests only (not the area quests), at
 * each of the three resurvey settings, by asking the quest at [FAR_DAYS] and then halving the days in between: a quest
 * that only `newer` tests open is not found (it is not open at FAR either).
 */
class StateDump(private val file: File) : Closeable {
    private val channel = FileOutputStream(file).channel
    private val buffers = Collections.synchronizedList(ArrayList<ByteBuffer>())
    private val local = ThreadLocal.withInitial {
        ByteBuffer.allocate(RECORD * 8192).order(ByteOrder.LITTLE_ENDIAN).also { buffers += it }
    }
    val matches = AtomicLong()
    val dues = AtomicLong()

    fun match(type: Int, id: Long, lat: Double, lon: Double, quest: Int, mask: Int, hidden: Boolean) {
        matches.incrementAndGet()
        put(type, id, lat, lon, quest, mask or (if (hidden) HIDDEN else 0), MATCH, 0)
    }

    /** [setting] is the variant bit of the resurvey setting the date is for: [M_NOW] (the default), [M_05] or [M_2] */
    fun due(type: Int, id: Long, lat: Double, lon: Double, quest: Int, hidden: Boolean, setting: Int, dueMinute: Int) {
        dues.incrementAndGet()
        put(type, id, lat, lon, quest, setting or (if (hidden) HIDDEN else 0), DUE, dueMinute)
    }

    private fun put(type: Int, id: Long, lat: Double, lon: Double, quest: Int, flags: Int, kind: Int, due: Int) {
        val b = local.get()
        if (b.remaining() < RECORD) drain(b)
        b.putLong(id * 4 + type)
        b.putInt((lat * 1e7).roundToInt())
        b.putInt((lon * 1e7).roundToInt())
        b.putShort(quest.toShort())
        b.put(flags.toByte())
        b.put(kind.toByte())
        b.putInt(due)
    }

    private fun drain(b: ByteBuffer) {
        b.flip()
        synchronized(channel) { while (b.hasRemaining()) channel.write(b) }
        b.clear()
    }

    override fun close() {
        synchronized(buffers) { buffers.forEach(::drain) }
        channel.close()
    }

    /** the sidecar `<file>.json`: what the records mean */
    fun writeSidecar(asOf: Instant, quests: List<String>) {
        File(file.path + ".json").writeText(
            "{\"asOf\":\"$asOf\",\"record\":\"key i64, lat i32, lon i32, quest u16, flags u8, kind u8, due i32\"," +
                "\"matches\":${matches.get()},\"dues\":${dues.get()}," +
                "\"quests\":${quests.joinToString(",", "[", "]") { jsonString(it) }}}\n")
    }

    companion object {
        const val RECORD = 24
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
