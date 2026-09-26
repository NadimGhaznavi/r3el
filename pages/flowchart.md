---
title: Batch and per-item flowcharts
author_profile: true
layout: single
---

[Documentation index](../index.md) · [Directory patterns](directory-patterns.md) · [Import and cleanup](import-cleanup.md)

## Batch flow

A batch starts when the user chooses **New Batch**. R3el handles files directly
inside the source first, then scans immediate child directories for supported
patterns. The destination defaults to `/exports/disk1/archive/media/movies`.

```mermaid
flowchart TD
    Start["New Batch: source, destination, batch size"] --> Select["Select ordinary files directly inside the source"]
    Select --> Files["Identify and match ordinary files in groups of up to 10"]
    Files --> Capacity{"Batch capacity remains?"}
    Capacity -->|Yes| Scan["Scan immediate child directories for supported patterns"]
    Capacity -->|No| Finish["Finish batch; keep results in workspace"]
    Scan --> DirectoryItems["Process matched directory items one at a time"]
    DirectoryItems --> Finish
```

**Batch size counts selections, not displayed rows.** An ordinary file counts
as one; a matched directory also counts as one, even when it yields several
movies. Unmatched directories are left untouched. Nested directories contribute
to their parent's scan, but are not separately queued.

## Per-item flow

Ordinary files and matched directory items use the identification and matching
flow below. Each outcome returns to the batch to continue with the next item.

```mermaid
flowchart TD
    Identify["LLM supplies title, year, confidence"] --> Accepted{"Valid identification?"}
    Accepted -->|No, attempts exhausted| Review["Leave unresolved for review"]
    Accepted -->|Yes| TMDB["Search TMDB by title and year"]
    TMDB --> Count{"Number of matches?"}
    Count -->|One| Import["Import media and associated SRTs; save catalogue; clean up"]
    Count -->|Multiple| Choose["LLM chooses a numbered candidate"]
    Choose --> Confident{"Valid selection?"}
    Confident -->|Yes| Import
    Confident -->|No| Review
    Count -->|Zero| Retry["Retry identification and search; then adjacent years"]
    Retry --> Found{"A match found?"}
    Found -->|One| Import
    Found -->|Multiple| Choose
    Found -->|No| Review
    Import --> Next["Continue with the next item"]
    Review --> Next
```

The per-item flow groups retries for readability: identification allows two corrective
retries; zero TMDB results allow three fresh identifications before searches at
the final year minus one and plus one. Individual unresolved results do not
prevent the batch finishing. Unexpected processing errors can stop it.

**Stop Batch** finishes the current operation before stopping. **Clear Current
Batch** requests a stop if necessary, waits for the worker to release the
workspace, then clears working records. Catalogue entries, imported files, and
Event Log history remain. **Current Task:** shows the latest batch event.

See [Directory patterns](directory-patterns.md) for discovery decisions,
[Import and cleanup](import-cleanup.md) for filesystem operations, and
[Persistent workspace](file-states.md) for saved states.
