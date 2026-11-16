package openquests

import crosby.binary.Fileformat
import crosby.binary.Osmformat
import java.io.BufferedInputStream
import java.io.DataInputStream
import java.io.EOFException
import java.io.FileInputStream
import java.security.DigestInputStream
import java.security.MessageDigest
import java.util.zip.Inflater

/** Minimal OSM PBF reading on top of the protobuf classes in org.openstreetmap.pbf:osmpbf.
 *  Blobs are read sequentially (cheap), then inflated and decoded in parallel by the caller. */
class PbfFile(val header: Osmformat.HeaderBlock, val dataBlobs: List<ByteArray>, val sha256: String)

/** Reads all blobs into memory, hashing the file (sha256, lowercase hex) on the way. */
fun readPbf(path: String): PbfFile {
    var header: Osmformat.HeaderBlock? = null
    val blobs = ArrayList<ByteArray>()
    val digest = MessageDigest.getInstance("SHA-256")
    DataInputStream(BufferedInputStream(DigestInputStream(FileInputStream(path), digest), 1 shl 22)).use { inp ->
        while (true) {
            val headerLen = try { inp.readInt() } catch (_: EOFException) { break }
            val hb = ByteArray(headerLen).also { inp.readFully(it) }
            val blobHeader = Fileformat.BlobHeader.parseFrom(hb)
            val data = ByteArray(blobHeader.datasize).also { inp.readFully(it) }
            when (blobHeader.type) {
                "OSMHeader" -> header = Osmformat.HeaderBlock.parseFrom(inflate(data))
                "OSMData" -> blobs += data
            }
        }
    }
    val sha = digest.digest().joinToString("") { "%02x".format(it) }
    return PbfFile(header ?: error("no OSMHeader"), blobs, sha)
}

fun inflate(blobBytes: ByteArray): ByteArray {
    val blob = Fileformat.Blob.parseFrom(blobBytes)
    return when {
        blob.hasRaw() -> blob.raw.toByteArray()
        blob.hasZlibData() -> {
            val inf = Inflater()
            inf.setInput(blob.zlibData.toByteArray())
            val out = ByteArray(blob.rawSize)
            var n = 0
            while (n < out.size) {
                val r = inf.inflate(out, n, out.size - n)
                if (r == 0 && (inf.finished() || inf.needsInput())) break
                n += r
            }
            inf.end()
            check(n == out.size) { "short zlib blob: $n of ${out.size}" }
            out
        }
        else -> error("unsupported blob compression ${blob.dataCase}")
    }
}

fun decodeBlock(blobBytes: ByteArray): Osmformat.PrimitiveBlock =
    Osmformat.PrimitiveBlock.parseFrom(inflate(blobBytes))

enum class BlockKind { NODES, WAYS, RELATIONS, OTHER }

/** Kind of the elements in this block. Fails on mixed blocks (not produced by Geofabrik/osmium). */
fun Osmformat.PrimitiveBlock.kind(): BlockKind {
    val kinds = primitivegroupList.map { g ->
        when {
            g.hasDense() || g.nodesCount > 0 -> BlockKind.NODES
            g.waysCount > 0 -> BlockKind.WAYS
            g.relationsCount > 0 -> BlockKind.RELATIONS
            else -> BlockKind.OTHER
        }
    }.toSet()
    require(kinds.size == 1) { "mixed block: $kinds" }
    return kinds.first()
}

/** String table and coordinate/date scaling of one block. Coordinates are returned as
 *  fixed-point ints in 1e-7 degrees, packed as (lat shl 32) | lon. */
class BlockContext(b: Osmformat.PrimitiveBlock) {
    val strings: Array<String> = Array(b.stringtable.sCount) { b.stringtable.getS(it).toStringUtf8() }
    private val granularity = b.granularity.toLong()
    private val latOffset = b.latOffset
    private val lonOffset = b.lonOffset
    val dateGranularity = b.dateGranularity.toLong()

    fun lat7(raw: Long): Int = ((latOffset + granularity * raw) / 100).toInt()
    fun lon7(raw: Long): Int = ((lonOffset + granularity * raw) / 100).toInt()
}

fun pack(lat7: Int, lon7: Int): Long = (lat7.toLong() shl 32) or (lon7.toLong() and 0xffffffffL)
fun unpackLat7(p: Long): Int = (p shr 32).toInt()
fun unpackLon7(p: Long): Int = p.toInt()
const val NO_COORD = Long.MIN_VALUE

/** The nodes of one block, as the main pass reads them. With [NodeBlock.keep] also each node's version and
 *  time and the tagged ones' tags, for the area pass ([NodeStore]). */
