package openquests

import crosby.binary.Osmformat
import de.westnordost.streetcomplete.data.elementfilter.filters.RelativeDate
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Relation
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import de.westnordost.streetcomplete.util.ktx.now
import kotlinx.datetime.LocalDate
import kotlinx.datetime.TimeZone
import java.io.File
import java.lang.management.ManagementFactory
import java.lang.management.MemoryType
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.atomic.AtomicLongArray
import java.util.stream.IntStream

private const val DEFAULT_PBF = "C:/Users/kk/Code/toronto-streets-osm/data/osm/ontario-latest.osm.pbf"
private const val DEFAULT_BOUNDARIES = "C:/Users/kk/Code/ontario-farmland/cache/boundaries.json"
private const val TORONTO = 324211L

class Rect(val minLat: Double, val minLon: Double, val maxLat: Double, val maxLon: Double) {
    fun contains(lat: Double, lon: Double) = lat in minLat..maxLat && lon in minLon..maxLon
}

private val TYPES = listOf("node", "way", "relation")

/** Runs every quest filter on each tagged element whose center is in [prefilter], and counts
 *  matches inside [spikeBbox] and inside [city]. */
class Tally(val quests: List<SpikeQuest>, val city: Polygon, val prefilter: Rect, val spikeBbox: Rect) {
    val inBbox = AtomicLongArray(quests.size * 3)
    val inCity = AtomicLongArray(quests.size * 3)
    val candidates = AtomicLongArray(3)
    val noTimestamp = AtomicLongArray(3)
    val noCenter = AtomicLongArray(3)
    val matchLines = ConcurrentLinkedQueue<String>()

    fun inPrefilter(lat7: Int, lon7: Int) = prefilter.contains(lat7 / 1e7, lon7 / 1e7)

    fun offer(e: Element, type: Int, lat7: Int, lon7: Int) {
        val lat = lat7 / 1e7
        val lon = lon7 / 1e7
        candidates.incrementAndGet(type)
        if (e.timestampEdited == 0L) noTimestamp.incrementAndGet(type)
        val bbox = spikeBbox.contains(lat, lon)
        var cityKnown = false
        var inside = false
        for ((qi, q) in quests.withIndex()) {
            if (!q.filter.matches(e)) continue
            if (bbox) inBbox.incrementAndGet(qi * 3 + type)
            if (!cityKnown) { inside = city.contains(lat, lon); cityKnown = true }
            if (inside) {
                inCity.incrementAndGet(qi * 3 + type)
                matchLines += "${q.name}\t${TYPES[type]}\t${e.id}\t${e.version}\t${e.timestampEdited}\t$lat\t$lon"
            }
        }
    }
}

private fun tagsOf(keys: List<Int>, vals: List<Int>, strings: Array<String>): Map<String, String> {
    val m = HashMap<String, String>(keys.size * 2)
    for (i in keys.indices) m[strings[keys[i]]] = strings[vals[i]]
    return m
}

private class LongList {
    var a = LongArray(8000); var n = 0
    fun add(v: Long) { if (n == a.size) a = a.copyOf(n * 2); a[n++] = v }
    fun toArray() = a.copyOf(n)
}

private fun processNodes(b: Osmformat.PrimitiveBlock, t: Tally): Pair<LongArray, LongArray> {
    val ctx = BlockContext(b)
    val ids = LongList()
    val coords = LongList()
    for (g in b.primitivegroupList) {
        if (g.hasDense()) {
            val d = g.dense
            val hasInfo = d.hasDenseinfo()
            val info = d.denseinfo
            val hasKv = d.keysValsCount > 0
            var id = 0L; var lat = 0L; var lon = 0L; var ts = 0L; var kv = 0
            for (i in 0 until d.idCount) {
                id += d.getId(i); lat += d.getLat(i); lon += d.getLon(i)
                if (hasInfo) ts += info.getTimestamp(i)
                val lat7 = ctx.lat7(lat); val lon7 = ctx.lon7(lon)
                ids.add(id); coords.add(pack(lat7, lon7))
                if (!hasKv) continue
                val start = kv
                while (d.getKeysVals(kv) != 0) kv += 2
                val end = kv
                kv++
                if (end == start || !t.inPrefilter(lat7, lon7)) continue
                val tags = HashMap<String, String>((end - start))
                var j = start
                while (j < end) { tags[ctx.strings[d.getKeysVals(j)]] = ctx.strings[d.getKeysVals(j + 1)]; j += 2 }
                val version = if (hasInfo) info.getVersion(i) else 1
                val node = Node(id, LatLon(lat7 / 1e7, lon7 / 1e7), tags, version, ts * ctx.dateGranularity)
                t.offer(node, 0, lat7, lon7)
            }
        }
        for (n in g.nodesList) {
            val lat7 = ctx.lat7(n.lat); val lon7 = ctx.lon7(n.lon)
            ids.add(n.id); coords.add(pack(lat7, lon7))
            if (n.keysCount == 0 || !t.inPrefilter(lat7, lon7)) continue
            val node = Node(n.id, LatLon(lat7 / 1e7, lon7 / 1e7), tagsOf(n.keysList, n.valsList, ctx.strings),
                if (n.hasInfo()) n.info.version else 1, n.info.timestamp * ctx.dateGranularity)
            t.offer(node, 0, lat7, lon7)
        }
    }
    return ids.toArray() to coords.toArray()
}

