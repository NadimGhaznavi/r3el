"""Record the lifecycle of one server instance."""

from uuid import uuid4

from r3el.constants.DEventCategory import DEventCategory
from r3el.constants.DEventName import DEventName
from r3el.constants.DR3el import DR3el
from r3el.entities.LogEvent import LogEvent
from r3el.interface.EventLogDb import EventLogDb


class ServerLifecycle:
    def __init__(self, events: EventLogDb) -> None:
        self._events = events
        self._process_id = str(uuid4())
        self._started_id = None

    def started(self) -> None:
        self._started_id = self._record(DEventName.SERVER_STARTED, "R3el server started (idle).")

    def stopped(self) -> None:
        self._record(DEventName.SERVER_STOPPED, "R3el server stopped.")

    def _record(self, name: str, message: str) -> int:
        return self._events.record(LogEvent(
            classification=DEventCategory.Server.LIFECYCLE,
            name=name, message=message, process_id=self._process_id,
            parent_event_id=self._started_id, source_name="R3elServer",
            app_version=DR3el.VERSION,
        ))
