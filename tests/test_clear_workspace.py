"""Clearing waits for active workers and deletes only the requested workspace."""

from contextlib import nullcontext
import unittest
from unittest.mock import Mock, patch

from r3el.app.ClearWorkspace import ClearWorkspace
from r3el.interface.WorkspaceDb import WorkspaceDb, WorkspaceBusy, WorkspaceActionConflict


class ClearWorkspaceTests(unittest.TestCase):
    def test_stops_then_waits_for_worker_before_clearing(self):
        workspace = Mock()
        workspace.clear.side_effect = [WorkspaceBusy(), None]
        with patch('r3el.app.ClearWorkspace.time.sleep') as sleep:
            ClearWorkspace(workspace).run('batch')
        workspace.request_stop.assert_called_once_with('batch', matching=True)
        self.assertEqual(workspace.clear.call_count, 2)
        sleep.assert_called_once_with(0.2)

    def test_stale_request_fails_without_waiting(self):
        workspace = Mock()
        workspace.request_stop.side_effect = WorkspaceActionConflict()
        with self.assertRaises(WorkspaceActionConflict):
            ClearWorkspace(workspace).run('old')
        workspace.clear.assert_not_called()

    def test_idle_workspace_is_deleted_with_its_event_but_not_catalogue_or_logs(self):
        db = Mock()
        db.transaction.side_effect = nullcontext
        db.query.return_value = [{'batch_id': 'batch', 'state': 'matching_completed',
                                 'stop_requested': False, 'started_event_id': 1}]
        workspace = WorkspaceDb(db)
        with patch.object(workspace, 'processing', side_effect=nullcontext), \
                patch.object(workspace, 'matching', side_effect=nullcontext), \
                patch.object(workspace._events, 'record_in_transaction') as record:
            workspace.clear('batch')
        db.execute.assert_called_once_with('DELETE FROM media_file_batches WHERE batch_id = %s', ('batch',))
        self.assertEqual(record.call_args.args[0].name, 'batch_cleared')

    def test_active_or_wrong_batch_is_not_deleted(self):
        for row, error in (({'batch_id': 'batch', 'state': 'processing', 'stop_requested': True}, WorkspaceBusy),
                           ({'batch_id': 'other', 'state': 'matching_completed', 'stop_requested': False},
                            WorkspaceActionConflict)):
            db = Mock()
            db.transaction.side_effect = nullcontext
            db.query.return_value = [row]
            workspace = WorkspaceDb(db)
            with patch.object(workspace, 'processing', side_effect=nullcontext), \
                    patch.object(workspace, 'matching', side_effect=nullcontext), self.assertRaises(error):
                workspace.clear('batch')
            db.execute.assert_not_called()
