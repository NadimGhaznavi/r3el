"""Movie metadata and credits stored in the local catalogue."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from r3el.entity.TMDBReference import TMDBGenre


@dataclass(frozen=True)
class MovieCredit:
    person_id: int
    name: str
    role: str
    character: str | None = None
    billing_order: int | None = None


@dataclass(frozen=True)
class CatalogueMovie:
    tmdb_id: int
    title: str
    original_title: str | None
    release_date: date | None
    overview: str | None
    runtime: int | None
    poster_path: str | None
    backdrop_path: str | None
    imdb_id: str | None
    rating: Decimal | None
    vote_count: int | None
    genres: list[TMDBGenre]
    credits: list[MovieCredit]
