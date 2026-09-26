---
title: Runtime behaviour
author_profile: true
layout: single
---

[Documentation index](../index.md)

# Runtime behaviour

Normal service startup resumes interrupted processing when configured with a
model URL. An empty workspace, a completed batch, or an explicit stop request
remains idle. Opening the Control page never starts a new batch.

**New Batch** selects ordinary files first and processes them in groups of up to
10. After those groups, remaining batch capacity is filled by matching immediate
child directories. Their contents are scanned recursively, but nested directories
are not separate batch selections. Each directory item is identified, matched
and imported before advancing.

TMDB selection, catalogue saving, media/SRT moves, duplicate handling and source
cleanup are implemented. The worker runs independently of browser refresh.
Unresolved items remain available for review; unmatched directories are left
unchanged. A completed batch remains visible until replaced or cleared.

**Stop Batch** requests a cooperative stop after the current operation.
**Clear Current Batch** waits for processing to stop and removes only workspace
records. **TMDB ID** and **Replace Local Media** provide the supported manual
corrections in the Action column; there is no action dropdown or Process Batch
button.

The explicit `--run-batch` diagnostic mode runs identification without the normal
automatic matching/import pipeline.

See the [batch overview](flowchart.md),
[directory patterns](directory-patterns.md), [import and cleanup](import-cleanup.md),
and [persistent workspace](file-states.md).
