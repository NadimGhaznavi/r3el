# ZMQ messages

R3el uses one JSON frame per request/reply at `DR3el.ZMQ_ENDPOINT` (by default
`tcp://127.0.0.1:42221`). `ZMQMsg` defines the envelope, `DZMQ` defines protocol
version/timing, and `DMessage` defines application sender, target, method, and
control response constants. `MessageHandler` routes requests to separate handlers.
Sender names identify message roles; they are not authentication credentials.

## New batch

```json
{
  "protocol_version": 1,
  "sender": "r3el-control",
  "target": "batch",
  "method": "new_batch",
  "payload": {
    "input_directory": "/exports/disk1/archive/film",
    "output_directory": "/exports/disk1/archive/media",
    "batch_size": 5
  }
}
```

`BatchControl` sends this message. `BatchControlHandler` uses `BatchConfiguration`
to validate exactly these parameters: absolute directory paths and an integer
batch size from `DR3el.BATCH_SIZES` (5 or 10). The input directory must be readable
by the R3el service when processing starts. The output directory is retained for
future file operations; identification does not write there.

The reply has sender `r3el`, target `r3el-control`, and method `new_batch`.
Its payload is one of:

- `{"status": "accepted"}`: scheduled for processing, not yet completed.
- `{"status": "busy"}`: another batch is reserved/running; nothing was queued.
- `{"status": "error", "error": {"code": "invalid_parameters", "message": "..."}}`.
- `{"status": "error", "error": {"code": "not_configured"}}`: no model URL,
  or the server is in diagnostic one-batch mode.
- `{"status": "error", "error": {"code": "unknown_request"}}`: unsupported routing
  or sender for this command.

`BatchProcessor` reserves a single batch and schedules execution on the application
loop. `BatchRunner` opens a fresh database connection and composes identification
resources. The listener thread remains free for tool submissions. Completion
returns the processor to idle. Expected filesystem, HTTP, and database connection
failures are logged and also release it; programming errors propagate.

The workspace is assumed empty. No replacement or cleanup is implemented, and a
retained workspace is never silently reused or overwritten by New Batch. Such a
request fails during execution and is reported in the server journal.
There is no automatic retry: a lost acceptance reply does not prove the batch
wasn't started. The event log records batch/item outcomes.

## Identification submission

MCP uses sender `mcp-identification`, target `identification`, and method
`submit_identification`. The payload contains `attempt_id` and a `submission`
object with `title`, `year`, and `confidence`. `SubmissionHandler` resolves the
server-owned attempt and returns `ok`, `rejected`, or `error`. Idle servers reject
submissions with no active attempt. The existing MCP behavior is unchanged.

Malformed envelopes and transport-handler failures use the existing `error`
reply with codes `invalid_request` and `handler_error`, respectively.
