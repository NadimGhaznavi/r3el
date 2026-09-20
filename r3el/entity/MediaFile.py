"""Current working data for one file in a batch."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from r3el.entity.Identification import Identification


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

    @property
    def filename(self) -> str:
        return Path(self.path).name
