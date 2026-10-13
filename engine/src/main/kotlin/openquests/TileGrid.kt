package openquests

import de.westnordost.streetcomplete.data.download.tiles.enclosingTilePos
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import java.io.File
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.LongAdder
import java.util.zip.GZIPOutputStream

/**
 * Counted quests per slippy-map tile at [zoom] (SC's own tile maths, `enclosingTilePos`), per quest, for
 * heatmaps. Only what `open` counts: the default resurvey multiplier, quests hidden by notes left out.
 * z14 is about 2.2 x 1.6 km in southern Ontario.
 */
class TileGrid(val zoom: Int = 14) {
    private val cells = ConcurrentHashMap<Long, LongAdder>()

    fun add(quest: Int, position: LatLon) {
        val t = position.enclosingTilePos(zoom)
        cells.computeIfAbsent((quest.toLong() shl 40) or (t.x.toLong() shl 20) or t.y.toLong()) { LongAdder() }.increment()
    }

    /** gzipped JSON: `{"asOfDate":…,"zoom":14,"quests":{"AddX":[[x,y,n],…]}}`, quests by name, cells by x, y */
    fun write(file: File, asOfDate: String, quests: List<QuestDef>) {
        val byQuest = cells.entries.groupBy { (it.key shr 40).toInt() }
        val sb = StringBuilder()
        sb.append("{\"asOfDate\":${jsonString(asOfDate)},\"zoom\":$zoom,\"quests\":{")
        byQuest.keys.sortedBy { quests[it].name }.forEachIndexed { i, qi ->
            if (i > 0) sb.append(',')
            sb.append(jsonString(quests[qi].name)).append(":[")
            byQuest.getValue(qi).map { Triple(((it.key shr 20) and 0xFFFFF).toInt(), (it.key and 0xFFFFF).toInt(), it.value.sum()) }
                .sortedWith(compareBy({ it.first }, { it.second }))
                .joinTo(sb, ",") { "[${it.first},${it.second},${it.third}]" }
            sb.append(']')
        }
        sb.append("}}\n")
        file.absoluteFile.parentFile.mkdirs()
        val tmp = File(file.path + ".tmp")
        GZIPOutputStream(tmp.outputStream()).bufferedWriter().use { it.write(sb.toString()) }
        file.delete()
        tmp.renameTo(file) || error("could not rename $tmp to $file")
    }
}
