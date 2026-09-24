"""Stop requests preserve checkpoints and prevent further file processing."""

from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, Mock, patch

from r3el.app.BatchIdentification import BatchIdentification
from r3el.app.BatchMatching import BatchMatching
from r3el.app.BatchRunner import BatchRunner
from r3el.entity.BatchRequest import BatchRequest
from r3el.entity.BatchStopped import BatchStopped
from r3el.entity.Identification import Identification
from r3el.entity.MediaFile import MediaFile, MediaFileState
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState
from r3el.interface.FileMgr import FileMgr


class StopIdentificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_after_current_file_preserves_it_and_skips_next_file(self):
        with TemporaryDirectory() as directory:
            for name in ('one.mkv', 'two.mkv'):
                Path(directory, name).touch()
            workspace = Mock()
            workspace.processing.side_effect = nullcontext
            workspace.load.return_value = None
            workspace.create.return_value = 1
            workspace.check_stop.side_effect = [None, BatchStopped()]
            with patch('r3el.app.BatchIdentification.ToolConversation') as conversation:
                conversation.return_value.run = AsyncMock(return_value={
                    'status': 'identified', 'attempts': 1,
                    'identification': {'title': 'One', 'year': 2020, 'confidence': 10}})
                with self.assertRaises(BatchStopped):
                    await BatchIdentification(FileMgr(directory), Mock(), 'endpoint', Mock(),
                        Mock(return_value=1), workspace).run(2)
                conversation.return_value.run.assert_awaited_once()
            workspace.save_file.assert_called_once()
            self.assertEqual(workspace.save_file.call_args.args[1].state, MediaFileState.IDENTIFIED)
            self.assertEqual(workspace.save_batch_state.call_args.args[1], MediaFileBatchState.CANCELLED)

    async def test_runner_returns_to_idle_without_starting_matching(self):
        with patch('r3el.app.BatchRunner.DbMgr'), \
                patch('r3el.app.BatchRunner.BatchIdentification') as identification, \
                patch('r3el.app.BatchRunner.BatchMatching') as matching:
            identification.return_value.run = AsyncMock(side_effect=BatchStopped())
            await BatchRunner('url', 'endpoint', Mock()).run(BatchRequest('/in', '/out', 137))
            matching.assert_not_called()


class StopMatchingTests(unittest.TestCase):
    @patch('r3el.app.BatchMatching.TMDB.from_environment')
    @patch('r3el.app.BatchMatching.BatchMatching._catalogue')
    def test_current_file_finishes_and_next_file_does_not_start(self, catalogue, tmdb):
        workspace = Mock()
        workspace.processing.side_effect = nullcontext
        workspace.matching.side_effect = nullcontext
        workspace.load.return_value = MediaFileBatch('batch', 2, '/in',
            state=MediaFileBatchState.MATCHING, files=[
                MediaFile(str(index), f'/in/{index}.mkv', MediaFileState.IDENTIFIED,
                          Identification('Movie', 2020, 10)) for index in range(2)])
        workspace.check_stop.side_effect = [None, None, BatchStopped()]
        tmdb.return_value.search.return_value = {'total_results': 1, 'results': [{'id': 42}]}
        with self.assertRaises(BatchStopped):
            BatchMatching(workspace, Mock(return_value=1)).run('batch')
        workspace.save_match.assert_called_once()
        catalogue.assert_called_once()
        tmdb.return_value.search.assert_called_once()
        self.assertEqual(workspace.save_batch_state.call_args.args[1], MediaFileBatchState.CANCELLED)

    @patch('r3el.app.BatchMatching.TMDB.from_environment')
    @patch('r3el.app.BatchMatching.RetryIdentification')
    def test_zero_result_stop_preserves_query_without_starting_retry(self, retry, tmdb):
        workspace = Mock()
        workspace.processing.side_effect = nullcontext
        workspace.matching.side_effect = nullcontext
        workspace.load.return_value = MediaFileBatch('batch', 1, '/in',
            state=MediaFileBatchState.MATCHING, files=[
                MediaFile('one', '/in/one.mkv', MediaFileState.IDENTIFIED, Identification('Movie', 2020, 10))])
        workspace.check_stop.side_effect = [None, None, BatchStopped()]
        tmdb.return_value.search.return_value = {'total_results': 0, 'results': []}
        with self.assertRaises(BatchStopped):
            BatchMatching(workspace, Mock(return_value=1)).run('batch')
        workspace.save_match.assert_called_once()
        retry.assert_not_called()
