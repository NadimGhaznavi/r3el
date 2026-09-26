"""Local video and artwork paths prepared for a catalogue transaction."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MovieFiles:
    video: str
    poster: str | None = None
    backdrop: str | None = None
    associated: list[dict] = field(default_factory=list)
