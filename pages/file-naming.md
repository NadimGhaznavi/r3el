---
title: File naming
author_profile: true
layout: single
---

[Documentation index](../index.md)

The batch's output directory is the root. Each resolved movie gets a
`Title (Year)` directory, using the normalization below. The video uses the
same name with its original extension. For example, a batch output of
`/exports/disk1/archive/media/movies` produces:

```text
/exports/disk1/archive/media/movies/Title (2020)/Title (2020).mkv
```

Posters and backdrops are downloaded into that folder and referenced by the
catalogue. Movie title/year come from the accepted TMDB record.

The default output is /exports/disk1/archive/media/movies. Two-part movies
use Title (Year) Part 1.ext and Title (Year) Part 2.ext. Associated SRTs use the
matching video stem, such as Title (Year) Part 1.srt. Files are moved within the
same filesystem without copying contents; see [import and cleanup](import-cleanup.md).

For multiple formats matched to the same TMDB movie, retain the first available
format in this order: `mkv`, `mp4`, `m4v`, `avi`, `mov`, `wmv`, `flv`, `mpg`/`mpeg`.
Extensions are compared without case; `mpg` and `mpeg` have equal preference,
so an already catalogued copy wins that tie. This is a container preference,
not an assessment of resolution or encoding quality.

After the preferred video is saved, lower-ranked versions are deleted and their
catalogue file links removed. This also applies when a better format arrives in
a later batch. Cleanup is checkpointed for retries and logged under File / Delete.
Files with the same extension retain the existing collision protection; they
are not automatically deleted by this format policy.

```python
import re
import unicodedata


def movie_filename(title: str, year: int, extension: str) -> str:
    title = unicodedata.normalize("NFKC", title)

    replacements = {
        ":": " - ",
        "/": " - ",
        "\\": " - ",
        "#": "",
        "%": " percent ",
        '"': "",
        "*": "",
        "?": "",
        "<": "",
        ">": "",
        "|": "",
    }

    for old, new in replacements.items():
        title = title.replace(old, new)

    # Normalize curly apostrophes/quotes.
    title = title.replace("’", "'")
    title = title.replace("‘", "'")
    title = title.replace("“", "")
    title = title.replace("”", "")

    # Collapse whitespace and tidy separators.
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"\s*-\s*", " - ", title)
    title = title.strip(" .-")

    extension = extension.lstrip(".")

    return f"{title} ({year}).{extension}"
```
