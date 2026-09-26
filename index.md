---
title: R3el Movie and TV Show Organizer
author_profile: true
layout: single
---

![R3el Logo](/pages/images/r3el.png)

The **R3el Project uses** a locally hosted [Large Language Model (LLM)](https://en.wikipedia.org/wiki/Large_language_model) to organize a collection of files that contain movies or TV shows.

## Batch processing

- [Batch process overview](pages/01-high-level-flow.md) — the main flowchart.
- [Directory patterns](pages/directory-patterns.md) — two-part movies, separate dated movies, and SRT associations.
- [Import and source cleanup](pages/import-cleanup.md) — moves, commits, conflicts, and cleanup.
- [Runtime behaviour](pages/runtime-behaviour.md) — starting, stopping, and completing batches.

## Using and operating R3el

- [Control, Catalogue, and Event Log](pages/control-server.md)
- [Identification server and installation](pages/one-batch-identification.md)
- [File naming and format preference](pages/file-naming.md)

## Technical reference

- [Persistent workspace and states](pages/file-states.md)
- [Catalogue schema](pages/schema.md)
- [ZeroMQ messages](pages/zmq-messages.md)
- [Coding guidelines](pages/coding-guidelines.md)

## Project information

- [README](README.md)
- [Changelog](CHANGELOG.md)
- [Repository agent instructions](AGENTS.md)

<footer style="margin-top: 3rem; text-align: center; font-size: 0.75em;">
  Powered by
  <a href="https://www.themoviedb.org/">
    <img src="{{ '/pages/images/tmdb.svg' | relative_url }}" alt="TMDB" width="100" style="vertical-align: middle;">
  </a>
</footer>
