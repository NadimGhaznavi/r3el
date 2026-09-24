"""CLI credential precedence and safe file parsing."""

import unittest
from unittest.mock import patch

from r3el.interface.TMDB import TMDBError
from r3el.interface.TMDBCredentials import TMDBCredentials


@patch.dict('os.environ', {}, clear=True)
class TMDBCredentialsTests(unittest.TestCase):
    @patch.dict('os.environ', {'TMDB_TOKEN': 'environment-token'})
    @patch('pathlib.Path.read_text')
    def test_environment_takes_precedence(self, read):
        self.assertEqual(TMDBCredentials.token(), 'environment-token')
        read.assert_not_called()

    @patch('pathlib.Path.read_text', return_value='TMDB_TOKEN=installed-token\nTMDB_KEY=key\n')
    def test_installed_credentials(self, read):
        self.assertEqual(TMDBCredentials.token(), 'installed-token')
        self.assertEqual(read.call_count, 1)

    @patch('pathlib.Path.read_text', side_effect=[PermissionError, 'export TMDB_TOKEN="home-token" # comment\n'])
    def test_home_fallback(self, read):
        self.assertEqual(TMDBCredentials.token(), 'home-token')

    @patch('pathlib.Path.read_text', side_effect=FileNotFoundError)
    def test_missing_credentials(self, read):
        with self.assertRaisesRegex(TMDBError, 'Set TMDB_TOKEN'):
            TMDBCredentials.token()

    @patch('pathlib.Path.read_text', return_value='TMDB_TOKEN="unterminated-secret')
    def test_invalid_file_does_not_expose_secret(self, read):
        with self.assertRaises(TMDBError) as error:
            TMDBCredentials.token()
        self.assertNotIn('unterminated-secret', str(error.exception))

    @patch('pathlib.Path.read_text', return_value="TMDB_TOKEN='$(example)'\n")
    def test_shell_expression_is_literal_data(self, read):
        self.assertEqual(TMDBCredentials.token(), '$(example)')
