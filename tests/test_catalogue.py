"""Catalogue metadata validation and resolved-match checkpoint behavior."""

from contextlib import nullcontext
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
import unittest
from unittest.mock import Mock, patch

from r3el.app.BatchMatching import BatchMatching
from r3el.entity.Identification import Identification
from r3el.entity.MediaFile import MediaFile, MediaFileState
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.entity.MovieFiles import MovieFiles
from r3el.interface.TMDB import TMDBError
from r3el.interface.TMDBCatalogue import TMDBCatalogue
from r3el.constants.DEventCategory import DEventCategory


def movie_payload():
    return dict(id=42, title='Movie', original_title='Original', release_date='2020-02-03',
                overview='Synopsis', runtime=123, poster_path='/poster.jpg', backdrop_path='/backdrop.jpg',
                imdb_id='tt123', vote_average=7.123, vote_count=25, original_language='en',
                genres=[{'id': 18, 'name': 'Drama'}], credits={
                    'cast': [{'id': 1, 'name': 'Person', 'character': 'Hero', 'order': 0},
                             {'id': 1, 'name': 'Person', 'character': 'Twin', 'order': 1}],
                    'crew': [{'id': 1, 'name': 'Person', 'job': role} for role in
                             ('Director', 'Producer', 'Executive Producer', 'Co-Producer', 'Editor')]})


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.details.return_value = movie_payload()

    def test_fields_and_all_roles_preserve_multiple_characters(self):
        movie = TMDBCatalogue(self.client).movie(42)
        self.assertEqual(movie.release_date, date(2020, 2, 3))
        self.assertEqual(movie.rating, Decimal('7.123'))
        self.assertEqual(movie.runtime, 123)
        self.assertEqual(movie.imdb_id, 'tt123')
        self.assertEqual([credit.role for credit in movie.credits],
                         ['Actor', 'Actor', 'Director', 'Producer', 'Executive Producer', 'Co-Producer'])
        self.assertEqual([credit.character for credit in movie.credits[:2]], ['Hero', 'Twin'])
        self.assertFalse(hasattr(movie, 'language'))

    def test_missing_optional_values_are_null_and_duplicate_credits_collapsed(self):
        self.client.details.return_value = {'id': 42, 'title': 'Movie', 'release_date': '',
                                           'genres': [], 'credits': {'cast': [], 'crew': []}}
        movie = TMDBCatalogue(self.client).movie(42)
        self.assertIsNone(movie.release_date)
        self.assertIsNone(movie.rating)
        self.assertEqual(movie.credits, [])
        payload = movie_payload()
        payload['credits']['crew'].append(payload['credits']['crew'][0])
        self.client.details.return_value = payload
        self.assertEqual(len(TMDBCatalogue(self.client).movie(42).credits), 6)

    def test_malformed_metadata_is_an_external_error(self):
        for field, value in (('title', None), ('runtime', True), ('runtime', -1),
                             ('release_date', '2020-02-31'), ('vote_average', float('nan')),
                             ('genres', None), ('credits', {}), ('vote_count', '25')):
            with self.subTest(field=field):
                payload = movie_payload()
                payload[field] = value
                self.client.details.return_value = payload
                with self.assertRaisesRegex(TMDBError, 'invalid catalogue metadata'):
                    TMDBCatalogue(self.client).movie(42)


