# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
