package openquests

import de.westnordost.streetcomplete.data.elementfilter.filters.RelativeDate
import kotlinx.datetime.LocalDate
import kotlinx.datetime.LocalTime
import kotlinx.datetime.TimeZone
import kotlinx.datetime.atTime
import kotlinx.datetime.toInstant
import kotlinx.datetime.toLocalDateTime
import kotlinx.serialization.json.Json
import openquests.custom.ScFeatures
import kotlinx.serialization.json.jsonObject
import java.io.File
import java.lang.management.ManagementFactory
import java.lang.management.MemoryType
import java.util.concurrent.TimeUnit
import kotlin.system.exitProcess
import kotlin.time.Instant

private const val USAGE = """usage: sc-open-quests-engine count --pbf <file.osm.pbf> --quests <data/quests/vX.json>
           --cities <config/cities.json> --out <docs/data> [--source-meta <meta.json>]
           [--today <ISO instant or date>] [--dump-matches <file.tsv> --dump-quests <Name,Name>]
           [--dump-elements <file.jsonl> --dump-city <cityId>] [--area-unit tiles|city]
           [--notes <clip.jsonl>] [--grid <dir>] [--resurvey-multiplier 0.5|1|2] [--parts <dir>]

Writes <out>/snapshots/<asOfDate>.json and <out>/quests.json (see DATA-FORMAT.md). Age filters are
evaluated at the extract's osmosis_replication_timestamp; --today overrides that (tests). A bare date
means noon of that day in the cities' time zone. Paths are relative to the working directory.
--dump-elements writes every tagged element whose quest position is in that city, as input for
tools/sc-harness CheckCustomQuests. The area quests run on one map data per city (the app after
downloading the whole city; also the oracle's exact input); --area-unit tiles runs them per z16 tile,
the app's smallest download.
--notes: a clip of the planet notes dump (tools/clip_notes.py) that reaches asOf. The notes open at asOf
hide the quests at their positions, and the note quest is counted. Without it, neither.
Age quests are also counted at the app's other resurvey settings (0.5 and 2: open05/aged05, open2/aged2 in
the snapshot); --resurvey-multiplier sets the default the run counts at instead of 1 (checks only).
--grid writes <dir>/<asOfDate>.json.gz: counted quests per z14 tile, for heatmaps.
--parts: the parts registries (config/parts); a city with <dir>/<cityId>.json gets the open quests of
each of its parts in the snapshot, counted from the city's own quests by position. Nothing else changes."""

class CountOptions(
    val pbf: File,
    val quests: File,
    val cities: File,
    val out: File?,
    val sourceMeta: File? = null,
    val today: Instant? = null,
    val dumpMatches: File? = null,
    val dumpQuests: Set<String> = emptySet(),
    val dumpElements: File? = null,
    val dumpCity: String? = null,
    val areaUnit: AreaUnit = AreaUnit.CITY,
    val notes: File? = null,
    val grid: File? = null,
    val resurveyMultiplier: Float = 1f,
    val parts: File? = null,
    val baseDir: File = File("."),
)

class CountResult(val engine: Engine, val meta: SnapshotMeta, val registry: Registry)

fun main(args: Array<String>) {
    try {
        if (args.isEmpty() || args[0] in setOf("-h", "--help", "help")) { println(USAGE); return }
        require(args[0] == "count") { "unknown command ${args[0]}\n$USAGE" }
        val opts = parseArgs(args.drop(1))
        count(opts)
    } catch (e: Throwable) {
        System.err.println("error: ${e.message ?: e}")
        if (e !is IllegalArgumentException) e.printStackTrace()
        exitProcess(1)
    }
}

fun parseArgs(args: List<String>): CountOptions {
    val m = HashMap<String, String>()
    var i = 0
    while (i < args.size) {
        val k = args[i]
        require(k.startsWith("--") && i + 1 < args.size) { "bad argument '$k'\n$USAGE" }
        m[k.removePrefix("--")] = args[i + 1]
        i += 2
    }
    val known = setOf("pbf", "quests", "cities", "out", "source-meta", "today", "dump-matches", "dump-quests", "dump-elements", "dump-city", "area-unit", "notes", "grid", "resurvey-multiplier", "parts")
    require(m.keys.all { it in known }) { "unknown option(s) ${m.keys - known}\n$USAGE" }
    fun req(k: String) = File(m[k] ?: throw IllegalArgumentException("--$k is required\n$USAGE"))
    return CountOptions(
        pbf = req("pbf"),
        quests = req("quests"),
        cities = req("cities"),
        out = req("out"),
        sourceMeta = m["source-meta"]?.let(::File),
        today = m["today"]?.let(::parseToday),
        dumpMatches = m["dump-matches"]?.let(::File),
        dumpQuests = m["dump-quests"]?.split(',')?.map { it.trim() }?.filter { it.isNotEmpty() }?.toSet().orEmpty(),
        dumpElements = m["dump-elements"]?.let(::File),
        dumpCity = m["dump-city"],
        areaUnit = m["area-unit"]?.let { AreaUnit.valueOf(it.uppercase()) } ?: AreaUnit.CITY,
        notes = m["notes"]?.let(::File),
        grid = m["grid"]?.let(::File),
        resurveyMultiplier = m["resurvey-multiplier"]?.toFloat()?.also {
            require(it in setOf(0.5f, 1f, 2f)) { "--resurvey-multiplier: the app offers 0.5, 1 and 2" }
        } ?: 1f,
        parts = m["parts"]?.let(::File),
    ).also { require((it.dumpElements == null) == (it.dumpCity == null)) { "--dump-elements and --dump-city go together" } }
}

