---
title: Control, Catalogue, and Event Log
author_profile: true
layout: single
---

[Documentation index](../index.md)

# R3el Control

When processing stops with no matches or unresolved multiple matches, the **Action** column
offers a text field and **TMDB ID** button on those rows. Enter a positive movie
ID to fetch that exact TMDB record, including one outside the original results.
The request runs in the background and uses the usual catalogue, artwork, move,
and format-preference workflow. Failed lookups show an error and preserve the
original match results for correction. Active, resolved, Ignore, and Delete
rows do not offer manual matching.

The site opens the **Catalogue**, with navigation ordered Catalogue, Control,
then Event log. Control is available at `/control`.

The **Catalogue** navigation link shows four recent additions beside the logo.
Arrow buttons browse older/newer groups of four. Title search matches part of a
title and displays poster/title/year cards five across in a separate Search
Results panel. Each card opens a movie page with a poster and summary, Director,
Producers, Cast, and Files boxes. These pages read saved catalogue data and local
artwork without querying TMDB.

Movie file lists and individual episodes include Play in VLC links. These
use the stored path with the leading `/exports/` replaced by `/imports/`, for
example `r3el-vlc:///imports/disk1/Movie.mkv`. Other path prefixes stay unchanged.

On the Linux desktop running Chrome and VLC, run this once as your desktop user
(without sudo), from a checkout of R3el:

```sh
python3 scripts/vlc-link.py --install
```

