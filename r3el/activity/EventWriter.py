"""Prepare correlated event content for the database interface."""

from collections.abc import Callable
import json

from r3el.constants.DR3el import DR3el
from r3el.entity.EventCategory import EventCategory
from r3el.entity.LogEvent import LogEvent


class EventWriter:
    def __init__(self, record: Callable[[LogEvent], int], context: dict,
                 parent_event_id: int | None = None) -> None:
        self.record = record
        self.context = context
        self.parent_event_id = parent_event_id

    def write(self, category: EventCategory, name: str, data,
              *, source: str, level: str = 'INFO') -> int:
        return self.record(LogEvent(
            classification=category, name=name,
            message=json.dumps({'context': self.context, 'data': data}, ensure_ascii=False, allow_nan=False),
            level=level, process_id=self.context.get('item_id', self.context['batch_id']),
            parent_event_id=self.parent_event_id, source_name=source, app_version=DR3el.VERSION,
        ))
