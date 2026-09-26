"""Movie and TV search and external response validation for TMDB."""

import os
import re

import httpx

from r3el.entity.TMDBReference import TMDBGenre, TMDBLanguage, TMDBReference


class TMDBError(RuntimeError):
    """A movie search could not produce a valid response."""


class TMDBNotFound(TMDBError):
    """TMDB has no record for the requested resource."""


class TMDB:
    URL = 'https://api.themoviedb.org/3/search/movie'

    def __init__(self, token: str) -> None:
        self._token = token

    @classmethod
    def from_environment(cls) -> 'TMDB':
        token = os.environ.get('TMDB_TOKEN', '').strip()
        if not token or any(character.isspace() for character in token):
            raise TMDBError('Configure TMDB_TOKEN with a TMDB API Read Access Token.')
        return cls(token)

    def search(self, title: str, year: int | None = None) -> dict:
        return self._search(self.URL, self.search_parameters(title, year))

    def search_tv(self, title: str, year: int | None = None) -> dict:
        parameters = {'query': title, 'page': 1}
        if year is not None:
            parameters['first_air_date_year'] = year
        return self._search('https://api.themoviedb.org/3/search/tv', parameters)

    def _search(self, url: str, parameters: dict) -> dict:
        payload = self._get(url, parameters)
        if (not isinstance(payload, dict)
                or type(payload.get('total_results')) is not int
                or payload['total_results'] < 0
                or not isinstance(payload.get('results'), list)
                or not all(isinstance(item, dict) and type(item.get('id')) is int
                           for item in payload['results'])
                or len(payload['results']) > payload['total_results']
                or (payload['total_results'] > 0 and not payload['results'])
                or (payload['total_results'] == 1 and len(payload['results']) != 1)):
            raise TMDBError('TMDB returned an invalid search response.')
        return payload

    @staticmethod
    def search_parameters(title: str, year: int | None = None) -> dict:
        parameters = {'query': title, 'page': 1}
        if year is not None:
            parameters['primary_release_year'] = year
        return parameters

    def details(self, movie_id: int) -> dict:
        """Return the full movie record and related descriptive data."""
        payload = self._get(f'https://api.themoviedb.org/3/movie/{movie_id}', {
            'append_to_response': 'alternative_titles,credits,external_ids,images,keywords,release_dates,translations,videos',
        })
        if (not isinstance(payload, dict) or type(payload.get('id')) is not int
                or payload['id'] != movie_id):
            raise TMDBError(f'TMDB returned invalid details for movie {movie_id}.')
        return payload

    def tv_details(self, series_id: int) -> dict:
        """Return series details with related data, without crawling seasons."""
        payload = self._get(f'https://api.themoviedb.org/3/tv/{series_id}', {
            'append_to_response': 'alternative_titles,credits,external_ids,images,keywords,content_ratings,translations,videos',
        })
        if (not isinstance(payload, dict) or type(payload.get('id')) is not int
                or payload['id'] != series_id):
            raise TMDBError(f'TMDB returned invalid details for TV series {series_id}.')
        return payload

    def tv_season(self, series_id: int, season: int) -> dict:
        payload = self._get(f'https://api.themoviedb.org/3/tv/{series_id}/season/{season}', {})
        return payload

    def tv_episode(self, series_id: int, season: int, episode: int) -> dict:
        return self._get(f'https://api.themoviedb.org/3/tv/{series_id}/season/{season}/episode/{episode}',
                         {'append_to_response': 'credits'})

    def reference(self) -> TMDBReference:
        genres = self._get('https://api.themoviedb.org/3/genre/movie/list', {'language': 'en'})
        languages = self._get('https://api.themoviedb.org/3/configuration/languages', {})
        if (not isinstance(genres, dict) or not isinstance(genres.get('genres'), list)
                or not genres['genres']
                or not all(isinstance(row, dict) and type(row.get('id')) is int and row['id'] > 0
                           and isinstance(row.get('name'), str) and 0 < len(row['name']) <= 100
                           for row in genres['genres'])):
            raise TMDBError('TMDB returned an invalid movie genre catalog.')
        if (not isinstance(languages, list) or not languages
                or not all(isinstance(row, dict) and isinstance(row.get('iso_639_1'), str)
                           and re.fullmatch('[a-z]{2}', row['iso_639_1'])
                           and isinstance(row.get('english_name'), str)
                           and 0 < len(row['english_name']) <= 100
                           and isinstance(row.get('name'), str) and len(row['name']) <= 100
                           for row in languages)):
            raise TMDBError('TMDB returned an invalid language catalog.')
        return TMDBReference(
            [TMDBGenre(row['id'], row['name']) for row in genres['genres']],
            [TMDBLanguage(row['iso_639_1'], row['english_name'], row['name']) for row in languages])

    def _get(self, url: str, parameters: dict) -> dict | list:
        try:
            response = httpx.get(
                url, params=parameters,
                headers={'Authorization': f'Bearer {self._token}', 'Accept': 'application/json'},
                timeout=15,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                raise TMDBNotFound('TMDB returned HTTP 404.') from error
            raise TMDBError(f'TMDB returned HTTP {error.response.status_code}.') from error
        except httpx.RequestError as error:
            raise TMDBError('Unable to reach TMDB. Try matching again.') from error
        try:
            return response.json()
        except ValueError as error:
            raise TMDBError('TMDB returned invalid JSON.') from error
