"""Run with R3EL_TEST_DB=1 as a MariaDB socket administrator.

Integration checks create and remove their own database and account.
"""

import os
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fake_llm import FakeLLM
import secrets
import signal
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import pymysql

from r3el.activity.EventReport import EventReport
from r3el.activity.EventSchema import EventSchema
from r3el.constants.DEventCategory import DEventCategory
from r3el.entity.EventCategory import EventCategory
from r3el.entity.LogEvent import LogEvent
from r3el.interface.DbMgr import DbMgr
from r3el.interface.EventLogDb import EventLogDb


class ReportFilterTests(unittest.TestCase):
    def test_invalid_external_filters_do_not_reach_database(self):
        events = Mock()
        report = EventReport(events)
        for category, subcategory in [(None, 'Unknown'), ('Unknown', None), ('Server', 'Unknown')]:
            with self.subTest(category=category, subcategory=subcategory):
                with self.assertRaises(ValueError):
                    report.recent(category, subcategory)
        events.recent.assert_not_called()

    def test_hierarchy_supplies_filters(self):
        self.assertEqual(DEventCategory.CHILDREN['Server'], ('Lifecycle',))
        events = Mock()
        EventReport(events).recent('Server', 'Lifecycle')
        events.recent.assert_called_once_with(category='Server', subcategory='Lifecycle', name=None)


