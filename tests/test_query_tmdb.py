"""Standalone TMDB query formatting and command-line validation."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch

from r3el.interface.TMDB import TMDBError

spec = importlib.util.spec_from_file_location('query_tmdb', Path(__file__).resolve().parents[1] / 'scripts/query-tmdb.py')
query = importlib.util.module_from_spec(spec)
spec.loader.exec_module(query)


class QueryTMDBTests(unittest.TestCase):
    @patch.object(query.TMDB, 'from_environment')
    def test_title_year_query_and_readable_results(self, factory):
        factory.return_value.search.return_value = {'total_results': 11, 'results': [
            {'id': 42, 'title': 'Superman', 'release_date': '2025-07-09',
             'original_language': 'en', 'overview': 'A hero in Metropolis.', 'vote_average': 7.2, 'vote_count': 50}]}
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(query.main(['Superman', '2025']), 0)
        factory.return_value.search.assert_called_once_with('Superman', 2025)
        for expected in ('1. Superman', 'Showing 1 of 11', '2025-07-09', '7.2/10',
                         'A hero in Metropolis.', 'https://www.themoviedb.org/movie/42'):
            self.assertIn(expected, output.getvalue())

    @patch.object(query.TMDB, 'from_environment')
    def test_no_matches_and_external_failure(self, factory):
        factory.return_value.search.return_value = {'total_results': 0, 'results': []}
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(query.main(['Movie', '2025']), 0)
        self.assertIn('No matches found.', output.getvalue())
        factory.side_effect = TMDBError('Configure TMDB_TOKEN.')
        with redirect_stderr(StringIO()) as errors:
            self.assertEqual(query.main(['Movie', '2025']), 1)
        self.assertIn('Configure TMDB_TOKEN.', errors.getvalue())

    @patch.object(query.TMDB, 'from_environment')
    def test_invalid_arguments_never_query(self, factory):
        for args in (['Movie'], ['Movie', '25'], ['Movie', '20250'], ['Movie', '0000'], [' ', '2025']):
            with self.subTest(args=args), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
                query.main(args)
            self.assertEqual(error.exception.code, 2)
        factory.assert_not_called()
