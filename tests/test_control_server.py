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
        self.db = Mock()
        self.factory.return_value = self.db
        self.event = dict(event_id=42, occurred_at=datetime(2026, 9, 20, 14, 30),
                          category='Identification', subcategory='Result', name='item_completed',
                          log_level='INFO', source_name='BatchIdentification', process_id='item-123',
                          parent_event_id=41, app_version='0.1.0',
                          content=json.dumps({'title': '<script>alert(1)</script> 🎬'}))
        self.db.query.return_value = [self.event]

    def request(self, path):
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request('GET', path)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode()
        finally:
            connection.close()

    def test_list_escapes_content_and_closes_connection(self):
        status, headers, body = self.request('/')
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
        for query in ('category=Unknown', 'subcategory=Result', 'category=Server&subcategory=Tool',
                      'category=Server&category=Batch', 'refresh=-1', 'other=value'):
            with self.subTest(query=query):
                self.assertEqual(self.request('/?' + query)[0], 400)
        self.db.query.assert_not_called()

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
        self.assertIn('No events match these filters.', self.request('/')[2])
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
            status, _, body = self.request('/')
        self.assertEqual(status, 503)
        self.assertIn('Event log unavailable', body)
        self.assertNotIn('private database details', body)
        self.db.close.assert_called_once()

    def test_connection_failure_returns_503(self):
        self.factory.side_effect = pymysql.OperationalError('connection refused')
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.request('/')[0], 503)

    def test_each_request_owns_a_new_connection(self):
        first, second = Mock(), Mock()
        first.query.return_value = second.query.return_value = []
        self.factory.side_effect = [first, second]
        self.assertEqual(self.request('/')[0], 200)
        self.assertEqual(self.request('/')[0], 200)
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
page = EventPages().render('events.html', events=[], category=None, subcategory=None, refresh=0)
assert b'No events match these filters.' in page
"""
            subprocess.run([sys.executable, '-B', '-c', render], cwd=stage, check=True)
