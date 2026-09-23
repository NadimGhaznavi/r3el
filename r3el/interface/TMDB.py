"""Movie search and external response validation for TMDB."""

import os

import httpx


class TMDBError(RuntimeError):
    """A movie search could not produce a valid response."""


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

    def search(self, title: str, year: int) -> dict:
        try:
            response = httpx.get(
                self.URL, params={'query': title, 'year': year, 'page': 1},
                headers={'Authorization': f'Bearer {self._token}', 'Accept': 'application/json'},
                timeout=15,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise TMDBError(f'TMDB returned HTTP {error.response.status_code}.') from error
        except httpx.RequestError as error:
            raise TMDBError('Unable to reach TMDB. Try matching again.') from error
        try:
            payload = response.json()
        except ValueError as error:
            raise TMDBError('TMDB returned invalid JSON.') from error
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
