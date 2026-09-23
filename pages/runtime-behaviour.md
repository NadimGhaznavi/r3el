# R3el workflow

## Implemented

1. Create a persistent workspace containing a `MediaFileBatch` and its selected
   `MediaFile` records, or reload the existing batch.
2. Identify pending files with Qwen, saving each outcome and its current issues.
3. Mark the batch `identification_completed` and retain it for action review.
4. Process Batch queries Pending and Approve files with an identification by
   title/year and skips Ignore/Delete files. Save results as each file finishes,
   continuing past missing identifications and lookup failures.

The server starts idle. Explicit diagnostic `--run-batch` resumes unfinished
identification; completed files are skipped. No new batch starts automatically.

The Control server provides New Batch, saved action choices, Process Batch, and event reports.

## Planned

| Stage | Work |
| --- | --- |
| Review | Approve, reject, or modify proposed records. |
| Execution | Apply approved filesystem operations and finalize media DB records. |

After finalization, clear the temporary workspace and allow the next batch.
Keep final media records; resolved issues do not require a separate history.
Workspace cleanup and these later stages are not implemented yet.

[Persistent workspace](file-states.md) · [Running identification](one-batch-identification.md) · [Event Log](control-server.md)
