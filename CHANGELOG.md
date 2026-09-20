# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