class NodeBlock(val keep: Boolean, dict: TagDict?) {
    var n = 0
        private set
    var ids = LongArray(8000); var coords = LongArray(8000)
    var versions = IntArray(if (keep) 8000 else 0); var seconds = IntArray(if (keep) 8000 else 0)
    /** the tagged nodes' positions in this block, ascending; node tagged[k]'s tags end at tagEnd[k] in [tags] */
    var tagged = IntArray(if (keep) 256 else 0); var tagEnd = IntArray(if (keep) 256 else 0)
    var taggedCount = 0
        private set
    val tags: TagChunk? = if (keep) TagChunk(dict!!) else null

    /** [millis]: the node's timestamp. Kept as seconds: OSM's are whole seconds. */
    fun add(id: Long, coord: Long, version: Int, millis: Long) {
        if (n == ids.size) {
            ids = ids.copyOf(n * 2); coords = coords.copyOf(n * 2)
            if (keep) { versions = versions.copyOf(n * 2); seconds = seconds.copyOf(n * 2) }
        }
        ids[n] = id; coords[n] = coord
        if (keep) {
            require(millis % 1000 == 0L && millis / 1000 <= Int.MAX_VALUE) { "node $id: timestamp $millis ms is not whole seconds before 2038" }
            versions[n] = version; seconds[n] = (millis / 1000).toInt()
        }
        n++
    }

    /** the tags of the node added last (not empty) */
    fun tagLast(t: Map<String, String>) {
        if (taggedCount == tagged.size) { tagged = tagged.copyOf(taggedCount * 2); tagEnd = tagEnd.copyOf(taggedCount * 2) }
        tags!!.add(t)
        tagged[taggedCount] = n - 1; tagEnd[taggedCount] = tags.n
        taggedCount++
    }
}

/**
 * Every node of the file, sorted by id, as columns: id -> packed coordinate for both passes ([get]) and,
 * when the area pass runs, each node's version and time and the tagged ones' tags, so that the area pass
 * neither reads the nodes again nor keeps its own copy of them (DESIGN.md, "Batch engine speed-up").
 * A node is found through a table of where each stretch of 256 ids starts ([bucketStart]): one read
 * of the table, then a search among the few nodes of that stretch (a search by block and then inside the
 * block was two thirds of the area pass's read of the ways).
 */
class NodeStore(blocks: List<NodeBlock>, dict: TagDict?, maxBuckets: Long = MAX_BUCKETS) {
    private val nonEmpty = blocks.filter { it.n > 0 }
    private val blockStart = IntArray(nonEmpty.size + 1)
    val count: Int
    val size: Long get() = count.toLong()
    val ids: LongArray
    val coords: LongArray
    val versions: IntArray
    private val seconds: IntArray
    /** the positions of the tagged nodes, ascending */
    val tagged: IntArray
    private val tags: TagStore?
    val keep = blocks.any { it.keep }

    init {
        val total = nonEmpty.sumOf { it.n.toLong() }
        require(total <= Int.MAX_VALUE) { "$total nodes: over what one file may hold" }
        count = total.toInt()
        for (i in nonEmpty.indices) blockStart[i + 1] = blockStart[i] + nonEmpty[i].n
        ids = LongArray(count); coords = LongArray(count)
        versions = IntArray(if (keep) count else 0); seconds = IntArray(if (keep) count else 0)
        val taggedTotal = nonEmpty.sumOf { it.taggedCount }
        val kvTotal = nonEmpty.sumOf { (it.tags?.n ?: 0).toLong() }
        require(kvTotal <= Int.MAX_VALUE) { "$kvTotal tag strings on nodes: over what one file may hold" }
        tagged = IntArray(taggedTotal)
        val tagStart = IntArray(taggedTotal + 1); val kv = IntArray(kvTotal.toInt())
        var t = 0; var kvAt = 0
        for (i in nonEmpty.indices) {
            val b = nonEmpty[i]; val at = blockStart[i]
            b.ids.copyInto(ids, at, 0, b.n); b.coords.copyInto(coords, at, 0, b.n)
            if (keep) { b.versions.copyInto(versions, at, 0, b.n); b.seconds.copyInto(seconds, at, 0, b.n) }
            for (k in 0 until b.taggedCount) { tagged[t + k] = at + b.tagged[k]; tagStart[t + k + 1] = kvAt + b.tagEnd[k] }
            b.tags?.let { it.kv.copyInto(kv, kvAt, 0, it.n); kvAt += it.n }
            t += b.taggedCount
        }
        tags = if (keep) TagStore(tagStart, kv, dict!!.strings()) else null
        var prev = Long.MIN_VALUE
        for (id in ids) {
            require(id > prev) { "ids not sorted ($prev then $id); the file must be sorted Type_then_ID" }
            prev = id
        }
    }

