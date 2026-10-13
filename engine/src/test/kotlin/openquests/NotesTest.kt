package openquests

import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.time.Instant

class NotesTest {
    private fun note(id: Long, lat: String, lon: String, vararg comments: String) =
        """{"id":$id,"lat":"$lat","lon":"$lon","created":"${comments.first().substringAfter("\"timestamp\":\"").substringBefore('"')}",""" +
            """"comments":[${comments.joinToString(",")}]}"""

    private fun c(action: String, ts: String, text: String = "", uid: Long? = 1) =
        """{"action":"$action","timestamp":"$ts"${if (uid != null) ",\"uid\":$uid" else ""},"text":${jsonString(text)}}"""

    private fun clip(vararg notes: String): NotesClip {
        val f = File.createTempFile("notes", ".jsonl").apply { deleteOnExit() }
        f.writeText(
            """{"schema":1,"source":"planet-notes-261011.osn.bz2","sha256":"ab","until":"2026-10-11T00:00:00Z","bbox":[-95.2,41.6,-74.3,56.9],"poly":"ontario.poly","notes":${notes.size}}""" +
                "\n" + notes.joinToString("\n") + "\n"
        )
        return NotesClip.load(f)
    }

    private val notes = clip(
        // a question: a quest
        note(1, "43.6532100", "-79.3832000", c("opened", "2026-01-01T00:00:00Z", "Is this shop still open?")),
        // a statement: open, so it hides quests, but not a quest
        note(2, "43.7000000", "-79.4000000", c("opened", "2026-01-01T00:00:00Z", "Shop closed.")),
        // a semicolon counts as a (Greek) question mark in SC's list
        note(3, "43.7100000", "-79.4100000", c("opened", "2026-01-01T00:00:00Z", "name; address")),
        // #surveyme in a later comment makes a statement a quest, but only once it has been written
        note(4, "43.7200000", "-79.4200000", c("opened", "2026-01-01T00:00:00Z", "Shop closed."),
            c("commented", "2026-06-01T00:00:00Z", "Please check #SurveyMe", uid = 2)),
        // closed, then reopened
        note(5, "43.7300000", "-79.4300000", c("opened", "2025-01-01T00:00:00Z", "What is here?"),
            c("closed", "2025-02-01T00:00:00Z", "", uid = 2), c("reopened", "2026-03-01T00:00:00Z", "", uid = 3)),
        // closed for good
        note(6, "43.7400000", "-79.4400000", c("opened", "2025-01-01T00:00:00Z", "What is here?"),
            c("closed", "2025-02-01T00:00:00Z", "done", uid = 2)),
        // anonymous, created after the first asOf below
        note(7, "43.7500000", "-79.4500000", c("opened", "2026-08-01T00:00:00Z", "Why?", uid = null)),
    )

    private fun questIds(asOf: String) = OpenNotes(notes.source, notes.openAt(Instant.parse(asOf))).quests.map { it.id }
    private fun openIds(asOf: String) = notes.openAt(Instant.parse(asOf)).map { it.id }

    @Test fun `state at a past instant`() {
        assertEquals(listOf(1L, 2L, 3L, 4L), openIds("2026-02-15T00:00:00Z"))
        assertEquals(listOf(1L, 2L, 3L, 4L, 5L, 7L), openIds("2026-10-01T00:00:00Z"))
        assertEquals(listOf(5L, 6L), openIds("2025-01-15T00:00:00Z"))
    }

    @Test fun `note quests with the app's defaults`() {
        assertEquals(listOf(1L, 3L), questIds("2026-02-15T00:00:00Z"))
        assertEquals(listOf(1L, 3L, 4L, 5L, 7L), questIds("2026-10-01T00:00:00Z"))
    }

    @Test fun `comments after asOf are not seen`() {
        val n4 = notes.openAt(Instant.parse("2026-02-15T00:00:00Z")).single { it.id == 4L }
        assertEquals(1, n4.comments.size)
    }

    @Test fun `with showAllNotes every open note is a quest`() {
        val open = notes.openAt(Instant.parse("2026-02-15T00:00:00Z"))
        assertEquals(listOf(1L, 2L, 3L, 4L), OpenNotes(notes.source, open, showAllNotes = true).quests.map { it.id })
    }

    @Test fun `the user conditions apply to the user's own notes only`() {
        val n = notes.openAt(Instant.parse("2026-10-01T00:00:00Z")).single { it.id == 4L }
        assertTrue(n.shouldShowAsQuest(NOBODY, true))
        // the last comment is the user's reply, but it holds #surveyme: still shown
        assertTrue(n.shouldShowAsQuest(2L, true))
        val n1 = notes.openAt(Instant.parse("2026-10-01T00:00:00Z")).single { it.id == 1L }
        assertTrue(n1.shouldShowAsQuest(1L, true)) // the user opened it, but not via StreetComplete
    }

    @Test fun `every open note hides quests at its position, truncated to 6 decimals`() {
        val open = OpenNotes(notes.source, notes.openAt(Instant.parse("2026-02-15T00:00:00Z")))
        assertTrue(open.hides(LatLon(43.6532109, -79.3832009))) // same after truncation
        assertTrue(open.hides(LatLon(43.7, -79.4))) // a statement note hides too
        assertFalse(open.hides(LatLon(43.653211, -79.3832))) // 1e-6 away
        assertFalse(open.hides(LatLon(43.74, -79.44))) // closed note
    }

    @Test fun `a dump that ends before asOf is refused`() {
        assertFailsWith<IllegalArgumentException> { notes.openAt(Instant.parse("2026-10-12T00:00:00Z")) }
    }
}
