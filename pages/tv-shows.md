---
title: TV show imports
author_profile: true
layout: single
---

[Documentation index](../index.md) · [Directory patterns](directory-patterns.md) · [Catalogue schema](schema.md)

TV series use the same source and batch controls as movies. Each matching
top-level directory counts as one batch selection, including all nested seasons.
Supported videos must be larger than 100 MiB for discovery.

| Source shape | Interpretation |
| --- | --- |
| 11.22.63/11.22.63-01.mkv through -08.mkv | Consistently numbered episodes; the LLM identifies the series and proposes the missing season. |
| 12-Monkeys/12-Monkeys-S01E01.mkv | Explicit season and episode, even with only one video. |
| Slow-Horses/season-2/...S02E05... plus other season directories | One series selection with individual episode mappings across seasons. |
| Show 1x01, Show S01 E01, Show-S01-E01, Show Season 1 Episode 01 | Alternate explicit season/episode forms. |
| Show/season-1/show.103.hdtv.mp4 | Compact episode numbers use the season folder as context. An explicit episode number in the immediate release folder can also identify its video. |
| Black Lagoon 01 The Black Lagoon.mkv | Numbered episodes with titles and a consistent series prefix. |

TV patterns take priority over two-part movies. Explicit season/episode numbers
cannot be changed by the LLM. Numbered files must share a consistent filename
prefix and have unique episode mappings. Season zero is allowed for specials.
Titles beginning with numbers, such as `S01E01 1200 A.M.` or
`Season 2 Episode 09 - 4 Days Out`, are supported.

Discovery selects recognizable episodes even when other videos in the directory
cannot be matched. Extras, featurettes, combined-episode videos, duplicate mappings,
and files whose season conflicts with their folder stay at the source. Their
subtitles are not reassigned to selected episodes. Skipped videos appear in Match
Results, and the directory scan event reports the selected and skipped counts.
Cleanup preserves any remaining media or subtitles.

Filename title prefixes keep visibly misfiled shows out of the parent series.
Collections containing distinct series without a single matching parent title
remain unmatched; use each series directory as a separate immediate child of the
source. Bare unpadded movie sequels in a mixed directory are not selected as TV.
Discovery still expects one episode per video and does not rewrite conflicting
season or episode numbers. Start a new batch to apply these discovery rules to
previously scanned directories.

TV identification has two phases. First, the LLM receives the captured `find -ls`
listing and calls `submit_tv_series` with only the series title and confidence.
TMDB is searched by name without a year filter. Multiple matches use the existing
LLM selection dialogue; zero matches retry series identification without adjacent-year
searches. Manual TMDB ID correction also resolves the identity before episode mapping
can start. The displayed year comes from the selected TMDB record, never an LLM guess.

Second, a fresh dialogue receives the confirmed series name and year, folder context,
and sorted relative filenames keyed by `1`, `2`, and so on in JSON. Full server paths and
the raw `find -ls` output are omitted from this phase's prompt. It supplies
only numeric file-ID/season/episode mappings; it cannot change the series identity.
The backend assigns the IDs and resolves them back to the exact original paths,
so the LLM never needs to reproduce filenames. Every ID must appear exactly once.
The mapping
and its completion marker are saved together. Unresolved mapping leaves the files
untouched. Each mapped episode is
checked against TMDB season and episode metadata before importing it. Unknown
episodes remain at the source while other valid episodes can finish.

The Event Log and Current Task distinguish series identification, candidate selection,
episode mapping and import. The batch reports “Series identified”, “Episodes mapped”
and “Imported” as these stages complete.

## Destination and naming

The batch saves a TV destination alongside its movie destination. It is the
tv sibling of the chosen movie directory. With the default movie destination,
TV imports go to /exports/disk1/archive/media/tv automatically.

For example:

```text
tv/
  Slow Horses (2022)/
    Season 02/
      Slow Horses (2022) S02E05 - Boardroom Politics.mkv
      Slow Horses (2022) S02E05 - Boardroom Politics.srt
```

Series title/year and episode title come from TMDB. If filename normalization
removes the entire episode title (for example, `/`), the filename ends at the
season and episode number. The catalogue keeps the original episode title.
SRT association follows the
existing deterministic rules; ambiguous SRTs remain unresolved. Moves use hard
links followed by source-name removal, without copying or reading back media
contents. Existing destination files require explicit Replace Local Media.

## Checkpoints and catalogue

The TV catalogue has series, seasons, episodes, episode files, series/episode
credits, artwork, and its own genre tables. People and credit roles are shared
with movies. Movie and TV IDs have separate namespaces, including catalogue URLs.

Each episode's catalogue records and workspace checkpoint commit together before
its sources are removed. Restart can complete a committed move without importing
already completed episodes again. A failed episode does not roll back successful
episodes. Source cleanup remains recursive: any supported media or SRT at any
depth, or a linked subdirectory, preserves the source tree.

Catalogue searches and recent additions include TV series. Series pages show
imported episodes with saved summaries, air dates, runtimes, still images and
expandable episode credits, plus local files. The batch Match Results page shows each video's
episode mapping and import outcome.

Install/upgrade applies the TV schema and deploys the new prompt and modules.
The feature does not repair or reclassify already completed movie batches.
