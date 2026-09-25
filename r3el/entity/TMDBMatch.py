"""Saved query, downloaded response, and outcome of movie matching."""

from dataclasses import dataclass, field


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
    catalogue_saved: bool = False
    catalogue_error: str | None = None
    source_path: str | None = None
    catalogue_path: str | None = None
    file_moved: bool = False
    duplicate: bool = False
    discard_files: list[dict] = field(default_factory=list)
    year_offset: int = 0

    @property
    def needs_manual_match(self) -> bool:
        return (not self.skipped and not self.catalogue_saved and not self.selection_pending
                and not self.selected_number and self.response is not None
                and self.response['total_results'] != 1)

    @property
    def resolved_response(self) -> dict | None:
        """Keep only the chosen movie, including for older saved multi-result searches."""
        if not self.selected_number or self.response is None or self.response['total_results'] == 1:
            return self.response
        movie = self.response['results'][self.selected_number - 1]
        return dict(self.response, results=[movie], total_results=1, total_pages=1, page=1)

    @property
    def label(self) -> str:
        if self.skipped:
            return 'Skipped'
        if self.error is not None:
            return 'Match failed'
        if self.catalogue_error is not None:
            return 'Catalogue failed'
        if self.selected_number:
            return '1 match'
        count = self.response['total_results']
        if count == 0:
            return 'No matches'
        return '1 match' if count == 1 else f'{count} matches'
