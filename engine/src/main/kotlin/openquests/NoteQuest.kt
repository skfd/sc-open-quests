package openquests

import de.westnordost.streetcomplete.data.osmnotes.Note
import de.westnordost.streetcomplete.data.osmnotes.NoteComment

/*
 * Port of the private note filter in SC's commonMain `data/osmnotes/notequests/OsmNoteQuestController.kt`
 * (pinned in engine/PORTED-QUESTS.txt as OsmNoteQuest; the controller itself cannot be vendored, it
 * needs the app's database, settings and login). Everything below `shouldShowAsQuest` is copied
 * verbatim; only `private` became `internal` on the entry point and `ApplicationConstants.NAME` is
 * spelled out (ApplicationConstants.kt refers to BuildConfig).
 *
 * The app passes the logged-in user's id and `!prefs.showAllNotes` (default: showAllNotes = false).
 * The engine counts for a user who has written none of the notes ([NOBODY]), with the default setting,
 * so a note is a quest if its first comment holds a question mark or any comment holds "#surveyme".
 */

/** a user id no note comment has: the user conditions never apply */
const val NOBODY = -1L

private const val APPLICATION_NAME = "StreetComplete" // ApplicationConstants.NAME

internal fun Note.shouldShowAsQuest(
    userId: Long,
    showOnlyNotesPhrasedAsQuestions: Boolean
): Boolean {
    /*
        We usually don't show notes where either the user is the last responder, or the
        note was created with the app and has no replies.
        If the most recent comment contains "#surveyme", we want to show the note regardless.
        See https://github.com/streetcomplete/StreetComplete/issues/6052#issuecomment-2567163451
     */
    if (
        (
            comments.last().isReplyFromUser(userId) ||
            (probablyCreatedByUserInThisApp(userId) && !hasReplies)
        )
        && !comments.last().containsSurveyRequiredMarker()
    ) {
        return false
    }

    /*
        many notes are created to report problems on the map that cannot be resolved
        through an on-site survey.
        Likely, if something is posed as a question, the reporter expects someone to
        answer/comment on it, possibly an information on-site is missing, so let's only show these
     */
    if (showOnlyNotesPhrasedAsQuestions
        && !probablyContainsQuestion()
        && !containsSurveyRequiredMarker()
    ) {
        return false
    }

    return true
}

private fun Note.probablyContainsQuestion(): Boolean {
    /**
     * Source: https://en.wikipedia.org/wiki/Question_mark
     *
     * NOTE: some languages, like Thai, do not use any question mark, so this would be more
     * difficult to determine.
     */
    val questionMarksAroundTheWorld = listOf(
        "?", // Latin question mark
        "¿", // Spanish question mark in case the closing latin one was omitted
        ";", // Greek question mark (a different character than semicolon, though same appearance)
        ";", // semicolon (often used instead of proper greek question mark)
        "؟", // mirrored question mark (used in script written from right to left, like Arabic)
        "՞", // Armenian question mark
        "፧", // Ethiopian question mark
        "꘏", // Vai question mark
        "？", // full width question mark (often used in modern Chinese / Japanese)
    )
    val text = comments.firstOrNull()?.text ?: return false
    return text.lastIndexOfAny(questionMarksAroundTheWorld) != -1
}

private fun Note.containsSurveyRequiredMarker(): Boolean =
    comments.any { it.containsSurveyRequiredMarker() }

private fun NoteComment.containsSurveyRequiredMarker(): Boolean =
    text?.contains("#surveyme", ignoreCase = true) == true

private fun Note.probablyCreatedByUserInThisApp(userId: Long): Boolean {
    val firstComment = comments.first()
    val isViaApp = firstComment.text?.contains("via " + APPLICATION_NAME) == true
    return firstComment.isFromUser(userId) && isViaApp
}

private val Note.hasReplies: Boolean get() =
    comments.any { it.isReply }

private fun NoteComment.isReplyFromUser(userId: Long): Boolean =
    isFromUser(userId) && isReply

private val NoteComment.isReply: Boolean get() =
    action == NoteComment.Action.COMMENTED

private fun NoteComment.isFromUser(userId: Long): Boolean =
    user?.id == userId
