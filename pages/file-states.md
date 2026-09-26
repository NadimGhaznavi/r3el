---
title: Persistent workspace
author_profile: true
layout: single
---

[Documentation index](../index.md)

# Persistent workspace

`MediaFileBatch` owns the active batch; `MediaFile` holds each file's current
working data. They persist in `media_file_batches` and `media_files` so
processing survives a restart.

## MediaFile

| Field | Purpose |
| --- | --- |
| `id` | Stable identity referenced by events. |
| `path` | File location, including filename. |
| `state` | Current identification workflow state. |
| `action` | Saved preparation decision: `pending`, `approve`, `ignore`, or `delete`. |
| `identification` | Accepted title, year, and integer confidence from 0 to 10. |
| `issues` | Current problems as `{code, message}` entries; empty when clear. |
| `attempts` | Attempts used for the saved outcome. |
| `tmdb_match` | Saved query, movie search response, failure, or skipped outcome; null before matching. |
| `retries` | Persisted count of fresh identifications triggered by zero TMDB results, from 0 to 3. |

| State | Meaning |
| --- | --- |
| `pending` | Awaiting identification. |
| `identified` | LLM identification accepted; TMDB matching still needed. |
| `unresolved_llm` | Identification attempts exhausted. |
| `unresolved_hidden_file` | Hidden filename skipped without contacting the LLM. |

Discovery creates `pending` files. Identification transitions each to one of
these three outcomes.

## Preparation actions

`MediaFileAction` is persisted separately from identification state in
`media_files.action`. New files start with `pending`. The identification checkpoint
saves `approve` when confidence equals `DR3el.AUTO_APPROVE_CONFIDENCE` (10), otherwise
`pending`, in the same transaction as the file outcome and completion event.

The Action dropdown is no longer shown in Control. The stored action field
remains part of the processing contract: pending/approve items can be matched;
ignore/delete items are skipped.

Matching starts automatically. One TMDB result resolves the movie; multiple
results trigger an LLM choice using candidate numbers, titles, overview excerpts
and vote counts. Zero results trigger up to three fresh identifications, then
searches one year earlier and later. Unresolved results remain available for
manual **TMDB ID** selection. Exact destination conflicts show **Entry exists**
and offer **Replace Local Media**.

Matching saves catalogue metadata and imports media. The catalogue_saved and
file_moved checkpoints distinguish the database commit from filesystem completion.
The displayed **Imported** label replaces Identified; the internal identification
state remains identified. Check match results and Current Task for import errors
or work still in progress.

Directory rows include find_ls for the two-part dialogue; separate movies from
a dated directory carry source_directory. Attachments retain video/SRT pairing
and part numbers. Ambiguous subtitles carry unresolved_srt issues and remain at
the source. See [directory patterns](directory-patterns.md) and
[import and cleanup](import-cleanup.md).

## MediaFileBatch

Stores `id`, `requested_size`, `source_directory`, `destination_directory`, ordered `files`, `state`,
and `started_event_id`. One batch occupies the workspace.

| State | Meaning |
| --- | --- |
| `processing` | Identification underway. |
| `failed` | Processing stopped on an error. |
| `cancelled` | User stopped processing; older releases also used this for service shutdown. |
| `identification_completed` | Diagnostic identification finished without the automatic import pipeline. |
| `matching` | Automatic TMDB matching underway. |
| `matching_completed` | Automatic matching finished; results available for review. |
| `matching_failed` | Automatic matching stopped on an error. |

Explicit diagnostic `--run-batch` resumes pending files and returns failed/cancelled batches to
`processing`. Identification completion is not finalization. Normal server startup resumes
interrupted processing or matching from the saved selection; completed batches and
explicit Stop Batch requests remain idle. Legacy cancelled batches without a stop
request also resume. New Batch remains disabled for interrupted work;
control-requested New Batch replaces a finished workspace with a fresh selection.
Active processing blocks replacement; catalogue records and event history remain. The destination
directory is saved with the batch and used for importing matched movies.

## Persistence and cleanup

- Entities store data; activities perform work and state transitions.
- `WorkspaceDb` uses `DbMgr` to save the selection before identification and
  commit each file outcome with its completion event.
- Diagnostic `--run-batch` uses the saved selection, skips saved outcomes, and retries an
  interrupted file. Only one processor can hold the workspace.
- Issues represent current problems, not an accumulating cleanup history.
- Identification-complete batches remain available without repeating model calls.
- New Batch clears finished working records as part of committing the fresh
  selection. Final media records remain. Event Log retention is separate.

## Batch counters

`batch_completed` counts MediaFiles: `count` is the total;
`unresolved_llm` and `unresolved_hidden_file` count those states, including zero.
Batch lifecycle events are separate from file states.

See [One-batch identification](one-batch-identification.md) for operation.
