"""Persistent workspace membership and identification progress."""

from dataclasses import dataclass, field
from enum import StrEnum

from r3el.entity.MediaFile import MediaFile


class MediaFileBatchState(StrEnum):
    PROCESSING = 'processing'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    IDENTIFICATION_COMPLETED = 'identification_completed'
    MATCHING = 'matching'
    MATCHING_COMPLETED = 'matching_completed'
    MATCHING_FAILED = 'matching_failed'


@dataclass
class MediaFileBatch:
    id: str
    requested_size: int
    source_directory: str
    files: list[MediaFile] = field(default_factory=list)
    state: MediaFileBatchState = MediaFileBatchState.PROCESSING
    started_event_id: int | None = None
    destination_directory: str | None = None
