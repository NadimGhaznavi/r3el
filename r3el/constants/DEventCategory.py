"""The shared category hierarchy for event writers and report filters."""

from r3el.entities.EventCategory import EventCategory


class DEventCategory:
    class Server:
        NAME = "Server"
        LIFECYCLE = EventCategory(NAME, "Lifecycle")

    ALL = (Server.LIFECYCLE,)
    CHILDREN = {}
    for classification in ALL:
        CHILDREN.setdefault(classification.category, []).append(classification.subcategory)
    CHILDREN = {parent: tuple(children) for parent, children in CHILDREN.items()}
    del classification
