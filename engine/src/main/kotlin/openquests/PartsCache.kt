package openquests

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.Closeable
import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.channels.FileChannel
import java.nio.file.StandardOpenOption

/**
 * The part outlines of a world in one binary file (DESIGN.md, "Release 1: the world day"; HANDOFF, blocker 1).
 * A run with tens of thousands of parts spent nearly all its startup opening and parsing their GeoJSON files
 * (63,353 part entries: reading the files 20.7 s, JSON 10.9 s, the polygons 2.0 s); from here each outline is one
 * positional read of its rings as raw doubles, and the polygon is built from them as [Polygon.fromGeoJson] builds it,
 * bit for bit (the same doubles in the same order, the same band count).
 *
 * An outline the cache lacks is parsed from its GeoJSON as before (counted in [Reader.parsed]). Each entry records
 * its source file's size and modification time at build, but checking them per outline costs more than the cache
 * saves on Windows, so it is opt-in ([VERIFY]); the caller decides once whether the cache is current.
 *
 * Layout, little endian: header `OQPC` magic (i32), version (i32), entries (i32), index offset (i64); the data, per
 * entry: rings (i32), then per ring its points (i32) and lat, lon f64 pairs; the index at the end, sorted by path
 * (UTF-8 bytes), per entry: path length (i32), path, source size (i64), source mtime (i64), data offset (i64), data
 * length (i32). Paths are the parts registries' `geometry` strings, relative to the run's base directory.
 */
object PartsCache {
    private const val MAGIC = 0x4350514F // "OQPC"
    private const val VERSION = 1

    /** the outlines named by every registry (each `.json` file) in [dirs], each once, written to [out] */
    fun build(dirs: List<File>, baseDir: File, out: File) {
        val t0 = System.nanoTime()
        // sorted by UTF-8 bytes, the order Reader.find searches
        val paths = java.util.TreeSet<String>(Comparator { a, b ->
            compareBytes(a.toByteArray(Charsets.UTF_8), b.toByteArray(Charsets.UTF_8)) })
        var registries = 0
        for (dir in dirs) {
            require(dir.isDirectory) { "$dir: not a directory" }
            // the registries in it, and in every directory named `parts` below it (a world's files/<f>/parts): one
            // argument for a whole world, which a .bat's 8191-character command line could not list
            val files = dir.walkTopDown()
                .filter { it.isFile && it.name.endsWith(".json") && (it.parentFile == dir || it.parentFile.name == "parts") }
                .toList()
            for (f in files) {
                registries++
                val root = Json.parseToJsonElement(f.readText()).jsonObject
                val parts = root["parts"]?.jsonArray ?: continue  // a file beside the registries that is not one
                for (e in parts) paths += e.jsonObject["geometry"]!!.jsonPrimitive.content
            }
        }
        out.absoluteFile.parentFile.mkdirs()
        val tmp = File(out.path + ".tmp")
        class Entry(val path: ByteArray, val size: Long, val mtime: Long, val offset: Long, val length: Int)
        val entries = ArrayList<Entry>(paths.size)
        RandomAccessFile(tmp, "rw").use { raf ->
            raf.setLength(0)
            val ch = raf.channel
            ch.write(header(0, 0L))
            var offset = HEADER.toLong()
            for (path in paths) {
                val src = File(baseDir, path)
                val size = src.length()
                val mtime = src.lastModified()
                val rings = Polygon.geoJsonRings(src)
                val n = 4 + rings.sumOf { 4 + 16 * (it.size / 2) }
                val b = ByteBuffer.allocate(n).order(ByteOrder.LITTLE_ENDIAN)
                b.putInt(rings.size)
                for (r in rings) { b.putInt(r.size / 2); for (v in r) b.putDouble(v) }
                b.flip()
                while (b.hasRemaining()) ch.write(b)
                entries += Entry(path.toByteArray(Charsets.UTF_8), size, mtime, offset, n)
                offset += n
            }
            val idx = ByteBuffer.allocate(entries.sumOf { 4 + it.path.size + 28 }).order(ByteOrder.LITTLE_ENDIAN)
            for (e in entries) {
                idx.putInt(e.path.size); idx.put(e.path); idx.putLong(e.size); idx.putLong(e.mtime)
                idx.putLong(e.offset); idx.putInt(e.length)
            }
            idx.flip()
            while (idx.hasRemaining()) ch.write(idx)
            ch.position(0)
            ch.write(header(entries.size, offset))
            ch.force(true)
        }
        if (out.exists()) out.delete()
        require(tmp.renameTo(out)) { "could not rename $tmp to $out" }
        log("parts cache: ${entries.size} outlines from $registries registries in ${dirs.size} dir(s), " +
            "%.1f MB, %.1f s -> $out".format(out.length() / 1e6, (System.nanoTime() - t0) / 1e9))
    }

