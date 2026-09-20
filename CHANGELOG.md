# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Summary

Established a MariaDB event log with shared category/subcategory definitions,
filterable history, and server lifecycle events.

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
