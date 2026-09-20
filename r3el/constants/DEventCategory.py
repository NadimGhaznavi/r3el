"""The shared category hierarchy for event writers and report filters."""

from r3el.entity.EventCategory import EventCategory


class DEventCategory:
    class Server:
        NAME = "Server"
        LIFECYCLE = EventCategory(NAME, "Lifecycle")

    class Batch:
        NAME = "Batch"
        LIFECYCLE = EventCategory(NAME, "Lifecycle")
        DISCOVERY = EventCategory(NAME, "Discovery")

    class Identification:
        NAME = "Identification"
        CONVERSATION = EventCategory(NAME, "Conversation")
        TOOL = EventCategory(NAME, "Tool")
        VALIDATION = EventCategory(NAME, "Validation")
        RESULT = EventCategory(NAME, "Result")

    ALL = (Server.LIFECYCLE, Batch.LIFECYCLE, Batch.DISCOVERY,
           Identification.CONVERSATION, Identification.TOOL,
           Identification.VALIDATION, Identification.RESULT)
    CHILDREN = {}
    for classification in ALL:
        CHILDREN.setdefault(classification.category, []).append(classification.subcategory)
    CHILDREN = {parent: tuple(children) for parent, children in CHILDREN.items()}
    del classification
