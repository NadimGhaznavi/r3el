# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Summary

- Flattened the identification workflow into `r3el/app`, with shared `prompts/` and `tools/` packages; updated imports, MCP startup, and deployment paths, and removed the empty `app/r3el` folder.

Added one-batch filename identification through modular prompts, an LLM conversation,
MCP tools, and a ZeroMQ server listener, with correlated MariaDB event logging.

- Added basic title/year/confidence validation and two correction retries before recording `unresolved_llm`.
- Removed seven unused Ax3l/SnakeLab reporting and service-check modules from `r3el/activity`, retaining R3el's event reporting, schema, writer, and lifecycle activities.
- Removed the unused SnakeLab application, its legacy prompt/configuration/database helpers, and the old Snake-game prompt placeholder from `r3el/app`; retained the identification workflow and shared `Prompt` class.
- The server requires an explicit LLM URL, processes one batch, and exits; deployment no longer starts or enables automatic batch runs.
- Added a filesystem interface for bounded, nonrecursive filename retrieval, with a fresh scan on each call.
- Renamed the `r3el.entities` package to `r3el.entity` and updated imports and deployment paths.
- Added category parent/child constants, event entities, and separate database and reporting components.
- Install and upgrade initialize the event schema explicitly; the server logs startup and graceful shutdown.
- Category and subcategory filters apply to the full event history before limiting results.
- Documented interface, activity, and entity class responsibilities to guide development and prevent monolithic classes.
- The R3el server sleeps in a loop and exits cleanly on SIGTERM or SIGINT.
- Added a minimal idle R3el service and simplified its deployment, with Plotly as the initial dependency.

- Created Git branch structure to support release management.
- New `new_release.sh` script.
