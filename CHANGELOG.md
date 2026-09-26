---
title: Changelog
author_profile: true
layout: single
permalink: /changelog/
---

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed
- Fade the robot eyes between purple and dark cyan over a six-minute cycle, 20 times slower than before.
- Place Catalogue Title Search and Category Search side by side, stacking on narrow screens, with the Title Search button on its own row.

## [4.9.0] - 2026-09-26 @ 06:33

### Changed
- Group catalogue TV episodes into collapsed Season boxes, ordered by season and episode number, with Season 0 specials after the regular seasons.

## [4.8.1] - 2026-09-26 @ 06:17

### Fixed
- Align the animated robot eyes with the measured eye centres in the original logo.

## [4.8.0] - 2026-09-26 @ 06:05

### Changed
- Map TV episodes in separate LLM conversations per season, with sorted file IDs restarting at 1 for each conversation. Save the combined mapping only after every group succeeds; show season progress in the existing Event Log and Current Task.

## [4.7.0] - 2026-09-26 @ 05:58

### Added
- Slowly fade the robot's eyes through purple, teal and gold on the Control and Catalogue pages, respecting reduced-motion preferences.

## [4.6.1] - 2026-09-26 @ 05:52

### Fixed
- Bound TV series-identification prompts to a sorted JSON sample of filenames instead of the complete raw directory listing, retaining all file paths on the server for episode mapping.
- Record rejected LLM requests (HTTP 400, including context overflow) as unresolved items with the server's error in the Event Log, without repeatedly submitting the same request or stopping R3el.

## [4.6.0] - 2026-09-26 @ 05:41

### Added
- Add a Movie / TV / Both selector to catalogue Title Search, defaulting to Both; category searches continue to include both types and require every selected category.

## [4.5.3] - 2026-09-26 @ 05:29

### Changed
- Constrain the episode tool's file IDs to the labels in the current prompt and require the matching number of mappings; retain backend validation for duplicates and episode numbers.

### Changed
- Present simplified TV episode-mapping data as JSON, retaining sorted numeric file IDs and server-side path resolution. Document JSON task data as a development guideline.

### Changed
- Simplify the episode-mapping prompt to the confirmed show and sorted relative filenames numbered 1., 2., and so on; keep full paths and the mapping on the server.

## [4.5.2] - 2026-09-26 @ 05:19

### Fixed
- Use numeric file IDs for LLM episode mappings and resolve them to untouched source paths in the backend, avoiding filename transcription errors such as altered apostrophes.

## [4.5.0] - 2026-09-26 @ 04:55

### Changed
- Make the catalogue totals slightly larger and italic.

### Added
- Add total catalogued seasons (TV Series) and TV Episodes beneath the catalogue logo, with thousands separators.

## [4.4.0] - 2026-09-26 @ 04:51

### Added
- Show stacked movie and TV-series totals beneath the catalogue logo in its purple colour.

## [4.3.3] - 2026-09-26 @ 04:44

### Changed
- Group Director, Producers and Cast inside a People box, collapsed by default, and rename Imported episodes to Episodes on catalogue pages.

## [4.3.2] - 2026-09-26 @ 04:32

### Changed
- Add the dedicated `submit_tv_series(title, confidence)` tool and search TV series by name only, using the existing LLM selection dialogue for multiple matches.
- Remove guessed years and adjacent-year retries from TV identification; display the selected TMDB record's year as metadata and update event and match reporting accordingly.

## [4.3.0] - 2026-09-26 @ 04:20

### Changed
- Split TV processing into series identification and TMDB confirmation, followed by a separate episode-mapping dialogue using the confirmed series identity.
- Keep movie and TV event context consistent and distinguish TV series identification, episode mapping and import in logs and batch reporting.
- Save episode mappings and their completion marker atomically; unresolved series or mapping cannot start imports.
- Use the active dialogue's tool name in correction prompts for movies, two-part movies and TV episodes.

## [4.2.5] - 2026-09-26 @ 04:00

### Fixed
- Show meaningful LLM identification activity and readable directory discovery, TV prompt and batch continuation messages in the Event Log and Current Task.

## [4.2.4] - 2026-09-26 @ 03:55

### Fixed
- Keep Current Task refreshing from the Event Log while a batch-table link or input has focus, including TV episode progress, without replacing the focused table.

## [4.2.2] - 2026-09-26 @ 03:39

### Tests
- Check actual TV dialogue, search, import, failure and cleanup event payloads against Event Log and Current Task templates to catch producer/display mismatches.

