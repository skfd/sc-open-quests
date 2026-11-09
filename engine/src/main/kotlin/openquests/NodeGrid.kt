package openquests

import java.io.File
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong
import kotlin.math.floor

/** `nodegrid --pbf <file> --out <file.json> [--step 0.05]`: how many nodes each square of a degree grid
 *  holds, for cutting a large area into cells of about equal engine work (the engine's cost is flat per
 *  node; DESIGN.md, "The whole world: measured and proposed"). Counts every node, tagged or not. Writes
 *  `{"step": s, "nodes": N, "cells": [[row, col, n], ...]}`, row = floor(lat / s), col = floor(lon / s),
 *  only squares that hold a node. Changes nothing the count reads. */
fun nodeGrid(args: List<String>) {
    val m = args.chunked(2).associate { (k, v) -> k.removePrefix("--") to v }
    require(m.keys.all { it in setOf("pbf", "out", "step") }) { "nodegrid: unknown option(s) ${m.keys}" }
    val pbf = m["pbf"] ?: error("nodegrid: --pbf is required")
    val out = File(m["out"] ?: error("nodegrid: --out is required"))
    val step = m["step"]?.toDouble() ?: 0.05
    val t0 = System.nanoTime()
    val file = readPbf(pbf)
    val counts = ConcurrentHashMap<Long, AtomicLong>()
    val total = AtomicLong()
    file.dataBlobs.parallelStream().forEach { blob ->
        val b = decodeBlock(blob)
        if (b.kind() != BlockKind.NODES) return@forEach
        val ctx = BlockContext(b)
        val local = HashMap<Long, Long>()
        fun add(lat7: Int, lon7: Int) {
            val r = floor(lat7 / 1e7 / step).toLong(); val c = floor(lon7 / 1e7 / step).toLong()
            local.merge((r shl 32) or (c and 0xffffffffL), 1L, Long::plus)
        }
        for (g in b.primitivegroupList) {
            if (g.hasDense()) {
                val d = g.dense
                var lat = 0L; var lon = 0L
                for (i in 0 until d.idCount) { lat += d.getLat(i); lon += d.getLon(i); add(ctx.lat7(lat), ctx.lon7(lon)) }
            }
            for (n in g.nodesList) add(ctx.lat7(n.lat), ctx.lon7(n.lon))
        }
        var sum = 0L
        for ((k, v) in local) { counts.computeIfAbsent(k) { AtomicLong() }.addAndGet(v); sum += v }
        total.addAndGet(sum)
    }
    val sb = StringBuilder("{\"step\": $step, \"nodes\": ${total.get()}, \"cells\": [")
    counts.entries.sortedBy { it.key }.forEachIndexed { i, (k, v) ->
        if (i > 0) sb.append(',')
        sb.append('[').append(k shr 32).append(',').append(k.toInt()).append(',').append(v.get()).append(']')
    }
    sb.append("]}\n")
    out.parentFile?.mkdirs()
    out.writeText(sb.toString())
    println("nodegrid: ${total.get()} nodes in ${counts.size} squares of $step degrees, " +
        "%.1f s".format((System.nanoTime() - t0) / 1e9))
}
