"""Keep filename identification focused on the supplied title and year."""

from r3el.app.Prompt import Prompt


class Focus(Prompt):
    def __init__(self) -> None:
        super().__init__(
            "If the filename directly contains a plausible title and 4-digit year, "
            "treat those as authoritative for this stage. Do not compare against "
            "remembered filmography or question whether the film exists. Submit "
            "immediately unless the filename itself is ambiguous."
        )

    @property
    def source_name(self) -> str:
        return 'focus'
