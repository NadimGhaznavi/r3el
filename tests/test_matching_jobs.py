"""Background matching completion, failure, and shutdown contracts."""

from threading import Event
import unittest
from unittest.mock import Mock, patch

from r3el.app.MatchingJobs import MatchingJobs
from r3el.interface.WorkspaceDb import WorkspaceActionConflict
from r3el.entity.BatchStopped import BatchStopped


class MatchingJobsTests(unittest.TestCase):
    def test_manual_requests_are_deduplicated_by_file_and_movie(self):
        entered, release = Event(), Event()
        execute = Mock(side_effect=lambda *args, **kwargs: (entered.set(), release.wait(3)))
        jobs = MatchingJobs(execute)
        try:
            job = jobs.submit('batch', file_id='file', movie_id=42)
            self.assertTrue(entered.wait(1))
            self.assertEqual(jobs.submit('batch', file_id='file', movie_id=42), job)
            self.assertIsNone(jobs.submit('batch', file_id='other', movie_id=42))
            self.assertIsNone(jobs.submit('batch', file_id='file', movie_id=43))
            self.assertIsNone(jobs.submit('batch'))
        finally:
            release.set()
            jobs.close()
        execute.assert_called_once_with('batch', file_id='file', movie_id=42)

    def test_requested_stop_is_reported_as_cancelled(self):
        jobs = MatchingJobs(Mock(side_effect=BatchStopped()))
        jobs.submit('batch')
        jobs.close()
        self.assertEqual(jobs.current()['status'], 'cancelled')

    def test_reservation_duplicate_and_close(self):
        entered, release = Event(), Event()

        def execute(batch):
            entered.set()
            release.wait(3)

        jobs = MatchingJobs(execute)
        try:
            job = jobs.submit('batch')
            self.assertTrue(entered.wait(1))
            self.assertEqual(jobs.submit('batch'), job)
            self.assertIsNone(jobs.submit('other'))
        finally:
            release.set()
            jobs.close()
        self.assertEqual(jobs.current()['status'], 'completed')
        self.assertIsNone(jobs.submit('batch'))

    def test_expected_failure_is_reported(self):
        jobs = MatchingJobs(Mock(side_effect=WorkspaceActionConflict('stale batch')))
        with self.assertLogs(level='ERROR'):
            jobs.submit('batch')
            jobs.close()
        self.assertEqual(jobs.current()['status'], 'failed')

    def test_programming_failure_surfaces_and_reports_failed(self):
        jobs = MatchingJobs(Mock(side_effect=TypeError('bug')))
        with patch('threading.excepthook') as hook:
            jobs.submit('batch')
            jobs.close()
        self.assertEqual(jobs.current()['status'], 'failed')
        self.assertIsInstance(hook.call_args.args[0].exc_value, TypeError)
