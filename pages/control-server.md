# R3el Control

`r3el-control.service` is a standalone Jinja2 report server. It displays the
MariaDB event log while the identification service is running or stopped and
does not require Qwen. When the workspace is empty, the landing page provides a Media Directory text box prefilled from `DR3el.FILM_DIR`,
an Output Directory text box prefilled from `DR3el.MEDIA_DIR`, a Batch Size dropdown
(5 or 10, default 10), and a New Batch button. The button sends the directories
and size to the identification server over ZeroMQ. Labels and result messages
use Jinja2; shared defaults live in `DR3el`, and message names live in `DMessage`.
The R3el logo is deployed with the server assets. File actions can be reviewed before TMDB matching.

The control server is a human-operated web application. Starting it, opening a
page, or refreshing status never sends a batch-start command. Only submitting
the New Batch form does so. An empty workspace offers that action; a retained
batch shows the current work instead. The identification worker finishing does
not clear the application's workspace or automatically begin another batch.

When the workspace contains a batch, the landing page shows its filenames and
saved statuses in selection order. The Control section stays visible but greyed
out, with “Batch is being processed...” beneath its heading. Saved input/output
directories and batch size appear as static text, and New Batch is disabled. This also applies to
completed, failed, cancelled, and zero-file batches retained in the workspace.
The file table ends with an Action dropdown: Pending / Approve / Ignore / Delete.
These choices are saved in the workspace when changed. Identification initially
selects Approve for confidence 10 and Pending otherwise. Rows still awaiting
identification have disabled dropdowns until an outcome is available on reload.
Saving an action updates button readiness without reloading the page. A failed
or uncertain save disables further edits until the user reloads to read the saved
state; no save is retried automatically.

Process Batch is enabled as soon as identification is complete for a nonempty
batch, even with Pending actions. Clicking it steps through the files and searches
movies by the saved title and year for Pending and Approve files. Ignore and Delete files are skipped without file operations.
The background worker holds the workspace processing lock; action changes
receive a conflict while it runs. Duplicate submissions for the active batch
return the same job instead of starting more work. Results are saved per file as searches finish.

After matching, Match Results links show **1 match**, **No matches**, or
**N matches**, using TMDB's total result count. **Match failed** links show the
failure; **Skipped** has no link. The details page shows the queried title/year and a movie card for each downloaded
candidate: poster, title/year, language, rating/votes, genres, overview, release date,
original title, and a link to the movie on TMDB. A single total result is Resolved;
multiple results trigger a `multiple_choice` LLM prompt with numbered candidate
titles and overview excerpts (about 160 characters, extended to the end of the
sentence). The model calls `submit_multiple_choice(number)` through MCP. A temporary
loopback ZeroMQ listener validates the integer against the server-owned attempt
and candidate count, rejecting stale or duplicate submissions. Only the number
is exposed as a tool argument. A valid choice is saved and marked Resolved;
0 means no confident choice. Plain-text numbers are not accepted as submissions.
Invalid replies and connection failures leave the result Ambiguous and can be retried
without repeating the TMDB search. Selection uses the downloaded first page.
The control service uses `R3EL_LLM_URL` from `/etc/r3el/server.env`, defaulting to
the local Qwen service. Missing metadata has
explicit placeholders. The layout stacks on small screens. Saved JSON remains
available in a collapsed details section. When only the first page of a larger
result set is downloaded, the page states how many results are shown. Opening or refreshing
these pages reads the saved result without querying TMDB. Matching again reuses
successful queries and retries failures. Changing a file action clears its result.
Pending and Approve files without an identification receive Match failed. Missing
identifications and lookup failures do not stop processing the remaining files.

`POST /workspace/match` accepts `batch_id` and promptly returns HTTP 202 with
`accepted: true` and a `job_id`. `GET /workspace/match/status/<job_id>` reports
`running`, `completed`, or `failed`. The browser polls status and saved file
progress every two seconds, then reloads on completion. Reloading the page during
processing resumes polling without submitting another job. Errors stop polling
and ask the user to inspect saved results. The worker owns its database connection
and continues independently of browser connections; shutdown waits for it to finish.
Job status is held in memory for the latest job. After a service restart an old
job ID returns 404; saved file results remain available and processing can be retried.
`GET /matches/<batch_id>/<file_id>` displays a saved result.
Changing an action never executes file operations. `POST /workspace/actions`
accepts `batch_id`, `file_id`, and `action`, returning saved readiness as JSON.

