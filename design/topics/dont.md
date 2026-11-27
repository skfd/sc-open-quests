## Don't

- Don't hand-write Overpass queries, and don't take filters from the OSM wiki's Turbo links (#2072). They
  drift and some are wrong.
- Don't use ohsome as the engine. Its filter language can't express regex, numbers, dates or element age,
  and v1 dies 2026-11-30. At most, use it to backfill history for the plain key/value quests.
- Don't silently approximate. A quest counted with simplified logic says so on the page.
- Don't compare raw counts across cities on the default view; normalize first.
- Don't mix runs from different SC versions or settings in one line without marking the break.
- Don't treat open OSM notes as noise. The app hides a quest whose center sits exactly on an open note.
  Modelled since 2026-10-12 (see "Notes" below).
- Don't schedule at 12:00 or 12:30; the sibling trackers already use those slots.
- Don't stall on the 51 custom quests. Ship the filter quests first. (Superseded: every quest is supported
  since 2026-11, and the rule below now holds.)
- **Don't publish a count of a subset of quests (the owner, 2026-11-16).** Any number that goes on the site,
  in a snapshot, a series or a place page, covers every quest type of the pinned SC version, as the full
  count does: filter quests, custom quests, area quests, notes and ageing. A faster path that handles only
  some of them (the stream's tier 1, element-only quests, a world day without area quests or their dates)
  is a test or a building block, never a publication. A world day is publishable only when it gives every
  quest, checked against a full count.
