"""Compatibility mapping derived from the category catalog."""

from ax3l.constants.DEventCategory import DEventCategory


class DEventDisplay:
    LABELS = {
        name: label
        for category in DEventCategory.ALL
        for name, label in category.LABELS.items()
    }
