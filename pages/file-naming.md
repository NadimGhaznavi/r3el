The batch's output directory is the root. Each resolved movie gets a
`Title (Year)` directory, using the normalization below. The video uses the
same name with its original extension. For example, a batch output of
`/exports/disk1/archive/media/movies` produces:

```text
/exports/disk1/archive/media/movies/Title (2020)/Title (2020).mkv
```

Posters and backdrops are downloaded into that folder and referenced by the
catalogue. Movie title/year come from the accepted TMDB record.

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
