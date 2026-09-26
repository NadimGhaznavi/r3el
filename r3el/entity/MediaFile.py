"""Current working data for one file in a batch."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from r3el.entity.Identification import Identification
from r3el.entity.MediaAttachment import MediaAttachment
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.entity.TMDBMatch import TMDBMatch


class MediaFileState(StrEnum):
    PENDING = 'pending'
    IDENTIFIED = 'identified'
    UNRESOLVED_LLM = 'unresolved_llm'
    UNRESOLVED_HIDDEN_FILE = 'unresolved_hidden_file'


@dataclass(frozen=True)
class MediaFileIssue:
    code: str
    message: str


@dataclass
class MediaFile:
    id: str
    path: str
    state: MediaFileState = MediaFileState.PENDING
    identification: Identification | None = None
    issues: list[MediaFileIssue] = field(default_factory=list)
    attempts: int = 0
    action: MediaFileAction = MediaFileAction.PENDING
    tmdb_match: TMDBMatch | None = None
    retries: int = 0
    updated_at: datetime | None = None

    media_type: str = 'movie'
    source_directory: str | None = None
    find_ls: str | None = None
    attachments: list[MediaAttachment] = field(default_factory=list)

    @property
    def directory_context(self) -> dict | None:
        if self.find_ls is None:
            return None
        if self.media_type == 'tv':
            return {'find-ls': self.find_ls, 'episodes': {
                file.path: {'season_number': file.season_number, 'episode_number': file.episode_number}
                for file in self.attachments if file.kind == 'video'}}
        videos = [file.path for file in self.attachments if file.kind == 'video']
        return {'find-ls': self.find_ls, 'media_file_a': videos[0], 'media_file_b': videos[1]}

    def assign_episodes(self, episodes: list[dict]) -> None:
        mapping = {row['path']: row for row in episodes}
        for file in self.attachments:
            row = mapping.get(file.path if file.kind == 'video' else file.media_path)
            if row:
                file.season_number, file.episode_number = row['season_number'], row['episode_number']

    def assign_parts(self, part_one: str, part_two: str) -> None:
        parts = {part_one: 1, part_two: 2}
        for file in self.attachments:
            file.part = parts.get(file.path if file.kind == 'video' else file.media_path)

    @property
    def filename(self) -> str:
        return Path(self.path).name

    @property
    def display_year(self) -> int | None:
        if self.media_type != 'tv':
            return self.identification.year if self.identification else None
        match = self.tmdb_match
        if match is None or match.selection_pending or match.selection_error or match.error:
            return None
        response = match.resolved_response
        if response is None or response['total_results'] != 1:
            return None
        value = response['results'][0].get('first_air_date')
        try:
            return date.fromisoformat(value).year if value else None
        except (ValueError, TypeError):
            return None

    @property
    def pending(self) -> bool:
        return (self.state == MediaFileState.PENDING
                or (self.tmdb_match is not None and self.tmdb_match.selection_pending))
