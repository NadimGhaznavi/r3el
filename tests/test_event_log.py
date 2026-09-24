"""Run with R3EL_TEST_DB=1 as a MariaDB socket administrator.

Integration checks create and remove their own database and account.
"""

import os
import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from fake_llm import FakeLLM
import secrets
import signal
import subprocess
import sys
import unittest
import time

import zmq

from r3el.constants.DMessage import DMessage
from r3el.entity.BatchRequest import BatchRequest
from r3el.entity.BatchStopped import BatchStopped
from r3el.interface.BatchControl import BatchControl
from r3el.zmq.ZMQClient import ZMQClient
from r3el.zmq.ZMQMsg import ZMQMsg
from unittest.mock import Mock, patch
from uuid import uuid4

import pymysql

from r3el.activity.EventReport import EventReport
from r3el.activity.EventSchema import EventSchema
from r3el.activity.WorkspaceSchema import WorkspaceSchema
from r3el.activity.CatalogueSchema import CatalogueSchema
from r3el.app.BatchMatching import BatchMatching
from r3el.entity.CatalogueMovie import CatalogueMovie, MovieCredit
from r3el.entity.MovieFiles import MovieFiles
from r3el.interface.CatalogueDb import CatalogueDb
from r3el.constants.DEventCategory import DEventCategory
from r3el.constants.DEventName import DEventName
from r3el.activity.EventWriter import EventWriter
from r3el.entity.EventCategory import EventCategory
from r3el.entity.LogEvent import LogEvent
from r3el.entity.MediaFile import MediaFile, MediaFileIssue, MediaFileState
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState
from r3el.entity.Identification import Identification
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.entity.TMDBReference import TMDBGenre, TMDBLanguage, TMDBReference
from r3el.activity.TMDBReferenceSchema import TMDBReferenceSchema
from r3el.interface.TMDBReferenceDb import TMDBReferenceDb
from r3el.interface.WorkspaceDb import WorkspaceActionConflict
from r3el.interface.DbMgr import DbMgr
from r3el.interface.EventLogDb import EventLogDb
from r3el.interface.WorkspaceDb import WorkspaceDb


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
        WorkspaceSchema(cls.db).apply()
        WorkspaceSchema(cls.db).apply()
        CatalogueSchema(cls.db).apply()
        CatalogueSchema(cls.db).apply()

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
        for table in ('movie_artwork', 'movie_files', 'movie_credits', 'movie_genres', 'movies', 'people'):
            self.db.execute(f'DELETE FROM {table}')
        self.db.execute('DELETE FROM tmdb_movie_genres WHERE genre_id = 99999')
        self.db.execute('DELETE FROM media_file_batches')
        self.db.execute('DELETE FROM events ORDER BY event_id DESC')

    def assert_batch_equal(self, actual, expected):
        self.assertEqual(replace(actual, files=[replace(item, updated_at=None) for item in actual.files]), expected)

    def workspace_batch(self):
        return MediaFileBatch(str(uuid4()), 10, '/tmp/films',
                              files=[MediaFile(str(uuid4()), '/tmp/films/a.mkv')])

    def test_stop_request_is_durable_and_does_not_wait_for_processing_lock(self):
        workspace = WorkspaceDb(self.db)
        batch = self.workspace_batch()
        workspace.create(batch, self.event(), self.event())
        reader = DbMgr()
        try:
            with workspace.processing(), workspace.matching():
                WorkspaceDb(reader).request_stop(batch.id)
                WorkspaceDb(reader).request_stop(batch.id)
                with self.assertRaises(BatchStopped):
                    workspace.check_stop(batch.id)
            self.assertTrue(WorkspaceDb(reader).snapshot().stop_requested)
        finally:
            reader.close()
        self.assertEqual(len(self.events.recent(name='batch_stop_requested')), 1)
        WorkspaceSchema(self.db).apply()
        self.assertTrue(workspace.load().stop_requested)

    def test_stop_rejects_idle_and_stale_batches(self):
        workspace = WorkspaceDb(self.db)
        with self.assertRaises(WorkspaceActionConflict):
            workspace.request_stop('missing')
        batch = self.workspace_batch()
        batch.state = MediaFileBatchState.MATCHING_COMPLETED
        workspace.create(batch, self.event(), self.event())
        with self.assertRaises(WorkspaceActionConflict):
            workspace.request_stop(batch.id)
        workspace.request_stop(batch.id, matching=True)
        self.assertTrue(workspace.load().stop_requested)

    def test_file_updated_timestamp_is_saved_in_utc_and_preserved_by_upgrade(self):
        workspace = WorkspaceDb(self.db)
        batch = self.workspace_batch()
        before = self.db.query('SELECT UTC_TIMESTAMP(6) AS now')[0]['now']
        workspace.create(batch, self.event(), self.event())
        saved = workspace.load().files[0]
        self.assertGreaterEqual(saved.updated_at.replace(tzinfo=None), before)
        self.assertEqual(saved.updated_at.utcoffset().total_seconds(), 0)
        self.db.execute("UPDATE media_files SET updated_at = '2000-01-01 00:00:00' WHERE file_id = %s", (saved.id,))
        saved.state = MediaFileState.IDENTIFIED
        saved.identification = Identification('Movie', 2020, 10)
        workspace.save_file(batch.id, saved, self.event())
        updated = workspace.load().files[0].updated_at
        self.assertGreaterEqual(updated.replace(tzinfo=None), before)
        WorkspaceSchema(self.db).apply()
        self.assertEqual(workspace.load().files[0].updated_at, updated)

    def catalogue_movie(self):
        return CatalogueMovie(42, 'Film', 'Original', date(2020, 2, 3), 'Overview', 120,
            '/poster.jpg', '/backdrop.jpg', 'tt123', Decimal('7.123'), 10,
            [TMDBGenre(99999, 'Test genre')], [
                MovieCredit(7, 'Person', 'Actor', 'Hero', 0),
                MovieCredit(7, 'Person', 'Actor', 'Twin', 1),
                *[MovieCredit(7, 'Person', role) for role in
                  ('Director', 'Producer', 'Executive Producer', 'Co-Producer')]])

    def test_catalogue_normalized_refresh_and_durable_file_links(self):
        movie = self.catalogue_movie()
        catalogue = CatalogueDb(self.db)
        with self.db.transaction():
            catalogue.save_in_transaction(movie, MovieFiles('/films/a.mkv', '/films/poster.jpg', '/films/backdrop.jpg'))
        with self.db.transaction():
            catalogue.save_in_transaction(movie, MovieFiles('/films/a.mkv', '/films/poster.jpg', '/films/backdrop.jpg'))
            catalogue.save_in_transaction(movie, MovieFiles('/films/b.mkv'))
        self.assertEqual(len(self.db.query('SELECT * FROM movies')), 1)
        self.assertEqual(len(self.db.query('SELECT * FROM people')), 1)
        self.assertEqual(len(self.db.query('SELECT * FROM movie_credits')), 6)
        self.assertEqual(len(self.db.query('SELECT * FROM movie_files')), 2)
        self.assertEqual(self.db.query('SELECT release_year FROM movies')[0]['release_year'], 2020)
        self.assertEqual(self.db.query('SELECT rating FROM movies')[0]['rating'], Decimal('7.123'))
        updated = replace(movie, title='Updated', genres=[], credits=[movie.credits[0]])
        with self.db.transaction():
            catalogue.save_in_transaction(updated, MovieFiles('/films/a.mkv'))
        self.assertEqual(self.db.query('SELECT title FROM movies')[0]['title'], 'Updated')
        self.assertEqual(len(self.db.query('SELECT * FROM movie_credits')), 1)
        self.assertEqual(self.db.query('SELECT * FROM movie_genres'), [])
        self.assertEqual(len(self.db.query('SELECT * FROM movie_files')), 2)

    def test_catalogue_checkpoint_rolls_back_and_survives_workspace_removal(self):
        workspace = WorkspaceDb(self.db)
        batch = self.workspace_batch()
        workspace.create(batch, self.event(), self.event())
        movie = self.catalogue_movie()
        result = TMDBMatch('Film', 2020, response={'total_results': 1, 'results': [{'id': 42}]},
                           catalogue_saved=True)
        files = MovieFiles('/output/Film (2020)/Film (2020).mkv', '/output/Film (2020)/poster.jpg')
        with self.assertRaises(pymysql.IntegrityError):
            workspace.save_catalogue(batch.id, batch.files[0].id, movie, result, self.event(message=None), files)
        self.assertEqual(self.db.query('SELECT * FROM movies'), [])
        self.assertEqual(self.db.query('SELECT * FROM people'), [])
        self.assertEqual(self.db.query('SELECT * FROM movie_files'), [])
        self.assertIsNone(workspace.load().files[0].tmdb_match)
        workspace.save_catalogue(batch.id, batch.files[0].id, movie, result, self.event(), files)
        self.assertTrue(workspace.load().files[0].tmdb_match.catalogue_saved)
        self.assertEqual(workspace.load().files[0].path, files.video)
        self.assertEqual(self.db.query('SELECT path FROM movie_artwork')[0]['path'], files.poster)
        with self.assertRaises(pymysql.IntegrityError):
            workspace.save_catalogue(batch.id, batch.files[0].id,
                replace(movie, title='Should roll back', credits=[]), result, self.event(message=None), files)
        self.assertEqual(self.db.query('SELECT title FROM movies')[0]['title'], 'Film')
        self.assertEqual(len(self.db.query('SELECT * FROM movie_credits')), 6)
        self.db.execute('DELETE FROM media_file_batches')
        self.assertEqual(len(self.db.query('SELECT * FROM movies')), 1)
        self.assertEqual(len(self.db.query('SELECT * FROM movie_files')), 1)

    @patch('r3el.app.BatchMatching.TMDB.from_environment')
    def test_catalogue_processing_moves_video_and_commits_final_path(self, factory):
        with TemporaryDirectory() as directory:
            source = Path(directory) / 'incoming.mkv'
            source.write_bytes(b'video')
            inode = source.stat().st_ino
            output = Path(directory) / 'chosen-output'
            batch = self.workspace_batch()
            batch.files[0].path = str(source)
            batch.files[0].state = MediaFileState.IDENTIFIED
            batch.files[0].identification = Identification('Film', 2020, 10)
            batch.state = MediaFileBatchState.IDENTIFICATION_COMPLETED
            batch.destination_directory = str(output)
            workspace = WorkspaceDb(self.db)
            workspace.create(batch, self.event(), self.event())
            workspace.save_file(batch.id, batch.files[0], self.event())
            factory.return_value.search.return_value = {'total_results': 1, 'results': [{'id': 42}]}
            factory.return_value.details.return_value = {
                'id': 42, 'title': 'Film', 'release_date': '2020-02-03',
                'genres': [], 'credits': {'cast': [], 'crew': []}}
            runner = BatchMatching(workspace, self.events.record)
            runner.run(batch.id)
            target = output / 'Film (2020)' / 'Film (2020).mkv'
            self.assertFalse(source.exists())
            self.assertEqual(target.stat().st_ino, inode)
            saved = workspace.load().files[0]
            self.assertEqual(saved.path, str(target))
            self.assertTrue(saved.tmdb_match.file_moved)
            self.assertEqual(self.db.query('SELECT path FROM movie_files')[0]['path'], str(target))
            runner.run(batch.id)
            factory.return_value.details.assert_called_once_with(42)
            saved = self.events.recent(category='DB', subcategory='Create Record')
            moved = self.events.recent(category='File', subcategory='Move')
            self.assertEqual(len(saved), 1)
            self.assertEqual(len(moved), 1)
            self.assertLess(saved[0]['event_id'], moved[0]['event_id'])
            self.assertEqual(json.loads(saved[0]['content'])['data']['movie_id'], 42)
            self.assertEqual(json.loads(moved[0]['content'])['data']['destination_path'], str(target))

    def test_workspace_creation_and_checkpoint_are_atomic(self):
        workspace = WorkspaceDb(self.db)
        batch = self.workspace_batch()
        with workspace.processing():
            with self.assertRaises(pymysql.IntegrityError):
                workspace.create(batch, self.event(), self.event(message=None))
            self.assertIsNone(workspace.load())
            self.assertEqual(self.events.recent(), [])
            batch.started_event_id = workspace.create(batch, self.event(), self.event())
            item = batch.files[0]
            item.state = MediaFileState.IDENTIFIED
            item.identification = Identification('Film 🎬', 2001, 9)
            item.attempts = 2
            item.action = MediaFileAction.APPROVE
            with self.assertRaises(pymysql.IntegrityError):
                workspace.save_file(batch.id, item, self.event(message=None))
            self.assertEqual(workspace.load().files[0].state, MediaFileState.PENDING)
            self.assertEqual(workspace.load().files[0].action, MediaFileAction.PENDING)
            self.assertEqual(len(self.events.recent()), 2)
            workspace.save_file(batch.id, item, self.event())
            with self.assertRaises(pymysql.IntegrityError):
                workspace.save_batch_state(batch.id, MediaFileBatchState.IDENTIFICATION_COMPLETED,
                                           self.event(message=None))
            self.assertEqual(workspace.load().state, MediaFileBatchState.PROCESSING)
        reader = DbMgr()
        try:
            restored = WorkspaceDb(reader).load()
            self.assert_batch_equal(restored, batch)
        finally:
            reader.close()

    def test_retry_checkpoint_is_atomic_and_upgrade_preserves_count(self):
        workspace = WorkspaceDb(self.db)
        batch = self.workspace_batch()
        batch.started_event_id = workspace.create(batch, self.event(), self.event())
        item = batch.files[0]
        item.state = MediaFileState.IDENTIFIED
        item.identification = Identification('Film', 2000, 10)
        item.retries = 2
        item.tmdb_match = TMDBMatch('Film', 2000, response={'total_results': 0, 'results': []},
                                    selection_pending=True)
        with self.assertRaises(pymysql.IntegrityError):
            workspace.save_file(batch.id, item, self.event(message=None))
        self.assertEqual(workspace.load().files[0].retries, 0)
        self.assertIsNone(workspace.load().files[0].tmdb_match)
        workspace.save_file(batch.id, item, self.event())
        WorkspaceSchema(self.db).apply()
        restored = workspace.load().files[0]
        self.assertEqual(restored.retries, 2)
        self.assertTrue(restored.pending)
        item.identification = Identification('Correct Film', 2000, 10)
        item.tmdb_match = None
        workspace.save_file(batch.id, item, self.event())
        self.assertEqual(replace(workspace.load().files[0], updated_at=None), item)

    def test_workspace_action_changes_persist_without_changing_identification(self):
        workspace = WorkspaceDb(self.db)
        batch = self.workspace_batch()
        batch.started_event_id = workspace.create(batch, self.event(), self.event())
        item = batch.files[0]
        with self.assertRaises(WorkspaceActionConflict):
            workspace.save_action(batch.id, item.id, MediaFileAction.APPROVE)
        item.state = MediaFileState.IDENTIFIED
        item.identification = Identification('Film', 2000, 10)
        item.action = MediaFileAction.APPROVE
        workspace.save_file(batch.id, item, self.event())
        for action in MediaFileAction:
            saved = workspace.save_action(batch.id, item.id, action)
            self.assertEqual(saved.files[0].action, action)
            self.assertEqual(saved.files[0].identification, item.identification)
            self.assertEqual(saved.files[0].state, MediaFileState.IDENTIFIED)
            self.assertEqual(workspace.snapshot().files[0].action, action)
        with self.assertRaises(WorkspaceActionConflict):
            workspace.save_action(str(uuid4()), item.id, MediaFileAction.IGNORE)
        with self.assertRaises(WorkspaceActionConflict):
            workspace.save_action(batch.id, str(uuid4()), MediaFileAction.IGNORE)

    def test_workspace_action_upgrade_initializes_only_legacy_rows(self):
        workspace = WorkspaceDb(self.db)
        batch = self.workspace_batch()
        batch.files.extend([MediaFile(str(uuid4()), '/tmp/films/b'),
                            MediaFile(str(uuid4()), '/tmp/films/c')])
        batch.started_event_id = workspace.create(batch, self.event(), self.event())
        for item, confidence in zip(batch.files, (10, 8)):
            item.state = MediaFileState.IDENTIFIED
            item.identification = Identification('Film', 2020, confidence)
            workspace.save_file(batch.id, item, self.event())
        self.db.execute('ALTER TABLE media_files DROP COLUMN action')
        try:
            WorkspaceSchema(self.db).apply()
            self.assertEqual([item.action for item in workspace.load().files],
                             [MediaFileAction.APPROVE, MediaFileAction.PENDING, MediaFileAction.PENDING])
            workspace.save_action(batch.id, batch.files[0].id, MediaFileAction.PENDING)
            workspace.save_action(batch.id, batch.files[1].id, MediaFileAction.IGNORE)
            WorkspaceSchema(self.db).apply()
            self.assertEqual([item.action for item in workspace.load().files],
                             [MediaFileAction.PENDING, MediaFileAction.IGNORE, MediaFileAction.PENDING])
        finally:
            WorkspaceSchema(self.db).apply()

    def test_tmdb_results_survive_reload_and_upgrade_and_action_changes_clear_them(self):
        workspace = WorkspaceDb(self.db)
        batch = self.workspace_batch()
        workspace.create(batch, self.event(), self.event())
        item = batch.files[0]
        item.state = MediaFileState.IDENTIFIED
        item.identification = Identification('Film', 2000, 10)
        item.action = MediaFileAction.APPROVE
        workspace.save_file(batch.id, item, self.event())
        result = TMDBMatch('Film', 2000, response={'total_results': 1, 'results': [{'id': 42}]})
        with workspace.processing():
            log = EventWriter(self.events.record, {'batch_id': batch.id, 'item_id': item.id})
            search_id = log.write(DEventCategory.TMDB.SEARCH, DEventName.TMDB_SEARCH,
                                  {'query': 'Film', 'primary_release_year': 2000}, source='TMDB')
            log.parent_event_id = search_id
            event = log.prepare(DEventCategory.TMDB.RESULT, DEventName.TMDB_RESULT,
                                result.response, source='TMDB')
            before = len(self.events.recent())
            with self.assertRaises(pymysql.IntegrityError):
                workspace.save_match(batch.id, item.id, result, self.event(message=None))
            self.assertIsNone(workspace.load().files[0].tmdb_match)
            self.assertEqual(len(self.events.recent()), before)
            workspace.save_match(batch.id, item.id, result, event)
            saved_events = self.events.recent(category='TMDB', subcategory='Result')
            self.assertEqual(len(saved_events), 1)
            self.assertEqual(saved_events[0]['parent_event_id'], search_id)
            self.assertEqual(saved_events[0]['name'], 'tmdb_result')
        WorkspaceSchema(self.db).apply()
        reader = DbMgr()
        try:
            self.assertEqual(WorkspaceDb(reader).snapshot().files[0].tmdb_match, result)
            with workspace.matching(), self.assertRaises(RuntimeError):
                WorkspaceDb(reader).save_action(batch.id, item.id, MediaFileAction.DELETE)
            with workspace.processing():
                WorkspaceDb(reader).save_action(batch.id, item.id, MediaFileAction.APPROVE)
        finally:
            reader.close()
        self.assertEqual(workspace.save_action(batch.id, item.id, MediaFileAction.APPROVE)
                         .files[0].tmdb_match, result)
        self.assertIsNone(workspace.save_action(batch.id, item.id, MediaFileAction.IGNORE)
                          .files[0].tmdb_match)

    def test_tmdb_reference_catalogs_persist_refresh_and_rollback_together(self):
        TMDBReferenceSchema(self.db).apply()
        catalog = TMDBReference([TMDBGenre(53, 'Thriller')], [TMDBLanguage('fr', 'French', 'Français')])
        references = TMDBReferenceDb(self.db)
        references.save(catalog)
        TMDBReferenceSchema(self.db).apply()
        reader = DbMgr()
        try:
            self.assertEqual(TMDBReferenceDb(reader).load(), catalog)
        finally:
            reader.close()
        with self.assertRaises(pymysql.IntegrityError):
            references.save(TMDBReference([TMDBGenre(53, 'Changed')], [TMDBLanguage('fr', 'French', None)]))
        self.assertEqual(references.load(), catalog)
        references.save(TMDBReference([TMDBGenre(53, 'Updated'), TMDBGenre(18, 'Drama')], []))
        refreshed = references.load()
        self.assertEqual(refreshed.genres, [TMDBGenre(18, 'Drama'), TMDBGenre(53, 'Updated')])
        self.assertEqual(refreshed.languages, catalog.languages)

    def test_workspace_issues_and_exclusive_processing(self):
        first = WorkspaceDb(self.db)
        reader = DbMgr()
        try:
            second = WorkspaceDb(reader)
            with first.processing():
                with self.assertRaises(RuntimeError):
                    with second.processing():
                        self.fail('Both processors acquired the workspace')
                batch = self.workspace_batch()
                batch.started_event_id = first.create(batch, self.event(), self.event())
                item = batch.files[0]
                item.state = MediaFileState.UNRESOLVED_LLM
                item.issues = [MediaFileIssue('unresolved_llm', 'Missing title'),
                               MediaFileIssue('missing_year', 'No year supplied')]
                item.attempts = 3
                first.save_file(batch.id, item, self.event())
            with second.processing():
                self.assert_batch_equal(second.load(), batch)
                with self.assertRaises(pymysql.IntegrityError):
                    second.create(self.workspace_batch(), self.event(), self.event())
                self.assert_batch_equal(second.load(), batch)
        finally:
            reader.close()

    def test_workspace_snapshot_reads_saved_status_while_processor_holds_lock(self):
        processor = WorkspaceDb(self.db)
        reader_db = DbMgr()
        try:
            reader = WorkspaceDb(reader_db)
            self.assertIsNone(reader.snapshot())
            with processor.processing():
                batch = self.workspace_batch()
                batch.started_event_id = processor.create(batch, self.event(), self.event())
                self.assertEqual(reader.snapshot().files[0].state, MediaFileState.PENDING)
                batch.files[0].state = MediaFileState.IDENTIFIED
                processor.save_file(batch.id, batch.files[0], self.event())
                self.assertEqual(reader.snapshot().files[0].state, MediaFileState.IDENTIFIED)
        finally:
            reader_db.close()

    def test_workspace_upgrade_keeps_existing_batch(self):
        workspace = WorkspaceDb(self.db)
        batch = self.workspace_batch()
        with workspace.processing():
            batch.started_event_id = workspace.create(batch, self.event(), self.event())
        # Recreate the old layout, then apply the same upgrade used by installation.
        self.db.execute('ALTER TABLE media_file_batches DROP COLUMN destination_directory')
        try:
            WorkspaceSchema(self.db).apply()
            WorkspaceSchema(self.db).apply()
            self.assert_batch_equal(workspace.load(), batch)
        finally:
            WorkspaceSchema(self.db).apply()

    def test_restart_resumes_only_pending_files(self):
        good = {'title': 'Example', 'year': 2001, 'confidence': 9}
        with TemporaryDirectory() as directory, FakeLLM([good, good], block_at=1) as llm:
            root = Path(directory)
            for name in ('a.mkv', 'b.mkv', 'c.mkv'):
                (root / name).touch()
            with self.run_batch(root, llm.url) as process:
                try:
                    self.assertTrue(llm.blocked.wait(20), 'second file did not start')
                    before = WorkspaceDb(self.db).load()
                    self.assertEqual([item.state for item in before.files],
                                     ['identified', 'pending', 'pending'])
                finally:
                    process.kill()
                    process.communicate(timeout=10)
            llm.release.set()
            # Recovery must use the saved selection, not the new size or directory.
            with TemporaryDirectory() as other, FakeLLM([good, good]) as resumed_llm:
                with self.run_batch(other, resumed_llm.url, size=500) as process:
                    output, error = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 0, error)
                self.assertEqual(len(resumed_llm.requests), 2)
                self.assertEqual([row['filename'] for row in json.loads(output.splitlines()[1])],
                                 ['a.mkv', 'b.mkv', 'c.mkv'])
            after = WorkspaceDb(self.db).load()
            self.assertEqual(after.id, before.id)
            self.assertEqual([item.id for item in after.files], [item.id for item in before.files])
            self.assertEqual(after.requested_size, 3)
            self.assertEqual(after.source_directory, directory)
            self.assertEqual(after.state, MediaFileBatchState.IDENTIFICATION_COMPLETED)
            self.assertEqual(sum(row['name'] == 'item_completed' for row in self.events.recent()), 3)
            # A completed identification batch is retained, not started again.
            with self.run_batch(root, 'http://127.0.0.1:1') as process:
                output, error = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, error)
            self.assertEqual(len(json.loads(output.splitlines()[1])), 3)
            names = [row['name'] for row in self.events.recent()]
            self.assertEqual(names.count('batch_started'), 1)
            self.assertEqual(names.count('batch_completed'), 1)
            self.assertEqual(names.count('batch_resumed'), 1)

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
            sys.executable, '-B', '-u', '-m', 'r3el.server.R3elServer', '--run-batch',
            '--film-dir', str(root), '--batch-size', str(size), '--llm-url', url,
            '--zmq-endpoint', 'tcp://127.0.0.1:*',
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_control_starts_batch_and_server_returns_to_idle(self):
        good = {'title': 'Example', 'year': 2001, 'confidence': 9}
        with TemporaryDirectory() as directory, FakeLLM([good], block=True) as llm:
            root = Path(directory)
            source = root / 'input'
            source.mkdir()
            (source / 'a.mkv').write_text('untouched')
            output = str(root / 'output')
            endpoint = 'ipc://' + str(root / 'control.sock')
            process = subprocess.Popen([
                sys.executable, '-B', '-u', '-m', 'r3el.server.R3elServer',
                '--llm-url', llm.url, '--zmq-endpoint', endpoint,
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env=dict(os.environ, TMDB_TOKEN=''))
            try:
                # Probe readiness without sending or retrying any batch commands.
                probe = ZMQMsg(sender=DMessage.CONTROL, method='unknown')
                deadline = time.monotonic() + 15
                while True:
                    try:
                        ZMQClient(endpoint, timeout=0.1).request(probe)
                        break
                    except zmq.Again:
                        self.assertIsNone(process.poll())
                        self.assertLess(time.monotonic(), deadline)
                self.assertIsNone(WorkspaceDb(self.db).load())
                self.assertEqual(llm.requests, [])
                control = BatchControl(endpoint)
                parameters = BatchRequest(str(source), output, 5)
                self.assertEqual(control.new_batch(parameters)['status'], DMessage.ACCEPTED)
                self.assertTrue(llm.blocked.wait(15))
                self.assertEqual(control.new_batch(parameters)['status'], DMessage.BUSY)
                llm.release.set()
                deadline = time.monotonic() + 20
                while True:
                    batch = WorkspaceDb(self.db).load()
                    if batch.state == MediaFileBatchState.MATCHING_COMPLETED:
                        break
                    self.assertIsNone(process.poll())
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(0.05)
                self.assertEqual(batch.source_directory, str(source))
                self.assertEqual(batch.destination_directory, output)
                self.assertEqual(batch.requested_size, 5)
                self.assertEqual(batch.files[0].identification.title, good['title'])
                self.assertEqual(len(llm.requests), 1)
                self.assertEqual(llm.errors, [])
                self.assertEqual((source / 'a.mkv').read_text(), 'untouched')
                self.assertFalse(Path(output).exists())
                self.assertIsNone(process.poll())
                self.assertEqual(ZMQClient(endpoint).request(probe).payload['error']['code'],
                                 DMessage.UNKNOWN_REQUEST)
                process.terminate()
                _, error = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0, error)
                names = [row['name'] for row in self.events.recent()]
                self.assertEqual(names.count('batch_started'), 1)
                self.assertEqual(names.count('batch_completed'), 2)
                self.assertEqual(names[0], 'stopped')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                process.stdout.close()
                process.stderr.close()

    def test_one_batch_real_http_mcp_zmq_and_database(self):
        good = {'title': 'Example', 'year': 2001, 'confidence': 9}
        # A malformed reply and server correction, an exhausted file, then success.
        submissions = ['{"choices": []}', {**good, 'confidence': 0.9}, good] + [{**good, 'year': 'bad'}] * 3 + [good]
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
            self.assertEqual(schema['properties']['confidence']['type'], 'integer')
            self.assertEqual(schema['properties']['confidence']['minimum'], 0)
            self.assertEqual(schema['properties']['confidence']['maximum'], 10)
            self.assertEqual(results[0]['identification']['confidence'], 9)
            self.assertIs(type(results[0]['identification']['confidence']), int)
            saved = WorkspaceDb(self.db).load().files[0].identification.confidence
            self.assertEqual(saved, 9)
            self.assertIs(type(saved), int)
            rejected = self.events.recent(name='submission_rejected')
            self.assertTrue(any('confidence must be an integer between 0 and 10.' in row['content']
                                for row in rejected))
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
        good = {'title': 'Example', 'year': 2001, 'confidence': 9}
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
            good = {'title': 'Example', 'year': 2001, 'confidence': 9}
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