    private const val HEADER = 20
    /** `-Dopenquests.partsCacheVerify=true`: check each source's size and time before using its entry. Off by
     *  default: on Windows those two calls were 14.1 s of a 17.6 s load (62,513 outlines), so the caller keeps the
     *  cache current instead (world_cells.py partcache: one check of the world's places.json, placesets.parts_cache) */
    private val VERIFY = System.getProperty("openquests.partsCacheVerify", "false") == "true"

    private fun header(count: Int, indexOffset: Long): ByteBuffer =
        ByteBuffer.allocate(HEADER).order(ByteOrder.LITTLE_ENDIAN).apply {
            putInt(MAGIC); putInt(VERSION); putInt(count); putLong(indexOffset); flip()
        }

    private fun compareBytes(a: ByteArray, b: ByteArray): Int {
        val n = minOf(a.size, b.size)
        for (i in 0 until n) {
            val x = a[i].toInt() and 0xff
            val y = b[i].toInt() and 0xff
            if (x != y) return x - y
        }
        return a.size - b.size
    }

    /** Reads outlines from a cache built by [build]. Not thread-safe: one per run, used while parts load. */
    class Reader(val file: File, private val baseDir: File, private val verify: Boolean = VERIFY) : Closeable {
        private val ch = FileChannel.open(file.toPath(), StandardOpenOption.READ)
        private val count: Int
        private val paths: Array<ByteArray>
        private val size: LongArray
        private val mtime: LongArray
        private val offset: LongArray
        private val length: IntArray
        /** outlines read from the cache, and parsed from their GeoJSON (not in the cache, or changed since) */
        var fromCache = 0; private set
        var parsed = 0; private set

        init {
            val h = read(0, HEADER)
            require(h.int == MAGIC) { "$file: not a parts cache" }
            require(h.int == VERSION) { "$file: parts cache version not $VERSION" }
            count = h.int
            val indexOffset = h.long
            val idx = read(indexOffset, (ch.size() - indexOffset).toInt())
            paths = arrayOfNulls<ByteArray>(count).let { a ->
                size = LongArray(count); mtime = LongArray(count); offset = LongArray(count); length = IntArray(count)
                for (i in 0 until count) {
                    val p = ByteArray(idx.int); idx.get(p); a[i] = p
                    size[i] = idx.long; mtime[i] = idx.long; offset[i] = idx.long; length[i] = idx.int
                }
                @Suppress("UNCHECKED_CAST") (a as Array<ByteArray>)
            }
        }

        private fun read(at: Long, n: Int): ByteBuffer {
            val b = ByteBuffer.allocate(n).order(ByteOrder.LITTLE_ENDIAN)
            var pos = at
            while (b.hasRemaining()) { val r = ch.read(b, pos); require(r > 0) { "$file: short read at $pos" }; pos += r }
            return b.flip()
        }

        private fun find(path: String): Int {
            val key = path.toByteArray(Charsets.UTF_8)
            var lo = 0
            var hi = count - 1
            while (lo <= hi) {
                val mid = (lo + hi) ushr 1
                val c = compareBytes(paths[mid], key)
                if (c == 0) return mid
                if (c < 0) lo = mid + 1 else hi = mid - 1
            }
            return -1
        }

        /** the outline at [path] (a registry's `geometry`), from the cache if its source is unchanged */
        /** nanoseconds in: the index lookup and the source check, the read, decoding doubles, building polygons */
        val nanos = LongArray(4)

        fun polygon(path: String): Polygon {
            val t0 = System.nanoTime()
            val src = File(baseDir, path)
            val i = find(path)
            if (i < 0 || (verify && (src.length() != size[i] || src.lastModified() != mtime[i]))) {
                parsed++
                return Polygon.fromGeoJson(src)
            }
            fromCache++
            val t1 = System.nanoTime()
            val b = read(offset[i], length[i])
            val t2 = System.nanoTime()
            val rings = ArrayList<DoubleArray>()
            repeat(b.int) {
                val r = DoubleArray(2 * b.int)
                b.asDoubleBuffer().get(r)  // the doubles at once, little endian as the buffer
                b.position(b.position() + 8 * r.size)
                rings += r
            }
            val t3 = System.nanoTime()
            return Polygon.fromRings(rings).also {
                val t4 = System.nanoTime()
                nanos[0] += t1 - t0; nanos[1] += t2 - t1; nanos[2] += t3 - t2; nanos[3] += t4 - t3
            }
        }

        override fun close() = ch.close()
    }
}
