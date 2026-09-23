"""Movie matching contracts, saved results, and credential installation."""

from contextlib import nullcontext
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import httpx

from r3el.app.BatchMatching import BatchMatching
from r3el.constants.DEventCategory import DEventCategory
from r3el.constants.DEventName import DEventName
from r3el.entity.Identification import Identification
from r3el.entity.MediaFile import MediaFile, MediaFileState
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.interface.TMDB import TMDB, TMDBError
from r3el.interface.WorkspaceDb import WorkspaceActionConflict


class TMDBTests(unittest.TestCase):
    @patch('r3el.interface.TMDB.httpx.get')
    def test_movie_query_uses_title_year_and_bearer_token(self, get):
        payload = {'total_results': 1, 'results': [{'id': 42, 'title': 'A Movie'}]}
        get.return_value = httpx.Response(200, json=payload, request=httpx.Request('GET', TMDB.URL))
        self.assertEqual(TMDB('secret').search('A Movie', 2020), payload)
        self.assertEqual(get.call_args.kwargs['params'],
                         {'query': 'A Movie', 'primary_release_year': 2020, 'page': 1})
        self.assertEqual(get.call_args.kwargs['headers']['Authorization'], 'Bearer secret')
        self.assertEqual(get.call_args.args, (TMDB.URL,))

    @patch('r3el.interface.TMDB.httpx.get')
    def test_failures_are_not_no_matches_and_do_not_expose_credentials(self, get):
        for status in (401, 429, 500):
            get.return_value = httpx.Response(status, text='secret', request=httpx.Request('GET', TMDB.URL))
            with self.assertRaises(TMDBError) as raised:
                TMDB('secret').search('Film', 2020)
            self.assertNotIn('secret', str(raised.exception))
            self.assertIn(str(status), str(raised.exception))
        get.side_effect = httpx.ReadTimeout('secret')
        with self.assertRaisesRegex(TMDBError, 'Unable to reach TMDB'):
            TMDB('secret').search('Film', 2020)

    @patch('r3el.interface.TMDB.httpx.get')
    def test_malformed_responses_are_rejected(self, get):
        for payload in ([], {}, {'total_results': True, 'results': []},
                        {'total_results': 1, 'results': []},
                        {'total_results': 1, 'results': [{'title': 'missing id'}]},
                        {'total_results': 0, 'results': [{'id': 1}]}):
            get.return_value = httpx.Response(200, json=payload, request=httpx.Request('GET', TMDB.URL))
            with self.assertRaises(TMDBError):
                TMDB('secret').search('Film', 2020)
        get.return_value = httpx.Response(200, text='not JSON', request=httpx.Request('GET', TMDB.URL))
        with self.assertRaisesRegex(TMDBError, 'invalid JSON'):
            TMDB('secret').search('Film', 2020)

    def test_missing_configuration_fails_clearly(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(TMDBError, 'TMDB_TOKEN'):
            TMDB.from_environment()


class BatchMatchingTests(unittest.TestCase):
    def setUp(self):
        self.files = [MediaFile(str(index), f'/tmp/{index}.mkv', MediaFileState.IDENTIFIED,
                               Identification('Movie', 2020, 10), action=action)
                      for index, action in enumerate((MediaFileAction.APPROVE,
                          MediaFileAction.IGNORE, MediaFileAction.DELETE))]
        self.batch = MediaFileBatch('batch', 5, '/tmp', files=self.files,
                                   state=MediaFileBatchState.IDENTIFICATION_COMPLETED)
        self.workspace = Mock()
        self.workspace.processing.side_effect = nullcontext
        self.workspace.matching.side_effect = nullcontext
        self.workspace.load.return_value = self.batch
        self.workspace.save_match.side_effect = self.save
        self.record = Mock(return_value=123)

    def save(self, batch_id, file_id, result, event):
        next(item for item in self.files if item.id == file_id).tmdb_match = result

    @patch('r3el.app.BatchMatching.TMDB.from_environment')
    def test_only_approved_files_are_queried_and_repeated_submissions_reuse_results(self, factory):
        factory.return_value.search.return_value = {'total_results': 1, 'results': [{'id': 42}]}
        runner = BatchMatching(self.workspace, self.record)
        runner.run('batch')
        self.assertEqual([item.tmdb_match.label for item in self.files], ['1 match', 'Skipped', 'Skipped'])
        runner.run('batch')
        factory.return_value.search.assert_called_once_with('Movie', 2020)
        self.record.assert_called_once()
        search = self.record.call_args.args[0]
        self.assertEqual(search.classification, DEventCategory.TMDB.SEARCH)
        self.assertEqual(search.name, DEventName.TMDB_SEARCH)
        self.assertEqual(json.loads(search.message)['data']['parameters'],
                         {'query': 'Movie', 'primary_release_year': 2020, 'page': 1})
        events = [call.args[3] for call in self.workspace.save_match.call_args_list if call.args[3] is not None]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].parent_event_id, 123)
        self.assertEqual(events[0].classification, DEventCategory.TMDB.RESULT)
        self.assertEqual(events[0].name, DEventName.TMDB_RESULT)
        self.assertEqual(json.loads(events[0].message)['data']['response'],
                         factory.return_value.search.return_value)
        self.assertEqual(json.loads(events[0].message)['context']['filename'], '0.mkv')

    @patch('r3el.app.BatchMatching.TMDB.from_environment')
    def test_not_ready_or_stale_batch_never_queries_tmdb(self, factory):
        runner = BatchMatching(self.workspace, self.record)
        for state, action, batch_id in (
            (MediaFileBatchState.PROCESSING, MediaFileAction.APPROVE, 'batch'),
            (MediaFileBatchState.IDENTIFICATION_COMPLETED, MediaFileAction.PENDING, 'batch'),
            (MediaFileBatchState.IDENTIFICATION_COMPLETED, MediaFileAction.APPROVE, 'old-batch'),
        ):
            self.batch.state, self.files[0].action = state, action
            with self.assertRaises(WorkspaceActionConflict):
                runner.run(batch_id)
        self.batch.files = []
        with self.assertRaises(WorkspaceActionConflict):
            runner.run('batch')
        factory.assert_not_called()
        self.workspace.save_match.assert_not_called()
        self.record.assert_not_called()

    @patch('r3el.app.BatchMatching.TMDB.from_environment')
    def test_failed_queries_are_saved_and_can_be_retried(self, factory):
        factory.return_value.search.side_effect = [TMDBError('TMDB returned HTTP 429.'),
                                                  {'total_results': 0, 'results': []}]
        runner = BatchMatching(self.workspace, self.record)
        runner.run('batch')
        self.assertEqual(self.files[0].tmdb_match.label, 'Match failed')
        failed_event = self.workspace.save_match.call_args_list[0].args[3]
        self.assertEqual(failed_event.level, 'ERROR')
        self.assertEqual(failed_event.parent_event_id, 123)
        self.assertEqual(json.loads(failed_event.message)['data']['error'], 'TMDB returned HTTP 429.')
        runner.run('batch')
        self.assertEqual(self.files[0].tmdb_match.label, 'No matches')
        self.assertEqual(self.record.call_count, 2)

    @patch('r3el.app.BatchMatching.TMDB.from_environment')
    def test_missing_identification_is_a_failure_and_all_skipped_needs_no_credentials(self, factory):
        self.files[0].identification = None
        BatchMatching(self.workspace, self.record).run('batch')
        self.assertEqual(self.files[0].tmdb_match.label, 'Match failed')
        self.files[0].action = MediaFileAction.IGNORE
        BatchMatching(self.workspace, self.record).run('batch')
        factory.assert_not_called()
        self.record.assert_not_called()

    def test_ambiguity_uses_total_results_not_first_page_length(self):
        result = TMDBMatch('Movie', 2020, response={'total_results': 21, 'results': [{'id': 1}]})
        self.assertEqual(result.label, '21 matches')


class CredentialInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('install_tmdb',
            Path(__file__).resolve().parents[1] / 'scripts/install-tmdb.py')
        cls.installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.installer)

    def test_quoted_exports_are_stored_with_private_permissions_and_can_be_updated(self):
        with TemporaryDirectory() as directory:
            source, destination = Path(directory) / 'source', Path(directory) / 'tmdb.env'
            source.write_text('# credentials\nexport TMDB_TOKEN="test.token"\nTMDB_KEY=abc123\n')
            self.installer.install_credentials(source, destination)
            self.assertEqual(destination.read_text(), 'TMDB_TOKEN=test.token\nTMDB_KEY=abc123\n')
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            source.write_text('TMDB_TOKEN=replacement\nTMDB_KEY=other\n')
            self.installer.install_credentials(source, destination)
            self.assertIn('replacement', destination.read_text())

    def test_invalid_input_preserves_existing_credentials_and_is_not_executed(self):
        with TemporaryDirectory() as directory:
            source, destination = Path(directory) / 'source', Path(directory) / 'tmdb.env'
            destination.write_text('existing')
            for content in ('TMDB_TOKEN=only\n', 'TMDB_TOKEN=$(whoami)\nTMDB_KEY=abc\n',
                            'TMDB_TOKEN=one\nTMDB_TOKEN=two\nTMDB_KEY=abc\n'):
                source.write_text(content)
                with self.assertRaises(ValueError):
                    self.installer.install_credentials(source, destination)
                self.assertEqual(destination.read_text(), 'existing')
