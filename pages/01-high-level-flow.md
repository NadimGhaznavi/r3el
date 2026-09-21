# R3el workflow

## Implemented

1. Create a persistent workspace containing a `MediaFileBatch` and its selected
   `MediaFile` records, or reload the existing batch.
2. Identify pending files with Qwen, saving each outcome and its current issues.
3. Mark the batch `identification_completed` and retain it for the next stage.

Restart resumes unfinished work. Completed files are skipped; a completed
identification batch is returned without starting another batch.

The Control server displays events. It does not yet provide batch controls or
human review.

## Planned

| Stage | Work |
| --- | --- |
| Matching | Match accepted identifications to TMDB and prepare records for review. |
| Review | Approve, reject, or modify proposed records. |
| Execution | Apply approved filesystem operations and finalize media DB records. |

After finalization, clear the temporary workspace and allow the next batch.
Keep final media records; resolved issues do not require a separate history.
Workspace cleanup and these later stages are not implemented yet.

[Persistent workspace](file-states.md) · [Running identification](one-batch-identification.md) · [Event Log](control-server.md)
