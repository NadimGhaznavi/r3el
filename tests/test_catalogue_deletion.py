"""File safety and optional MariaDB deletion checks (R3EL_TEST_DB=1)."""

from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import pymysql

from r3el.activity.CatalogueSchema import CatalogueSchema
from r3el.app.DeleteCatalogue import DeleteCatalogue
from r3el.interface.CatalogueDeletionDb import CatalogueDeletionDb
from r3el.interface.CatalogueFileDeletion import CatalogueFileDeletion
from r3el.interface.DbMgr import DbMgr


class FileDeletionTests(unittest.TestCase):
    def test_only_requested_files_removed_and_retry_tolerates_missing_files(self):
        with TemporaryDirectory() as directory:
            video = Path(directory, 'video.mkv')
            subtitle = Path(directory, 'video.srt')
            other = Path(directory, 'other.mkv')
            for target in (video, subtitle, other):
                target.touch()
            files = CatalogueFileDeletion()
            files.remove([str(video), str(subtitle)])
            files.remove([str(video), str(subtitle)])
            self.assertFalse(video.exists())
            self.assertFalse(subtitle.exists())
            self.assertTrue(other.exists())

    def test_preflight_rejects_directory_relative_path_and_symbolic_links(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / 'video.mkv'
            video.touch()
            link = root / 'linked'
            link.symlink_to(root, target_is_directory=True)
            file_link = root / 'linked.mkv'
            file_link.symlink_to(video)
            for bad in (str(root), 'relative.mkv', str(link / 'video.mkv'), str(file_link),
                        str(root / '..' / 'video.mkv')):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    CatalogueFileDeletion().remove([str(video), bad])
                self.assertTrue(video.exists())

    def test_missing_entry_never_removes_files(self):
        catalogue = Mock()
        @contextmanager
        def missing(*args):
            yield None
        catalogue.deleting.side_effect = missing
        files = Mock()
        self.assertFalse(DeleteCatalogue(catalogue, files).run('movie', 42))
        files.remove.assert_not_called()


@unittest.skipUnless(os.environ.get('R3EL_TEST_DB') == '1', 'requires MariaDB socket administrator')
class CatalogueDeletionDatabaseTests(unittest.TestCase):
    def setUp(self):
        socket = os.environ.get('R3EL_TEST_DB_SOCKET', '/run/mysqld/mysqld.sock')
        admin = pymysql.connect(unix_socket=socket, user='root', autocommit=True)
        self.addCleanup(admin.close)
        name = 'r3el_delete_' + uuid4().hex[:16]
        with admin.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE `{name}`')
        def drop():
            with admin.cursor() as cursor:
                cursor.execute(f'DROP DATABASE `{name}`')
        self.addCleanup(drop)
        connection = pymysql.connect(unix_socket=socket, user='root',
                                     database=name, autocommit=True, cursorclass=pymysql.cursors.DictCursor)
        with patch.dict(os.environ, {'DB_HOST': 'unused', 'DB_USER': 'unused',
                                    'DB_PASSWORD': '', 'DB_NAME': name}), \
                patch('r3el.interface.DbMgr.pymysql.connect', return_value=connection):
            self.db = DbMgr()
        self.addCleanup(self.db.close)
        CatalogueSchema(self.db).apply()
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.deletion = DeleteCatalogue(CatalogueDeletionDb(self.db), CatalogueFileDeletion())

    def file(self, name):
        path = self.root / name
        path.touch()
        return str(path)

    def movie(self, identifier=42):
        self.db.execute('INSERT INTO movies (tmdb_id,title,fetched_at) VALUES (%s,%s,NOW())',
                        (identifier, 'Movie'))
        paths = [self.file(f'{identifier}.mkv'), self.file(f'{identifier}.srt'), self.file(f'{identifier}.jpg')]
        for path in paths[:2]:
            self.db.execute('INSERT INTO movie_files (path_hash,path,movie_id) VALUES (%s,%s,%s)',
                            (sha256(path.encode()).digest(), path, identifier))
        self.db.execute("INSERT INTO movie_artwork VALUES (%s,%s,%s,'poster')",
                        (sha256(paths[2].encode()).digest(), paths[2], identifier))
        self.db.execute('INSERT INTO watched (movie_id,watched_at) VALUES (%s,NOW())', (identifier,))
        self.db.execute("INSERT INTO people VALUES (1,'Person') ON DUPLICATE KEY UPDATE name=VALUES(name)")
        self.db.execute('INSERT INTO movie_credits (movie_id,position,person_id,role_id) VALUES (%s,0,1,1)',
                        (identifier,))
        self.db.execute("INSERT INTO tmdb_movie_genres VALUES (18,'Drama') ON DUPLICATE KEY UPDATE name=VALUES(name)")
        self.db.execute('INSERT INTO movie_genres VALUES (%s,18)', (identifier,))
        return paths

    def show(self):
        self.db.execute("INSERT INTO tv_series (tmdb_id,title,added_at,fetched_at) VALUES (42,'Show',NOW(),NOW())")
        poster = self.file('show.jpg')
        self.db.execute("INSERT INTO tv_artwork VALUES (%s,%s,42,NULL,NULL,'poster')",
                        (sha256(poster.encode()).digest(), poster))
        self.db.execute("INSERT INTO people VALUES (1,'Person')")
        self.db.execute('INSERT INTO tv_series_credits (series_id,position,person_id,role_id) VALUES (42,0,1,1)')
        self.db.execute("INSERT INTO tmdb_tv_genres VALUES (18,'Drama')")
        self.db.execute('INSERT INTO tv_series_genres VALUES (42,18)')
        paths = {}
        for season in (0, 1, 2):
            episode = 100 + season
            self.db.execute("INSERT INTO tv_seasons (series_id,season_number,tmdb_id,title) VALUES (42,%s,%s,'Season')",
                            (season, episode))
            self.db.execute("INSERT INTO tv_episodes (tmdb_id,series_id,season_number,episode_number,title) "
                            "VALUES (%s,42,%s,1,'Episode')", (episode, season))
            paths[season] = [self.file(f's{season}.mkv'), self.file(f's{season}.srt'), self.file(f's{season}.jpg')]
            for path, kind in zip(paths[season][:2], ('video', 'subtitle')):
                self.db.execute('INSERT INTO tv_episode_files VALUES (%s,%s,%s,%s)',
                                (sha256(path.encode()).digest(), path, episode, kind))
            path = paths[season][2]
            self.db.execute("INSERT INTO tv_artwork VALUES (%s,%s,42,NULL,%s,'still')",
                            (sha256(path.encode()).digest(), path, episode))
            self.db.execute('INSERT INTO tv_episode_credits (episode_id,position,person_id,role_id) VALUES (%s,0,1,1)',
                            (episode,))
            path = self.file(f'season{season}.jpg')
            paths[season].append(path)
            self.db.execute("INSERT INTO tv_artwork VALUES (%s,%s,42,%s,NULL,'poster')",
                            (sha256(path.encode()).digest(), path, season))
            self.db.execute('INSERT INTO watched (episode_id,watched_at) VALUES (%s,NOW())', (episode,))
        return poster, paths

    def test_movie_deletes_files_and_records_and_can_be_reimported(self):
        paths = self.movie()
        self.assertTrue(self.deletion.run('movie', 42))
        self.assertTrue(all(not Path(path).exists() for path in paths))
        for table in ('movies', 'movie_files', 'movie_artwork', 'movie_credits', 'movie_genres', 'watched'):
            self.assertEqual(self.db.query(f'SELECT * FROM {table}'), [])
        self.assertFalse(self.deletion.run('movie', 42))
        self.movie()

    def test_one_season_preserves_other_seasons_and_show_artwork(self):
        poster, paths = self.show()
        self.assertTrue(self.deletion.run('tv', 42, 1))
        self.assertFalse(self.deletion.run('tv', 42, 1))
        self.assertTrue(all(not Path(path).exists() for path in paths[1]))
        self.assertTrue(all(Path(path).exists() for season in (0, 2) for path in paths[season]))
        self.assertTrue(Path(poster).exists())
        self.assertEqual(len(self.db.query('SELECT * FROM watched')), 2)
        self.assertTrue(self.deletion.run('tv', 42, 0))
        self.assertTrue(self.deletion.run('tv', 42, 2))
        self.assertEqual(len(self.db.query('SELECT * FROM tv_series')), 1)

    def test_whole_show_removes_all_seasons(self):
        poster, paths = self.show()
        self.assertTrue(self.deletion.run('tv', 42))
        self.assertFalse(Path(poster).exists())
        self.assertTrue(all(not Path(path).exists() for files in paths.values() for path in files))
        for table in ('tv_series', 'tv_seasons', 'tv_episodes', 'tv_episode_files', 'tv_artwork',
                      'tv_series_credits', 'tv_episode_credits', 'tv_series_genres', 'watched'):
            self.assertEqual(self.db.query(f'SELECT * FROM {table}'), [])

    def test_partial_filesystem_failure_rolls_back_records_and_retry_finishes(self):
        paths = self.movie()
        original = Path.unlink
        def unlink(path, **kwargs):
            if str(path) == paths[1]:
                raise PermissionError('Cannot remove subtitle')
            original(path, **kwargs)
        with patch.object(Path, 'unlink', unlink), self.assertRaises(PermissionError):
            self.deletion.run('movie', 42)
        self.assertFalse(Path(paths[0]).exists())
        self.assertEqual(len(self.db.query('SELECT * FROM movie_files')), 2)
        self.assertEqual(len(self.db.query('SELECT * FROM watched')), 1)
        self.assertTrue(self.deletion.run('movie', 42))

    def test_shared_artwork_is_preserved(self):
        paths = self.movie()
        self.db.execute("INSERT INTO tv_series (tmdb_id,title,added_at,fetched_at) VALUES (43,'Show',NOW(),NOW())")
        self.db.execute("INSERT INTO tv_artwork VALUES (%s,%s,43,NULL,NULL,'poster')",
                        (sha256(paths[2].encode()).digest(), paths[2]))
        self.assertTrue(self.deletion.run('movie', 42))
        self.assertTrue(Path(paths[2]).exists())