### Fixed
- Render TV search events using their first-air year instead of requiring a movie release year, fixing Event Log and Current Task rendering.

## [4.2.1] - 2026-09-26 @ 03:30

### Fixed
- Fix Event Log and Current Task rendering of TV source-directory cleanup events, which incorrectly required a duplicate file's preferred path.

## [4.2.0] - 2026-09-26 @ 03:27

### Added
- Log TMDB TV series, season and episode detail requests, results and failures; include episode numbers in catalogue-save and move messages shown in the Event Log and Current Task.

## [4.1.0] - 2026-09-26 @ 03:23

### Added
- Display saved episode summaries, air dates, runtimes, credits and still images on TV catalogue pages using the existing catalogue theme.

## [4.0.0] - 2026-09-26 @ 03:10

### Added
- Import TV series from numbered episodes, explicit SxxExx filenames and nested season directories, with TV patterns taking priority over movie patterns.
- Identify series and episode mappings through the existing LLM/MCP workflow; use TMDB TV search, selection and metadata validation.
- Automatically route TV imports to the tv sibling of the movie destination, with season folders, episode titles and paired SRT naming.
- Persist series, seasons, episodes, credits, genres and artwork with per-episode catalogue/move checkpoints.
- Include TV series in catalogue searches and recent additions, with separate series routes and episode outcomes on match pages.
- Document the TV use cases and deploy the new schema, prompt and application modules through the installer.

## [3.1.0] - 2026-09-26 @ 02:22

### Summary

- Added TV support to the TMDB query tool. Scoping out TV support...

### Added
- Add query-tmdb --type movie|tv, including optional first-air-year filtering and raw series details for TV searches. Movies remain the default.

### Changed
- Make the year optional in query-tmdb; title-only searches omit the release-year filter in both readable and raw output modes.

## [3.0.3] - 2026-09-26 @ 02:00

### Fixed
- Require every selected category in catalogue search, so additional selections narrow the results.

## [3.0.2] - 2026-09-26 @ 01:56

### Changed
- Remove the instructional hint beneath catalogue Title Search.

### Changed
- Show the number of matching movies in the catalogue Search Results heading.

## [3.0.1] - 2026-09-26 @ 01:51

### Changed
- Add multi-category checkbox search to Catalogue, matching any selected genre and displaying the standard movie cards.

## [3.0.0] - 2026-09-26 @ 01:45

### Summary

- Added category search to the catalogue.

### Changed
- Rename catalogue Search to Title Search and add a Category Search panel listing all locally stored TMDB genres alphabetically.

### Fixed
- Publish the changelog as a Jekyll page and correct its documentation-index link.

## [2.0.0] - 2026-09-26 @ 01:17

### Documentation
- Add batch overview, directory-pattern and import/cleanup flowcharts. Link every documentation page from the top-level index and correct outdated workflow descriptions.

### Changed
- Rename the batch status prefix to Current Task:.
- Rename the Event Log refresh button to Update.

## [1.9.0] - 2026-09-26 @ 00:43

### Changed
- Redesign movie detail pages with a boxed poster and summary layout, separate Director, Producers, and Cast panels, and no redundant back-to-catalogue link.

## [1.8.0] - 2026-09-25 @ 23:57

### Added
- Show catalogue search results in a separate panel below the Search form.
- Browse catalogue additions four at a time with older/newer arrow buttons while preserving the title search.
- Redesign Catalogue with the Control-page logo layout, four recent additions, and title search with five-column poster grids. Preserve the first catalogue-added timestamp when refreshing movie metadata.

## [1.7.4] - 2026-09-25 @ 23:35

### Changed
- Move directory videos and associated SRTs using the same filesystem staging as single-file imports, without copying or reading back media contents. Log move events and retain sources until catalogue commit.

## [1.7.3] - 2026-09-25 @ 23:12

### Fixed
- Default new movie batches to /exports/disk1/archive/media/movies.
- Add scripts/relocate-imported-movies.py for a one-time preview/apply repair of movie directories imported directly into media, including catalogue file and artwork paths.

## [1.7.1] - 2026-09-25 @ 22:55

### Changed
- Include TMDB vote counts alongside titles and overview excerpts in the LLM movie-selection prompt.

## [1.7.0] - 2026-09-25 @ 22:43

### Changed
- Show the current batch’s latest Event Log message beneath the batch controls, with a link to its details and automatic progress refresh.


### Changed

- Report byte-level verification progress in the Event Log and verify copied media in larger blocks before deleting sources.

- Move the batch-processing status beneath the New Batch, Stop Batch, and Clear Current Batch buttons and display it in bold yellow.

