# Identification server

The server starts idle and keeps its MCP/ZeroMQ listener available until stopped.
It does not scan files, resume the workspace, or contact the model on startup.
The control page's New Batch button sends input/output directories and batch size
to the server. It runs one batch and returns to idle while keeping the listener
available. This path assumes an empty workspace; clearing and replacement remain
unimplemented. Output directories are saved for later stages, not used to move files.
An explicit `--run-batch` option retains the one-batch diagnostic workflow described below.

With `--run-batch` and an empty workspace, R3el scans regular files directly inside `DR3el.FILM_DIR`,
selects up to `DR3el.BATCH_SIZE` names alphabetically, saves the selection,
identifies each, and exits. Subdirectories and symbolic links are excluded.
It leaves source files untouched. It does not yet perform TMDB matching,
create a persistent review queue, or move files into `MEDIA_DIR`.

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
Running `--run-batch` again returns its results without calling the model. Workspace
cleanup belongs to finalization, which is not implemented yet.

Install and upgrade apply `EventSchema` followed by `WorkspaceSchema`.

## Run

For a source checkout, install dependencies and set `DB_HOST`, `DB_USER`,
`DB_PASSWORD`, and `DB_NAME` (`DB_PORT` defaults to 3306). Initialize both
schemas, then run against an available model:

```bash
.venv/bin/python -B -m r3el.activity.EventSchema
.venv/bin/python -B -m r3el.activity.WorkspaceSchema
.venv/bin/python -B -m r3el.server.R3elServer --run-batch --llm-url http://MODEL_HOST:PORT
```

Optional `--film-dir`, `--batch-size`, and `--zmq-endpoint` arguments override
defaults in `DR3el`; the default batch size is 10. Use a separate database
for an isolated workspace. For `--run-batch`, supply `--llm-url` or `R3EL_LLM_URL`; idle startup needs neither.

Installation/upgrade prepares the systemd unit but leaves it stopped and
disabled for automatic startup. The installed unit defaults `R3EL_LLM_URL` to
`http://127.0.0.1:27770`; `/etc/r3el/server.env` can override it. Start the shared
model and wait until `http://127.0.0.1:27770/health` returns HTTP 200, then
start the idle listener:

```bash
sudo systemctl start r3el-server.service
```

The service stays idle until stopped. Only the explicit `--run-batch` diagnostic
mode exits after identification. The normal service accepts batches from the web interface.

## Shared Qwen service

Install and upgrade check systemd for Ax3l's production `qwen-server.service`.
An installed service is reused without rewriting its unit, MCP configuration,
account, enabled state, or running state. A masked or broken unit must be
repaired explicitly. Ax3l and R3el are intended to run one at a time.

If absent, R3el installs that same service name using Ax3l's model defaults:
`/opt/prod/llama.cpp/bin/llama-server`,
`/opt/prod/models/Qwen3.5-4B-Q4_K_M.gguf`, context size 12288,
host `0.0.0.0`, port 27770, metrics, Jinja, and the same systemd hardening.
The assets must already exist and be accessible to the service account;
the installer does not download or rebuild them.

The new service uses an independent `qwen` account and
`/etc/qwen-server/mcp.json` with no server-side tools, since R3el manages its
own MCP conversations. It is left stopped and disabled. Start it with
`sudo systemctl start qwen-server.service` before checking readiness.
R3el uninstall preserves the shared model service, its account/configuration,
llama.cpp, and GGUF. An existing Ax3l service retains its Ax3l dependencies.

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