/** Way center for the spike: plain average of its nodes (closing node counted once). */
private fun processWays(b: Osmformat.PrimitiveBlock, nodes: SortedLongMap, t: Tally): Pair<LongArray, LongArray> {
    val ctx = BlockContext(b)
    val ids = LongList()
    val centers = LongList()
    var refs = LongArray(2000)
    for (g in b.primitivegroupList) for (w in g.waysList) {
        val rc = w.refsCount
        if (refs.size < rc) refs = LongArray(rc * 2)
        var ref = 0L
        for (i in 0 until rc) { ref += w.getRefs(i); refs[i] = ref }
        val n = if (rc >= 2 && refs[0] == refs[rc - 1]) rc - 1 else rc
        var sumLat = 0L; var sumLon = 0L; var cnt = 0
        for (i in 0 until n) {
            val c = nodes[refs[i]]
            if (c == NO_COORD) continue
            sumLat += unpackLat7(c); sumLon += unpackLon7(c); cnt++
        }
        val center = if (cnt == 0) NO_COORD else pack((sumLat / cnt).toInt(), (sumLon / cnt).toInt())
        ids.add(w.id); centers.add(center)
        if (w.keysCount == 0) continue
        if (center == NO_COORD) { t.noCenter.incrementAndGet(1); continue }
        val lat7 = unpackLat7(center); val lon7 = unpackLon7(center)
        if (!t.inPrefilter(lat7, lon7)) continue
        // nodeIds left empty: no element filter looks at them, and it saves boxing ~150M longs
        val way = Way(w.id, emptyList(), tagsOf(w.keysList, w.valsList, ctx.strings),
            if (w.hasInfo()) w.info.version else 1, w.info.timestamp * ctx.dateGranularity)
        t.offer(way, 1, lat7, lon7)
    }
    return ids.toArray() to centers.toArray()
}

/** Relation center for the spike: average of its member nodes' positions and member ways'
 *  centers. Sub-relation members are ignored. */
private fun processRelations(b: Osmformat.PrimitiveBlock, nodes: SortedLongMap, ways: SortedLongMap, t: Tally) {
    val ctx = BlockContext(b)
    for (g in b.primitivegroupList) for (r in g.relationsList) {
        if (r.keysCount == 0) continue
        var memId = 0L
        var sumLat = 0L; var sumLon = 0L; var cnt = 0
        for (i in 0 until r.memidsCount) {
            memId += r.getMemids(i)
            val c = when (r.getTypes(i)) {
                Osmformat.Relation.MemberType.NODE -> nodes[memId]
                Osmformat.Relation.MemberType.WAY -> ways[memId]
                else -> NO_COORD
            }
            if (c == NO_COORD) continue
            sumLat += unpackLat7(c); sumLon += unpackLon7(c); cnt++
        }
        if (cnt == 0) { t.noCenter.incrementAndGet(2); continue }
        val lat7 = (sumLat / cnt).toInt(); val lon7 = (sumLon / cnt).toInt()
        if (!t.inPrefilter(lat7, lon7)) continue
        val rel = Relation(r.id, emptyList(), tagsOf(r.keysList, r.valsList, ctx.strings),
            if (r.hasInfo()) r.info.version else 1, r.info.timestamp * ctx.dateGranularity)
        t.offer(rel, 2, lat7, lon7)
    }
}

private fun <T> parallelMap(from: Int, until: Int, f: (Int) -> T): List<T> =
    IntStream.range(from, until).parallel().mapToObj { f(it) }.toList()

/** First blob index whose kind is >= [kind]; kinds are monotonic in a Type_then_ID sorted file. */
private fun lowerBound(blobs: List<ByteArray>, kind: BlockKind): Int {
    var lo = 0; var hi = blobs.size
    while (lo < hi) {
        val mid = (lo + hi) ushr 1
        if (decodeBlock(blobs[mid]).kind() < kind) lo = mid + 1 else hi = mid
    }
    return lo
}

private fun secs(t0: Long) = "%.1f s".format((System.nanoTime() - t0) / 1e9)

