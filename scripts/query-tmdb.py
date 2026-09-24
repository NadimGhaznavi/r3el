#!/usr/bin/env python3
"""Search TMDB movies by title and four-digit release year."""

import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import textwrap

# Support invocation from any working directory, including the installed checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3el.interface.TMDB import TMDB, TMDBError
from r3el.interface.TMDBCredentials import TMDBCredentials


def release_year(value: str) -> int:
    if not re.fullmatch(r'[0-9]{4}', value) or int(value) == 0:
        raise argparse.ArgumentTypeError('year must be four digits, for example 2025')
    return int(value)


def movie_title(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError('title must not be blank')
    return value.strip()


def format_results(title: str, year: int, response: dict, width: int) -> str:
    rows = [f'TMDB movie search: {title} ({year:04d})',
            f"Results: {response['total_results']}"]
    movies = response['results']
    if not movies:
        return '\n'.join(rows + ['', 'No matches found.'])
    if len(movies) < response['total_results']:
        rows.append(f"Showing {len(movies)} of {response['total_results']} results (first page).")
    for number, movie in enumerate(movies, 1):
        name = movie.get('title') or movie.get('original_title') or 'Untitled movie'
        rows.extend(['', f'{number}. {name}', '-' * min(width, 72)])
        if movie.get('original_title') and movie['original_title'] != name:
            rows.append(f"   Original title: {movie['original_title']}")
        rows.extend([
            f"   Release date: {movie.get('release_date') or 'Unknown'}",
            f"   Language: {movie.get('original_language') or 'Unknown'}",
            f"   TMDB ID: {movie['id']}",
        ])
        if movie.get('vote_average') is not None:
            rows.append(f"   Rating: {movie['vote_average']}/10 ({movie.get('vote_count', 0)} votes)")
        rows.extend([f"   URL: https://www.themoviedb.org/movie/{movie['id']}", '',
                     textwrap.fill(movie.get('overview') or 'No overview available.', width=width,
                                   initial_indent='   ', subsequent_indent='   ')])
    return '\n'.join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        epilog='Reads TMDB_TOKEN from the environment, /etc/r3el/tmdb.env, or ~/.tmdb. Searches the first page with primary_release_year.')
    parser.add_argument('title', type=movie_title, help='movie title (quote titles containing spaces)')
    parser.add_argument('year', type=release_year, help='four-digit release year')
    parser.add_argument('-r', '--raw', action='store_true',
                        help='print the complete search response as formatted JSON')
    args = parser.parse_args(argv)
    try:
        response = TMDB(TMDBCredentials.token()).search(args.title, args.year)
    except TMDBError as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    if args.raw:
        print(json.dumps(response, indent=2, ensure_ascii=False))
    else:
        width = max(40, min(shutil.get_terminal_size(fallback=(100, 24)).columns, 120))
        print(format_results(args.title, args.year, response, width))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
