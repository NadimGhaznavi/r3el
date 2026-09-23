"""Shared TMDB movie genres and language names, independent of any batch."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TMDBGenre:
    id: int
    name: str


@dataclass(frozen=True)
class TMDBLanguage:
    code: str
    english_name: str
    native_name: str


@dataclass(frozen=True)
class TMDBReference:
    genres: list[TMDBGenre]
    languages: list[TMDBLanguage]
