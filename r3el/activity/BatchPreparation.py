"""Determine whether batch identification is complete enough for processing."""

from r3el.entity.MediaFile import MediaFileState
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState


class BatchPreparation:
    @staticmethod
    def ready(batch: MediaFileBatch) -> bool:
        return (batch.state == MediaFileBatchState.IDENTIFICATION_COMPLETED
                and bool(batch.files)
                and all(item.state != MediaFileState.PENDING for item in batch.files))
