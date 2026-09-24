"""A human-started batch continues from identification through matching."""

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
            matching.return_value.run.side_effect = lambda *a: order.append('match')
            await BatchRunner('http://configured-model:1234', 'endpoint', Mock()).run(
                BatchRequest('/tmp', '/tmp/out', 5))
            self.assertEqual(order, ['identify', 'match'])
            self.assertEqual(identification.return_value.run.call_args.kwargs['completion_state'],
                             MediaFileBatchState.MATCHING)
            matching.return_value.run.assert_called_once_with('batch')
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