/** An ISO instant (2026-10-11T16:00:00Z) or a date (2026-10-11, noon in the system time zone). */
fun parseToday(s: String): Instant =
    if (s.length == 10) LocalDate.parse(s).atTime(LocalTime(12, 0)).toInstant(TimeZone.currentSystemDefault())
    else Instant.parse(s)

fun count(opts: CountOptions): CountResult {
    val tStart = System.nanoTime()
    val registry = Registry.load(opts.quests, withNotes = opts.notes != null)
    val cities = loadCities(opts.cities, opts.baseDir)
    require(cities.isNotEmpty()) { "no cities in ${opts.cities}" }

    // SC's date filters use the JVM's default zone; all cities must share it
    val zone = TimeZone.currentSystemDefault()
    val zones = cities.map { it.timeZone }.toSet()
    require(zones == setOf(zone.id)) {
        "cities use time zone(s) $zones but the JVM runs in ${zone.id}; start it with -Duser.timezone=${zones.first()} " +
            "(cities in different zones need separate runs)"
    }
    RelativeDate.MULTIPLIER = opts.resurveyMultiplier
    // SC's getFeature() reads osmfeatures in the default locale; only the en-CA presets are bundled
    val language = java.util.Locale.getDefault().toLanguageTag()
    require(language == ScFeatures.LANGUAGE) {
        "the JVM runs in locale $language; start it with -Duser.language=en -Duser.country=CA (feature presets are bundled for ${ScFeatures.LANGUAGE})"
    }

    val parts = opts.parts?.let { loadParts(it, cities, opts.baseDir) }.orEmpty()
    val engine = Engine(registry, cities, parts)
    if (opts.grid != null) engine.grid = TileGrid()
    engine.dumpQuests = opts.dumpQuests
    engine.areaUnit = opts.areaUnit
    opts.dumpCity?.let { id ->
        engine.dumpElementsCity = cities.indexOfFirst { it.id == id }.also { require(it >= 0) { "--dump-city: no city $id" } }
    }
    log("${registry.quests.size} quests in ${opts.quests.path} (${engine.quests.size} counted: " +
        "${registry.filterQuests.size} filter, ${engine.quests.count { it.custom != null || it.area != null }} ported custom" +
        "${if (opts.notes != null) ", the note quest" else ""}), ${cities.size} cities" +
        (if (opts.parts != null) " (${parts.size} parts in ${parts.map { it.city }.distinct().size})" else "") + "; " +
        "threads=${Runtime.getRuntime().availableProcessors()} maxHeap=${Runtime.getRuntime().maxMemory() shr 20} MB")

    var t0 = System.nanoTime()
    val pbf = readPbf(opts.pbf.path)
    val replication = pbf.header.osmosisReplicationTimestamp
    require(replication > 0) { "${opts.pbf}: header has no osmosis_replication_timestamp" }
    val extractTimestamp = Instant.fromEpochSeconds(replication)
    log("read ${pbf.dataBlobs.size} blobs in %.1f s; replication timestamp $extractTimestamp; sha256 ${pbf.sha256}"
        .format((System.nanoTime() - t0) / 1e9))
    require("Sort.Type_then_ID" in pbf.header.optionalFeaturesList) { "${opts.pbf}: not sorted Type_then_ID" }

    val source = readSourceMeta(opts.sourceMeta, opts.pbf, pbf.sha256)
    val asOf = opts.today ?: extractTimestamp
    EngineClock.install(asOf)
    val asOfDate = asOf.toLocalDateTime(zone).date.toString()
    log("asOf $asOf ($asOfDate ${zone.id})${if (opts.today != null) " [--today override]" else ""}")

    engine.notes = opts.notes?.let { f ->
        t0 = System.nanoTime()
        val clip = NotesClip.load(f)
        OpenNotes(clip.source, clip.openAt(asOf)).also {
            log("notes: ${clip.notes.size} in ${f.path} (from ${clip.source.source}, until ${clip.source.until}); " +
                "${it.open.size} open at asOf, ${it.quests.size} note quests; %.1f s".format((System.nanoTime() - t0) / 1e9))
        }
    }

    t0 = System.nanoTime()
    engine.run(pbf.dataBlobs)
    val passSeconds = (System.nanoTime() - t0) / 1e9
    val runSeconds = (System.nanoTime() - tStart) / 1e9
    logStats(engine, passSeconds, runSeconds)

    val meta = SnapshotMeta(
        asOf = asOf.toString(),
        asOfDate = asOfDate,
        timeZone = zone.id,
        extractTimestamp = extractTimestamp.toString(),
        scVersion = registry.scVersion,
        scCommit = registry.scCommit,
        resurveyMultiplier = RelativeDate.MULTIPLIER.toDouble(),
        areaUnit = opts.areaUnit.name.lowercase(),
        engineCommit = gitHead(opts.baseDir),
        source = source,
        notes = engine.notes?.let { NotesMeta(it.source, it.open.size, it.showAllNotes) },
        runSeconds = runSeconds,
    )
    opts.out?.let { out ->
        val snapshot = File(out, "snapshots/${meta.asOfDate}.json")
        snapshot.parentFile.mkdirs()
        snapshot.writeText(snapshotJson(meta, engine))
        File(out, "quests.json").writeText(questsJson(registry, cities))
        log("wrote $snapshot and ${File(out, "quests.json")}")
    }
    opts.grid?.let { dir ->
        val f = File(dir, "${meta.asOfDate}.json.gz")
        engine.grid!!.write(f, meta.asOfDate, engine.quests)
        log("wrote $f")
    }
    opts.dumpMatches?.let { f ->
        f.absoluteFile.parentFile.mkdirs()
        f.bufferedWriter().use { engine.writeDump(it) }
        log("wrote $f")
    }
    opts.dumpElements?.let { f ->
        f.absoluteFile.parentFile.mkdirs()
        f.bufferedWriter().use { engine.writeElements(it) }
        log("wrote $f")
    }
    return CountResult(engine, meta, registry)
}

