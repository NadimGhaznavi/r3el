"""Determine whether the saved batch decisions are ready for TMDB matching."""

from r3el.entity.MediaFile import MediaFileState
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState


class BatchPreparation:
    @staticmethod
    def ready(batch: MediaFileBatch) -> bool:
        return (batch.state == MediaFileBatchState.IDENTIFICATION_COMPLETED
                and bool(batch.files)
                and all(item.state != MediaFileState.PENDING
                        and item.action != MediaFileAction.PENDING for item in batch.files))
