import json
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, Mock, patch

from r3el.app.BatchIdentification import BatchIdentification
from r3el.interface.FileMgr import FileMgr
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.interface.WorkspaceDb import WorkspaceDb, WorkspaceOccupied


class BatchIdentificationTests(unittest.IsolatedAsyncioTestCase):
    def workspace(self, record):
        workspace = Mock(spec=WorkspaceDb)
        workspace.processing.side_effect = nullcontext
        workspace.load.return_value = None

        def create(batch, started, discovered, **kwargs):
            event_id = record(started)
            record(discovered)
            return event_id

        workspace.create.side_effect = create
        workspace.save_file.side_effect = lambda batch_id, item, event: record(event)
        workspace.save_batch_state.side_effect = lambda batch_id, state, event: record(event)
        return workspace

    async def test_hidden_files_are_recorded_without_starting_conversations(self):
        events = []

        def record(event):
            events.append(event)
            return len(events)

        with TemporaryDirectory() as directory:
            root = Path(directory)
            names = ['.DS_Store', '._Film.mkv', '.hidden', 'Film.2026.mkv']
            for name in names:
                (root / name).write_text('untouched')
            (root / '.directory').mkdir()
            (root / '.link').symlink_to(root / 'Film.2026.mkv')
            llm, handler = Mock(), Mock()
            with patch('r3el.app.BatchIdentification.ToolConversation') as conversation:
                conversation.return_value.run = AsyncMock(
                    return_value={'status': 'identified', 'attempts': 1,
                                  'identification': {'title': 'Film', 'year': 2026, 'confidence': 9}})
                results = await BatchIdentification(
                    FileMgr(root), llm, 'unused', handler, record, self.workspace(record)).run(10)
                conversation.assert_called_once()
                self.assertEqual(conversation.call_args.args[3].context['filename'], 'Film.2026.mkv')
                conversation.return_value.run.assert_awaited_once()
            self.assertEqual(results, [
                {'filename': name, 'status': 'unresolved_hidden_file', 'attempts': 0,
                 'issues': [{'code': 'hidden_file', 'message': 'Hidden filename; identification skipped.'}]}
                for name in names[:3]
            ] + [{'filename': names[3], 'status': 'identified', 'attempts': 1, 'issues': [],
                  'identification': {'title': 'Film', 'year': 2026, 'confidence': 9}}])
            completed = [json.loads(event.message) for event in events if event.name == 'item_completed']
            self.assertEqual([item['data']['status'] for item in completed],
                             [result['status'] for result in results])
            self.assertEqual(json.loads(events[-1].message)['data'],
                             {'count': 4, 'unresolved_llm': 0, 'unresolved_hidden_file': 3})
            for name in names:
                self.assertEqual((root / name).read_text(), 'untouched')

    async def test_hidden_only_batch_obeys_limit_without_contacting_llm(self):
        with TemporaryDirectory() as directory:
            for name in ('.a', '.b', 'visible.mkv'):
                Path(directory, name).touch()
            llm, handler = Mock(), Mock()
            with patch('r3el.app.BatchIdentification.ToolConversation') as conversation:
                record = Mock(return_value=1)
                results = await BatchIdentification(
                    FileMgr(directory), llm, 'unused', handler, record, self.workspace(record)).run(2)
                conversation.assert_not_called()
            self.assertEqual([result['filename'] for result in results], ['.a', '.b'])
            self.assertTrue(all(result['status'] == 'unresolved_hidden_file' for result in results))
            self.assertEqual(llm.mock_calls, [])
            self.assertEqual(handler.mock_calls, [])

    async def test_new_batch_saves_output_directory_without_touching_it(self):
        with TemporaryDirectory() as directory:
            record = Mock(return_value=1)
            workspace = self.workspace(record)
            destination = str(Path(directory, 'future-output'))
            await BatchIdentification(
                FileMgr(directory), Mock(), 'unused', Mock(), record, workspace,
            ).run(5, destination_directory=destination, new_batch=True)
            batch = workspace.create.call_args.args[0]
            self.assertEqual(batch.source_directory, directory)
            self.assertEqual(batch.destination_directory, destination)
            self.assertEqual(batch.requested_size, 5)
            self.assertFalse(Path(destination).exists())

    async def test_new_batch_does_not_reuse_or_replace_existing_workspace(self):
        record = Mock(return_value=1)
        workspace = self.workspace(record)
        workspace.load.return_value = Mock(state="processing")
        files = Mock()
        with self.assertRaises(WorkspaceOccupied):
            await BatchIdentification(files, Mock(), 'unused', Mock(), record, workspace).run(
                5, destination_directory='/tmp/output', new_batch=True)
        files.filenames.assert_not_called()
        workspace.create.assert_not_called()
        workspace.save_batch_state.assert_not_called()

    async def test_new_batch_replaces_finished_workspace_with_fresh_selection(self):
        with TemporaryDirectory() as directory:
            Path(directory, '.new').touch()
            record = Mock(return_value=1)
            workspace = self.workspace(record)
            workspace.load.return_value = Mock(state='matching_completed')
            results = await BatchIdentification(FileMgr(directory), Mock(), 'unused', Mock(),
                                                 record, workspace).run(5, new_batch=True)
            self.assertEqual([item['filename'] for item in results], ['.new'])
            self.assertTrue(workspace.create.call_args.kwargs['replace_existing'])

    async def test_confidence_initializes_saved_action_once(self):
        for confidence, action in ((0, MediaFileAction.PENDING), (8, MediaFileAction.PENDING),
                                   (10, MediaFileAction.APPROVE)):
            with self.subTest(confidence=confidence), TemporaryDirectory() as directory:
                Path(directory, 'film.mkv').touch()
                record = Mock(return_value=1)
                workspace = self.workspace(record)
                with patch('r3el.app.BatchIdentification.ToolConversation') as conversation:
                    conversation.return_value.run = AsyncMock(return_value={
                        'status': 'identified', 'attempts': 1,
                        'identification': {'title': 'Film', 'year': 2020, 'confidence': confidence}})
                    await BatchIdentification(FileMgr(directory), Mock(), 'unused', Mock(),
                                              record, workspace).run(5)
                self.assertEqual(workspace.save_file.call_args.args[1].action, action)
