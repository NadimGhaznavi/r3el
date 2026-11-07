---
title: Identification server
author_profile: true
layout: single
lang: en
locale: en-US
language_name: English
translation_key: r3el-one-batch-identification
---

[Documentation index](../index.md)

# Identification server

The normal server keeps its MCP/ZeroMQ listener available until stopped.
It resumes interrupted work on startup when a model URL is configured, while
completed or explicitly stopped batches remain idle.

**New Batch** sends source, destination and batch size to the server. It runs
identification, TMDB matching, candidate selection, catalogue saving and media
moves automatically. Ordinary files are processed in groups of up to 10, followed
by matched directory items. See the [batch overview](flowchart.md) and
[directory patterns](directory-patterns.md).

The explicit --run-batch diagnostic workflow selects regular files directly
inside the source, excludes subdirectories and symbolic links, identifies
filenames and exits. It can reload a retained workspace and skip saved outcomes.
Identification alone leaves source files untouched; this diagnostic path does
not run the normal automatic import pipeline.

## Components

Workflow classes live directly in `r3el/app`, with prompts in `r3el/app/prompts`
and MCP tools in `r3el/app/tools`. The stdio MCP entry point is
`python -m r3el.app.tools`.

- `FileMgr` is the filesystem interface.
- `FileContext`, `SubmitIdentificationPrompt`, and `InvalidIdentification`
  supply task context, tool instructions, and corrective feedback separately.
- `BatchIdentification` and `ToolConversation` are activities coordinating
  the batch and individual conversations.
- `LLM` and `IdentificationTools` bridge HTTP and stdio MCP. The tool schema
  is discovered from MCP and sent with the model request.
- The MCP `SubmitIdentification` bridge forwards values over ZeroMQ.
- `SubmissionHandler` and `ValidateIdentification` run in R3el. They perform
  ordinary form validation and return either an identification or a rejection.
- `Identification` holds the accepted title, year, and integer confidence from 0 to 10.
- `MediaFileBatch` and `MediaFile` hold the current workspace data.
- `WorkspaceDb` saves and reloads the workspace through the shared `DbMgr`.

The model supplies only the form values. R3el assigns the batch, item, and
attempt identifiers outside the model's control. The listener resolves the
attempt identifier to the active server-owned context.

Prompts that supply data use a JSON object with separate `instructions` and
`data` fields in the message content. Dates, filenames, and validation reasons
remain structured values. TMDB selection uses the same format, with a `query`
object and a `candidates` array containing `number`, `title`, `overview`, and `vote_count`.
Overview excerpts still extend through the sentence ending after roughly 160
characters; missing overviews are empty strings. Instruction-only prompts such
as `focus` retain their wording.

## Results and logging

See [Persistent workspace](file-states.md) for states and batch-summary counters.

Hidden filenames (names beginning with `.`) are flagged as
`unresolved_hidden_file` with zero attempts and are never sent to the LLM.
They count toward the batch size and remain in the results and event log.

Each other filename gets one initial attempt and at most `MAX_LLM_RETRIES = 2`
correction attempts. Invalid tool-call structure or rejected form data produces
a corrective prompt. Exhaustion records `unresolved_llm` and advances to the
next file. An accepted submission is `identified`, not TMDB-resolved.
The prompts and tool schema request integer confidence from 0 to 10. Validation
rejects fractional values, strings, booleans, and out-of-range numbers without coercion.

HTTP, MCP, database, and transport failures abort the batch and are not
silently retried as identification failures. SIGTERM/SIGINT cancel the current
conversation, close the MCP process and listener, and stop the server.

The event log records retrieved filenames, prompt sources and contents, raw
model replies, tool receipt/results, validation decisions, and item/batch
outcomes. JSON content carries batch/item/attempt IDs; item IDs are MediaFile IDs.
Parent event IDs connect the batch, item, attempt, and its tool events.
Results are saved in `media_file_batches` and `media_files`, recorded in the
event log, and printed as JSON. File results include an `issues` list.

## Restart and workspace

Each file outcome and its completion event commit together. Running again with `--run-batch` reloads
the retained batch and skips saved outcomes; an interrupted file starts a new
identification conversation. The saved directory, selection, and batch size
take precedence over new `--film-dir` and `--batch-size` arguments. Only one
processor can use the workspace at once. Resuming logs `batch_resumed`.

An `identification_completed` batch stays available for later matching and review.
Running `--run-batch` again returns its results without calling the model. **Clear Current Batch** removes working records after processing stops, retaining
media, catalogue records and event history.

