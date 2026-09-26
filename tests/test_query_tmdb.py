"""Standalone TMDB query formatting and command-line validation."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import json
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch

from r3el.interface.TMDB import TMDBError

spec = importlib.util.spec_from_file_location('query_tmdb', Path(__file__).resolve().parents[1] / 'scripts/query-tmdb.py')
query = importlib.util.module_from_spec(spec)
spec.loader.exec_module(query)


class QueryTMDBTests(unittest.TestCase):
    @patch.object(query.TMDBCredentials, 'token', return_value='test-token')
    @patch.object(query, 'TMDB')
    def test_tv_search_format_and_raw_details(self, factory, token):
        client = factory.return_value
        client.search_tv.return_value = {'total_results': 1, 'results': [
            {'id': 1396, 'name': 'Breaking Bad', 'original_name': 'Original',
             'first_air_date': '2008-01-20'}]}
        client.tv_details.return_value = {'id': 1396, 'number_of_seasons': 5}
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(query.main(['--type', 'tv', 'Breaking Bad']), 0)
        client.search_tv.assert_called_with('Breaking Bad', None)
        for text in ('TMDB TV search: Breaking Bad', '1. Breaking Bad',
                     'First air date: 2008-01-20', 'Original title: Original',
                     'https://www.themoviedb.org/tv/1396'):
            self.assertIn(text, output.getvalue())
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(query.main(['--type', 'tv', 'Breaking Bad', '2008', '--raw']), 0)
        client.search_tv.assert_called_with('Breaking Bad', 2008)
        client.tv_details.assert_called_once_with(1396)
        self.assertEqual(json.loads(output.getvalue())['results'][0]['number_of_seasons'], 5)
        client.search.assert_not_called()
        client.details.assert_not_called()

    @patch.object(query.TMDBCredentials, 'token', return_value='test-token')
    @patch.object(query, 'TMDB')
    def test_year_is_optional_for_readable_and_raw_output(self, factory, token):
        factory.return_value.search.return_value = {
            'total_results': 1, 'results': [{'id': 42, 'title': 'Movie'}]}
        factory.return_value.details.return_value = {'id': 42, 'title': 'Movie'}
        for args in (['Movie'], ['--raw', 'Movie']):
            with self.subTest(args=args), redirect_stdout(StringIO()) as output:
                self.assertEqual(query.main(args), 0)
            factory.return_value.search.assert_called_with('Movie', None)
            if '--raw' in args:
                self.assertEqual(json.loads(output.getvalue())['results'][0]['id'], 42)
            else:
                self.assertEqual(output.getvalue().splitlines()[0], 'TMDB movie search: Movie')

    @patch.object(query.TMDBCredentials, 'token', return_value='test-token')
    @patch.object(query, 'TMDB')
    def test_raw_response_preserves_all_fields(self, factory, token):
        response = {'page': 1, 'total_pages': 1, 'total_results': 1, 'results': [
            {'id': 42, 'title': 'Amélie', 'genre_ids': [35, 10749],
             'extra': {'child': [None, False, {'value': 'nested'}]}}]}
        factory.return_value.search.return_value = response
        details = {'id': 42, 'runtime': 122, 'genres': [{'id': 35, 'name': 'Comedy'}],
                   'credits': {'cast': [{'id': 1, 'name': 'Actor'}]}}
        factory.return_value.details.return_value = details
        for args in (['-r', 'Amélie', '2001'], ['Amélie', '2001', '--raw']):
            with self.subTest(args=args), redirect_stdout(StringIO()) as output:
                self.assertEqual(query.main(args), 0)
            self.assertEqual(json.loads(output.getvalue()), dict(response, results=[
                dict(response['results'][0], **details)]))
            self.assertIn('\n  "page": 1', output.getvalue())
            self.assertIn('Amélie', output.getvalue())
        self.assertEqual(factory.return_value.details.call_args_list,
                         [unittest.mock.call(42), unittest.mock.call(42)])

    @patch.object(query.TMDBCredentials, 'token', return_value='test-token')
    @patch.object(query, 'TMDB')
    def test_raw_details_failure_does_not_print_partial_json(self, factory, token):
        factory.return_value.search.return_value = {'total_results': 1, 'results': [{'id': 42}]}
        factory.return_value.details.side_effect = TMDBError('TMDB returned HTTP 404.')
        with redirect_stdout(StringIO()) as output, redirect_stderr(StringIO()) as errors:
            self.assertEqual(query.main(['-r', 'Movie', '2005']), 1)
        self.assertEqual(output.getvalue(), '')
        self.assertIn('HTTP 404', errors.getvalue())

    @patch.object(query.TMDBCredentials, 'token', return_value='test-token')
    @patch.object(query, 'TMDB')
    def test_title_year_query_and_readable_results(self, factory, token):
        factory.return_value.search.return_value = {'total_results': 11, 'results': [
            {'id': 42, 'title': 'Superman', 'release_date': '2025-07-09',
             'original_language': 'en', 'overview': 'A hero in Metropolis.', 'vote_average': 7.2, 'vote_count': 50}]}
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(query.main(['Superman', '2025']), 0)
        factory.return_value.search.assert_called_once_with('Superman', 2025)
        factory.return_value.details.assert_not_called()
        for expected in ('1. Superman', 'Showing 1 of 11', '2025-07-09', '7.2/10',
                         'A hero in Metropolis.', 'https://www.themoviedb.org/movie/42'):
            self.assertIn(expected, output.getvalue())

    @patch.object(query.TMDBCredentials, 'token', return_value='test-token')
    @patch.object(query, 'TMDB')
    def test_no_matches_and_external_failure(self, factory, token):
        factory.return_value.search.return_value = {'total_results': 0, 'results': []}
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(query.main(['Movie', '2025']), 0)
        self.assertIn('No matches found.', output.getvalue())
        factory.side_effect = TMDBError('Configure TMDB_TOKEN.')
        with redirect_stderr(StringIO()) as errors:
            self.assertEqual(query.main(['Movie', '2025']), 1)
        self.assertIn('Configure TMDB_TOKEN.', errors.getvalue())

    @patch.object(query.TMDBCredentials, 'token', return_value='test-token')
    @patch.object(query, 'TMDB')
    def test_invalid_arguments_never_query(self, factory, token):
        for args in (['--type', 'invalid', 'Movie'], [], ['Movie', '25'], ['Movie', '20250'], ['Movie', '0000'], [' ', '2025']):
            with self.subTest(args=args), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
                query.main(args)
            self.assertEqual(error.exception.code, 2)
        factory.assert_not_called()
