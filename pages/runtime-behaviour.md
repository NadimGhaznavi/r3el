# R3el workflow

## Implemented

1. Create a persistent workspace containing a `MediaFileBatch` and its selected
   `MediaFile` records, or reload the existing batch.
2. Identify the next group of up to 10 files with Qwen, saving each outcome and
   its current issues.
3. Continue automatically into TMDB matching for that group, without another
   button press.
4. Query Pending and Approve files with an identification by title/year, skipping
   Ignore/Delete files. Resolve multiple candidates with the LLM and retry
   zero-result identifications up to three times.
5. Save each result, then repeat identification and matching for the next group
   of up to 10 files. After the final group, finish with batch state `matching_completed`. Unexpected
   matching errors stop the batch with `matching_failed`.

The human starts each batch with New Batch. Processing then continues independently
of the browser. Process Batch remains available afterward for manual retries.

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