@unittest.skipUnless(os.environ.get('R3EL_TEST_DB') == '1', 'requires MariaDB socket administrator')
class EventDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.name = 'r3el_test_' + uuid4().hex[:16]
        password = secrets.token_hex(32)
        cls.admin = pymysql.connect(unix_socket='/run/mysqld/mysqld.sock', user='root', autocommit=True)
        cls.addClassCleanup(cls.admin.close)
        with cls.admin.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE `{cls.name}`')
        cls.addClassCleanup(cls.drop_database)
        with cls.admin.cursor() as cursor:
            cursor.execute('CREATE USER %s@localhost IDENTIFIED BY %s', (cls.name, password))
        cls.addClassCleanup(cls.drop_user)
        with cls.admin.cursor() as cursor:
            # Escape underscores: database grants treat them as wildcards.
            database_pattern = cls.name.replace('_', r'\_')
            cursor.execute(f'GRANT ALL ON `{database_pattern}`.* TO %s@localhost', (cls.name,))
        environment = patch.dict(os.environ, {
            'DB_HOST': '127.0.0.1', 'DB_PORT': '3306', 'DB_USER': cls.name,
            'DB_NAME': cls.name, 'DB_PASSWORD': password,
        })
        environment.start()
        cls.addClassCleanup(environment.stop)
        cls.db = DbMgr()
        cls.addClassCleanup(cls.db.close)
        # A connection must not create application tables.
        assert cls.db.query('SHOW TABLES') == []
        EventSchema(cls.db).apply()
        EventSchema(cls.db).apply()

    @classmethod
    def drop_database(cls):
        with cls.admin.cursor() as cursor:
            cursor.execute(f'DROP DATABASE `{cls.name}`')

    @classmethod
    def drop_user(cls):
        with cls.admin.cursor() as cursor:
            cursor.execute('DROP USER %s@localhost', (cls.name,))

    def setUp(self):
        self.events = EventLogDb(self.db)

    def tearDown(self):
        self.db.execute('DELETE FROM events ORDER BY event_id DESC')

    def event(self, **values):
        defaults = dict(classification=DEventCategory.Server.LIFECYCLE,
                        name='test', message="A film's title 🎬\nSecond line")
        defaults.update(values)
        return LogEvent(**defaults)

    def test_round_trip_parent_and_separate_reader(self):
        parent = self.events.record(self.event(process_id='workflow'))
        child = self.events.record(self.event(parent_event_id=parent, process_id='workflow'))
        reader = DbMgr()
        try:
            row = EventLogDb(reader).get(child)
            self.assertEqual(row['content'], self.event().message)
            self.assertEqual((row['category'], row['subcategory']), ('Server', 'Lifecycle'))
            self.assertEqual(row['parent_event_id'], parent)
            self.assertEqual(row['process_id'], 'workflow')
        finally:
            reader.close()

    def test_message_failure_rolls_back_metadata(self):
        with self.assertRaises(pymysql.IntegrityError):
            self.events.record(self.event(message=None))
        self.assertEqual(self.db.query('SELECT * FROM events'), [])

    def test_invalid_category_relationship_rejected(self):
        with self.assertRaises(pymysql.IntegrityError):
            self.events.record(self.event(classification=EventCategory('Other', 'Lifecycle')))
        self.assertEqual(self.db.query('SELECT * FROM events'), [])

    def test_filter_precedes_limit_and_parameters_are_bound(self):
        self.db.execute("INSERT INTO event_categories VALUES ('Other', 'Noise')")
        wanted = self.events.record(self.event())
        self.events.record(self.event(classification=EventCategory('Other', 'Noise')))
        rows = self.events.recent(category='Server', subcategory='Lifecycle', limit=1)
        self.assertEqual([row['event_id'] for row in rows], [wanted])
        self.assertEqual(self.events.recent(category="Server' OR 1=1 --"), [])

    def run_batch(self, root, url, size=3):
        return subprocess.Popen([
            sys.executable, '-B', '-u', '-m', 'r3el.server.R3elServer',
            '--film-dir', str(root), '--batch-size', str(size), '--llm-url', url,
            '--zmq-endpoint', 'tcp://127.0.0.1:*',
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_one_batch_real_http_mcp_zmq_and_database(self):
        good = {'title': 'Example', 'year': 2001, 'confidence': 0.9}
        # A malformed reply and server correction, an exhausted file, then success.
        submissions = ['{"choices": []}', {**good, 'title': ''}, good] + [{**good, 'year': 'bad'}] * 3 + [good]
        with TemporaryDirectory() as directory, FakeLLM(submissions) as llm:
            root = Path(directory)
            for name in ('a.mkv', 'b.mkv', 'c.mkv', 'd.mkv'):
                (root / name).write_text('untouched')
            (root / 'nested').mkdir()
            (root / 'nested' / 'hidden.mkv').touch()
            with self.run_batch(root, llm.url) as process:
                try:
                    output, error = process.communicate(timeout=75)
                except BaseException:
                    process.kill()
                    process.wait()
                    raise
            self.assertEqual(process.returncode, 0, error)
            self.assertEqual(llm.errors, [])
            results = json.loads(output.splitlines()[1])
            self.assertEqual([r['filename'] for r in results], ['a.mkv', 'b.mkv', 'c.mkv'])
            self.assertEqual([r['status'] for r in results], ['identified', 'unresolved_llm', 'identified'])
            self.assertEqual([r['attempts'] for r in results], [3, 3, 1])
            self.assertEqual(len(llm.requests), 7)
            self.assertTrue(any(m['role'] == 'tool' for m in llm.requests[2]['messages']))
            schema = llm.requests[0]['tools'][0]['function']['parameters']
            self.assertEqual(set(schema['required']), {'title', 'year', 'confidence'})
            self.assertEqual(schema['properties']['year']['type'], 'integer')
            for name in ('a.mkv', 'b.mkv', 'c.mkv', 'd.mkv'):
                self.assertEqual((root / name).read_text(), 'untouched')
        rows = self.events.recent()
        received = [r for r in rows if r['name'] == 'tool_received']
        self.assertEqual(len(received), 6)
        for row in received:
            context = json.loads(row['content'])['context']
            self.assertTrue(context['batch_id'])
            self.assertEqual(row['process_id'], context['item_id'])
            parent = self.events.get(row['parent_event_id'])
            self.assertEqual(parent['name'], 'attempt_started')
            self.assertEqual(json.loads(parent['content'])['context']['attempt_id'], context['attempt_id'])
        self.assertEqual(rows[0]['name'], 'stopped')
        self.assertEqual(sum(r['name'] == 'batch_completed' for r in rows), 1)

    def test_empty_batch_stops_without_contacting_llm(self):
        with TemporaryDirectory() as directory:
            with self.run_batch(directory, 'http://127.0.0.1:1') as process:
                output, error = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, error)
            self.assertEqual(json.loads(output.splitlines()[1]), [])

    def test_operational_error_aborts_without_retry(self):
        good = {'title': 'Example', 'year': 2001, 'confidence': 0.9}
        with TemporaryDirectory() as directory, FakeLLM([good], status=503) as llm:
            Path(directory, 'a.mkv').touch()
            with self.run_batch(directory, llm.url) as process:
                output, error = process.communicate(timeout=15)
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(len(llm.requests), 1)
        names = [row['name'] for row in self.events.recent()]
        self.assertIn('batch_failed', names)
        self.assertNotIn('item_completed', names)

    def test_lifecycle_records_start_and_stop_on_signals(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            good = {'title': 'Example', 'year': 2001, 'confidence': 0.9}
            with TemporaryDirectory() as directory, FakeLLM([good], block=True) as llm:
                Path(directory, 'a.mkv').touch()
                process = self.run_batch(directory, llm.url)
                try:
                    self.assertTrue(llm.called.wait(10), 'server did not call the model')
                    process.send_signal(sig)
                    output, error = process.communicate(timeout=10)
                    self.assertEqual(process.returncode, 0, error)
                    self.assertIn('R3el server stopped.', output)
                    rows = self.events.recent(category='Server', limit=2)
                    self.assertEqual([row['name'] for row in rows], ['stopped', 'started'])
                    self.assertEqual(rows[0]['parent_event_id'], rows[1]['event_id'])
                    self.assertIn('batch_cancelled', [r['name'] for r in self.events.recent()])
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                    process.stdout.close()
                    process.stderr.close()


if __name__ == '__main__':
    unittest.main()
