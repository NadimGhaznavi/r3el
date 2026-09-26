"""Supply the captured directory listing and two candidate media files."""

from r3el.app.Prompt import Prompt


class DirectoryContextTwoParts(Prompt):
    def __init__(self, data: dict) -> None:
        super().__init__(
            "The output below shows the contents of a directory that contains part one and two of a movie. "
            "The two parts have already been identified. Supply your best guess for which file is part one "
            "and which file is part 2. Also supply the title and year and confidence as an integer from 0 to 10.",
            data=data,
        )