private fun readSourceMeta(file: File?, pbf: File, sha256: String): SourceMeta {
    if (file == null) return SourceMeta(null, null, sha256, pbf.name)
    val o = Json.parseToJsonElement(file.readText()).jsonObject
    // osm-extracts (<file>.meta.json) writes sha256; toronto-streets-osm's meta.json pbf_sha256
    val metaSha = o.str("sha256") ?: o.str("pbf_sha256")
    require(metaSha == null || metaSha.equals(sha256, ignoreCase = true)) {
        "${file.path} describes a file with sha256 $metaSha, but ${pbf.path} has $sha256"
    }
    return SourceMeta(o.str("source_url"), o.str("source_last_modified")?.let(::httpDateToIso), sha256, o.str("file") ?: pbf.name)
}

/** "Thu, 16 Jul 2026 23:33:11 GMT" (HTTP Last-Modified) -> "2026-07-16T23:33:11Z"; ISO input is kept. */
fun httpDateToIso(s: String): String = try {
    java.time.ZonedDateTime.parse(s, java.time.format.DateTimeFormatter.RFC_1123_DATE_TIME).toInstant().toString()
} catch (_: java.time.format.DateTimeParseException) {
    Instant.parse(s).toString()
}

private fun gitHead(dir: File): String? = try {
    val p = ProcessBuilder("git", "rev-parse", "HEAD").directory(dir).redirectErrorStream(true).start()
    val out = p.inputStream.bufferedReader().readText().trim()
    if (p.waitFor(10, TimeUnit.SECONDS) && p.exitValue() == 0 && out.matches(Regex("[0-9a-f]{40}"))) out else null
} catch (_: Exception) {
    null
}

private fun logStats(engine: Engine, passSeconds: Double, runSeconds: Double) {
    val s = engine.stats
    fun arr(a: java.util.concurrent.atomic.AtomicLongArray) = (0..2).map { a[it] }
    log("tagged elements located (n/w/r): ${arr(s.located)}; in some city: ${arr(s.inCity)}")
    log("no SC geometry (n/w/r): ${arr(s.noGeometry)}; geometry errors: ${arr(s.geometryErrors)}; " +
        "bbox outside all cities: ${arr(s.outsideBboxes)}; relations the app ignores: ${s.ignoredRelations.get()}")
    val peakHeap = ManagementFactory.getMemoryPoolMXBeans()
        .filter { it.type == MemoryType.HEAP }.sumOf { it.peakUsage.used }
    log("pass %.1f s, total %.1f s; peak heap (sum of pool peaks) %d MB".format(passSeconds, runSeconds, peakHeap shr 20))
}
