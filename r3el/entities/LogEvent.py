"""Data recorded for one application event."""

from dataclasses import dataclass

from r3el.entities.EventCategory import EventCategory


@dataclass(frozen=True)
class LogEvent:
    classification: EventCategory
    name: str
    message: str
    level: str = "INFO"
    process_id: str | None = None
    parent_event_id: int | None = None
    source_name: str | None = None
    app_version: str | None = None
