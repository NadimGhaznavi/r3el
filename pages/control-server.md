# R3el Control

`r3el-control.service` is a standalone Jinja2 report server. It displays the
MariaDB event log while the identification service is running or stopped and
does not require Qwen. When the workspace is empty, the landing page provides a Media Directory text box prefilled from `DR3el.FILM_DIR`,
an Output Directory text box prefilled from `DR3el.MEDIA_DIR`, a Batch Size dropdown
(5 or 10, default 10), and a New Batch button. The button sends the directories
and size to the identification server over ZeroMQ. Labels and result messages
use Jinja2; shared defaults live in `DR3el`, and message names live in `DMessage`.
The R3el logo is deployed with the server assets. Human review will come later.

When the workspace contains a batch, the landing page shows its filenames and
saved statuses in selection order, with no form or button. This also applies to
completed, failed, cancelled, and zero-file batches retained in the workspace.
The table refreshes every `DR3el.WORKSPACE_REFRESH_SECONDS` (currently five seconds).
“Last updated” at the top right reports the page's latest workspace read in UTC,
not the time the file last changed. Pending files stay Pending until an outcome
is saved. Reads use the shared workspace interface without taking the processor's
exclusive lock. A database failure shows Workspace unavailable with no button.

New Batch assumes an empty workspace. It does not clear, replace, or resume a
retained batch. The output directory is stored with the batch for future stages;
identification does not create that directory or move source files. Set the
identification server's `--llm-url` or `R3EL_LLM_URL` before requesting work.

The command receives an immediate `accepted` reply; this means accepted for
processing, not completed. While running, additional commands receive `busy`
and are not queued. The listener continues handling MCP submissions throughout
the batch. The server returns to idle after completion. Check `/events` for
outcomes and the service journal for failures before workspace creation.
A timeout is an uncertain outcome and is never retried automatically.

`POST /batches` handles the form. Successful submissions redirect to a GET page
so refreshing it does not resubmit work. Both services accept `--zmq-endpoint`
when using a nondefault endpoint. See [ZMQ messages](zmq-messages.md).

Install and upgrade copy the Python modules and templates, initialize the
event and workspace schemas, then enable and start the control service. Open
`http://<server>:42220/`. It listens on all interfaces by default, using
`DR3el.PORT`. The separate batch service remains stopped and disabled until
explicitly started. Uninstall removes both R3el units and preserves Qwen.

The page shows up to 500 matching events, newest first. Category, subcategory,
and event-name dropdowns sit in the table's second header row and apply to
the full database history before the limit. The Event / source dropdown
selects event names such as `tool_received` and `tool_started`. Rows display
source first on one line, for example `FileMgr - files_retrieved`.
Choose manual refresh or a 5, 30, or 60 second page refresh. Event links open
the complete message, source, process ID, app version, and parent event.
The full message page indents JSON and preserves plain text. For `reply_received`,
Message shows the decoded LLM reasoning with Markdown formatting (headings, lists,
emphasis, code blocks, tables, and line breaks). The full logged payload remains
below a JSON heading. Embedded HTML is escaped and unsafe link schemes are blocked.
Replies without reasoning show an explicit empty-state message. Times are UTC.

## Message templates

The Message column uses Jinja templates in `r3el/server/templates/messages/`.
`EventPages` selects `<event-name>.html` when present, otherwise `default.html`.
Selection uses only the event name; category and subcategory filter rows.
The default shows indented JSON or unchanged plain text, limited to 1,200
characters with an ellipsis. The entire preview links to the full event;
there is no separate Full event link, including for server lifecycle messages.

Each custom template owns the entire Message cell. Its whole message links to
`/events/<event_id>`, without a separate Full event link:

| Event / template name | Display |
| --- | --- |
| `files_retrieved` | `Retrieved filenames (XXX): foo.txt, bar.xls, ...` — total count, first two names in stored order, literal `...`. |
| `batch_started` | `Batch started with size: XXX` using `data.batch_size`. |
| `batch_completed` | `Batch completed with size: XXX, unresolved_llm: YYY` using `data.count` and `data.unresolved_llm`. |
| `attempt_started` | `Filename: …` using `context.filename`. |
| `reply_received` | `Filename: …, Reasoning: …` using the decoded reply's `reasoning_content`, up to 20 characters or the first newline, followed by literal `...`. |
| `tool_completed` | `Tool completed. Attempts: XX, Filename: …` using `context.attempt` and `context.filename`. |
| `submission_accepted` | `Submission accepted. Attempts: XX, Filename: …, Title: …, Year: XXXX, Confidence: XX.` using the attempt context and `data.identification`. |
| `tool_received` | `Tool received. Attempts: XX, Filename: …, Title: …, Year: XXXX, Confidence: XX.` using the attempt context and submitted `data`; missing fields show `—`. |
| `item_started` | `Filename: …` using `context.filename`. |
| `item_completed` | `Filename: …` using `context.filename`. |
| `batch_failed` | Only `data.error`. |
| `batch_cancelled` | `Batch cancelled`. |

`batch_resumed` and other events without a custom template use the default.

Confidence is requested and accepted as an integer from 0 to 10, stored and
displayed directly. Tool-received events show the submitted value before
validation; missing fields display `—`.

Each message template receives:

- `event`: the event metadata and original `content`.
- `message.payload`: the decoded JSON value, or the original string for plain
  text messages. Events written by `EventWriter` have `message.payload.context`
  and `message.payload.data`.
- `message.text`: the complete indented JSON or original plain text.

Use simple HTML and Jinja expressions to select fields, labels, and layout.
Keep calculations in Python. HTML escaping is enabled; missing required
variables and template errors surface normally. The default is used only
when the event-specific template is absent, not when it is broken.

To customize an event, add its named template and include its path in the
`modules` list in `scripts/install-services.sh` so install and upgrade deploy
it. The Full event page retains the complete payload independently of the column's
custom presentation; `reply_received` adds formatted reasoning above that payload.

## Standalone startup

To start or stop the whole installed stack, use `scripts/services.sh start`
or `scripts/services.sh stop` from the checkout or installation directory.
The helper uses sudo when needed. Startup runs control, Qwen, waits five
seconds, then starts the R3el batch server. Shutdown reverses that order
without delays. A failed command stops the script and returns an error.
The five-second delay is not a model health check. The server starts idle with its MCP/ZeroMQ listener; see [Running identification](one-batch-identification.md).

With dependencies installed, the event schema initialized, and `DB_HOST`,
`DB_USER`, `DB_PASSWORD`, and `DB_NAME` in the environment:

```bash
.venv/bin/python -B -m r3el.server.ControlServer --host 127.0.0.1 --port 42220
```

`GET /` reads MariaDB to show either batch controls or the retained workspace. `/events` shows the log. `/events/<id>` shows one event.
`/health` reports HTTP server liveness without querying MariaDB; a database
failure on a report page returns HTTP 503. Invalid filters return HTTP 400
and missing events return HTTP 404. The service journal contains database
error details:

```bash
journalctl -u r3el-control.service -f
```

`ControlServer` handles HTTP and request-owned database connections.
`EventPages` renders templates kept alongside the server. `EventReport`
resolves category filters, and `EventLogDb` reads through the shared `DbMgr`.
