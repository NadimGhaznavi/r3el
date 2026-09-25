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

After automatic batch processing stops, Action dropdowns save human choices
immediately. Menus are disabled throughout identification and matching. Pending
identification rows cannot be edited, preventing a later
checkpoint from overwriting a user choice. Resuming identification skips saved
outcomes and preserves their actions. A user can set a confidence-10 item back to
Pending; rendering and schema upgrades do not reapply defaults to saved choices.

The schema upgrade initializes legacy rows once: identified confidence-10 files
become Approve, and all others become Pending. It preserves rows and identification
data. Apply the workspace schema through the usual install/upgrade flow.

`BatchPreparation.ready` requires a nonempty batch with completed identification
and no pending identification rows. New Batch starts matching automatically.
Process Batch is available afterward for retries, including when actions are
still Pending. Pending and Approve files with an
identification are queried by title/year; Ignore and Delete
files are skipped. Results are checkpointed in `media_files.tmdb_match` as JSON.
Exactly one total result is a match; zero triggers a fresh identification and
search, up to three retries. Continued zero results trigger searches for the final
identified title one year earlier, then one year later. Only exactly one result
is accepted from these searches; otherwise the file becomes `unresolved_llm`
for manual TMDB ID matching. Adjacent-year progress is saved with the query.
Multiple results from the original-year searches trigger
a `multiple_choice` prompt containing candidate numbers, titles, and short overview excerpts ending at a
sentence boundary. The LLM
selection is saved as `selected_number` (1-based; 0 means no confident choice),
with failures stored separately in `selection_error`. A valid selection resolves
the match and keeps only the chosen movie in the saved workspace response.
The original search response remains in the event log. Old saved
responses without a selection are processed on the next Process Batch request.
Missing identifications and failed lookups are recorded as failures and do not
stop processing the remaining files. Failures remain distinct from zero-result responses. Action changes clear the
saved result; repeated matching reuses successful responses and retries failures.
While an LLM choice is in progress, `selection_pending` is saved with the TMDB
result. The file displays Pending and its action menu is disabled, while the
existing match-count link remains available. Its filename identification and
saved action are preserved. Selection completion clears the flag, including
failed or uncertain choices; interrupted selections can be retried with Process
Batch using the saved candidates. Process Batch updates the file table every two
seconds while its background job is running.

Matching never moves or deletes files.

Later stages are proposed:

`identified → review_ready → approved → completed`

TMDB results currently persist separately from identification state. A later
review stage can introduce `review_ready` and a selected candidate; finalization
will execute approved operations. These later stages are not implemented yet.

## MediaFileBatch

Stores `id`, `requested_size`, `source_directory`, `destination_directory`, ordered `files`, `state`,
and `started_event_id`. One batch occupies the workspace.

| State | Meaning |
| --- | --- |
| `processing` | Identification underway. |
| `failed` | Processing stopped on an error. |
| `cancelled` | User stopped processing; older releases also used this for service shutdown. |
| `identification_completed` | Diagnostic identification finished; matching can be started manually. |
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
directory is optional for older batches and saved for future file operations.

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
