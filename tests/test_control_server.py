"""Exercise the control server over HTTP with isolated database connections."""

from datetime import datetime
from http.client import HTTPConnection
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time
from urllib.parse import urlencode

import zmq

from r3el.constants.DMessage import DMessage
from r3el.entity.BatchRequest import BatchRequest
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.entity.TMDBReference import TMDBReference
from r3el.interface.WorkspaceDb import WorkspaceActionConflict
from r3el.entity.MediaFile import MediaFile, MediaFileState
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState
import unittest
from unittest.mock import Mock, patch

import pymysql

from r3el.server.ControlServer import make_server


class ControlServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server('127.0.0.1', 0)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.factory_patch = patch('r3el.server.ControlServer.DbMgr')
        self.factory = self.factory_patch.start()
        self.addCleanup(self.factory_patch.stop)
        self.workspace_patch = patch('r3el.server.ControlServer.WorkspaceDb.snapshot', return_value=None)
        self.workspace = self.workspace_patch.start()
        self.addCleanup(self.workspace_patch.stop)
        self.reference_patch = patch('r3el.server.ControlServer.TMDBReferenceDb.load',
                                     return_value=TMDBReference([], []))
        self.reference_patch.start()
        self.addCleanup(self.reference_patch.stop)
        self.db = Mock()
        self.factory.return_value = self.db
        self.event = dict(event_id=42, occurred_at=datetime(2026, 9, 20, 14, 30),
                          category='Batch', subcategory='BatchIdentification', name='item_completed',
                          log_level='INFO', source_name='BatchIdentification', process_id='item-123',
                          parent_event_id=41, app_version='0.1.0',
                          content=json.dumps({'context': {'filename': '<script>alert(1)</script> 🎬'},
                                              'data': {}}))
        self.db.query.return_value = [self.event]

    def request(self, path, method='GET', body=None, headers=None):
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode()
        finally:
            connection.close()

    @patch('r3el.server.ControlServer.CatalogueDb.movies')
    def test_catalogue_lists_linked_titles_and_empty_state(self, movies):
        movies.return_value = [{'tmdb_id': 42, 'title': '<Movie>', 'release_year': 2020},
                               {'tmdb_id': 43, 'title': 'Other', 'release_year': None}]
        status, _, body = self.request('/catalogue')
        self.assertEqual(status, 200)
        self.assertIn('<a href="/catalogue/42">&lt;Movie&gt; (2020)</a>', body)
        self.assertIn('<a href="/catalogue/43">Other</a>', body)
        self.assertNotIn('<Movie>', body)
        self.db.close.assert_called_once()
        movies.return_value = []
        self.assertIn('No movies in the catalogue yet.', self.request('/catalogue')[2])

    @patch('r3el.server.ControlServer.CatalogueDb.get')
    def test_catalogue_entry_renders_saved_metadata(self, get):
        get.return_value = dict(tmdb_id=42, title='<Movie>', release_year=2020,
            original_title='Original', release_date='2020-02-03', runtime=120,
            overview='A saved overview.', genres=[{'name': 'Drama'}], rating=8.25,
            vote_count=100, imdb_id='tt123', credits=[{'name': '<Actor>', 'role': 'Actor',
                'character_name': 'Hero'}], files=[{'path': '/movies/Movie.mkv'}], artwork=[{'kind': 'poster'}])
        status, _, body = self.request('/catalogue/42')
        self.assertEqual(status, 200)
        get.assert_called_once_with(42)
        for text in ('&lt;Movie&gt; (2020)', 'A saved overview.', '120 minutes', 'Drama',
                     '&lt;Actor&gt; — Actor (Hero)', '/movies/Movie.mkv', '/catalogue/42/poster', 'tt123'):
            self.assertIn(text, body)
        self.assertNotIn('image.tmdb.org', body)
        get.return_value = None
        self.assertEqual(self.request('/catalogue/42')[0], 404)
        for path in ('/catalogue/0', '/catalogue/4294967296', '/catalogue/abc'):
            self.assertEqual(self.request(path)[0], 404)

    @patch('r3el.server.ControlServer.CatalogueDb.artwork_path')
    def test_catalogue_serves_only_registered_artwork(self, artwork):
        with TemporaryDirectory() as directory:
            poster = Path(directory) / 'poster.jpg'
            poster.write_bytes(b'image')
            artwork.return_value = str(poster)
            status, headers, body = self.request('/catalogue/42/poster')
            self.assertEqual((status, headers['Content-Type'], body), (200, 'image/jpeg', 'image'))
            artwork.assert_called_once_with(42, 'poster')
            poster.unlink()
            self.assertEqual(self.request('/catalogue/42/poster')[0], 404)
            artwork.return_value = None
            self.assertEqual(self.request('/catalogue/42/backdrop')[0], 404)
            self.assertEqual(self.request('/catalogue/42/../../etc/passwd')[0], 404)

    @patch('r3el.server.ControlServer.CatalogueDb.movies', side_effect=pymysql.OperationalError('private details'))
    def test_catalogue_database_failure_is_reported_without_details(self, movies):
        with self.assertLogs(level='ERROR'):
            status, _, body = self.request('/catalogue')
        self.assertEqual(status, 503)
        self.assertIn('Catalogue unavailable', body)
        self.assertNotIn('private details', body)
        self.db.close.assert_called_once()

    def test_empty_workspace_shows_batch_controls(self):
        status, _, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn('Media Directory', body)
        self.assertIn('value="/exports/disk1/archive/film"', body)
        self.assertIn('value="5"', body)
        self.assertIn('step="1" value="10" required', body)
        self.assertIn('type="submit" aria-describedby="batch-note">New Batch', body)
        self.assertIn('/static/r3el.png', body)
        self.assertIn('Last updated:', body)
        self.assertNotIn('http-equiv="refresh"', body)
        self.workspace.assert_called_once()
        self.db.close.assert_called_once()

    @patch('r3el.server.ControlServer.BatchControl.new_batch')
    def test_startup_and_page_refreshes_never_start_a_batch(self, new_batch):
        with make_server('127.0.0.1', 0):
            new_batch.assert_not_called()
        batch = MediaFileBatch('batch-1', 5, '/tmp/input')
        for workspace in (None, batch):
            self.workspace.return_value = workspace
            for path in ('/', '/', '/?result=accepted', '/?result=accepted'):
                with self.subTest(workspace=workspace, path=path):
                    status, _, body = self.request(path)
                    self.assertEqual(status, 200)
                    self.assertIn('<button', body)
                    self.assertEqual('type="button" disabled' in body, workspace is not None)
                    self.assertNotIn('http-equiv="refresh"', body)
        new_batch.assert_not_called()

    def test_occupied_workspace_shows_static_controls_and_ordered_files(self):
        self.workspace.return_value = MediaFileBatch(
            'batch-1', 5, '/tmp/<input>', destination_directory='/tmp/<output>',
            files=[MediaFile('file-1', '/tmp/input/z<&>.mkv'),
                   MediaFile('file-2', '/tmp/input/a.mkv', state=MediaFileState.IDENTIFIED),
                   MediaFile('file-3', '/tmp/input/b.mkv', state=MediaFileState.UNRESOLVED_LLM),
                   MediaFile('file-4', '/tmp/input/.hidden', state=MediaFileState.UNRESOLVED_HIDDEN_FILE)],
        )
        for state in MediaFileBatchState:
            with self.subTest(state=state):
                self.workspace.return_value.state = state
                status, _, body = self.request('/')
                self.assertEqual(status, 200)
                self.assertIn('Current batch files', body)
                self.assertIn('z&lt;&amp;&gt;.mkv', body)
                self.assertLess(body.index('z&lt;&amp;&gt;.mkv'), body.index('a.mkv'))
                for label in ('Pending', 'Identified', 'Unresolved — identification', 'Unresolved — hidden file'):
                    self.assertIn(label, body)
                self.assertIn('<h1 id="control-heading">Control</h1>', body)
                self.assertIn('id="batch-processing"', body)
                active = state in (MediaFileBatchState.PROCESSING, MediaFileBatchState.MATCHING)
                self.assertEqual('class="control-occupied"' in body, active)
                self.assertIn('/tmp/&lt;input&gt;', body)
                self.assertIn('/tmp/&lt;output&gt;', body)
                if active:
                    self.assertIn('<dt>Batch Size</dt><dd>5</dd>', body)
                    self.assertIn('type="button" disabled', body)
                    self.assertNotIn('<input', body)
                else:
                    self.assertIn('type="submit" aria-describedby="batch-note">New Batch', body)
                controls = re.search(r'<section.*?</section>', body, re.S).group(0)
                self.assertNotIn('<select', controls)
                self.assertIn('class="file-action"', body)
                self.assertEqual(bool(re.search(r'<form[^>]*aria-label="New batch"', body)), not active)
                self.assertNotIn('http-equiv="refresh"', body)
                header = re.search(r'<header.*?</header>', body, re.S).group(0)
                self.assertRegex(header, r'Last updated: <time datetime="[^"]+\+00:00" data-local-time="full">—</time>')

    def test_process_batch_is_enabled_after_identification_even_with_pending_actions(self):
        batch = MediaFileBatch('batch-1', 5, '/tmp', files=[
            MediaFile('file-1', '/tmp/a.mkv', state=MediaFileState.IDENTIFIED,
                      action=MediaFileAction.APPROVE)])
        self.workspace.return_value = batch
        for state, action, enabled in (
            (MediaFileBatchState.PROCESSING, MediaFileAction.APPROVE, False),
            (MediaFileBatchState.FAILED, MediaFileAction.APPROVE, False),
            (MediaFileBatchState.MATCHING, MediaFileAction.APPROVE, False),
            (MediaFileBatchState.MATCHING_COMPLETED, MediaFileAction.APPROVE, True),
            (MediaFileBatchState.MATCHING_FAILED, MediaFileAction.APPROVE, True),
            (MediaFileBatchState.IDENTIFICATION_COMPLETED, MediaFileAction.PENDING, True),
            (MediaFileBatchState.IDENTIFICATION_COMPLETED, MediaFileAction.APPROVE, True),
            (MediaFileBatchState.IDENTIFICATION_COMPLETED, MediaFileAction.IGNORE, True),
            (MediaFileBatchState.IDENTIFICATION_COMPLETED, MediaFileAction.DELETE, True),
        ):
            with self.subTest(state=state, action=action):
                batch.state, batch.files[0].action = state, action
                body = self.request('/')[2]
                button = re.search(r'<button id="match-tmdb"[^>]*>', body).group(0)
                self.assertEqual('disabled' not in button, enabled)
                self.assertIn('type="button"', button)
                self.assertIn('>Process Batch</button>', body)
                self.assertNotIn('onclick', button)
                self.assertIn(f'<option value="{action}" selected>', body)
        batch.files = []
        self.assertIn('type="button" disabled', re.search(
            r'<button id="match-tmdb"[^>]*>', self.request('/')[2]).group(0))

    def test_automatic_pipeline_disables_menus_and_polls_without_matching_post(self):
        self.workspace.return_value = MediaFileBatch('batch', 5, '/tmp',
            files=[MediaFile('file', '/tmp/a.mkv', MediaFileState.IDENTIFIED)])
        for state in (MediaFileBatchState.PROCESSING, MediaFileBatchState.MATCHING):
            self.workspace.return_value.state = state
            body = self.request('/')[2]
            menu = re.search(r'<select class="file-action".*?>', body, re.S).group(0)
            self.assertIn('disabled', menu)
            self.assertIn('data-automatic-processing="true"', body)
            self.assertIn('window.setTimeout(pollAutomaticBatch, 2000);', body)

    @patch('r3el.server.ControlServer.WorkspaceDb.save_action')
    def test_action_change_is_saved_and_reports_readiness(self, save):
        save.return_value = MediaFileBatch('batch-1', 5, '/tmp',
            state=MediaFileBatchState.IDENTIFICATION_COMPLETED,
            files=[MediaFile('file-1', '/tmp/a', state=MediaFileState.IDENTIFIED,
                             action=MediaFileAction.DELETE)])
        status, _, body = self.request('/workspace/actions', 'POST',
            urlencode(dict(batch_id='batch-1', file_id='file-1', action='delete')),
            {'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {'saved': True, 'ready': True})
        save.assert_called_once_with('batch-1', 'file-1', MediaFileAction.DELETE)
        self.db.close.assert_called_once()

    @patch('r3el.server.ControlServer.BatchMatching.run')
    def test_matching_returns_before_work_finishes_and_reports_progress(self, run):
        entered, release = Event(), Event()

        def execute(batch_id):
            entered.set()
            self.assertTrue(release.wait(5))

        run.side_effect = execute
        self.workspace.return_value = MediaFileBatch('batch-1', 5, '/tmp')
        self.request('/')
        run.assert_not_called()
        try:
            status, _, body = self.request('/workspace/match', 'POST', 'batch_id=batch-1',
                {'Content-Type': 'application/x-www-form-urlencoded'})
            self.assertEqual(status, 202)
            job_id = json.loads(body)['job_id']
            self.assertTrue(entered.wait(2))
            status_url = '/workspace/match/status/' + job_id
            self.assertEqual(json.loads(self.request(status_url)[2])['status'], 'running')
            duplicate = self.request('/workspace/match', 'POST', 'batch_id=batch-1',
                {'Content-Type': 'application/x-www-form-urlencoded'})
            self.assertEqual(json.loads(duplicate[2])['job_id'], job_id)
            self.assertEqual(self.request('/workspace/match', 'POST', 'batch_id=other',
                {'Content-Type': 'application/x-www-form-urlencoded'})[0], 409)
            self.assertIn('pollMatching("' + job_id + '")', self.request('/')[2])
            self.assertEqual(self.request('/health')[0], 200)
            run.assert_called_once_with('batch-1')
        finally:
            release.set()
        deadline = time.monotonic() + 2
        while json.loads(self.request(status_url)[2])['status'] == 'running':
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.01)
        self.assertEqual(json.loads(self.request(status_url)[2])['status'], 'completed')
        self.assertNotIn('pollMatching("' + job_id + '")', self.request('/')[2])
        self.assertEqual(self.request('/workspace/match/status/unknown')[0], 404)

    @patch('r3el.server.ControlServer.BatchMatching.run')
    def test_invalid_matching_requests_do_not_run(self, run):
        for body in ('batch_id=', 'batch_id=../bad', 'batch_id=one&batch_id=two', 'file_id=one'):
            self.assertEqual(self.request('/workspace/match', 'POST', body,
                {'Content-Type': 'application/x-www-form-urlencoded'})[0], 400)
        self.assertEqual(self.request('/workspace/match', 'POST', 'batch_id=batch-1',
            {'Content-Type': 'application/x-www-form-urlencoded', 'Origin': 'https://elsewhere.invalid'})[0], 403)
        run.assert_not_called()

    @patch('r3el.interface.TMDB.httpx.get')
    def test_saved_results_are_linked_escaped_and_never_refetched(self, get):
        item = MediaFile('file-1', '/tmp/a.mkv', tmdb_match=TMDBMatch('<script>', 2020,
            response={'total_results': 1, 'results': [{'id': 42, 'title': '<script>alert(1)</script>'}]}))
        self.workspace.return_value = MediaFileBatch('batch-1', 5, '/tmp', files=[item])
        body = self.request('/')[2]
        self.assertIn('Match Results', body)
        self.assertIn('href="/matches/batch-1/file-1">1 match</a>', body)
        for _ in range(2):
            status, _, body = self.request('/matches/batch-1/file-1')
            self.assertEqual(status, 200)
            self.assertIn('&lt;script&gt;', body)
            self.assertNotIn('<script>', body.split('<main>', 1)[1].split('</main>', 1)[0])
            self.assertIn('\n  &#34;total_results&#34;: 1,', body)
        self.assertEqual(self.request('/matches/old-batch/file-1')[0], 404)
        self.assertEqual(self.request('/matches/batch-1/missing')[0], 404)
        item.tmdb_match = TMDBMatch(None, None, skipped=True)
        self.assertNotIn('href="/matches/', self.request('/')[2])
        self.assertEqual(self.request('/matches/batch-1/file-1')[0], 404)
        get.assert_not_called()

    @patch('r3el.server.ControlServer.WorkspaceDb.save_action')
    def test_invalid_and_stale_actions_are_rejected(self, save):
        for action in ('unknown', 'APPROVE', ''):
            status, _, _ = self.request('/workspace/actions', 'POST',
                urlencode(dict(batch_id='batch-1', file_id='file-1', action=action)),
                {'Content-Type': 'application/x-www-form-urlencoded'})
            self.assertEqual(status, 400)
        save.assert_not_called()
        save.side_effect = WorkspaceActionConflict('not ready')
        status, _, _ = self.request('/workspace/actions', 'POST',
            urlencode(dict(batch_id='batch-1', file_id='file-1', action='approve')),
            {'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(status, 409)
        self.db.close.assert_called_once()

    def test_retained_batch_with_no_files_still_disables_new_batch(self):
        self.workspace.return_value = MediaFileBatch('batch-1', 5, '/tmp/input')
        status, _, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn('No files in this batch.', body)
        self.assertIn('type="button" disabled', body)
        self.assertIn('<dd>Not available</dd>', body)

    def test_finished_batch_offers_new_batch_with_previous_parameters(self):
        for state in (MediaFileBatchState.MATCHING_COMPLETED, MediaFileBatchState.FAILED,
                      MediaFileBatchState.CANCELLED):
            with self.subTest(state=state):
                self.workspace.return_value = MediaFileBatch('batch-1', 137, '/tmp/input',
                    state=state, destination_directory='/tmp/output')
                status, _, body = self.request('/')
                self.assertEqual(status, 200)
                self.assertIn('type="submit" aria-describedby="batch-note">New Batch', body)
                self.assertIn('value="/tmp/input"', body)
                self.assertIn('value="/tmp/output"', body)
                self.assertIn('value="137"', body)

    def test_workspace_failure_does_not_offer_new_batch_or_expose_details(self):
        self.workspace.side_effect = pymysql.OperationalError('private database details')
        with self.assertLogs(level='ERROR'):
            status, _, body = self.request('/')
        self.assertEqual(status, 503)
        self.assertIn('Workspace unavailable', body)
        self.assertNotIn('<button', body)
        self.assertNotIn('private database details', body)
        self.db.close.assert_called_once()

    def test_workspace_connection_failure_returns_503(self):
        self.factory.side_effect = pymysql.OperationalError('private database details')
        with self.assertLogs(level='ERROR'):
            status, _, body = self.request('/')
        self.assertEqual(status, 503)
        self.assertNotIn('<button', body)
        self.workspace.assert_not_called()

    @patch('r3el.server.ControlServer.BatchControl.new_batch')
    def test_post_feedback_for_current_batch_has_disabled_button_and_no_refresh(self, new_batch):
        self.workspace.return_value = MediaFileBatch('batch-1', 5, '/tmp/input')
        new_batch.return_value = {'status': DMessage.BUSY}
        status, _, body = self.post_batch()
        self.assertEqual(status, 409)
        self.assertIn('Current batch files', body)
        self.assertIn('type="button" disabled', body)
        self.assertNotIn('http-equiv="refresh"', body)

    def test_control_refresh_options_and_invalid_values(self):
        for seconds in (0, 5, 30, 60):
            status, _, body = self.request(f'/?refresh={seconds}')
            self.assertEqual(status, 200)
            self.assertIn(f'<option value="{seconds}" selected>', body)
            self.assertNotIn('http-equiv="refresh"', body)
            self.assertIn(f'let refreshSeconds = {seconds};', body)
            self.assertIn('window.history.replaceState', body)
        for query in ('refresh=2', 'refresh=-1', 'refresh=5&refresh=30', 'other=value'):
            self.assertEqual(self.request('/?' + query)[0], 400)

    @patch('r3el.server.ControlServer.BatchControl.new_batch')
    def test_new_batch_retains_refresh_in_redirect_and_one_time_reload(self, new_batch):
        new_batch.return_value = {'status': DMessage.ACCEPTED}
        status, headers, _ = self.post_batch(refresh='30')
        self.assertEqual(status, 303)
        self.assertEqual(headers['Location'], '/?result=accepted&refresh=30')
        body = self.request(headers['Location'])[2]
        self.assertIn('window.location.replace("/?refresh=30"), 2000', body)
        self.assertNotIn('http-equiv="refresh"', body)
        self.assertIn('let refreshSeconds = 30;', body)
        new_batch.assert_called_once_with(BatchRequest('/tmp/input', '/tmp/output', 5))

    def post_batch(self, **values):
        fields = dict(input_directory='/tmp/input', output_directory='/tmp/output', batch_size='5')
        fields.update(values)
        return self.request('/batches', 'POST', urlencode(fields),
                            {'Content-Type': 'application/x-www-form-urlencoded'})

    @patch('r3el.server.ControlServer.BatchControl.new_batch')
    def test_free_form_size_and_numbered_updated_columns(self, new_batch):
        new_batch.return_value = {'status': DMessage.ACCEPTED}
        body = self.request('/')[2]
        self.assertIn('id="batch-size" name="batch_size" type="number"', body)
        self.assertEqual(self.post_batch(batch_size='137')[0], 303)
        self.assertEqual(new_batch.call_args.args[0].batch_size, 137)
        self.workspace.return_value = MediaFileBatch('batch-1', 137, '/tmp', files=[
            MediaFile('one', '/tmp/a.mkv', updated_at=datetime(2026, 9, 24, 13, 7)),
            MediaFile('two', '/tmp/b.mkv')])
        body = self.request('/')[2]
        self.assertRegex(body, r'<th scope="col">#</th><th[^>]+>Updated</th><th scope="col">Filename</th>')
        self.assertIn('<td>1</td>', body)
        self.assertIn('<td>2</td>', body)
        self.assertIn('datetime="2026-09-24T13:07:00.000+00:00" data-local-time="compact"', body)

    @patch('r3el.server.ControlServer.WorkspaceDb.request_stop')
    def test_stop_endpoint_and_validation(self, stop):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        status, _, body = self.request('/workspace/stop', 'POST', 'batch_id=batch-1', headers)
        self.assertEqual(status, 202)
        self.assertTrue(json.loads(body)['accepted'])
        stop.assert_called_once_with('batch-1', matching=False)
        stop.reset_mock()
        self.assertEqual(self.request('/workspace/stop', 'POST', 'batch_id=../bad', headers)[0], 400)
        self.assertEqual(self.request('/workspace/stop', 'POST', 'batch_id=batch-1',
                                     dict(headers, Origin='http://other-host'))[0], 403)
        stop.assert_not_called()
        stop.side_effect = WorkspaceActionConflict('Not running')
        self.assertEqual(self.request('/workspace/stop', 'POST', 'batch_id=batch-1', headers)[0], 409)

    def test_stop_button_tracks_running_and_requested_state(self):
        batch = MediaFileBatch('batch-1', 1, '/tmp', files=[MediaFile('one', '/tmp/one.mkv')])
        self.workspace.return_value = batch
        self.assertIn('id="stop-batch" type="button" aria-describedby=', self.request('/')[2])
        batch.stop_requested = True
        body = self.request('/')[2]
        self.assertIn('id="stop-batch" type="button" disabled', body)
        self.assertIn('Stopping after the current operation', body)
        batch.state = MediaFileBatchState.CANCELLED
        self.assertIn('Batch stopped. Completed work has been preserved.', self.request('/')[2])

    @patch('r3el.server.ControlServer.BatchControl.new_batch')
    def test_new_batch_forwards_parameters_and_redirects(self, new_batch):
        new_batch.return_value = {'status': DMessage.ACCEPTED}
        status, headers, _ = self.post_batch()
        self.assertEqual(status, 303)
        new_batch.assert_called_once_with(BatchRequest('/tmp/input', '/tmp/output', 5))
        self.assertEqual(headers['Location'], '/?result=accepted')
        body = self.request(headers['Location'])[2]
        self.assertIn('Batch accepted.', body)
        self.assertIn('window.setTimeout(() => window.location.replace("/"), 2000);', body)
        new_batch.assert_called_once()
        self.workspace.assert_called_once()
        self.db.close.assert_called_once()
        self.assertNotIn('window.setTimeout(() => window.location.replace', self.request('/')[2])

    @patch('r3el.server.ControlServer.BatchControl.new_batch')
    def test_invalid_form_is_not_forwarded(self, new_batch):
        for values in ({'batch_size': '0'}, {'batch_size': '-1'}, {'batch_size': '1.5'}, {'batch_size': 'true'},
                       {'input_directory': 'relative'}, {'output_directory': ''}, {'extra': 'field'}):
            with self.subTest(values=values):
                self.assertEqual(self.post_batch(**values)[0], 400)
        self.assertEqual(self.request('/batches', 'POST', 'batch_size=5&batch_size=10',
                                     {'Content-Type': 'application/x-www-form-urlencoded'})[0], 400)
        new_batch.assert_not_called()

    @patch('r3el.server.ControlServer.BatchControl.new_batch')
    def test_busy_and_missing_model_have_template_feedback(self, new_batch):
        new_batch.return_value = {'status': DMessage.BUSY}
        status, _, body = self.post_batch(input_directory='/tmp/<input>')
        self.assertEqual(status, 409)
        self.assertIn('already running', body)
        self.assertIn('/tmp/&lt;input&gt;', body)
        new_batch.return_value = {'status': DMessage.ERROR, 'error': {'code': DMessage.NOT_CONFIGURED}}
        self.assertEqual(self.post_batch()[0], 503)

    @patch('r3el.server.ControlServer.BatchControl.new_batch', side_effect=zmq.Again)
    def test_uncertain_acceptance_is_not_retried(self, new_batch):
        with self.assertLogs(level='ERROR'):
            status, _, body = self.post_batch()
        self.assertEqual(status, 503)
        self.assertIn('request may have reached the server', body)
        new_batch.assert_called_once()

    @patch('r3el.server.ControlServer.BatchControl.new_batch')
    def test_cross_origin_form_is_not_forwarded(self, new_batch):
        status, _, _ = self.request('/batches', 'POST', '', {'Origin': 'http://other-host'})
        self.assertEqual(status, 403)
        new_batch.assert_not_called()

    def test_logo_is_served_without_database(self):
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request('GET', '/static/r3el.png')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader('Content-Type'), 'image/png')
            self.assertEqual(response.read(),
                             (Path(__file__).resolve().parents[1] / 'pages/images/r3el.png').read_bytes())
        finally:
            connection.close()
        self.factory.assert_not_called()

    def test_list_escapes_content_and_closes_connection(self):
        status, headers, body = self.request('/events')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(int(headers['Content-Length']), len(body.encode()))
        self.assertIn('R3el Control', body)
        self.assertIn('item_completed', body)
        self.assertIn('🎬', body)
        self.assertNotIn('<script>alert(1)</script>', body)
        self.assertIn('&lt;script&gt;', body)
        self.assertIn('/events/42', body)
        self.db.close.assert_called_once()

    def test_filters_reach_database_before_limit_and_refresh_is_retained(self):
        status, _, body = self.request('/events?category=Batch&subcategory=BatchIdentification&refresh=5')
        self.assertEqual(status, 200)
        sql, params = self.db.query.call_args.args
        self.assertIn('e.category = %s AND e.subcategory = %s', sql)
        self.assertEqual(params, ('Batch', 'BatchIdentification', 500))
        self.assertIn('http-equiv="refresh" content="5"', body)
        self.assertIn('value="BatchIdentification" selected', body)

    def test_bad_filters_are_client_errors(self):
        for query in ('category=Unknown', 'category=Identification', 'subcategory=Unknown', 'category=Server&subcategory=Tool',
                      'category=Server&name=tool_received', 'subcategory=BatchIdentification&name=tool_received',
                      'category=Server&category=Batch', 'refresh=-1', 'other=value',
                      'name=unknown', 'name=tool_started&name=tool_received'):
            with self.subTest(query=query):
                self.assertEqual(self.request('/events?' + query)[0], 400)
        self.db.query.assert_not_called()

    def test_event_filter_applies_before_limit_with_other_filters(self):
        status, _, body = self.request('/events?category=Prompt&subcategory=SubmissionHandler&name=tool_received&refresh=30')
        self.assertEqual(status, 200)
        sql, params = self.db.query.call_args.args
        self.assertIn('e.name = %s', sql)
        self.assertLess(sql.index('e.name = %s'), sql.index('LIMIT %s'))
        self.assertEqual(params, ('Prompt', 'SubmissionHandler', 'tool_received', 500))
        self.assertIn('value="tool_received" selected', body)
        self.assertIn('value="submission_accepted"', body)

    def test_event_selection_fills_missing_parents(self):
        for query in ('name=tool_received', 'category=Prompt&name=tool_received',
                      'subcategory=SubmissionHandler&name=tool_received'):
            with self.subTest(query=query):
                status, _, body = self.request('/events?' + query)
                self.assertEqual(status, 200)
                self.assertEqual(self.db.query.call_args.args[1],
                                 ('Prompt', 'SubmissionHandler', 'tool_received', 500))
                for choice in ('Prompt', 'SubmissionHandler', 'tool_received'):
                    self.assertIn(f'value="{choice}" selected', body)

    def test_dropdowns_follow_selected_branch(self):
        for query, expected_subcategories, expected_events in (
            ('category=Batch', {'Lifecycle', 'Discovery', 'BatchIdentification'},
             {'batch_started', 'batch_resumed', 'batch_completed', 'batch_failed', 'batch_cancelled', 'batch_stop_requested', 'files_retrieved', 'item_started', 'item_completed'}),
            ('category=Batch&subcategory=BatchIdentification',
             {'Lifecycle', 'Discovery', 'BatchIdentification'}, {'item_started', 'item_completed'}),
            ('category=Prompt&subcategory=ToolConversation',
             {'ToolConversation', 'SubmissionHandler', 'LLMPrompt'}, {'attempt_started', 'attempt_failed', 'attempt_cancelled', 'reply_received', 'tool_started', 'tool_completed'}),
            ('category=Prompt&subcategory=SubmissionHandler',
             {'ToolConversation', 'SubmissionHandler', 'LLMPrompt'}, {'tool_received', 'submission_accepted', 'submission_rejected'}),
            ('category=Prompt&subcategory=LLMPrompt',
             {'ToolConversation', 'SubmissionHandler', 'LLMPrompt'}, {'prompt_sent'}),
            ('category=TMDB', {'Search', 'Result'}, {'tmdb_search', 'tmdb_result'}),
            ('category=TMDB&subcategory=Search', {'Search', 'Result'}, {'tmdb_search'}),
            ('category=TMDB&subcategory=Result', {'Search', 'Result'}, {'tmdb_result'}),
            ('category=File', {'Move', 'Delete'}, {'file_move', 'file_delete'}),
            ('category=Artifact', {'Download'}, {'artifact_download'}),
            ('category=DB&subcategory=Create+Record', {'Create Record'}, {'db_create_record'}),
            ('subcategory=Lifecycle',
             {'Lifecycle', 'Discovery', 'BatchIdentification', 'ToolConversation', 'SubmissionHandler', 'LLMPrompt', 'Search', 'Result', 'Move', 'Delete', 'Download', 'Create Record'},
             {'started', 'stopped', 'batch_started', 'batch_resumed', 'batch_completed', 'batch_failed', 'batch_cancelled', 'batch_stop_requested'}),
        ):
            with self.subTest(query=query):
                status, _, body = self.request('/events?' + query)
                self.assertEqual(status, 200)
                for select_id, expected in (('subcategory', expected_subcategories),
                                            ('event-name', expected_events)):
                    options = re.search(r'<select[^>]*id="' + select_id + r'"[^>]*>(.*?)</select>',
                                        body, re.S).group(1)
                    self.assertEqual(set(re.findall(r'<option value="([^\"]+)"', options)), expected)

    def test_reply_detail_shows_formatted_reasoning_and_json(self):
        self.event['name'] = 'reply_received'
        self.event['content'] = json.dumps({'context': {'filename': 'Film.mkv'}, 'data': json.dumps({
            'choices': [{'message': {'reasoning_content': '**Film**\n\n- First reason'}}],
        })})
        status, _, body = self.request('/events/42')
        self.assertEqual(status, 200)
        self.assertIn('<strong>Film</strong>', body)
        self.assertIn('<li>First reason</li>', body)
        self.assertLess(body.index('<strong>Film</strong>'), body.index('<h2>JSON</h2>'))
        self.assertIn('reasoning_content', body)

    def test_detail_has_full_content_and_parent_link(self):
        self.event['content'] = 'Long message\n' + 'x' * 2500
        status, _, body = self.request('/events/42')
        self.assertEqual(status, 200)
        self.assertIn('x' * 2500, body)
        self.assertIn('/events/41', body)
        self.assertIn('item-123', body)
        self.assertEqual(self.db.query.call_args.args[1], (42,))
        self.db.close.assert_called_once()

    def test_empty_log_and_missing_event(self):
        self.db.query.return_value = []
        self.assertIn('No events match these filters.', self.request('/events')[2])
        self.assertEqual(self.request('/events/42')[0], 404)
        self.assertEqual(self.request('/events/18446744073709551616')[0], 404)
        self.assertEqual(self.request('/unknown')[0], 404)

    def test_health_does_not_open_database(self):
        status, _, body = self.request('/health')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['service'], 'r3el-control')
        self.factory.assert_not_called()

    def test_database_failure_returns_503_without_exposing_details(self):
        self.db.query.side_effect = pymysql.OperationalError('private database details')
        with self.assertLogs(level='ERROR'):
            status, _, body = self.request('/events')
        self.assertEqual(status, 503)
        self.assertIn('Event log unavailable', body)
        self.assertNotIn('private database details', body)
        self.db.close.assert_called_once()

    def test_connection_failure_returns_503(self):
        self.factory.side_effect = pymysql.OperationalError('connection refused')
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.request('/events')[0], 503)

    def test_each_request_owns_a_new_connection(self):
        first, second = Mock(), Mock()
        first.query.return_value = second.query.return_value = []
        self.factory.side_effect = [first, second]
        self.assertEqual(self.request('/events')[0], 200)
        self.assertEqual(self.request('/events')[0], 200)
        first.close.assert_called_once()
        second.close.assert_called_once()