After New Batch is accepted, the control page reloads once after two seconds to
show the discovered files. It returns to `/`, removing the acceptance flag so the
reload does not repeat or resubmit the batch. Reload manually for later updates
to the table and timestamp.
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

## TMDB events

Movie matching records `tmdb_search` under **TMDB / Search** before each API
request, including filename, title, `primary_release_year`, page, and endpoint.
`tmdb_result` uses **TMDB / Result** and links to its search event. Its details
contain the complete response or error, queried title/year, and outcome.
Search events link to the batch's start event; both events carry batch/file IDs.
Credentials and authorization headers are never included.

Result events commit in the same transaction as the saved workspace result.
Expected search failures use ERROR severity; zero or multiple results remain INFO.
If configuration or identification is missing, a failure result links directly to
the batch because no search was sent. Ignore/Delete files and reused saved results
do not create search/result events. Each actual retry gets its own event pair.
Opening saved result pages does not generate matching events.

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
| `tmdb_search` | Linked filename, title, and primary release year; full details include query parameters. |
| `tmdb_result` | Linked filename and match count or failure; full details include the response or error. |
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

To start or stop the installed R3el services, use `scripts/services.sh start`
or `scripts/services.sh stop` from the checkout or installation directory.
The helper uses sudo when needed. Startup runs control, then the R3el batch
server. Shutdown reverses that order. Qwen is managed separately; this script
does not start or stop it. A failed command stops the script and returns an error.
The server starts idle with its MCP/ZeroMQ listener; see [Running identification](one-batch-identification.md).

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

## TMDB credentials

Install and upgrade read `TMDB_TOKEN` and `TMDB_KEY` from `/root/.tmdb`, accepting
plain or quoted assignments and optional `export` prefixes. The file is parsed as
data, never executed. Both values are required and installed atomically into
`/etc/r3el/tmdb.env`, alongside `database.env`, with root ownership and mode 0600.
The control service loads this file through systemd; uninstall removes the installed
copy and leaves `/root/.tmdb` alone. Missing or invalid source credentials stop the
service installer before services are stopped or application modules are replaced.

Movie searches use `TMDB_TOKEN` as a Bearer token. `TMDB_KEY` is retained with the
credentials. For standalone startup, provide `TMDB_TOKEN` in the environment.
See TMDB's [movie search](https://developer.themoviedb.org/reference/search-movie)
and [authentication](https://developer.themoviedb.org/docs/authentication-application)
documentation. This step uses the title and `primary_release_year` search parameters; exactly one
total result establishes a match. No TV search or candidate selection is included.

## Shared TMDB catalogs

`tmdb_movie_genres` stores TMDB genre IDs and English names. `tmdb_languages`
stores ISO 639-1 codes, English names, and native names. These catalogs are shared
application data and remain independent of workspace batches, ready for the future
browsing interface. The Match Results page reads them through `TMDBReferenceDb`.
Unknown IDs/codes remain visible as IDs/codes rather than being assigned a guessed name.

Install and upgrade explicitly create the tables, download both catalogs, validate
them, and upsert them in one transaction. A failed download or database write leaves
existing catalog records intact. Refreshes preserve IDs no longer returned by TMDB
so future media references are not broken. No background refresh or page-triggered
API request occurs. With DB credentials and `TMDB_TOKEN` in the environment, refresh
manually with `.venv/bin/python -m r3el.activity.TMDBReferenceRefresh`.

The catalogs come from TMDB's [movie genres](https://developer.themoviedb.org/reference/genre-movie-list)
and [languages](https://developer.themoviedb.org/reference/configuration-languages)
endpoints. Posters use the saved poster path and TMDB's documented
[image URL format](https://developer.themoviedb.org/docs/image-basics); the browser
loads the public image without receiving API credentials.
