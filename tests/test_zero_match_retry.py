"""Zero-result retries are fresh, checkpointed, and bounded across submissions."""

from contextlib import nullcontext
from copy import deepcopy
from dataclasses import asdict
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from r3el.app.BatchMatching import BatchMatching
from r3el.entity.Identification import Identification
from r3el.entity.MediaFile import MediaFile, MediaFileState
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.interface.TMDB import TMDBError
from r3el.interface.WorkspaceDb import WorkspaceDb


class ZeroMatchRetryTests(unittest.TestCase):
    def setUp(self):
        catalogue = patch('r3el.app.BatchMatching.BatchMatching._catalogue')
        catalogue.start()
        self.addCleanup(catalogue.stop)
        self.item = MediaFile('file', '/tmp/Actual.Movie.2025.mkv', MediaFileState.IDENTIFIED,
                              Identification('Creative Movie', 2025, 10), attempts=1)
        self.batch = MediaFileBatch('batch', 1, '/tmp', files=[self.item],
                                    state=MediaFileBatchState.IDENTIFICATION_COMPLETED)
        self.workspace = Mock()
        self.workspace.processing.side_effect = nullcontext
        self.workspace.matching.side_effect = nullcontext
        self.workspace.load.return_value = self.batch
        self.snapshots = []
        self.workspace.save_file.side_effect = lambda batch, item, event: self.snapshots.append(deepcopy(item))
        self.workspace.save_match.side_effect = lambda batch, file, result, event: setattr(
            next(item for item in self.batch.files if item.id == file), 'tmdb_match', result)
        self.record = Mock(return_value=1)
        self.runner = BatchMatching(self.workspace, self.record)
        self.zero = {'total_results': 0, 'results': []}
        self.single = {'total_results': 1, 'results': [{'id': 42, 'title': 'Actual Movie'}]}
        for target in ('r3el.app.BatchMatching.TMDB.from_environment',
                       'r3el.app.RetryIdentification.ZMQServer',
                       'r3el.app.RetryIdentification.ToolConversation'):
            patcher = patch(target)
            value = patcher.start()
            self.addCleanup(patcher.stop)
            if target.endswith('from_environment'):
                self.tmdb = value.return_value
            elif target.endswith('ToolConversation'):
                self.conversation = value
        self.conversation.return_value.run = AsyncMock(return_value={
            'status': 'identified', 'attempts': 1,
            'identification': {'title': 'Actual Movie', 'year': 2025, 'confidence': 10}})

    def test_zero_then_match_uses_fresh_identification_and_new_query(self):
        self.tmdb.search.side_effect = [self.zero, self.single]
        self.runner.run('batch')
        self.assertEqual(self.item.retries, 1)
        self.assertEqual(self.item.identification.title, 'Actual Movie')
        self.assertEqual(self.item.tmdb_match.label, '1 match')
        self.assertEqual(self.item.attempts, 2)
        self.assertEqual([call.args for call in self.tmdb.search.call_args_list],
                         [('Creative Movie', 2025), ('Actual Movie', 2025)])
        self.assertTrue(self.snapshots[0].pending)
        self.assertEqual(self.snapshots[0].retries, 1)
        self.assertIsNone(self.snapshots[1].tmdb_match)
        self.assertEqual(self.conversation.call_args.args[3].context['filename'], 'Actual.Movie.2025.mkv')

    def test_three_retries_exhaust_then_later_submissions_do_not_restart(self):
        self.tmdb.search.return_value = self.zero
        self.runner.run('batch')
        self.assertEqual(self.conversation.call_count, 3)
        self.assertEqual(self.tmdb.search.call_count, 4)
        self.assertEqual(self.item.retries, 3)
        self.assertEqual(self.item.state, MediaFileState.UNRESOLVED_LLM)
        self.assertEqual(self.item.action, MediaFileAction.PENDING)
        self.assertFalse(self.item.pending)
        self.runner.run('batch')
        self.assertEqual(self.conversation.call_count, 3)
        self.assertEqual(self.tmdb.search.call_count, 4)

    def test_saved_retry_count_and_zero_response_resume_remaining_budget(self):
        self.item.retries = 2
        self.item.tmdb_match = TMDBMatch('Creative Movie', 2025, response=self.zero)
        self.tmdb.search.return_value = self.zero
        self.runner.run('batch')
        self.assertEqual(self.conversation.call_count, 1)
        self.assertEqual(self.tmdb.search.call_count, 1)
        self.assertEqual(self.item.retries, 3)
        self.assertEqual(self.item.state, MediaFileState.UNRESOLVED_LLM)

    def test_third_retry_can_succeed_and_api_failure_does_not_trigger_reidentification(self):
        self.item.retries = 2
        self.item.tmdb_match = TMDBMatch('Creative Movie', 2025, response=self.zero)
        self.tmdb.search.return_value = self.single
        self.runner.run('batch')
        self.assertEqual(self.item.retries, 3)
        self.assertEqual(self.item.state, MediaFileState.IDENTIFIED)
        self.item.tmdb_match = None
        self.tmdb.search.side_effect = TMDBError('Unavailable')
        self.runner.run('batch')
        self.assertEqual(self.conversation.call_count, 1)
        self.assertEqual(self.item.tmdb_match.label, 'Match failed')

    def test_retry_can_flow_into_multiple_choice(self):
        self.tmdb.search.side_effect = [self.zero, {'total_results': 2, 'results': [{'id': 1}, {'id': 2}]}]
        with patch('r3el.app.BatchMatching.MovieSelection.run', return_value=TMDBMatch(
                'Actual Movie', 2025, response=self.single, selected_number=2)) as selection:
            self.runner.run('batch')
        selection.assert_called_once()
        self.assertEqual(self.item.tmdb_match.label, '1 match')

    def test_exhaustion_does_not_stop_next_file(self):
        self.item.retries = 3
        self.item.tmdb_match = TMDBMatch('Creative Movie', 2025, response=self.zero)
        next_item = MediaFile('next', '/tmp/Next.mkv', MediaFileState.IDENTIFIED, Identification('Next', 2020, 10))
        self.batch.files.append(next_item)
        self.tmdb.search.return_value = self.single
        self.runner.run('batch')
        self.assertEqual(next_item.tmdb_match.label, '1 match')
        self.conversation.assert_not_called()

    def test_retry_state_round_trips_through_workspace_row(self):
        self.tmdb.search.side_effect = [self.zero, self.single]
        self.runner.run('batch')
        item = WorkspaceDb._file(dict(file_id=self.item.id, path=self.item.path, state=self.item.state,
            identification=json.dumps(asdict(self.item.identification)), issues='[]', attempts=self.item.attempts,
            action=self.item.action, retries=self.item.retries, updated_at=None,
            tmdb_match=json.dumps(asdict(self.item.tmdb_match))))
        self.assertEqual(item, self.item)


