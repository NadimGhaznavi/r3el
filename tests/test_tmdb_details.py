"""Full movie detail retrieval preserves TMDB's nested data."""

import unittest
from unittest.mock import patch

from r3el.interface.TMDB import TMDB, TMDBError


class TMDBDetailsTests(unittest.TestCase):
    @patch('r3el.interface.TMDB.httpx.get')
    def test_details_endpoint_and_nested_response(self, get):
        payload = {'id': 42, 'budget': 1000, 'genres': [{'id': 18, 'name': 'Drama'}],
                   'credits': {'cast': [{'id': 7, 'name': 'Actor'}]}}
        get.return_value.json.return_value = payload
        self.assertEqual(TMDB('token').details(42), payload)
        self.assertEqual(get.call_args.args, ('https://api.themoviedb.org/3/movie/42',))
        self.assertIn('credits', get.call_args.kwargs['params']['append_to_response'].split(','))
        self.assertEqual(get.call_args.kwargs['headers']['Authorization'], 'Bearer token')

    @patch.object(TMDB, '_get')
    def test_invalid_or_wrong_movie_rejected(self, get):
        for payload in ([], {}, {'id': '42'}, {'id': 43}):
            with self.subTest(payload=payload), self.assertRaises(TMDBError):
                get.return_value = payload
                TMDB('token').details(42)
