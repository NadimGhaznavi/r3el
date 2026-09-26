---
title: Catalogue Schema
author_profile: true
layout: single
---

[Documentation index](../index.md)

The catalogue stores one movie per TMDB ID and keeps its local files separate
from the temporary batch workspace. A single search result or a successful
multiple-choice selection triggers a full TMDB details fetch and catalogue save.
Ambiguous, skipped, and failed matches do not create catalogue records.

| Table | Contents |
| --- | --- |
| `movies` | TMDB ID (primary key), title, original title, release date, derived release year, overview, runtime in minutes, poster/backdrop paths, IMDb ID, rating, vote count, UTC metadata fetch timestamp, and first-added timestamp |
| `people` | TMDB person ID (primary key) and name |
| `credit_roles` | Actor, Director, Producer, Executive Producer, Co-Producer |
| `movie_credits` | Movie, person, role, character name, and cast billing order |
| `tmdb_movie_genres` | Existing shared TMDB genre IDs and names |
| `movie_genres` | Unique movie/genre pairs |
| `movie_files` | Local file path linked to a movie |
| `movie_artwork` | Local poster/backdrop paths linked to a movie, with their media type |

There is no catalogue language field. Missing optional metadata is SQL `NULL`.
`release_year` is generated from `release_date`, so the two cannot disagree.
Ratings and vote counts are TMDB values as of `fetched_at`.

The added_at timestamp records first insertion and orders recent additions;
metadata refreshes preserve it. Existing rows are initialized from fetched_at.

People are shared across movies and roles. A person may be an actor, director,
and producer on the same movie; several cast characters remain separate credits.
Credit positions identify rows within a movie, while `billing_order` preserves
TMDB's cast order. Repeated identical credits are collapsed before saving.

File paths use a SHA-256 key to support long, case-sensitive paths without a
truncated unique index. Reprocessing the same path updates its movie link;
different paths can link to the same movie. File links have no dependency on
workspace rows and survive workspace removal. `movie_files.path` stores the final
video path. `movies.poster_path` and `movies.backdrop_path` retain TMDB's remote
paths; `movie_artwork.path` stores the downloaded local files.

The destination comes from the batch definition, without adding a fixed root
or an extra `movies` component. Under it, the movie directory is `Title (Year)`
and the video is `Title (Year).ext`, following [the naming rules](file-naming.md).
The title and year come from the selected TMDB movie; a missing release date
requires attention rather than inventing a year. Artwork uses names such as
`poster-<TMDB-image-name>.jpg` and `backdrop-<TMDB-image-name>.jpg`.

The source and destination must be on the same filesystem. Preparing a move
creates hard links without copying or hashing video bytes. The source name is
removed only after the catalogue transaction commits. The workspace path is
updated to the destination in that transaction. A separate completion checkpoint
allows retries after commit or source removal, without downloading metadata again.
The hidden `.r3el-<file-id>.video` link identifies an interrupted preparation and
is removed after the move. `.tmdb-id` identifies the movie owning the folder.
Existing unrelated destination files or conflicting movie identities cause a
visible failure; they are never overwritten. Failed downloads and database writes
leave the source in place. Prepared links/artwork can remain for the retry.

The service account needs read/write access to the source file and both parent
directories. The control service uses `ProtectSystem=full` so batch-selected data
directories remain writable while system directories stay read-only.

The save transaction refreshes the movie, people, genres, and credits and
upserts its file link alongside the workspace checkpoint and event. A failed
transaction rolls back all of these changes. Refreshing a movie replaces its
genre and credit associations while retaining its other file links.

Completed workspace matches carry a catalogue checkpoint to avoid repeat
downloads on repeated processing requests. Existing resolved matches without
that checkpoint are catalogued when processed again. A metadata failure retains
the chosen match, displays the failure, and can be retried without a new search.

`scripts/install-services.sh` applies `r3el.activity.CatalogueSchema` during
installation and upgrade. Schema creation is idempotent and runs explicitly,
never as a side effect of opening a database connection. Existing catalogue
records are preserved on upgrade; no automatic historical backfill runs.

## TV hierarchy

TV imports use tv_series, tv_seasons, tv_episodes and tv_episode_files, with
separate tv_artwork, tv_series_genres, tmdb_tv_genres, tv_series_credits and
tv_episode_credits tables. They share people and credit_roles with movies.

Season numbers are unique within a series; episode numbers are unique within a
season. Season zero supports specials. Episode file paths use the same SHA-256
path keys as movie files. Catalogue and attachment import checkpoints commit in
one transaction before source names are removed. See [TV show imports](tv-shows.md).

Workspace items carry media_type; attachments carry season_number,
episode_number and import_result. Batches persist tv_destination_directory,
derived as the tv sibling of the movie destination.
