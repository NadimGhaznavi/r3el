#!/usr/bin/env python3
"""Search TMDB movies or TV shows by title and optional four-digit year."""

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


def search_title(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError('title must not be blank')
    return value.strip()


def format_results(title: str, year: int | None, response: dict, width: int, media_type: str = 'movie') -> str:
    kind = 'TV' if media_type == 'tv' else 'movie'
    title_key, original_key, date_key, date_label = (
        ('name', 'original_name', 'first_air_date', 'First air date') if media_type == 'tv'
        else ('title', 'original_title', 'release_date', 'Release date'))
    heading = f'TMDB {kind} search: {title}' + (f' ({year:04d})' if year is not None else '')
    rows = [heading,
            f"Results: {response['total_results']}"]
    movies = response['results']
    if not movies:
        return '\n'.join(rows + ['', 'No matches found.'])
    if len(movies) < response['total_results']:
        rows.append(f"Showing {len(movies)} of {response['total_results']} results (first page).")
    for number, movie in enumerate(movies, 1):
        name = movie.get(title_key) or movie.get(original_key) or 'Untitled'
        rows.extend(['', f'{number}. {name}', '-' * min(width, 72)])
        if movie.get(original_key) and movie[original_key] != name:
            rows.append(f"   Original title: {movie[original_key]}")
        rows.extend([
            f"   {date_label}: {movie.get(date_key) or 'Unknown'}",
            f"   Language: {movie.get('original_language') or 'Unknown'}",
            f"   TMDB ID: {movie['id']}",
        ])
        if movie.get('vote_average') is not None:
            rows.append(f"   Rating: {movie['vote_average']}/10 ({movie.get('vote_count', 0)} votes)")
        rows.extend([f"   URL: https://www.themoviedb.org/{media_type}/{movie['id']}", '',
                     textwrap.fill(movie.get('overview') or 'No overview available.', width=width,
                                   initial_indent='   ', subsequent_indent='   ')])
    return '\n'.join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        epilog='Reads TMDB_TOKEN from the environment, /etc/r3el/tmdb.env, or ~/.tmdb. Searches the first page; the optional year filters movie release year or TV first-air year.')
    parser.add_argument('title', type=search_title, help='movie or TV title (quote titles containing spaces)')
    parser.add_argument('year', nargs='?', type=release_year, help='optional four-digit release year or TV first-air year')
    parser.add_argument('--type', choices=('movie', 'tv'), default='movie',
                        help='type to search (default: movie)')
    parser.add_argument('-r', '--raw', action='store_true',
                        help='fetch full movie or series details and related data for each hit and print JSON')
    args = parser.parse_args(argv)
    try:
        tmdb = TMDB(TMDBCredentials.token())
        search = tmdb.search_tv if args.type == 'tv' else tmdb.search
        response = search(args.title, args.year)
        if args.raw:
            details = tmdb.tv_details if args.type == 'tv' else tmdb.details
            response = dict(response, results=[
                dict(movie, **details(movie['id'])) for movie in response['results']])
    except TMDBError as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    if args.raw:
        print(json.dumps(response, indent=2, ensure_ascii=False))
    else:
        width = max(40, min(shutil.get_terminal_size(fallback=(100, 24)).columns, 120))
        print(format_results(args.title, args.year, response, width, args.type))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
