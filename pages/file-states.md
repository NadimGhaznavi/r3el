# Persistent workspace

`MediaFileBatch` owns the active batch; `MediaFile` holds each file's current
working data. Both persist in MariaDB so processing survives a restart.

## MediaFile

| Field | Purpose |
| --- | --- |
| `id` | Stable identity referenced by events. |
| `path` | File location, including filename. |
| `state` | Current workflow state. |
| `identification` | Accepted title, year, and confidence. |
| `issues` | Current problems as `{code, message}` entries; empty when clear. |
| `attempts` | Attempts used for the saved outcome. |

| State | Meaning |
| --- | --- |
| `pending` | Awaiting identification. |
| `identified` | LLM identification accepted; TMDB matching still needed. |
| `unresolved_llm` | Identification attempts exhausted. |
| `unresolved_hidden_file` | Hidden filename skipped without contacting the LLM. |

Discovery creates `pending` files. Identification transitions each to one of
these three outcomes.

Later stages are proposed:

`identified → review_ready → approved → completed`

TMDB matching produces `review_ready`; human review chooses `approved` or
`rejected`; batch finalization executes approved operations. These stages
and the selected TMDB record are not implemented yet.

## MediaFileBatch

Stores `id`, `requested_size`, `source_directory`, ordered `files`, `state`,
and `started_event_id`. One batch occupies the workspace.

| State | Meaning |
| --- | --- |
| `processing` | Identification underway. |
| `failed` | Processing stopped on an error. |
| `cancelled` | Processing interrupted. |
| `identification_completed` | All outcomes saved, awaiting the next stage. |

Restart resumes pending files and returns failed/cancelled batches to
`processing`. Identification completion is not finalization.

## Persistence and cleanup

- Entities store data; activities perform work and state transitions.
- `WorkspaceDb` uses `DbMgr` to save the selection before identification and
  commit each file outcome with its completion event.
- Restart uses the saved selection, skips saved outcomes, and retries an
  interrupted file. Only one processor can hold the workspace.
- Issues represent current problems, not an accumulating cleanup history.
- Identification-complete batches remain available without repeating model calls.
- Finalization will clear working records after file operations and final DB
  updates succeed. Final media records remain. Event Log retention is separate.

## Batch counters

`batch_completed` counts MediaFiles: `count` is the total;
`unresolved_llm` and `unresolved_hidden_file` count those states, including zero.
Batch lifecycle events are separate from file states.

See [One-batch identification](one-batch-identification.md) for operation.
