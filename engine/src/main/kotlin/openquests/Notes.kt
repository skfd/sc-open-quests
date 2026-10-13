package openquests

import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osmnotes.Note
import de.westnordost.streetcomplete.data.osmnotes.NoteComment
import de.westnordost.streetcomplete.data.user.User
import de.westnordost.streetcomplete.util.ktx.truncateTo6Decimals
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import kotlinx.serialization.json.longOrNull
import java.io.File
import kotlin.time.Instant

/** One note of a clip of the planet notes dump (tools/clip_notes.py): every comment it ever had. */
class NoteHistory(val id: Long, val position: LatLon, val created: Instant, val comments: List<NoteComment>)

/** Header of a clip: which dump it was cut from, and the newest comment in that dump. */
class NotesSource(val file: String, val source: String, val sha256: String, val until: Instant, val poly: String?)

/** A clip of the planet notes dump: all notes in the region, open or closed, with their whole history. */
class NotesClip(val source: NotesSource, val notes: List<NoteHistory>) {

    /**
     * The notes the app would download at [asOf]: the API's `notes?closed=0` gives the notes whose
     * last open/close action up to then is not a close, with their comments up to then; the app then
     * drops notes without comments (#1338). Moderator-hidden notes are missing from the dump
     * altogether, so a note hidden after [asOf] is missing here too.
     */
    fun openAt(asOf: Instant): List<Note> {
        require(asOf <= source.until) {
            "${source.file}: the notes dump ends at ${source.until}, before asOf $asOf; use a newer dump"
        }
        val asOfMs = asOf.toEpochMilliseconds()
        val open = ArrayList<Note>()
        for (n in notes) {
            if (n.created > asOf) continue
            val comments = n.comments.filter { it.timestamp <= asOfMs }
            if (comments.isEmpty()) continue
            val lastStatusChange = comments.lastOrNull {
                it.action == NoteComment.Action.OPENED || it.action == NoteComment.Action.CLOSED ||
                    it.action == NoteComment.Action.REOPENED || it.action == NoteComment.Action.HIDDEN
            }
            if (lastStatusChange != null && lastStatusChange.action != NoteComment.Action.OPENED &&
                lastStatusChange.action != NoteComment.Action.REOPENED) continue
            open += Note(n.position, n.id, n.created.toEpochMilliseconds(), null, Note.Status.OPEN, comments)
        }
        return open
    }

    companion object {
        fun load(file: File): NotesClip {
            val lines = file.bufferedReader().readLines().filter { it.isNotBlank() }
            require(lines.isNotEmpty()) { "${file.path}: empty notes clip" }
            val h = Json.parseToJsonElement(lines[0]).jsonObject
            require(h["schema"]?.jsonPrimitive?.content == "1") { "${file.path}: not a schema 1 notes clip" }
            val source = NotesSource(file.name, h.str("source")!!, h.str("sha256")!!, Instant.parse(h.str("until")!!), h.str("poly"))
            val notes = lines.subList(1, lines.size).map { parseNote(Json.parseToJsonElement(it).jsonObject) }
            val count = h["notes"]?.jsonPrimitive?.long
            require(count == null || count == notes.size.toLong()) { "${file.path}: header says $count notes, file has ${notes.size}" }
            return NotesClip(source, notes)
        }

        private fun parseNote(o: JsonObject): NoteHistory {
            // lat/lon are the dump's strings; the app parses the API's the same way (String.toDouble)
            val position = LatLon(o.str("lat")!!.toDouble(), o.str("lon")!!.toDouble())
            val comments = o["comments"]!!.jsonArray.map { c ->
                c as JsonObject
                val uid = c["uid"]?.jsonPrimitive?.longOrNull
                NoteComment(
                    timestamp = Instant.parse(c.str("timestamp")!!).toEpochMilliseconds(),
                    action = NoteComment.Action.valueOf(c.str("action")!!.uppercase()),
                    // empty and missing text give the same answer in every check of the port
                    text = c.str("text"),
                    // the display name is not used by the quest; only the id is compared
                    user = uid?.let { User(it, "") },
                )
            }
            return NoteHistory(o["id"]!!.jsonPrimitive.long, position, Instant.parse(o.str("created")!!), comments)
        }
    }
}

/**
 * What the notes at one instant do to the counts:
 * - [quests]: the notes that are note quests (OsmNoteQuestController.createQuestForNote) for a user
 *   who wrote none of them, with the app's default "show only notes phrased as questions";
 * - [hiddenPositions]: OsmQuestController.getBlacklistedPositions: the app hides every OSM quest whose
 *   position, truncated to 6 decimals, equals that of any open note (quest or not).
 */
class OpenNotes(val source: NotesSource, val open: List<Note>, val showAllNotes: Boolean = false) {
    val quests: List<Note> = open.filter { it.shouldShowAsQuest(NOBODY, !showAllNotes) }
    /** the note quests with the app's other setting, "show all notes" */
    val allQuests: List<Note> = open.filter { it.shouldShowAsQuest(NOBODY, false) }
    val hiddenPositions: Set<LatLon> = open.mapTo(HashSet()) { it.position.truncateTo6Decimals() }

    fun hides(position: LatLon): Boolean = position.truncateTo6Decimals() in hiddenPositions
}
