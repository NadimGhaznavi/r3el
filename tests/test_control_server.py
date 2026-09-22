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
from threading import Thread
from urllib.parse import urlencode

import zmq

from r3el.constants.DMessage import DMessage
from r3el.entity.BatchRequest import BatchRequest
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
        self.db = Mock()
        self.factory.return_value = self.db
        self.event = dict(event_id=42, occurred_at=datetime(2026, 9, 20, 14, 30),
                          category='Identification', subcategory='Result', name='item_completed',
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

    def test_empty_workspace_shows_batch_controls(self):
        status, _, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn('Media Directory', body)
        self.assertIn('value="/exports/disk1/archive/film"', body)
        self.assertIn('value="5"', body)
        self.assertIn('value="10" selected', body)
        self.assertIn('type="submit" aria-describedby="batch-note">New Batch', body)
        self.assertIn('/static/r3el.png', body)
        self.assertIn('Last updated:', body)
        self.assertNotIn('http-equiv="refresh"', body)
        self.workspace.assert_called_once()
        self.db.close.assert_called_once()

    def test_occupied_workspace_shows_ordered_filenames_and_statuses_without_buttons(self):
        self.workspace.return_value = MediaFileBatch(
            'batch-1', 5, '/tmp/input',
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
                self.assertNotIn('<button', body)
                self.assertNotIn('<form', body)
                self.assertIn('http-equiv="refresh" content="5"', body)
                header = re.search(r'<header.*?</header>', body, re.S).group(0)
                self.assertRegex(header, r'Last updated: <time datetime="[^"]+">[0-9-]+ [0-9:]+ UTC</time>')

    def test_retained_batch_with_no_files_still_hides_new_batch(self):
        self.workspace.return_value = MediaFileBatch('batch-1', 5, '/tmp/input')
        status, _, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn('No files in this batch.', body)
        self.assertNotIn('<button', body)

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
    def test_post_feedback_for_current_batch_has_no_button_or_post_refresh(self, new_batch):
        self.workspace.return_value = MediaFileBatch('batch-1', 5, '/tmp/input')
        new_batch.return_value = {'status': DMessage.BUSY}
        status, _, body = self.post_batch()
        self.assertEqual(status, 409)
        self.assertIn('Current batch files', body)
        self.assertNotIn('<button', body)
        self.assertNotIn('http-equiv="refresh"', body)

    def post_batch(self, **values):
        fields = dict(input_directory='/tmp/input', output_directory='/tmp/output', batch_size='5')
        fields.update(values)
        return self.request('/batches', 'POST', urlencode(fields),
                            {'Content-Type': 'application/x-www-form-urlencoded'})

    @patch('r3el.server.ControlServer.BatchControl.new_batch')
    def test_new_batch_forwards_parameters_and_redirects(self, new_batch):
        new_batch.return_value = {'status': DMessage.ACCEPTED}
        status, headers, _ = self.post_batch()
        self.assertEqual(status, 303)
        new_batch.assert_called_once_with(BatchRequest('/tmp/input', '/tmp/output', 5))
        self.assertEqual(headers['Location'], '/?result=accepted')
        self.assertIn('Batch accepted.', self.request(headers['Location'])[2])
        new_batch.assert_called_once()
        self.workspace.assert_called_once()
        self.db.close.assert_called_once()

    @patch('r3el.server.ControlServer.BatchControl.new_batch')
    def test_invalid_form_is_not_forwarded(self, new_batch):
        for values in ({'batch_size': '6'}, {'batch_size': 'true'},
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
        status, _, body = self.request('/events?category=Identification&subcategory=Result&refresh=5')
        self.assertEqual(status, 200)
        sql, params = self.db.query.call_args.args
        self.assertIn('e.category = %s AND e.subcategory = %s', sql)
        self.assertEqual(params, ('Identification', 'Result', 500))
        self.assertIn('http-equiv="refresh" content="5"', body)
        self.assertIn('value="Result" selected', body)

    def test_bad_filters_are_client_errors(self):
        for query in ('category=Unknown', 'subcategory=Unknown', 'category=Server&subcategory=Tool',
                      'category=Server&name=tool_received', 'subcategory=Result&name=tool_received',
                      'category=Server&category=Batch', 'refresh=-1', 'other=value',
                      'name=unknown', 'name=tool_started&name=tool_received'):
            with self.subTest(query=query):
                self.assertEqual(self.request('/events?' + query)[0], 400)
        self.db.query.assert_not_called()

    def test_event_filter_applies_before_limit_with_other_filters(self):
        status, _, body = self.request('/events?category=Identification&subcategory=Tool&name=tool_received&refresh=30')
        self.assertEqual(status, 200)
        sql, params = self.db.query.call_args.args
        self.assertIn('e.name = %s', sql)
        self.assertLess(sql.index('e.name = %s'), sql.index('LIMIT %s'))
        self.assertEqual(params, ('Identification', 'Tool', 'tool_received', 500))
        self.assertIn('value="tool_received" selected', body)
        self.assertIn('value="tool_started"', body)

    def test_event_selection_fills_missing_parents(self):
        for query in ('name=tool_received', 'category=Identification&name=tool_received',
                      'subcategory=Tool&name=tool_received'):
            with self.subTest(query=query):
                status, _, body = self.request('/events?' + query)
                self.assertEqual(status, 200)
                self.assertEqual(self.db.query.call_args.args[1],
                                 ('Identification', 'Tool', 'tool_received', 500))
                for choice in ('Identification', 'Tool', 'tool_received'):
                    self.assertIn(f'value="{choice}" selected', body)

    def test_dropdowns_follow_selected_branch(self):
        for query, expected_subcategories, expected_events in (
            ('category=Batch', {'Lifecycle', 'Discovery'},
             {'batch_started', 'batch_resumed', 'batch_completed', 'batch_failed', 'batch_cancelled', 'files_retrieved'}),
            ('category=Identification&subcategory=Result',
             {'Conversation', 'Tool', 'Validation', 'Result'}, {'item_completed'}),
            ('subcategory=Lifecycle',
             {'Lifecycle', 'Discovery', 'Conversation', 'Tool', 'Validation', 'Result'},
             {'started', 'stopped', 'batch_started', 'batch_resumed', 'batch_completed', 'batch_failed', 'batch_cancelled'}),
        ):
            with self.subTest(query=query):
                status, _, body = self.request('/events?' + query)
                self.assertEqual(status, 200)
                for select_id, expected in (('subcategory', expected_subcategories),
                                            ('event-name', expected_events)):
                    options = re.search(r'<select[^>]*id="' + select_id + r'"[^>]*>(.*?)</select>',
                                        body, re.S).group(1)
                    self.assertEqual(set(re.findall(r'<option value="([^\"]+)"', options)), expected)

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
page = EventPages().render('control.html', workspace=batch, refresh=5)
assert b'Film.mkv' in page and b'Pending' in page and b'<button' not in page
assert b'Workspace unavailable' in EventPages().render('workspace_error.html', refresh=0)
from pathlib import Path
assert Path('r3el/server/static/r3el.png').is_file()
page = EventPages().render('events.html', events=[], category=None, subcategory=None, name=None, refresh=0)
assert b'No events match these filters.' in page
event = dict(event_id=1, occurred_at='2026-09-20', log_level='INFO', category='Server',
             subcategory='Lifecycle', name='started', source_name='R3elServer', content='Started.')
page = EventPages().render('events.html', events=[event], category=None, subcategory=None, name=None, refresh=0)
assert b'<pre>Started.</pre>' in page
"""
            subprocess.run([sys.executable, '-B', '-c', render], cwd=stage, check=True)
