"""Prepare saved TMDB search data for the movie result cards."""

from datetime import date
import re

from r3el.entity.TMDBMatch import TMDBMatch
from r3el.entity.TMDBReference import TMDBReference


class MatchResults:
    def __init__(self, reference: TMDBReference) -> None:
        self._genres = {genre.id: genre.name for genre in reference.genres}
        self._languages = {language.code: language.english_name for language in reference.languages}

    def prepare(self, match: TMDBMatch) -> dict:
        if match.error is not None:
            return dict(status='Match failed', tone='failed', explanation=match.error, movies=[], total=0)
        noun = 'series' if match.media_type == 'tv' else 'movie'
        plural = 'series' if match.media_type == 'tv' else 'movies'
        query = 'title' if match.media_type == 'tv' else 'title and year'
        response = match.resolved_response
        total = response['total_results']
        selected = bool(match.selected_number)
        movies = [dict(self._movie(movie, match.media_type), selected=selected) for movie in response['results']]
        return dict(
            status='Resolved' if selected or total == 1 else 'No matches' if total == 0 else 'Ambiguous',
            tone='resolved' if selected or total == 1 else 'unresolved',
            explanation=(f'The LLM selected candidate {match.selected_number}.' if selected else
                         match.selection_error if match.selection_error else
                         'The LLM could not confidently select a title.' if match.selected_number == 0 else
                         f'Exactly one {noun} matches the queried {query}.' if total == 1 else
                         f'No {plural} match the queried {query}.' if total == 0 else
                         f'{total:,} {plural} found. No {noun} has been selected.'),
            movies=movies, total=total,
        )

    def _movie(self, movie: dict, media_type: str = 'movie') -> dict:
        # Search results may omit optional metadata; interpret it at this presentation boundary.
        try:
            released = date.fromisoformat(movie.get('first_air_date' if media_type == 'tv' else 'release_date') or '')
        except ValueError:
            released = None
        poster = movie.get('poster_path')
        poster_url = ('https://image.tmdb.org/t/p/w500' + poster
                      if poster and re.fullmatch(r'/[A-Za-z0-9_-]+\.(?:jpg|png|webp)', poster) else None)
        language = movie.get('original_language')
        score, votes = movie.get('vote_average'), movie.get('vote_count')
        return dict(
            title=movie.get('name' if media_type == 'tv' else 'title') or movie.get('original_name' if media_type == 'tv' else 'original_title') or 'Untitled movie',
            original_title=movie.get('original_name' if media_type == 'tv' else 'original_title') or 'Not available',
            year=released.year if released else 'Year unknown',
            release_date=f'{released:%B} {released.day}, {released.year}' if released else 'Not available',
            language=self._languages.get(language, language or 'Unknown'),
            genres=[self._genres.get(genre, f'Genre {genre}') for genre in movie.get('genre_ids', [])],
            overview=movie.get('overview') or 'No overview available.',
            rating=f'{score:.2f}' if score is not None and votes else 'Not rated',
            votes=f'{votes:,}' if votes is not None else None,
            id=movie['id'], media_type=media_type, url=f'https://www.themoviedb.org/{media_type}/{movie["id"]}', poster_url=poster_url,
        )
