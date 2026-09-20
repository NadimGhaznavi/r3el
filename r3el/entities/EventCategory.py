"""A log category's stored name, event names, and presentation labels."""

from typing import ClassVar


class EventCategory:
    CATEGORY: ClassVar[str]
    LABELS: ClassVar[dict[str, str]]
