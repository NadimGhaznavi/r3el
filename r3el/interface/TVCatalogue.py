"""Validate TMDB TV metadata and episode mappings before filesystem work."""

from dataclasses import fields
from datetime import date

from r3el.entity.CatalogueSeries import CatalogueSeries
from r3el.interface.TMDB import TMDBError
from r3el.interface.TMDBCatalogue import TMDBCatalogue


class TVCatalogue:
    @staticmethod
    def series(data: dict) -> CatalogueSeries:
        movie = TMDBCatalogue.from_details(dict(data, title=data.get('name'),
            original_title=data.get('original_name'), release_date=data.get('first_air_date'),
            imdb_id=data.get('external_ids', {}).get('imdb_id')), data['id'])
        return CatalogueSeries(**{field.name: getattr(movie, field.name) for field in fields(movie)})

    @staticmethod
    def season(data: dict, number: int) -> dict:
        if (not isinstance(data, dict) or type(data.get('id')) is not int or data['id'] <= 0 or data.get('season_number') != number
                or not isinstance(data.get('name'), str) or not isinstance(data.get('episodes'), list)):
            raise TMDBError(f'Invalid TMDB season {number}.')
        return data

    @staticmethod
    def episode(data: dict, season: int, episode: int) -> dict:
        if (not isinstance(data, dict) or type(data.get('id')) is not int or data['id'] <= 0
                or type(data.get('season_number')) is not int or type(data.get('episode_number')) is not int
                or data.get('season_number') != season or data.get('episode_number') != episode
                or not isinstance(data.get('name'), str) or not data['name'].strip()):
            raise TMDBError(f'TMDB does not confirm S{season:02}E{episode:02}.')
        try:
            if data.get('air_date'):
                date.fromisoformat(data['air_date'])
            runtime = data.get('runtime')
            if runtime is not None and (type(runtime) is not int or runtime < 0):
                raise ValueError()
            # Reuse the existing external credit validation.
            TVCatalogue.episode_credits(data)
        except (TypeError, KeyError, ValueError, TMDBError):
            raise TMDBError(f'Invalid TMDB metadata for S{season:02}E{episode:02}.') from None
        return data

    @staticmethod
    def episode_credits(data: dict):
        return TMDBCatalogue.from_details(dict(data, title=data['name'], genres=[],
            release_date=data.get('air_date'), credits=data['credits']), data['id']).credits