class FreshRetryConversationTests(unittest.TestCase):
    @patch('r3el.app.RetryIdentification.RetryIdentification._record_submission', return_value=1)
    @patch('r3el.app.RetryIdentification.LLM.from_environment')
    def test_real_mcp_retries_send_only_fresh_filename_prompts(self, factory, record_submission):
        from r3el.activity.EventWriter import EventWriter
        from r3el.app.RetryIdentification import RetryIdentification

        requests = []
        async def complete(payload):
            requests.append(deepcopy(payload))
            return json.dumps({'choices': [{'message': {'tool_calls': [{
                'id': 'identify', 'function': {'name': 'submit_identification',
                    'arguments': json.dumps({'title': 'Actual Movie', 'year': 2025, 'confidence': 10})}}]}}]})
        factory.return_value.complete = complete
        item = MediaFile('file', '/tmp/Actual.Movie.2025.mkv', MediaFileState.IDENTIFIED,
                         Identification('Creative Title', 2025, 10))
        log = EventWriter(Mock(return_value=1), {'batch_id': 'batch', 'item_id': 'file', 'filename': item.filename})
        for _ in range(2):
            item.tmdb_match = TMDBMatch(item.identification.title, 2025,
                                       response={'total_results': 0, 'results': []})
            RetryIdentification(Mock()).run(item, log)
        self.assertEqual(item.retries, 2)
        self.assertEqual(requests[0]['messages'], requests[1]['messages'])
        self.assertEqual(len(requests[0]['messages']), 4)
        self.assertTrue(all(message['role'] == 'user' for message in requests[0]['messages']))
        self.assertNotIn('Creative Title', json.dumps(requests))
        self.assertNotIn('total_results', json.dumps(requests))
        self.assertIn(item.filename, json.dumps(requests))
