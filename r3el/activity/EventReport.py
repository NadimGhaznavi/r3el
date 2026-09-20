"""Resolve external report filters using the shared category hierarchy."""

from r3el.constants.DEventCategory import DEventCategory
from r3el.constants.DEventName import DEventName
from r3el.interface.EventLogDb import EventLogDb


class EventReport:
    def __init__(self, events: EventLogDb) -> None:
        self._events = events

    def recent(self, category: str | None = None,
               subcategory: str | None = None, name: str | None = None) -> list[dict]:
        category, subcategory, name = self.resolve_filters(category, subcategory, name)
        return self._events.recent(category=category, subcategory=subcategory, name=name)

    @staticmethod
    def resolve_filters(category: str | None = None, subcategory: str | None = None,
                        name: str | None = None) -> tuple[str | None, str | None, str | None]:
        if category is not None and category not in DEventCategory.CHILDREN:
            raise ValueError("Unknown event category")
        if name is not None:
            if name not in DEventName.PARENTS:
                raise ValueError("Unknown event name")
            parent = DEventName.PARENTS[name]
            if category is not None and category != parent.category:
                raise ValueError("Select an event belonging to the selected category")
            if subcategory is not None and subcategory != parent.subcategory:
                raise ValueError("Select an event belonging to the selected subcategory")
            category, subcategory = parent.category, parent.subcategory
        if subcategory is not None and not any(
            parent.subcategory == subcategory and (category is None or parent.category == category)
            for parent in DEventCategory.ALL
        ):
            raise ValueError("Select a subcategory belonging to the selected category")
        return category, subcategory, name