### Changed

- Rename the displayed batch status from Identified to Imported.

## [1.6.0] - 2026-09-25 @ 22:31

### Added

- Recognize directories with multiple year-bearing media filenames as separate movies when the two-part pattern does not apply. Run the single-file dialogue for each movie, move associated subtitles, and remove the source directory only when no supported media or unresolved SRTs remain. A selected directory counts as one batch selection.

### Fixed

- Reject the two-part movie pattern when both media filenames contain different years at the beginning or just before the extension. Log the conflicting years so another directory pattern can handle the files.

## [1.5.1] - 2026-09-25 @ 22:12

### Fixed

- Enforce Batch Size across ordinary files and matched directories combined. Only immediate child directories of the source are batch candidates; scan their nested contents without queuing subdirectories independently.

## [1.5.0] - 2026-09-25 @ 22:07

### Added

- Add Clear Current Batch next to Stop Batch. Clear an idle workspace immediately, or stop active work before clearing its batch records; retain media, catalogue entries, and Event Log history.

## [1.4.4] - 2026-09-25 @ 21:56

### Changed

- Highlight “Processing batch...” in bold yellow.
- Remove the Approve/Pending/Ignore/Delete dropdown and its save feedback from the batch table. Keep TMDB ID and Replace Local Media controls in the Action column.

## [1.4.3] - 2026-09-25 @ 21:39

### Fixed

- After successful directory-media copying and catalogue save, delete the copied sources and the source directory. Preserve unresolved SRTs and their directory. Apply subtitle association during new directory scans; do not repair saved batches.

- Associate differently named SRTs with the lone video in the same CD folder when that folder contains exactly one subtitle. Preserve unresolved_srt for ambiguous associations and rename resolved subtitles with the video’s assigned part number.

## [1.4.2] - 2026-09-25 @ 21:25

### Added

- Label existing destination-media conflicts as Entry exists and offer Replace Local Media in the shared Action column alongside TMDB ID matching. Replacement applies only to the selected item’s destination media and associated subtitles, with durable retry permission and Event Log records.

### Changed

- Rename the current batch column from Filename to Filename / Directory.

## [1.4.0] - 2026-09-25 @ 21:04

### Summary

- Support directories that contain 2 supported media files i.e. 2 files that are larger than 100 Mb. This will be deemed to be a two part movie. The LLM is tasked with identifying the title, year, part one, and part two from the output of a `find -ls <dir>` command, along with a `file_a: <file-a>, file_b: <file-b>` payload.

### Added

- After ordinary files, scan source subdirectories on the server for exactly two supported videos larger than 100 MiB. Process each matching directory as one movie and leave unmatched directories untouched.
- Identify title, year, confidence, and part ordering with `DirectoryContextTwoParts`; validate that the response assigns each discovered video exactly once.
- Persist directory listings, associated files, part assignments, and discovery progress for restart recovery.
- Copy both parts and associated SRT subtitles using `Title (Year) Part N.ext`, preserve their sources, and catalogue all associated paths and part numbers.
- Leave ambiguous subtitles untouched with a persisted `unresolved_srt` issue and an Event Log entry.
- Log directory scans, pattern detections, subtitle associations, conversations, and copy checkpoints in the Event Log.

## [1.3.1] - 2026-09-25 @ 19:02

### Changed

- Remove the Refresh and Stop Batch explanatory notes.
- Remove the explanatory note beneath New Batch.
- Move New Batch and Stop Batch together below Refresh and remove the Process Batch button.
- Place the Update button on the same row as the Refresh menu.
- Remove the Reset link beside the Control page's Update button.

## [1.3.0] - 2026-09-25 @ 18:45

### Summary 

- Control Page layout improvements.

### Changed

- Keep the current batch column headers visible while scrolling within the table's bounded, keyboard-accessible scroll area.
- Enclose the current batch table in its own bordered box inside the Current Batch panel, with the header timestamp formatted as `MM-DD HH:MM:SS`.
- Arrange the Control page with the logo beside vertically aligned source, destination, batch size, and refresh settings. Rename the refresh button Update and move the local update time into a separate Current Batch header.

## [1.2.2] - 2026-09-25 @ 05:28

### Fixed

- Show Pending while adjacent-year TMDB searches run, as already happens during identification retries and multiple-choice selection. Clear the pending status on completion or failure.

## [1.2.1] - 2026-09-25 @ 05:18

### Changed

- Send multiple results from adjacent-year TMDB searches through the existing LLM multiple-choice workflow. Resume saved candidates without searching another year; unresolved choices remain available for manual TMDB ID matching.

