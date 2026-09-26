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

TV patterns take priority over two-part movies. Explicit season/episode numbers
cannot be changed by the LLM. Numbered files must share a consistent filename
prefix and have unique episode mappings. Season zero is allowed for specials.
Combined-episode filenames and conflicting mappings are left unmatched; this
initial implementation expects one episode per video.

TV identification has two phases. First, the LLM receives the captured `find -ls`
listing and supplies only the series title, first-air year and confidence. TMDB TV
search, multiple-choice selection, zero-result retries and manual TMDB ID correction
resolve that identity before episode mapping can start.

Second, a fresh dialogue receives the confirmed TMDB series name, ID, first-air
date and overview, together with the listing and detected episode files. It supplies
only file/season/episode mappings; it cannot change the series identity. The mapping
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

Series title/year and episode title come from TMDB. SRT association follows the
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