class InstalledControlTests(unittest.TestCase):
    def test_deployed_modules_and_templates_work_outside_checkout(self):
        root = Path(__file__).resolve().parents[1]
        installer = (root / 'scripts/install-services.sh').read_text()
        modules = re.search(r'modules=\((.*?)\n\)', installer, re.S).group(1).split()
        with TemporaryDirectory() as temporary:
            stage = Path(temporary)
            for module in modules:
                target = stage / 'r3el' / module
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / 'r3el' / module, target)
            result = subprocess.run([sys.executable, '-B', '-m', 'r3el.server.ControlServer', '--help'],
                                    cwd=stage, capture_output=True, text=True, check=True)
            self.assertIn('--port', result.stdout)
            render = """from r3el.server.EventPages import EventPages
page = EventPages().render('control.html', workspace=None, refresh=0)
assert b'Media Directory' in page
from r3el.entity.MediaFile import MediaFile
from r3el.entity.MediaFileBatch import MediaFileBatch
batch = MediaFileBatch('batch-1', 5, '/tmp', files=[MediaFile('file-1', '/tmp/Film.mkv')])
page = EventPages().render('control.html', workspace=batch, refresh=0)
assert b'Film.mkv' in page and b'Pending' in page and b'type="button" disabled' in page
assert b'Workspace unavailable' in EventPages().render('workspace_error.html', refresh=0)
from pathlib import Path
assert Path('r3el/server/static/r3el.png').is_file()
page = EventPages().render('events.html', events=[], category=None, subcategory=None, name=None, refresh=0)
assert b'No events match these filters.' in page
from datetime import datetime
event = dict(event_id=1, occurred_at=datetime(2026, 9, 20), log_level='INFO', category='Server',
             subcategory='Lifecycle', name='started', source_name='R3elServer', content='Started.')
page = EventPages().render('events.html', events=[event], category=None, subcategory=None, name=None, refresh=0)
assert b'<pre>Started.</pre>' in page
"""
            subprocess.run([sys.executable, '-B', '-c', render], cwd=stage, check=True)