## [1.2.0] - 2026-09-25 @ 05:00

### Changed

- After three zero-result identification retries, search TMDB one year earlier and then one year later; accept only a single match, otherwise leave the file for manual TMDB ID matching. Checkpoint these searches for resume and retry.
- Size manual TMDB ID fields to 15 characters and keep each field and its button on one line, allowing the table to expand as needed.

## [1.1.0] - 2026-09-25 @ 04:38

### Changed

- Offer the manual TMDB ID field and button for No matches rows after batch processing stops, using the existing lookup and catalogue workflow.

## [1.0.8] - 2026-09-24 @ 18:06

### Fixed

- Resume interrupted batches automatically when the identification service starts, using the saved selection, parameters, and checkpoints. Keep New Batch disabled for interrupted work, including shutdowns marked cancelled by older releases. Preserve explicit Stop Batch requests and keep completed batches idle.

## [1.0.7] - 2026-09-24 @ 16:54

### Changed

- Widen the Current batch layout from 60rem to 90rem to accommodate the manual TMDB ID column.

## [1.0.6] - 2026-09-24 @ 06:26

### Added

- Add a manual TMDB ID column for unresolved multiple-match rows after batch processing stops. Look up the exact movie in the background and use the existing catalogue, move, and format-preference workflow. Preserve unresolved results on lookup failure so users can correct the ID.

## [1.0.5] - 2026-09-24 @ 05:42

### Added

- Add an alphabetical Catalogue page with linked movie titles and years. Movie detail pages render stored metadata, cast and crew, local artwork, and catalogued file paths without calling TMDB.

## [1.0.4] - 2026-09-24 @ 05:30

### Added

- Prefer MKV, MP4, M4V, AVI, MOV, WMV, FLV, then MPG/MPEG for versions matched to the same TMDB movie. Delete lower-ranked formats only after the preferred file is catalogued, including replacements across batches. Checkpoint cleanup for retries, remove obsolete file links, and log File / Delete outcomes with a linked template.

## [1.0.3] - 2026-09-24 @ 05:16

### Fixed

- Enable New Batch when processing finishes, retaining the previous directory and size settings. Replace the finished workspace atomically on submission while preserving catalogue records, media, and event history; keep active batches protected.

## [1.0.2] - 2026-09-24 @ 04:56

### Added

- Add File / Move, Artifact / Download, and DB / Create Record events with linked message templates, filename context, paths, and movie identifiers. Log artwork download/reuse outcomes and failures, commit catalogue events with their records, and report completed or failed file moves.

## [1.0.1] - 2026-09-24 @ 04:42

### Added

- Add numbered batch rows and an Updated column formatted as `MM-DD HH:MM`. Display web timestamps in the browser's local timezone while keeping database timestamps in UTC.
- Replace the batch-size dropdown with a free-form positive-integer input.
- Add Stop Batch for automatic processing and manual matching. Persist stop requests, finish the current operation, preserve completed files and catalogue entries, and stop before another file or retry begins.

## [1.0.0] - 2026-09-24 @ 04:27

### Added

- Save resolved TMDB matches in a normalized local movie catalogue with people, credit roles, movie credits, genres, and durable file links. Include Director, Actor, Producer, Executive Producer, and Co-Producer credits; preserve multiple characters and cast billing order. Store the requested movie metadata without language.
- Install/upgrade creates the catalogue tables. Metadata and file links commit atomically with the workspace checkpoint and event; failed metadata downloads can be retried without repeating identification or search. Match Results shows catalogue save status.
- Create a `Title (Year)` folder beneath the batch's configured output directory, using the documented naming rules. Store local TMDB posters/backdrops with database references and move resolved videos there without copying bytes on the same filesystem. Preserve the source until the catalogue commit, reject destination collisions, and resume interrupted moves safely.

## [0.9.3] - 2026-09-24 @ 03:53

### Fixed

- Make CLI `-r` fetch full movie details for each search hit, including credits, keywords, external IDs, alternative titles, release dates, translations, images, and videos, instead of only search summaries.

## [0.9.2] - 2026-09-24 @ 03:48

### Added

- Add `-r` / `--raw` to the TMDB CLI to print the complete search response as formatted JSON, including nested fields.

## [0.9.1] - 2026-09-24 @ 03:38

### Fixed

- Let the TMDB CLI read existing credentials from `/etc/r3el/tmdb.env` or `~/.tmdb` when `TMDB_TOKEN` is not exported, without executing either file.

## [0.9.0] - 2026-09-24 @ 03:33

### Added

