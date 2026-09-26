"""Validated series metadata shared with the title/artwork file interface."""

from dataclasses import dataclass
from r3el.entity.CatalogueMovie import CatalogueMovie


@dataclass(frozen=True)
class CatalogueSeries(CatalogueMovie):
    """release_date is the series first-air date, never the episode air date."""
