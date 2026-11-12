package openquests

import openquests.custom.ScCountryInfos
import java.io.File

/** `regionids --in <points.tsv> --out <codes.tsv>`: the region ids SC's countryboundaries data gives at
 *  each point, the same lookup that gates quests by position ([regionIdsAt]). Input lines are
 *  `key<TAB>lon<TAB>lat`; output lines `key<TAB>id,id,...` in the input's order, the ids as the library
 *  returns them (subdivision first, e.g. `UA-43,RU`), empty where it names none. The place index files
 *  places by these (DESIGN.md, "Countries in the place index: StreetComplete's, not ours"). */
fun regionIds(args: List<String>) {
    val m = args.chunked(2).associate { (k, v) -> k.removePrefix("--") to v }
    require(m.keys.all { it in setOf("in", "out") }) { "regionids: unknown option(s) ${m.keys}" }
    val input = File(m["in"] ?: error("regionids: --in is required"))
    val out = File(m["out"] ?: error("regionids: --out is required"))
    val t0 = System.nanoTime()
    val b = ScCountryInfos.boundaries
    var n = 0
    out.bufferedWriter().use { w ->
        input.bufferedReader().useLines { lines ->
            for (line in lines) {
                if (line.isBlank()) continue
                val f = line.split('\t')
                require(f.size == 3) { "regionids: want key<TAB>lon<TAB>lat, got $line" }
                val ids = b.getIds(longitude = f[1].toDouble(), latitude = f[2].toDouble())
                w.write(f[0]); w.write("\t"); w.write(ids.joinToString(",")); w.write("\n")
                n++
            }
        }
    }
    log("regionids: $n points in %.1f s".format((System.nanoTime() - t0) / 1e9))
}