- Add a standalone CLI installer for `/opt/prod/r3el/bin/query-tmdb`, with an installation-local `.venv` and only the TMDB CLI dependencies. No database or service provisioning is required.

## [0.8.0] - 2026-09-23 @ 20:33

### Updated

- Process New Batch in groups of up to 10 files, finishing identification, TMDB matching, candidate selection, and retries for each group before starting the next. Preserve the selected batch size and refresh progress throughout.

- New Batch now runs filename identification straight into TMDB matching, multiple-choice selection, and bounded zero-result retries. Track automatic matching/completion/failure states, disable intermediate review controls, and refresh progress without another button press. Install/upgrade adds the batch states and supplies TMDB credentials to the identification service.

## [0.7.0] - 2026-09-23 @ 20:16

### Added

- Add `scripts/query-tmdb.py TITLE YYYY` to search TMDB and print numbered movies with release dates, languages, ratings, links, and wrapped overviews.

### Updated

- Refresh the Control file table in place instead of reloading the page. Apply/reset the interval without navigation, preserve action-menu behavior after refresh, and update completed matching results without a page reload.

## [0.6.11] - 2026-09-23 @ 19:59

### Added

- Add Manual, 5-second, 30-second, and 1-minute refresh options to the Control page, retaining the selected interval after starting or processing a batch.

## [0.6.9] - 2026-09-23 @ 19:55

### Added

- Add 20, 50, and 100 to the batch-size dropdown and accepted batch request sizes, keeping 10 as the default.

- Retry filename identification in a fresh LLM conversation when TMDB returns zero movies, then search again with the new title/year. Persist and display up to three retries per file; exhausted files become `unresolved_llm` and do not restart on later Process Batch requests. Install/upgrade adds the retry counter to the workspace schema.

## [0.6.7] - 2026-09-23 @ 19:40

### Updated

- Trust successful LLM selections: keep only the chosen TMDB movie in the workspace result and show only that movie through the 1 match link. Older saved selections also display only their chosen movie.

## [0.6.6] - 2026-09-23 @ 19:31

### Fixed

- Run Process Batch in a background worker and return HTTP 202 promptly, avoiding an open browser request during slow TMDB/LLM work. Poll job status and file progress, resume polling after a page reload, and reuse an active job on duplicate submissions.

## [0.6.5] - 2026-09-23 @ 19:21

### Added

- Show files as Pending with disabled action menus while multiple TMDB results are being resolved, retaining the matches link. Refresh the file table during Process Batch and restore review controls when selection finishes.

- Reload the Control page once, two seconds after New Batch is accepted, to show the discovered files without resubmitting the batch.

- Send an `example` prompt before the multiple-choice query, prefaced with “Here is an example.” and containing the Batman JSON example of a `submit_multiple_choice` call.

## [0.6.3] - 2026-09-23 @ 19:05

### Added

- Dedicated event previews for `multiple_choice` and `current_date` prompts, showing the search title/year and candidate count or current date, with filename and links to full details. Preserve readable previews for older plain-text prompts.

### Updated

- Keep event-log rows on one line within the table width, truncating overflowing text with an ellipsis while retaining full event details.

- Send LLM prompt data as structured JSON with separate instructions and data: TMDB queries and numbered candidates with overview excerpts, filenames, current dates, and validation feedback.

## [0.6.2] - 2026-09-23 @ 18:54

### Added

- Send the `focus` prompt after `current_date` during filename identification, treating plausible filename titles and four-digit years as authoritative without checking remembered filmography.

## [0.6.1] - 2026-09-23 @ 18:46

### Fixed

- Render multiple-choice tool and submission events with their own summaries, including previously saved entries, instead of requiring identification-only attempt/title/year/confidence fields that crashed the event report.

## [0.6.0] - 2026-09-23 @ 18:37

### Added

- Submit multiple-choice selections through the `submit_multiple_choice(number)` MCP tool and an attempt-bound ZeroMQ handler, with integer/range validation and duplicate rejection. Share MCP discovery and transport with identification.

- Ask the LLM to resolve multiple TMDB results with a `multiple_choice` prompt containing numbered candidate titles and roughly two lines of each overview, ending at a sentence boundary. Save and display the selection, retain the original response, and retry failed selections without repeating successful searches.

### Updated

- Limit `scripts/services.sh` to starting and stopping R3el's control and batch services. Leave Qwen managed separately and remove the Qwen startup delay.

## [0.5.3] - 2026-09-23 @ 18:05

### Added

