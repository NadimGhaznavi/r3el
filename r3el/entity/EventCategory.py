"""An event subcategory and its parent category."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EventCategory:
    category: str
    subcategory: str
