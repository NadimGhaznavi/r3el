"""Give the model today's date before the identification task."""

from datetime import date

from r3el.app.Prompt import Prompt


class CurrentDate(Prompt):
    def __init__(self) -> None:
        super().__init__(
            "Your internal training knowledge may be older than this date.",
            data={'current_date': date.today().isoformat()},
        )

    @property
    def source_name(self) -> str:
        return 'current_date'