- Send `current_date` as the first LLM prompt in each identification conversation, using the current date and reminding the model that its training knowledge may be older. Log it under Prompt / LLMPrompt.

## [0.5.2] - 2026-09-23 @ 17:48

### Added

- Log movie searches under TMDB / Search and responses or failures under TMDB / Result, with linked filename/query/outcome summaries. Retain the request parameters and full response or error in event details; commit each result event with its workspace checkpoint.

### Updated

- Enable Process Batch as soon as identification finishes, without requiring every file action to be resolved. Search TMDB for Pending and Approve files with an identification, skip Ignore/Delete, and continue past missing identifications or failed lookups.

- Query TMDB movies with `primary_release_year` instead of `year`, using the LLM's identified year.

## [0.5.1] - 2026-09-23 @ 05:33

### Added

- Store TMDB movie genres and languages in shared database catalogs, including stable IDs/codes and English/native language names. Install and upgrade refresh both catalogs atomically, retaining existing IDs for future media references.

### Updated

- Present Match Results as responsive movie cards with posters, title/year, language, rating/vote count, genres, overview, release date, original title, and a TMDB link. Only a single total result is marked Resolved; ambiguous, empty, and failed searches remain explicit. Keep saved JSON in a collapsed details section.

## [0.5.0] - 2026-09-23 @ 05:01

### Summary

- Added *The Movie Database* (TMDB) matching.

### Added

- Match approved movie identifications against TMDB by title and year, retaining the existing batch readiness rule and skipping Ignore/Delete files.
- Persist per-file responses and expose a Match Results column linking to formatted JSON, with distinct unmatched, ambiguous, failed, and skipped outcomes. Repeated matching reuses successful queries and retries failures; action changes clear saved results.
- Import TMDB_TOKEN and TMDB_KEY from /root/.tmdb during install/upgrade into root-only /etc/r3el/tmdb.env; the control service uses the token for movie searches.

### Updated

- Replace the Process Batch placeholder with Match TMDB. Serialize matching and action changes through the workspace lock; save results as each file completes without moving or deleting files.

## [0.4.2] - 2026-09-23 @ 02:35

### Summary

- Update EventLog categories and sub-categories.

### Updated

- Reclassify `attempt_failed` and `attempt_cancelled` as Prompt / ToolConversation, and both sources of `submission_rejected` as Prompt / SubmissionHandler. Remove the unused Identification event category.
- Reclassify `BatchIdentification - item_started` events as Batch / BatchIdentification.

## [0.4.1] - 2026-09-23 @ 02:26

### Summary

- Update EventLog categories and sub-categories.

### Updated

- Reclassify `prompt_sent` events as Prompt / LLMPrompt.
- Reclassify `ToolConversation - attempt_started` events as Prompt / ToolConversation.
- Reclassify `LLM - reply_received` events as Prompt / ToolConversation.
- Reclassify `ToolConversation - tool_started` events as Prompt / ToolConversation.
- Reclassify `SubmissionHandler - tool_received` events as Prompt / SubmissionHandler.
- Reclassify `SubmissionHandler - submission_accepted` events as Prompt / SubmissionHandler.
- Reclassify `ToolConversation - tool_completed` events as Prompt / ToolConversation.
- Reclassify `BatchIdentification - item_completed` events as Batch / BatchIdentification.

## [0.4.0] - 2026-09-22 @ 02:59

### Summary

- Add batch processing status and controls in the Control Server UI.

### Updated

- Add an Action dropdown after Status with Pending, Approve, Ignore, and Delete. Identification initializes confidence 10 to Approve and all other results to Pending; subsequent user selections are saved.
- Add the workspace action column and migrate existing records without resetting user choices on later upgrades.
- Enable Process Batch only for a nonempty, identification-complete batch with no Pending file actions. The button does not execute any operations yet.

## [0.3.16] - 2026-09-22 @ 02:16

### Updated

- Add Title, Year, and Confidence after Filename in the current batch table, keeping Status last. Show saved identification values or a dash when unavailable.

## [0.3.15] - 2026-09-22 @ 02:11

### Updated

- Rename Batch controls to Control and keep the section visible but greyed out for an occupied workspace, with saved settings as static text, a disabled New Batch button, and “Batch is being processed...” beneath the heading.

## [0.3.14] - 2026-09-21 @ 20:52

### Updated

- Remove automatic refresh from the batch control page; users reload to update workspace statuses and the Last updated timestamp.

- Document human-operated batch control and add regression coverage confirming that server startup and page refreshes never start batches.

## [0.3.13] - 2026-09-21 @ 20:28

### Updated