fun main(args: Array<String>) {
    val pbfPath = args.getOrElse(0) { DEFAULT_PBF }
    val boundariesPath = args.getOrElse(1) { DEFAULT_BOUNDARIES }
    val outDir = File(args.getOrElse(2) { "out" }).apply { mkdirs() }

    println("today=${LocalDate.now()} timeZone=${TimeZone.currentSystemDefault()} resurveyMultiplier=${RelativeDate.MULTIPLIER}")
    println("threads=${Runtime.getRuntime().availableProcessors()} maxHeap=${Runtime.getRuntime().maxMemory() shr 20} MB")
    val tStart = System.nanoTime()

    val quests = SPIKE_QUESTS
    // untagged elements are skipped below; make sure no filter would match them
    // (SC's own mayEvaluateToTrueWithNoTags is conservative, e.g. true for `highway ~ ...`)
    val untagged = listOf(Node(1, LatLon(0.0, 0.0)), Way(1, emptyList()), Relation(1, emptyList()))
    for (q in quests) require(untagged.none { q.filter.matches(it) }) { "${q.name} matches untagged elements" }
    val city = Polygon.fromOverpassJson(File(boundariesPath), TORONTO)
    val spikeBbox = Rect(43.58, -79.64, 43.86, -79.11)
    val prefilter = Rect(
        minOf(spikeBbox.minLat, city.minLat), minOf(spikeBbox.minLon, city.minLon),
        maxOf(spikeBbox.maxLat, city.maxLat), maxOf(spikeBbox.maxLon, city.maxLon),
    )
    val tally = Tally(quests, city, prefilter, spikeBbox)
    println("parsed ${quests.size} filters and Toronto polygon (bounds ${city.minLat},${city.minLon} - ${city.maxLat},${city.maxLon}) in ${secs(tStart)}")

    var t0 = System.nanoTime()
    val pbf = readPbf(pbfPath)
    println("read ${pbf.dataBlobs.size} blobs in ${secs(t0)}; required=${pbf.header.requiredFeaturesList} optional=${pbf.header.optionalFeaturesList} replication=${pbf.header.osmosisReplicationTimestamp}")
    val blobs = pbf.dataBlobs
    val wayStart = lowerBound(blobs, BlockKind.WAYS)
    val relStart = lowerBound(blobs, BlockKind.RELATIONS)
    println("blocks: nodes [0,$wayStart) ways [$wayStart,$relStart) relations [$relStart,${blobs.size})")

    t0 = System.nanoTime()
    val nodes = SortedLongMap(parallelMap(0, wayStart) { i ->
        decodeBlock(blobs[i]).also { require(it.kind() == BlockKind.NODES) }.let { processNodes(it, tally) }
    })
    println("nodes: ${nodes.size} in ${secs(t0)}")

    t0 = System.nanoTime()
    val ways = SortedLongMap(parallelMap(wayStart, relStart) { i ->
        decodeBlock(blobs[i]).also { require(it.kind() == BlockKind.WAYS) }.let { processWays(it, nodes, tally) }
    })
    println("ways: ${ways.size} in ${secs(t0)}")

    t0 = System.nanoTime()
    parallelMap(relStart, blobs.size) { i ->
        decodeBlock(blobs[i]).also { require(it.kind() == BlockKind.RELATIONS) }.let { processRelations(it, nodes, ways, tally) }
    }
    println("relations in ${secs(t0)}")
    val total = secs(tStart)

    println()
    println("%-26s %8s %8s %8s %8s | %18s".format("quest", "nodes", "ways", "rels", "TORONTO", "bbox n/w/r"))
    for ((qi, q) in quests.withIndex()) {
        val c = (0..2).map { tally.inCity[qi * 3 + it] }
        val b = (0..2).map { tally.inBbox[qi * 3 + it] }.joinToString("/")
        println("%-26s %8d %8d %8d %8d | %18s  %s".format(q.name, c[0], c[1], c[2], c.sum(), b, q.note))
    }
    println()
    println("tagged candidates in prefilter rect (n/w/r): ${(0..2).map { tally.candidates[it] }}")
    println("candidates without timestamp (n/w/r): ${(0..2).map { tally.noTimestamp[it] }}")
    println("tagged elements with no resolvable center (n/w/r): ${(0..2).map { tally.noCenter[it] }}")

    File(outDir, "spike-matches.tsv").bufferedWriter().use { w ->
        w.write("quest\ttype\tid\tversion\ttimestamp_ms\tlat\tlon\n")
        tally.matchLines.sorted().forEach { w.write(it); w.write("\n") }
    }

    val peakHeap = ManagementFactory.getMemoryPoolMXBeans()
        .filter { it.type == MemoryType.HEAP }.sumOf { it.peakUsage.used }
    println("total wall ${total}; peak heap (sum of pool peaks) ${peakHeap shr 20} MB")
}
