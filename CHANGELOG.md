# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
