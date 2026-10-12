package openquests

import crosby.binary.Fileformat
import crosby.binary.Osmformat
import java.io.BufferedInputStream
import java.io.DataInputStream
import java.io.EOFException
import java.io.FileInputStream
import java.util.zip.Inflater

/** Minimal OSM PBF reading on top of the protobuf classes in org.openstreetmap.pbf:osmpbf.
 *  Blobs are read sequentially (cheap), then inflated and decoded in parallel by the caller. */
class PbfFile(val header: Osmformat.HeaderBlock, val dataBlobs: List<ByteArray>)

fun readPbf(path: String): PbfFile {
    var header: Osmformat.HeaderBlock? = null
    val blobs = ArrayList<ByteArray>()
    DataInputStream(BufferedInputStream(FileInputStream(path), 1 shl 22)).use { inp ->
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
    return PbfFile(header ?: error("no OSMHeader"), blobs)
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

/** Sorted id -> packed coordinate lookup, made of per-block sorted arrays in file order. */
class SortedLongMap(blocks: List<Pair<LongArray, LongArray>>) {
    private val nonEmptyBlocks = blocks.filter { it.first.isNotEmpty() }
    private val firstIds = LongArray(nonEmptyBlocks.size) { nonEmptyBlocks[it].first[0] }
    val size: Long = nonEmptyBlocks.sumOf { it.first.size.toLong() }

    init {
        var prev = Long.MIN_VALUE
        for ((ids, _) in nonEmptyBlocks) for (id in ids) {
            require(id > prev) { "ids not sorted ($prev then $id); the file must be sorted Type_then_ID" }
            prev = id
        }
    }

    operator fun get(id: Long): Long {
        var bi = firstIds.binarySearch(id)
        if (bi < 0) bi = -bi - 2
        if (bi < 0) return NO_COORD
        val (ids, values) = nonEmptyBlocks[bi]
        val i = ids.binarySearch(id)
        return if (i >= 0) values[i] else NO_COORD
    }
}