- Render decoded LLM reasoning as formatted Markdown under Message on reply-received event details, with the complete raw payload below a JSON heading.

## [0.3.12] - 2026-09-21 @ 20:10

### Summary

- The control page can request an identification batch over ZeroMQ. R3el runs one
  batch at a time, keeps accepting MCP submissions, and returns to idle afterward.

### Updated

- Show current workspace filenames and saved statuses instead of batch controls when a batch is retained. Refresh every five seconds and display a top-right Last updated timestamp in UTC.

- Start R3el idle with its MCP/ZeroMQ listener; retain explicit `--run-batch` for manual diagnostics.
- Save the requested output directory with the batch; upgrade the workspace schema without replacing retained data. New Batch assumes an empty workspace.
- Centralize message routing names and separate request validation, dispatch, and batch execution.
- Add a Jinja2 batch-control landing page with the R3el logo, configured input directory, batch sizes 5 and 10, and a New Batch button. Keep reports at `/events`.

## [0.3.11] - 2026-09-21 @ 18:56

### Updated

- Display linked attempt-failed summaries with attempts, filename, and the error message.

## [0.3.10] - 2026-09-21 @ 18:53

### Updated

- Display linked `InvalidIdentification` prompt-sent summaries with the filename and a 20-character prompt preview extended to complete the word.

- Display linked `SubmissionHandler` rejection summaries with attempts, filename, and the rejection reason.

- Display linked tool-started summaries with attempts, filename, and the submitted title, year, and confidence.

## [0.3.9] - 2026-09-21 @ 18:41

### Updated

- Display linked `FileContext` and `SubmitIdentificationPrompt` prompt-sent summaries with the filename and the first 20 prompt characters, extending to complete the word.

- Request, validate, store, and display confidence as an integer from 0 to 10. Reject non-integer and out-of-range submissions through the existing correction flow.

## [0.3.8] - 2026-09-21 @ 18:08

### Updated

- Display linked tool-received summaries with attempts, filename, and submitted title, year, and confidence.

- Display linked accepted-submission summaries with attempts, filename, title, year, and confidence.

- Display linked `Tool completed. Attempts: XX, Filename: …` messages for `tool_completed`.

- Display linked filenames and reasoning previews for `reply_received`, limited to 20 decoded characters or the first newline and followed by `...`.

## [0.3.7] - 2026-09-21 @ 05:47

### Updated

- Display a linked batch-completion summary with the processed count and `unresolved_llm` count.

## [0.3.6] - 2026-09-21 @ 05:29

### Updated

- Display linked `Filename: …` messages for `item_started` and `item_completed`.

## [0.3.5] - 2026-09-21 @ 05:26

### Updated

- Display `Filename: …` for `attempt_started`, with the entire message linking to the full event.

## [0.3.4] - 2026-09-21 @ 05:19

### Summary

- Introduce new `MediaFile` and `MediaFileBatch` abstractions to track state information
as files are processed by the system.
- Persist these and their state in the database for resiliency.

### Created

- Persistent workspace with `MediaFileBatch` and `MediaFile` entities, current issues, stable IDs, and saved file selections. Restart resumes pending files; completed identification results remain available for later review.
- Atomic workspace/event checkpoints and an exclusive database processing lock, with MariaDB rollback and process-restart tests.

- Added a concise MediaFile design covering fields, current and proposed states, transitions, responsibilities, and batch-summary counters.

### Updated

- Make default event-message previews link directly to the full event, removing the separate Full event label for server lifecycle messages and other default displays.

- Refreshed the pages documentation for the persistent workspace, startup schemas, event-message templates, and planned workflow stages; repaired navigation links.

- Show `Batch cancelled` for `batch_cancelled`, linking the entire message to the full event.

- Show `Batch started with size: XXX` for `batch_started`, linking the entire message to the full event.

- Show only the error text for `batch_failed` messages, linking the entire message to the full event.

## [0.3.3] - 2026-09-20 @ 17:46

### Updated

- Display event source and name on one line, source first (for example, `FileMgr - files_retrieved`).

## [0.3.2] - 2026-09-20 @ 17:41

### Created

- A compact linked summary for retrieved filenames showing the total count, first two filenames, and literal `...`. Message templates now own their links.

- Event-specific Jinja message template selection with a default template preserving the current event-log preview. Decoded payloads are available to custom templates; the Full event page retains the complete message.

## [0.3.1] - 2026-09-20 @ 15:13

### Updated

- Defined event bucket parents in constants and made event-log filters cascade through category, subcategory, and event. Selecting an event fills in its parents; incompatible URL filters are rejected.

