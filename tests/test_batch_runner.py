"""A human-started batch continues from identification through matching."""

from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import AsyncMock, Mock, patch
import unittest

from r3el.app.BatchRunner import BatchRunner
from r3el.entity.BatchRequest import BatchRequest
from r3el.entity.MediaFile import MediaFile
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState


class BatchRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_identification_hands_off_automatically_using_separate_connection(self):
        with (patch('r3el.app.BatchRunner.DbMgr') as database,
              patch('r3el.app.BatchRunner.WorkspaceDb') as workspaces,
              patch('r3el.app.BatchRunner.BatchIdentification') as identification,
              patch('r3el.app.BatchRunner.BatchMatching') as matching):
            first, second = Mock(), Mock()
            database.side_effect = [first, second]
            batch = MediaFileBatch('batch', 5, '/tmp', files=[MediaFile('file', '/tmp/a.mkv')],
                                   state=MediaFileBatchState.MATCHING)
            workspace = workspaces.return_value
            workspace.load.return_value = batch
            identification.return_value.run = AsyncMock()
            order = []
            identification.return_value.run.side_effect = lambda *a, **kw: order.append('identify')
            matching.return_value.run.side_effect = lambda *a, **kw: order.append('match')
            await BatchRunner('http://configured-model:1234', 'endpoint', Mock()).run(
                BatchRequest('/tmp', '/tmp/out', 5))
            self.assertEqual(order, ['identify', 'match'])
            self.assertEqual(identification.return_value.run.call_args.kwargs['completion_state'],
                             MediaFileBatchState.MATCHING)
            matching.return_value.run.assert_called_once_with('batch', file_ids=['file'])
            self.assertEqual(matching.call_args.args[2].url, 'http://configured-model:1234/v1/chat/completions')
            self.assertEqual([call.args[0] for call in workspaces.call_args_list], [first, second])
            first.close.assert_called_once()
            second.close.assert_called_once()
            self.assertEqual(workspace.save_batch_state.call_args.args[1], MediaFileBatchState.MATCHING_COMPLETED)

    async def test_identification_failure_does_not_start_matching(self):
        with (patch('r3el.app.BatchRunner.DbMgr') as database,
              patch('r3el.app.BatchRunner.WorkspaceDb'),
              patch('r3el.app.BatchRunner.BatchIdentification') as identification,
              patch('r3el.app.BatchRunner.BatchMatching') as matching):
            identification.return_value.run = AsyncMock(side_effect=RuntimeError('identification failed'))
            with self.assertRaisesRegex(RuntimeError, 'identification failed'):
                await BatchRunner('http://model', 'endpoint', Mock()).run(BatchRequest('/tmp', '/tmp/out', 5))
            matching.assert_not_called()
            database.return_value.close.assert_called_once()

    async def test_matching_failure_is_persisted_and_surfaces(self):
        with (patch('r3el.app.BatchRunner.DbMgr') as database,
              patch('r3el.app.BatchRunner.WorkspaceDb') as workspaces,
              patch('r3el.app.BatchRunner.BatchIdentification') as identification,
              patch('r3el.app.BatchRunner.BatchMatching') as matching):
            identification.return_value.run = AsyncMock()
            matching.return_value.run.side_effect = RuntimeError('matching failed')
            workspaces.return_value.load.return_value = MediaFileBatch('batch', 5, '/tmp',
                files=[MediaFile('file', '/tmp/a.mkv')], state=MediaFileBatchState.MATCHING)
            with self.assertRaisesRegex(RuntimeError, 'matching failed'):
                await BatchRunner('http://model', 'endpoint', Mock()).run(BatchRequest('/tmp', '/tmp/out', 5))
            self.assertEqual(workspaces.return_value.save_batch_state.call_args.args[1],
                             MediaFileBatchState.MATCHING_FAILED)
            self.assertEqual(database.return_value.close.call_count, 2)

    async def test_empty_batch_finishes_without_searching(self):
        with (patch('r3el.app.BatchRunner.DbMgr'), patch('r3el.app.BatchRunner.WorkspaceDb') as workspaces,
              patch('r3el.app.BatchRunner.BatchIdentification') as identification,
              patch('r3el.app.BatchRunner.BatchMatching') as matching):
            identification.return_value.run = AsyncMock()
            workspaces.return_value.load.return_value = MediaFileBatch('batch', 5, '/tmp', files=[])
            await BatchRunner('http://model', 'endpoint', Mock()).run(BatchRequest('/tmp', '/tmp/out', 5))
            matching.assert_not_called()
            self.assertEqual(workspaces.return_value.save_batch_state.call_args.args[1],
                             MediaFileBatchState.MATCHING_COMPLETED)

    async def test_groups_finish_matching_before_next_identification(self):
        for count in (0, 5, 10, 20, 23, 50, 100):
            with self.subTest(count=count), TemporaryDirectory() as directory:
                filenames = [f'{index:03}.mkv' for index in range(count)]
                for filename in filenames:
                    Path(directory, filename).touch()
                with (patch('r3el.app.BatchRunner.DbMgr'),
                      patch('r3el.app.BatchRunner.WorkspaceDb') as workspaces,
                      patch('r3el.app.BatchRunner.EventLogDb') as events,
                      patch('r3el.app.BatchIdentification.ToolConversation') as conversation,
                      patch('r3el.app.BatchMatching.TMDB.from_environment') as tmdb,
                      patch('r3el.app.BatchMatching.BatchMatching._catalogue')):
                    workspace = workspaces.return_value
                    workspace.processing.side_effect = nullcontext
                    workspace.matching.side_effect = nullcontext
                    workspace.load.return_value = None
                    events.return_value.record.return_value = 1
                    order = []

                    def create(batch, *args, **kwargs):
                        workspace.load.return_value = batch
                        return 1

                    def state(batch_id, value, event):
                        workspace.load.return_value.state = value

                    def make_conversation(llm, endpoint, handler, log):
                        filename = log.context['filename']
                        async def identify():
                            order.append(('identify', filename))
                            return {'status': 'identified', 'attempts': 1,
                                    'identification': {'title': filename, 'year': 2020, 'confidence': 10}}
                        return Mock(run=identify)

                    def search(title, year):
                        order.append(('match', title))
                        return {'total_results': 1, 'results': [{'id': 42}]}

                    workspace.create.side_effect = create
                    workspace.save_batch_state.side_effect = state
                    conversation.side_effect = make_conversation
                    tmdb.return_value.search.side_effect = search
                    tmdb.return_value.details.return_value = {
                        'id': 42, 'title': 'Movie', 'genres': [], 'credits': {'cast': [], 'crew': []}}
                    await BatchRunner('http://model', 'endpoint', Mock()).run(
                        BatchRequest(directory, '/tmp/out', max(5, count)))
                    expected = []
                    for offset in range(0, count, 10):
                        group = filenames[offset:offset + 10]
                        expected.extend(('identify', filename) for filename in group)
                        expected.extend(('match', filename) for filename in group)
                    self.assertEqual(order, expected)
                    self.assertEqual(workspace.load.return_value.state,
                                     MediaFileBatchState.MATCHING_COMPLETED)
                    self.assertEqual(workspace.save_match.call_count, count)
                    self.assertEqual(workspace.create.call_count, 1)