    /** a bit per node: is it tagged? Most are not, and a map data asks every one of its nodes */
    private val taggedBits = LongArray((count + 63) ushr 6).also { bits ->
        for (p in tagged) bits[p ushr 6] = bits[p ushr 6] or (1L shl (p and 63))
    }

    private val minId = if (count > 0) ids[0] else 0L
    private val maxId = if (count > 0) ids[count - 1] else -1L
    /** a stretch is 256 ids, or more where the file's ids span more than maxBuckets of those (OSM's do not) */
    private val bucketShift: Int = run {
        require(count == 0 || maxId - minId >= 0) { "node ids span $minId..$maxId: over what the index holds" }
        var shift = 8
        while (count > 0 && ((maxId - minId) ushr shift) >= maxBuckets) shift++
        shift
    }
    /** bucketStart[b]: the first position whose id is at least minId + (b shl bucketShift) (count past the last) */
    private val bucketStart: IntArray = run {
        val buckets = if (count > 0) (maxId - minId) ushr bucketShift else 0L
        val start = IntArray(buckets.toInt() + 2)
        var b = 0
        for (i in 0 until count) {
            val nb = ((ids[i] - minId) ushr bucketShift).toInt()
            while (b < nb) start[++b] = i
        }
        while (b < start.size - 1) start[++b] = count
        start
    }

    /** the position of node [id], or -1 */
    fun indexOf(id: Long): Int {
        if (id < minId || id > maxId) return -1
        val b = ((id - minId) ushr bucketShift).toInt()
        var lo = bucketStart[b]; var hi = bucketStart[b + 1] - 1
        while (lo <= hi) {
            val mid = (lo + hi) ushr 1
            val v = ids[mid]
            if (v < id) lo = mid + 1 else if (v > id) hi = mid - 1 else return mid
        }
        return -1
    }

    /** [indexOf], looking first at the place after [previous] (the place of the node asked for before, or -1):
     *  a way's nodes were mostly made together, so the next one is the next of the file, and no search is needed */
    fun indexOfAfter(id: Long, previous: Int): Int {
        val next = previous + 1
        return if (next < count && ids[next] == id) next else indexOf(id)
    }

    /** the packed coordinate of node [id], or [NO_COORD] */
    operator fun get(id: Long): Long {
        val i = indexOf(id)
        return if (i >= 0) coords[i] else NO_COORD
    }

    /** which of [tagged] the node at [position] is, or -1 */
    fun taggedIndexOf(position: Int): Int =
        if (taggedBits[position ushr 6] and (1L shl (position and 63)) == 0L) -1
        else tagged.binarySearch(position).let { if (it >= 0) it else -1 }

    fun tagsOf(position: Int): Map<String, String> = taggedIndexOf(position).let { if (it < 0) emptyMap() else tags!!.tagsOf(it) }

    fun timestampOf(position: Int): Long = seconds[position] * 1000L
}

/** the most entries of [NodeStore]'s table (4 bytes each): at 256 ids an entry, ids up to 34 billion apart */
private const val MAX_BUCKETS = 1L shl 27

/** Every data blob of [path] handed to [f] as it is read, [threads] at once, with at most [ahead] read
 *  but not yet handled: memory stays bounded whatever the file's size (a planet). No hash. */
fun streamPbfBlobs(path: String, threads: Int, ahead: Int = threads * 4, f: (ByteArray) -> Unit) {
    val pool = java.util.concurrent.Executors.newFixedThreadPool(threads)
    val room = java.util.concurrent.Semaphore(ahead)
    val failure = java.util.concurrent.atomic.AtomicReference<Throwable>()
    try {
        DataInputStream(BufferedInputStream(FileInputStream(path), 1 shl 22)).use { inp ->
            while (failure.get() == null) {
                val headerLen = try { inp.readInt() } catch (_: EOFException) { break }
                val hb = ByteArray(headerLen).also { inp.readFully(it) }
                val blobHeader = Fileformat.BlobHeader.parseFrom(hb)
                val data = ByteArray(blobHeader.datasize).also { inp.readFully(it) }
                if (blobHeader.type != "OSMData") continue
                room.acquire()
                pool.execute {
                    try { f(data) } catch (t: Throwable) { failure.compareAndSet(null, t) } finally { room.release() }
                }
            }
        }
    } finally {
        pool.shutdown()
        pool.awaitTermination(1, java.util.concurrent.TimeUnit.DAYS)
    }
    failure.get()?.let { throw it }
}