Install and upgrade apply `EventSchema` followed by `WorkspaceSchema`, including
the matching lifecycle states. The server unit also loads TMDB credentials from
`/etc/r3el/tmdb.env` for automatic matching.

## Run

For a source checkout, install dependencies and set `DB_HOST`, `DB_USER`,
`DB_PASSWORD`, and `DB_NAME` (`DB_PORT` defaults to 3306). Initialize both
schemas, then run against LlamaSrv on its default inference port:

```bash
.venv/bin/python -B -m r3el.activity.EventSchema
.venv/bin/python -B -m r3el.activity.WorkspaceSchema
.venv/bin/python -B -m r3el.server.R3elServer --run-batch --llm-url http://127.0.0.1:51001
```

Optional `--film-dir`, `--batch-size`, and `--zmq-endpoint` arguments override
defaults in `DR3el`; the default batch size is 10. Use a separate database
for an isolated workspace. For `--run-batch`, supply `--llm-url` or `R3EL_LLM_URL`; idle startup needs neither.

Installation/upgrade prepares the systemd unit but leaves it stopped and
disabled for automatic startup. The installed unit defaults `R3EL_LLM_URL` to
`http://127.0.0.1:51001`, LlamaSrv's default inference endpoint;
`/etc/r3el/server.env` can override it. Start LlamaSrv separately and wait until
`http://127.0.0.1:51001/health` returns HTTP 200 (or check the configured model URL), then
start the idle listener:

```bash
sudo systemctl start r3el-server.service
```

The service waits for new batches when no interrupted work needs resuming. Only the explicit `--run-batch` diagnostic
mode exits after identification. The normal service accepts batches from the web interface.

## LlamaSrv model service

[LlamaSrv](https://llamasrv.osoyalce.com/)
([GitHub repository](https://github.com/NadimGhaznavi/llamasrv)) runs and manages
the local Qwen model independently of R3el. Follow LlamaSrv's installation and
model setup instructions first. Its default model is Qwen3.5-4B. Applications
send OpenAI-compatible requests to inference port `51001`; port `51000` is
LlamaSrv's control panel. R3el records that documented inference default in
`r3el/constants/DLlama.py`; LlamaSrv owns the model listener.

R3el install, upgrade, uninstall, and `scripts/services.sh` manage R3el's
services only. They do not provision, start, stop, or remove LlamaSrv, its
accounts/configuration, llama.cpp, or model files. The model may be stopped
while installing R3el or using its catalogue; it must be ready before starting
identification or LLM candidate selection. For a default LlamaSrv installation:

```bash
sudo systemctl start llamasrv-llm.service
curl -fsS http://127.0.0.1:51001/health
```

Wait for HTTP 200 before starting R3el's batch server. For another model host
or inference port, set `R3EL_LLM_URL` in `/etc/r3el/server.env` as described in
[model connection configuration](configuration.md#model-connection).

Keep LlamaSrv's `llama.jinja` setting enabled (the default), which passes
`--jinja` to llama-server. The Qwen model needs a tool-capable chat template;
see llama.cpp's [function-calling documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md).
R3el starts its own stdio MCP subprocess, supplies tool schemas with each
request, executes returned tool calls, and sends tool results back when a
correction is needed. It requests `tool_choice: "required"` with
`parallel_tool_calls: false` and expects one structured `message.tool_calls`
entry containing an ID, function name, and JSON-encoded arguments.
No R3el tool registration or `--mcp-servers-config` option is needed in LlamaSrv.
Other applications can supply and execute their own tools using the same model service.

When upgrading an older R3el installation, the new unit uses port `51001` unless
`/etc/r3el/server.env` overrides `R3EL_LLM_URL`. Existing overrides are preserved;
update an old endpoint or remove the override to use LlamaSrv's default. A
previously installed `qwen-server.service` and its files/accounts are left
untouched. Retire that service separately after checking its other consumers.

## Verification

```bash
.venv/bin/python -B -m unittest discover -s tests -v
sudo env R3EL_TEST_DB=1 .venv/bin/python -B -m unittest discover -s tests -v
```

The second command requires MariaDB root socket access and creates/removes a
unique test database and account. It uses temporary filenames and a fake LLM;
it does not use production files or the production database. Integration tests
exercise real HTTP, MCP, ZeroMQ, and MariaDB, including checkpoint rollback,
exclusive processing, and restart after killing the server mid-batch.
