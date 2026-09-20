# One-batch identification

This first slice scans only regular files directly inside `DR3el.FILM_DIR`,
selects up to `DR3el.BATCH_SIZE` names alphabetically, identifies each, and exits.
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
- `Identification` holds the accepted title, year, and confidence.

The model supplies only the form values. R3el assigns the batch, item, and
attempt identifiers outside the model's control. The listener resolves the
attempt identifier to the active server-owned context.

## Results and logging

Each filename gets one initial attempt and at most `MAX_LLM_RETRIES = 2`
correction attempts. Invalid tool-call structure or rejected form data produces
a corrective prompt. Exhaustion records `unresolved_llm` and advances to the
next file. An accepted submission is `identified`, not TMDB-resolved.

HTTP, MCP, database, and transport failures abort the batch and are not
silently retried as identification failures. SIGTERM/SIGINT cancel the current
conversation, close the MCP process and listener, and stop the server.

The event log records retrieved filenames, prompt sources and contents, raw
model replies, tool receipt/results, validation decisions, and item/batch
outcomes. JSON content carries batch/item/attempt IDs. Parent event IDs connect
the batch, item, attempt, and its tool events. This prototype's results are
stored in the event log and printed as JSON; staging tables come later.

## Run

DEV does not have access to the real LLM. Tests use a scripted local HTTP
server with real MCP, ZeroMQ, and MariaDB components.

Where the model is available, after installing dependencies and initializing
the event schema, with `DB_*` credentials in the environment:

```bash
.venv/bin/python -B -m r3el.server.R3elServer --llm-url http://MODEL_HOST:PORT
```

Optional `--film-dir`, `--batch-size`, and `--zmq-endpoint` arguments allow
isolated runs. Defaults come from `DR3el`. A missing model URL is an error;
there is no assumed DEV model endpoint.

Installation/upgrade prepares the systemd unit but leaves it stopped and
disabled for automatic startup. Set `R3EL_LLM_URL=http://MODEL_HOST:PORT` in
`/etc/r3el/server.env`, then explicitly start one batch:

```bash
sudo systemctl start r3el-server.service
```

The service exits after that batch and does not restart automatically. The
future web interface will replace this manual start with “Retrieve new batch.”

## Verification

```bash
.venv/bin/python -B -m unittest discover -s tests -v
sudo env R3EL_TEST_DB=1 .venv/bin/python -B -m unittest discover -s tests -v
```

The second command requires MariaDB root socket access and creates/removes a
unique test database and account. It uses temporary filenames and a fake LLM;
it does not use production files or the production database.
