# R3el workflow

## Implemented

1. Create a persistent workspace containing a `MediaFileBatch` and its selected
   `MediaFile` records, or reload the existing batch.
2. Identify pending files with Qwen, saving each outcome and its current issues.
3. Mark the batch `identification_completed` and retain it for action review.
4. Once every action is resolved, Match TMDB queries approved files by title/year
   and skips Ignore/Delete files. Save responses and display linked JSON results.

The server starts idle. Explicit diagnostic `--run-batch` resumes unfinished
identification; completed files are skipped. No new batch starts automatically.

The Control server provides New Batch, saved action choices, Match TMDB, and event reports.

## Planned

| Stage | Work |
| --- | --- |
| Review | Approve, reject, or modify proposed records. |
| Execution | Apply approved filesystem operations and finalize media DB records. |

After finalization, clear the temporary workspace and allow the next batch.
Keep final media records; resolved issues do not require a separate history.
Workspace cleanup and these later stages are not implemented yet.

[Persistent workspace](file-states.md) · [Running identification](one-batch-identification.md) · [Event Log](control-server.md)
