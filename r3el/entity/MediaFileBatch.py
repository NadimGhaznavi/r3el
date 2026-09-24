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
    stop_requested: bool = False

    @property
    def in_progress(self) -> bool:
        # Older releases checkpointed service shutdown as cancelled, without
        # the durable flag set by the user's Stop Batch action.
        return (self.state in (MediaFileBatchState.PROCESSING, MediaFileBatchState.MATCHING)
                or (self.state == MediaFileBatchState.CANCELLED and not self.stop_requested))
