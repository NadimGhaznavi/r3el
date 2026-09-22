"""A saved preparation decision, separate from identification progress."""

from enum import StrEnum


class MediaFileAction(StrEnum):
    PENDING = 'pending'
    APPROVE = 'approve'
    IGNORE = 'ignore'
    DELETE = 'delete'