class CatalogueMatchingTests(unittest.TestCase):
    def setUp(self):
        self.item = MediaFile('file', '/movies/movie.mkv', MediaFileState.IDENTIFIED,
                              Identification('Movie', 2020, 10))
        self.batch = MediaFileBatch('batch', 1, '/movies', files=[self.item],
                                    state=MediaFileBatchState.IDENTIFICATION_COMPLETED)
        self.workspace = Mock()
        self.workspace.load.return_value = self.batch
        self.workspace.processing.side_effect = nullcontext
        self.workspace.matching.side_effect = nullcontext
        self.workspace.save_match.side_effect = lambda batch, file, result, event: setattr(self.item, 'tmdb_match', result)
        self.workspace.save_catalogue.side_effect = lambda batch, file, movie, result, event, files: setattr(self.item, 'tmdb_match', result)
        patcher = patch('r3el.app.BatchMatching.TMDB.from_environment')
        self.client = patcher.start().return_value
        self.addCleanup(patcher.stop)
        self.client.search.return_value = {'total_results': 1, 'results': [{'id': 42}]}
        self.client.details.return_value = movie_payload()
        files = patch('r3el.app.BatchMatching.CatalogueFiles')
        self.files = files.start().return_value
        self.addCleanup(files.stop)
        self.files.prepare.return_value = MovieFiles('/output/Movie (2020)/Movie (2020).mkv')
        self.runner = BatchMatching(self.workspace, Mock(return_value=1))

    def test_single_match_catalogued_once(self):
        self.runner.run('batch')
        self.runner.run('batch')
        self.client.details.assert_called_once_with(42)
        self.workspace.save_catalogue.assert_called_once()
        self.assertTrue(self.item.tmdb_match.catalogue_saved)
        saved = self.workspace.save_catalogue.call_args.args[4]
        self.assertEqual(saved.classification, DEventCategory.DB.CREATE_RECORD)
        self.assertEqual(json.loads(saved.message)['data']['movie_id'], 42)
        moved = self.workspace.save_match.call_args.args[3]
        self.assertEqual(moved.classification, DEventCategory.File.MOVE)
        self.assertEqual(json.loads(moved.message)['data']['source_path'], '/movies/movie.mkv')

    def test_metadata_failure_retries_without_search_or_reidentification(self):
        self.client.details.side_effect = TMDBError('TMDB returned HTTP 429.')
        self.runner.run('batch')
        self.assertEqual(self.item.tmdb_match.label, 'Catalogue failed')
        self.workspace.save_catalogue.assert_not_called()
        self.client.details.side_effect = None
        self.runner.run('batch')
        self.client.search.assert_called_once()
        self.assertTrue(self.item.tmdb_match.catalogue_saved)
        self.assertIsNone(self.item.tmdb_match.catalogue_error)

    def test_only_selected_movie_is_catalogued(self):
        self.client.search.return_value = {'total_results': 2, 'results': [{'id': 1}, {'id': 42}]}
        chosen = TMDBMatch('Movie', 2020, response=deepcopy(self.client.search.return_value), selected_number=2)
        with patch('r3el.app.BatchMatching.MovieSelection.run', return_value=chosen), \
                patch('r3el.app.BatchMatching.LLM.from_environment'):
            self.runner.run('batch')
        self.client.details.assert_called_once_with(42)

    def test_no_selection_is_not_catalogued(self):
        self.item.tmdb_match = TMDBMatch('Movie', 2020,
            response={'total_results': 2, 'results': [{'id': 1}, {'id': 42}]}, selected_number=0)
        self.runner.run('batch')
        self.client.details.assert_not_called()
        self.workspace.save_catalogue.assert_not_called()

    def test_database_failure_keeps_source_and_does_not_finish_move(self):
        self.workspace.save_catalogue.side_effect = RuntimeError('Database failure')
        with self.assertRaisesRegex(RuntimeError, 'Database failure'):
            self.runner.run('batch')
        self.files.finish.assert_not_called()

    def test_committed_move_can_resume_without_redownloading_metadata(self):
        self.files.finish.side_effect = OSError('Source removal failed')
        self.runner.run('batch')
        self.assertTrue(self.item.tmdb_match.catalogue_saved)
        self.assertFalse(self.item.tmdb_match.file_moved)
        event = self.workspace.save_match.call_args.args[3]
        self.assertEqual(event.classification, DEventCategory.File.MOVE)
        self.assertEqual(event.level, 'ERROR')
        self.files.finish.side_effect = None
        self.runner.run('batch')
        self.client.details.assert_called_once()
        self.assertTrue(self.item.tmdb_match.file_moved)
        self.assertIsNone(self.item.tmdb_match.catalogue_error)