- Flag hidden files (names beginning with `.`) as `unresolved_hidden_file` without sending them to the LLM. Batch results and event logs retain these files with zero attempts.

## [0.3.0] - 2026-09-20 @ 14:47

### Created

- Added `scripts/services.sh start|stop`: start Control, Qwen, wait five seconds, then R3el; stop in reverse order without delays. Install and upgrade also copy the executable helper into the installation.

## [0.2.3] - 2026-09-20 @ 14:43

- Capitalized the event-log column heading as "Event / Source".

### Updated

- Gave Subcategory its own event-log column, with its dropdown directly below the heading.

## [0.2.2] - 2026-09-20 @ 14:38

- Updated the *film* and *media* paths to reflect the paths in production.

## [0.2.1] - 2026-09-20 @ 14:34

### Updated

- Moved category and subcategory filters into the event table's second header row and added an event-name dropdown under Event / source. All filters apply before the 500-event limit.

## [0.2.0] - 2026-09-20 @ 14:15

### Summary

- Added a standalone Jinja2 event viewer deployed as `r3el-control.service`, automatically enabled and started by install and upgrade.
- Completed the removal of unused SnakeLab/Ax3l application code, leaving the R3el identification workflow, event components, and shared Qwen service integration.

### Created

- Event log pages with category/subcategory filters, optional refresh, full message details, and parent-event navigation, using the shared database interfaces.
- An independent control HTTP server on port 42220 with a liveness endpoint and database-unavailable error page.
- HTTP tests for filtering, HTML escaping, error responses, connection cleanup, and installed template loading.

### Updated

- Install, upgrade, and uninstall now manage the control service and deploy its Jinja2 templates and dependency.

### Removed

- The legacy reporting server and its nine SnakeLab report templates, replaced by the R3el event viewer.
- SnakeLab query and MCP interfaces, the Ax3l server and tool dispatcher, and unused watchdog and health service helpers.
- Obsolete SnakeLab, Ax3l, reporting, event display, Phi, and vision-model constants.
- The unused Plotly dependency.

## [0.1.0] - 2026-09-20 @ 13:47

### Summary

- Install and upgrade now reuse Ax3l's installed `qwen-server.service`, or provision a shared Qwen 3.5 4B service using the existing llama.cpp/GGUF assets and matching model settings. The R3el service defaults to its local endpoint; shared services are preserved on uninstall.

- Flattened the identification workflow into `r3el/app`, with shared `prompts/` and `tools/` packages; updated imports, MCP startup, and deployment paths, and removed the empty `app/r3el` folder.

Added one-batch filename identification through modular prompts, an LLM conversation,
MCP tools, and a ZeroMQ server listener, with correlated MariaDB event logging.

### Added

- Basic title/year/confidence validation and two correction retries before recording `unresolved_llm`.
- A filesystem interface for bounded, nonrecursive filename retrieval, with a fresh scan on each call.
- Category parent/child constants, event entities, and separate database and reporting components.
- An R3el systemd service and deployment scripts, with Plotly as the initial dependency.
- Shared Qwen service provisioning using the existing llama.cpp executable and Qwen 3.5 4B GGUF, with installer tests.
- Development guidelines documenting interface, activity, and entity class responsibilities.
- Git branch structure to support release management.
- The `scripts/new-release.sh` release script.

### Changed

- The server processes one identification batch and exits, replacing the initial idle loop; SIGTERM and SIGINT trigger graceful cleanup.
- Deployment leaves the R3el service stopped and disabled for automatic startup.
- Install and upgrade reuse an existing `qwen-server.service` unchanged, or install it if absent; uninstall preserves the shared model service and assets.
- The installed R3el service defaults to the local Qwen URL, with an override available through `R3EL_LLM_URL`; direct CLI runs require an explicit URL or environment setting.
- Flattened the identification workflow into `r3el/app` and updated imports, MCP startup, and deployment paths.
- Renamed the `r3el.entities` package to `r3el.entity` and updated imports and deployment paths.
- Install and upgrade initialize the event schema explicitly; the server logs startup and graceful shutdown.
- Category and subcategory filters apply to the full event history before limiting results.

### Removed

- Seven unused Ax3l/SnakeLab reporting and service-check modules from `r3el/activity`, retaining R3el's event reporting, schema, writer, and lifecycle activities.
- The unused SnakeLab application, its legacy prompt/configuration/database helpers, and the old Snake-game prompt placeholder from `r3el/app`; retained the identification workflow and shared `Prompt` class.
- The empty `app/r3el` folder after flattening the workflow packages.
