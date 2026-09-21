# R3el Control

`r3el-control.service` is a standalone Jinja2 report server. It displays the
MariaDB event log while the identification service is running or stopped and
does not require Qwen. This first control page is read-only; batch commands
and human review actions will come later.

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
The full message page indents JSON and preserves plain text. Times are UTC.

## Message templates

The Message column uses Jinja templates in `r3el/server/templates/messages/`.
`EventPages` selects `<event-name>.html` when present, otherwise `default.html`.
Selection uses only the event name; category and subcategory filter rows.
The default shows indented JSON or unchanged plain text, limited to 1,200
characters with an ellipsis, followed by a Full event link.

Each custom template owns the entire Message cell. Its whole message links to
`/events/<event_id>`, without a separate Full event link:

| Event / template name | Display |
| --- | --- |
| `files_retrieved` | `Retrieved filenames (XXX): foo.txt, bar.xls, ...` — total count, first two names in stored order, literal `...`. |
| `batch_started` | `Batch started with size: XXX` using `data.batch_size`. |
| `batch_failed` | Only `data.error`. |
| `batch_cancelled` | `Batch cancelled`. |

`batch_completed`, `batch_resumed`, and other events currently use the default.

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
it. The Full event page always shows the complete generic message, independent
of the column's custom presentation.

## Standalone startup

To start or stop the whole installed stack, use `scripts/services.sh start`
or `scripts/services.sh stop` from the checkout or installation directory.
The helper uses sudo when needed. Startup runs control, Qwen, waits five
seconds, then starts the R3el batch server. Shutdown reverses that order
without delays. A failed command stops the script and returns an error.
The five-second delay is not a model health check. The batch server resumes
the retained workspace; see [Running identification](one-batch-identification.md).

With dependencies installed, the event schema initialized, and `DB_HOST`,
`DB_USER`, `DB_PASSWORD`, and `DB_NAME` in the environment:

```bash
.venv/bin/python -B -m r3el.server.ControlServer --host 127.0.0.1 --port 42220
```

`GET /` and `/events` show the log. `/events/<id>` shows one event.
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