Alternatively, copy just `scripts/vlc-link.py` to that desktop and run it with
`--install`. It requires Python 3, VLC (`vlc` on PATH), and `xdg-mime` from
xdg-utils. The installer registers a per-user `r3el-vlc:` link handler using a
[desktop entry](https://specifications.freedesktop.org/desktop-entry/latest-single/).
Click a media path and accept Chrome's external application prompt. The media
must be mounted at `/imports/...` on that desktop. This opens the local file in
VLC; it does not stream the media from the R3el server.

Title Search, Search Index, Category Search, and Random Search share a row.
Random Search has a single Search button that replaces Recent additions with four
random movies, TV shows, or episodes (or all entries when fewer than four exist).
Each click draws a fresh selection without duplicates within that selection.
Episode cards use the show poster and link to the episode in its show page. The index contains
Numbers and Symbols on its own line, with the alphabet wrapping into narrower rows below, matching the first character
of movie or TV show titles (not episode titles). Leading spaces are ignored.
Index results use the same poster/title/year cards and result count as the other
searches. Letters without matching titles are omitted; each letter has two extra
spaces on either side. Title Search places Type on a separate line. The middle box
fits its contents, Category Search takes the remaining width before Random Search, and the boxes stack
on narrow screens.

`r3el-control.service` is a standalone Jinja2 report server. It displays the
MariaDB event log while the identification service is running or stopped and
does not require Qwen. The Control page places the logo beside vertically aligned
settings in a bordered panel. When the workspace is empty, it provides a Source text box prefilled from `DR3el.FILM_DIR`,
a Destination text box prefilled from `DR3el.MEDIA_DIR`, a free-form Batch Size
number input (positive whole numbers, default 10), and a New Batch button. The maximum
is 4,294,967,295, matching the database column's capacity. The button sends the directories
and size to the identification server over ZeroMQ. Labels and result messages
use Jinja2; shared defaults live in `DR3el`, and message names live in `DMessage`.
The R3el logo is deployed with the server assets. New Batch runs identification and TMDB matching without an intermediate pause.

The control server is a human-operated web application. Opening a page or
refreshing status never starts a batch. The identification service automatically
resumes interrupted processing after restart, using saved batch parameters and
file checkpoints. Completed batches and explicit Stop Batch requests remain idle.
Only submitting New Batch creates a fresh selection. An empty or finished workspace offers that action; an active
batch disables it. New Batch replaces the finished workspace with a fresh
selection, preserving catalogue records, media, and event history. The identification worker finishing does
not clear the application's workspace or automatically begin another batch.

When the workspace contains a batch, the landing page shows its filenames and
saved statuses in selection order. The first columns are `#` (starting at 1) and
`Updated` (`MM-DD HH:MM` in the browser's local timezone). Updated records the last
saved change to the file, rather than the latest page refresh. Older workspace
rows show `—` until changed; upgrading does not invent historical timestamps.
While processing, the Control section is greyed out, saved directories and size
appear as static text, and New Batch is disabled. When processing finishes, fails,
or is stopped, editable controls return with the previous settings, including
for empty batches. Automatic progress polling enables New Batch on completion.
Replacement and fresh selection commit together; a failed selection or database
transaction leaves the previous workspace intact.
The file table ends with an **Action** column containing **TMDB ID** or
**Replace Local Media** when applicable. The Pending / Approve / Ignore / Delete
dropdown is no longer displayed. **Clear Current Batch** is available when a
workspace exists; it safely stops processing before clearing working records,
preserving catalogue entries, imported media, and events.
Beneath the controls, the bold yellow **Current Task:** line shows the current
batch's latest Event Log message and links to its details.

The server processes groups of up to 10 files within the selected batch. Each
group completes identification, TMDB matching, LLM selection, and zero-result
retries before identification starts for the next group. Remaining files stay
Pending. The last group may contain fewer than 10 files.

**Stop Batch** requests a cooperative stop for automatic processing or a manual
TMDB ID matching job. The request is committed independently of the worker's processing
lock. The current operation finishes safely, then the worker stops before another
file or identification retry. An in-flight model/API call must return or time out;
the button does not kill services or interrupt a catalogue transaction or file move.
Completed work remains saved, untouched pending files remain pending, and the batch
is marked cancelled. The UI shows stopping/stopped status. Stop requests survive
restarts and cannot be silently resumed by a repeated matching request.
This does not clear the retained workspace or add a Resume action.

After each group's identification, the server automatically searches movies by the saved title
and year for Pending and Approve files. Ignore and Delete files are skipped without
file operations. New Batch and Stop Batch sit together below Refresh.
There is no Process Batch button; unresolved matches can be corrected with the TMDB ID button.
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
0 means no confident choice. After a successful selection, the **1 match** link
shows only the chosen movie, including in its saved JSON; other candidates are
discarded from the workspace result. Plain-text numbers are not accepted as submissions.
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

A zero-result TMDB search automatically starts a fresh filename-identification
conversation with the normal current-date, focus, filename, and submission prompts.
Previous identifications and search failures are not included in the LLM messages.
The new title/year is searched again, even when it is identical to the previous
answer. The **Retries** column tracks up to three additional identifications after
the initial one. If the third retry still has no matches, TMDB is searched with
the final identified title and one year earlier, then one year later. The first
adjacent-year search returning exactly one movie is accepted. Multiple results
use the usual LLM multiple-choice workflow; an unresolved choice is left for
the manual TMDB ID field. Only zero results continue to the next year.
If neither year gives any matches, use the manual TMDB ID field. The file becomes
`unresolved_llm` and later matching requests leave it exhausted. The batch
continues to other files. API failures do not count as zero-result searches;
failed adjacent-year requests can be retried without repeating completed years.
The Status column shows Pending while identification retries, adjacent-year
requests, and LLM multiple-choice selection are running.
Retry counts and outcomes are checkpointed with their events and survive restarts;
install/upgrade applies the new `media_files.retries` column. Form-correction
attempts within an identification conversation remain a separate counter.

`POST /workspace/match` accepts `batch_id` and promptly returns HTTP 202 with
`accepted: true` and a `job_id`. `GET /workspace/match/status/<job_id>` reports
`running`, `completed`, or `failed`. The browser polls status and saved file
progress every two seconds, then updates the table in place on completion. Reloading the page during
processing resumes polling without submitting another job. Errors stop polling
and ask the user to inspect saved results. The worker owns its database connection
and continues independently of browser connections; shutdown waits for it to finish.
Job status is held in memory for the latest job. After a service restart an old
job ID returns 404; saved file results remain available and processing can be retried.
`GET /matches/<batch_id>/<file_id>` displays a saved result.
Changing an action never executes file operations. `POST /workspace/actions`
accepts `batch_id`, `file_id`, and `action`, returning saved readiness as JSON.

After New Batch is accepted, the control page reloads once after two seconds to
show the discovered files. It returns to `/control`, removing the acceptance flag so the
reload does not repeat or resubmit the batch. During automatic processing, the
table updates every two seconds until the batch finishes or fails. The Refresh dropdown offers Manual
(the default), 5 seconds, 30 seconds, and 1 minute, with an Update button.
Refresh updates only the file table, button readiness,
and last-updated timestamp; the page and form inputs stay in place. Update
applies the interval without navigation. Refresh waits while an action menu is
focused or a save is in progress. The selected interval stays in the URL and is retained
after New Batch acceptance and matching completion.
The Current Batch panel contains the file table in its own bordered box.
Long batches scroll within that box, with the column headers fixed at its top.
“Updated” on the right of its header uses `MM-DD HH:MM:SS` and reports the page's latest workspace read in the browser's local timezone,
not the time the file last changed. Pending files stay Pending until an outcome
is saved. Reads use the shared workspace interface without taking the processor's
exclusive lock. A database failure shows Workspace unavailable with no button.

New Batch replaces a finished workspace. Service startup resumes an interrupted
retained batch. The output directory is stored with the batch and used by the
automatic import stage after matching. Set the
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
Replies without reasoning show an explicit empty-state message. Displayed times use the browser’s local timezone, including daylight-saving changes. Database values remain UTC; timestamp elements carry explicit UTC offsets for display conversion.

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

Catalogue processing records **Artifact / Download** for each poster or backdrop
download, reuse, or failure; **DB / Create Record** when catalogue metadata and
file references commit; and **File / Move** when the source removal completes or
fails. These events carry batch/file context and link to the batch event.
Catalogue record events share the record's transaction, and move events share
the saved completion checkpoint. Already completed files do not repeat these
events when a batch resumes.

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
| `file_move` | Linked filename, source/destination paths, and move outcome or error. |
| `file_delete` | Linked filename, duplicate paths, preferred video path, and deletion outcome or error. |
| `artifact_download` | Linked filename, artwork type, source URL, local path, and download/reuse outcome or error. |
| `db_create_record` | Linked filename, title, TMDB ID, local video path, and catalogue save outcome. |
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
Both the control and batch services load this file through systemd; uninstall removes the installed
copy and leaves `/root/.tmdb` alone. Missing or invalid source credentials stop the
service installer before services are stopped or application modules are replaced.

Movie searches use `TMDB_TOKEN` as a Bearer token. `TMDB_KEY` is retained with the
credentials. For standalone startup, provide `TMDB_TOKEN` in the environment.
See TMDB's [movie search](https://developer.themoviedb.org/reference/search-movie)
and [authentication](https://developer.themoviedb.org/docs/authentication-application)
documentation. This step uses the title and `primary_release_year` search parameters; exactly one
total result establishes a match. Multiple results use LLM candidate selection;
TV search is not included.

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

## Command-line TMDB search

Query a title with an optional four-digit year:

```bash
.venv/bin/python scripts/query-tmdb.py "Superman"
.venv/bin/python scripts/query-tmdb.py "Superman" 2025
```

Choose TV shows with --type tv; movies remain the default (--type movie).
For TV, the optional year filters the first air date, not every episode's year.

```bash
.venv/bin/python scripts/query-tmdb.py --type tv "Breaking Bad"
.venv/bin/python scripts/query-tmdb.py --type tv "Breaking Bad" 2008 --raw
```

TV raw output includes series details and related credits, keywords, external
IDs, alternative titles, content ratings, translations, images, and videos.
It does not fetch each season or episode separately.

For a standalone CLI installation with its own virtual environment:

```bash
sudo scripts/install-cli.sh
/opt/prod/r3el/bin/query-tmdb "Superman" 2025
```

Add `-r` (or `--raw`) to fetch the full movie record for each first-page
search hit and print indented JSON. Each result retains its search fields and
adds all fields from TMDB movie details, including runtime, budget, revenue,
genres, production companies, and collection information. It also includes
credits, keywords, external IDs, alternative titles, release dates, translations,
images, and videos through TMDB `append_to_response`. Search pagination metadata
is preserved; this does not crawl reviews, recommendations, or other search pages:

```bash
/opt/prod/r3el/bin/query-tmdb -r "Superman" 2025
```

The installer creates or reuses `/opt/prod/r3el/.venv` and installs only the
CLI's Python dependencies and modules. It does not provision databases or
install or start services. The installed command works from any directory
without activating the venv or keeping the development checkout available.
The CLI reads `TMDB_TOKEN` from the invoking shell first, then
`/etc/r3el/tmdb.env`, then `~/.tmdb` (for root, `/root/.tmdb`).
Credential files are read as data, never executed. Unreadable files are skipped;
existing credential permissions are preserved.

The script uses the same `primary_release_year` search as batch processing and prints
numbered results with release date, language, rating, TMDB link, and full wrapped
overview. It clearly labels partial first-page results and reports no matches.
It exits with status 1 for a TMDB/configuration failure and 2 for invalid arguments.
It does not contact the LLM or modify the workspace. Install/upgrade deploys the
script alongside the service helper.
