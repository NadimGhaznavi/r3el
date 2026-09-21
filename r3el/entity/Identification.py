"""A model-supplied identification, awaiting TMDB matching in a later phase."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Identification:
    title: str
    year: int
    confidence: int
