# R3el Control

`r3el-control.service` is a standalone Jinja2 report server. It displays the
MariaDB event log while the identification service is running or stopped and
does not require Qwen. This first control page is read-only; batch commands
and human review actions will come later.

Install and upgrade copy the Python modules and templates, initialize the
event schema, then enable and start the control service. Open
`http://<server>:42220/`. It listens on all interfaces by default, using
`DR3el.PORT`. The separate batch service remains stopped and disabled until
explicitly started. Uninstall removes both R3el units and preserves Qwen.

The page shows up to 500 matching events, newest first. Category and
subcategory filters apply to the full database history before the limit.
Choose manual refresh or a 5, 30, or 60 second page refresh. Event links open
the complete message, source, process ID, app version, and parent event.
JSON messages are indented; plain text messages are preserved. Times are UTC.

## Standalone startup

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
