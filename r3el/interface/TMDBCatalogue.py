"""Validate and convert external TMDB movie details for the catalogue."""

from datetime import date
from decimal import Decimal
import math

from r3el.entity.CatalogueMovie import CatalogueMovie, MovieCredit
from r3el.entity.TMDBReference import TMDBGenre
from r3el.interface.TMDB import TMDB, TMDBError


class TMDBCatalogue:
    def __init__(self, client: TMDB) -> None:
        self._client = client

    def movie(self, movie_id: int) -> CatalogueMovie:
        data = self._client.details(movie_id)
        return self.from_details(data, movie_id)

    @classmethod
    def from_details(cls, data: dict, movie_id: int) -> CatalogueMovie:
        try:
            return cls._convert(data)
        except (KeyError, TypeError, ValueError, OverflowError):
            raise TMDBError(f'TMDB returned invalid catalogue metadata for movie {movie_id}.') from None

    @staticmethod
    def _text(value, *, required: bool = False) -> str | None:
        if value is None or value == '':
            if required:
                raise ValueError('Missing text')
            return None
        if not isinstance(value, str):
            raise ValueError('Invalid text')
        return value

    @staticmethod
    def _integer(value, *, minimum: int = 0) -> int | None:
        if value is None and minimum == 0:
            return None
        if type(value) is not int or not minimum <= value <= 4294967295:
            raise ValueError('Invalid integer')
        return value

    @classmethod
    def _convert(cls, data: dict) -> CatalogueMovie:
        released = cls._text(data.get('release_date'))
        released = date.fromisoformat(released) if released else None
        if released is not None and released.year < 1000:
            raise ValueError('Release date outside database range')
        rating = data.get('vote_average')
        if rating is not None:
            if type(rating) not in (int, float) or not math.isfinite(rating) or not 0 <= rating <= 10:
                raise ValueError('Invalid rating')
            rating = Decimal(str(rating))
        genres = []
        for row in data['genres']:
            name = cls._text(row['name'], required=True)
            if len(name) > 100:
                raise ValueError('Invalid genre name')
            genres.append(TMDBGenre(cls._integer(row['id'], minimum=1), name))
        if len({genre.id for genre in genres}) != len(genres):
            raise ValueError('Duplicate genre')
        credits = []
        for row in data['credits']['cast']:
            credits.append(MovieCredit(
                cls._integer(row['id'], minimum=1), cls._text(row['name'], required=True), 'Actor',
                cls._text(row.get('character')), cls._integer(row.get('order'))))
        for row in data['credits']['crew']:
            if row['job'] in ('Director', 'Producer', 'Executive Producer', 'Co-Producer'):
                credits.append(MovieCredit(
                    cls._integer(row['id'], minimum=1), cls._text(row['name'], required=True), row['job']))
        imdb_id = cls._text(data.get('imdb_id'))
        if imdb_id is not None and len(imdb_id) > 32:
            raise ValueError('Invalid IMDb ID')
        return CatalogueMovie(
            cls._integer(data['id'], minimum=1), cls._text(data['title'], required=True),
            cls._text(data.get('original_title')), released, cls._text(data.get('overview')),
            cls._integer(data.get('runtime')), cls._text(data.get('poster_path')),
            cls._text(data.get('backdrop_path')), imdb_id, rating,
            cls._integer(data.get('vote_count')), genres, list(dict.fromkeys(credits)))
