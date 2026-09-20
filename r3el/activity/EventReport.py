"""Resolve external report filters using the shared category hierarchy."""

from r3el.constants.DEventCategory import DEventCategory
from r3el.constants.DEventName import DEventName
from r3el.interface.EventLogDb import EventLogDb


class EventReport:
    def __init__(self, events: EventLogDb) -> None:
        self._events = events

    def recent(self, category: str | None = None,
               subcategory: str | None = None, name: str | None = None) -> list[dict]:
        if category is not None and category not in DEventCategory.CHILDREN:
            raise ValueError("Unknown event category")
        if subcategory is not None and (
            category is None or subcategory not in DEventCategory.CHILDREN[category]
        ):
            raise ValueError("Select a subcategory belonging to the selected category")
        if name is not None and name not in DEventName.ALL:
            raise ValueError("Unknown event name")
        return self._events.recent(category=category, subcategory=subcategory, name=name)
