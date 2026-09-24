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