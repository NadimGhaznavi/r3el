"""A source file associated with a directory processing item."""

from dataclasses import dataclass


@dataclass
class MediaAttachment:
    path: str
    kind: str = 'video'
    part: int | None = None
    media_path: str | None = None
