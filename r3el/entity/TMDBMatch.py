"""Saved query, downloaded response, and outcome of movie matching."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TMDBMatch:
    title: str | None
    year: int | None
    response: dict | None = None
    error: str | None = None
    skipped: bool = False
    selected_number: int | None = None
    selection_error: str | None = None
    selection_pending: bool = False

    @property
    def label(self) -> str:
        if self.skipped:
            return 'Skipped'
        if self.error is not None:
            return 'Match failed'
        if self.selected_number:
            return '1 match'
        count = self.response['total_results']
        if count == 0:
            return 'No matches'
        return '1 match' if count == 1 else f'{count} matches'
