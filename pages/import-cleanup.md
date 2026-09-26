---
title: Import and source cleanup
author_profile: true
layout: single
---

[Documentation index](../index.md) · [Batch overview](01-high-level-flow.md) · [Directory patterns](directory-patterns.md)

One TMDB match, an accepted LLM selection, or a manual TMDB ID identifies the
movie to import. Its TMDB title and release year determine the destination names.

```mermaid
flowchart TD
    Resolved["Movie resolved"] --> Details["Fetch movie details and apply format preference"]
    Details --> Existing{"Preferred movie already catalogued?"}
    Existing -->|Yes, incoming format is worse| Duplicate["Keep existing media; remove lower-ranked duplicate after checkpoint"]
    Existing -->|No, or incoming format is preferred| Names["Name destination videos and paired SRTs"]
    Names --> Conflict{"Destination collision?"}
    Conflict -->|Yes, replacement not authorized| Entry["Entry exists: preserve source; offer Replace Local Media"]
    Entry -->|User requests replacement| Names
    Conflict -->|No, or replacement authorized| Stage["Stage same-filesystem hard links; prepare artwork"]
    Stage --> Commit["Commit catalogue records, file paths and workspace checkpoint"]
    Commit --> Inodes["Check source and destination inode identity"]
    Inodes --> Remove["Remove source names and staging links"]
    Remove --> Source{"Directory import?"}
    Duplicate --> Source
    Source -->|No| Done["Record outcome; continue batch"]
    Source -->|Yes| Remain{"Any supported media or SRT remains anywhere below source?"}
    Remain -->|Yes| Retain["Keep directory and remaining files"]
    Remain -->|No| Linked{"Any linked subdirectory?"}
    Linked -->|Yes| Retain
    Linked -->|No| Delete["Delete source directory and remaining non-media contents"]
    Retain --> Done
    Delete --> Done
```

Moves use hard links and unlink operations within one filesystem. **Media bytes
are neither copied nor read back for verification.** Sources remain until the
catalogue transaction commits. Inode checks use filesystem metadata, not content
checksums. A different-filesystem destination fails rather than silently copying.

SRTs move alongside their associated videos and receive the same stem. Two-part
movies use `Title (Year) Part 1.ext` and `Title (Year) Part 2.ext`; paired
subtitles use the corresponding `.srt` names. See [File naming](file-naming.md).

Directory cleanup checks recursively, including subdirectories of any depth.
Remaining videos of any supported size, unresolved SRTs, and linked subdirectories
prevent removal of the source tree. A directory with no such content can be
removed, including release notes. For a directory containing separate movies,
this check follows each movie's completion, so the remaining movies keep it alive.

The diagram shows the successful path and destination conflicts. Filesystem or
catalogue errors preserve sources until the commit/removal boundary and record an
error for review. Format-preference deletion is distinct from an exact-path
collision: the latter requires **Replace Local Media**.

See [Catalogue schema](schema.md) for transactions and stored paths and
[Control and Event Log](control-server.md) for monitoring.
