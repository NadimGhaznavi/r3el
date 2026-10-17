"""Movie correction with real files and optional MariaDB transaction checks."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import date
from hashlib import sha256
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from r3el.app.EditCatalogueMovie import EditCatalogueMovie
from r3el.entity.CatalogueMovie import CatalogueMovie
from r3el.interface.CatalogueDb import CatalogueDb
from r3el.interface.CatalogueEditDb import CatalogueEditDb
from r3el.interface.CatalogueEditFiles import CatalogueEditFiles
from tests import test_catalogue_deletion as deletion_tests


def corrected_movie():
    return CatalogueMovie(43, 'Correct Movie', None, date(2021, 1, 2), 'New synopsis',
                          100, '/new-poster.jpg', '/new-backdrop.jpg', None, None, None, [], [])


def download(remote, folder, kind):
    target = folder / f'{kind}-{remote[1:]}'
    target.write_bytes(b'new image')
    return str(target), 'downloaded'


class EditFilesTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.old = self.root / 'Wrong Movie (2020)'
        self.old.mkdir()
        self.entries = []
        for name, kind, part in (('Part 1.mkv', 'video', 1), ('Part 2.mkv', 'video', 2),
                                 ('Part 1.srt', 'subtitle', 1)):
            path = self.old / name
            path.write_bytes(name.encode())
            self.entries.append(dict(path=str(path), kind=kind, part=part))
        self.art = self.old / 'old-poster.jpg'
        self.art.write_bytes(b'old image')
        self.files = CatalogueEditFiles()
        self.patch = patch('r3el.interface.CatalogueFiles.CatalogueFiles._download_image', side_effect=download)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_replaces_multipart_video_subtitles_and_artwork(self):
        paths = [entry['path'] for entry in self.entries] + [str(self.art)]
        with self.files.replacing():
            prepared = self.files.prepare(corrected_movie(), self.entries, Mock())
            self.files.remove(paths)
        self.assertTrue(all(not Path(path).exists() for path in paths))
        self.assertEqual([entry['part'] for entry in prepared.associated], [1, 2, 1])
        for old, new in zip(self.entries, prepared.associated):
            self.assertEqual(Path(new['path']).read_bytes(), Path(old['path']).name.encode())
        self.assertEqual(Path(prepared.poster).read_bytes(), b'new image')
        self.assertEqual(Path(prepared.backdrop).read_bytes(), b'new image')
        self.assertEqual(list(self.root.rglob('.r3el-*')), [])

    def test_transaction_failure_restores_every_original_and_removes_new_files(self):
        paths = [entry['path'] for entry in self.entries] + [str(self.art)]
        with self.assertRaisesRegex(RuntimeError, 'commit failed'):
            with self.files.replacing():
                prepared = self.files.prepare(corrected_movie(), self.entries, Mock())
                self.files.remove(paths)
                raise RuntimeError('commit failed')
        self.assertTrue(all(Path(path).is_file() for path in paths))
        self.assertFalse(Path(prepared.video).exists())
        self.assertEqual(list(self.root.rglob('.r3el-*')), [])

    def test_download_failure_keeps_originals_and_cleans_staging(self):
        with patch('r3el.interface.CatalogueFiles.CatalogueFiles._download_image', side_effect=OSError('offline')):
            with self.assertRaises(OSError), self.files.replacing():
                self.files.prepare(corrected_movie(), self.entries, Mock())
        self.assertEqual(list(self.root.iterdir()), [self.old])
        self.assertTrue(self.art.exists())
        self.assertTrue(all(Path(entry['path']).exists() for entry in self.entries))

    def test_partial_file_removal_restores_all_originals(self):
        paths = [entry['path'] for entry in self.entries] + [str(self.art)]
        unlink = Path.unlink
        def fail(path, *args, **kwargs):
            if str(path) == paths[1]:
                raise PermissionError('Cannot remove file')
            return unlink(path, *args, **kwargs)
        with self.assertRaises(PermissionError):
            with self.files.replacing():
                prepared = self.files.prepare(corrected_movie(), self.entries, Mock())
                with patch.object(Path, 'unlink', fail):
                    self.files.remove(paths)
        self.assertTrue(all(Path(path).exists() for path in paths))
        self.assertFalse(Path(prepared.video).exists())
        self.assertEqual(list(self.root.rglob('.r3el-*')), [])

    def test_existing_destination_is_never_overwritten(self):
        target = self.root / 'Correct Movie (2021)'
        target.mkdir()
        existing = target / 'keep.mkv'
        existing.write_bytes(b'keep')
        with self.assertRaises(FileExistsError), self.files.replacing():
            self.files.prepare(corrected_movie(), self.entries, Mock())
        self.assertEqual(existing.read_bytes(), b'keep')

    def test_identical_title_and_year_use_distinct_directory(self):
        with self.files.replacing():
            prepared = self.files.prepare(replace(corrected_movie(), title='Wrong Movie',
                                                  release_date=date(2020, 1, 2)), self.entries, Mock())
        self.assertEqual(Path(prepared.video).parent.name, 'Wrong Movie (2020) [TMDB 43]')
        self.assertTrue(all(Path(entry['path']).exists() for entry in self.entries))


@unittest.skipUnless(os.environ.get('R3EL_TEST_DB') == '1', 'requires MariaDB socket administrator')
class EditDatabaseTests(unittest.TestCase):
    def setUp(self):
        deletion_tests.CatalogueDeletionDatabaseTests.setUp(self)
        self.root = self.root / 'Wrong Movie (2020)'
        self.root.mkdir()

    file = deletion_tests.CatalogueDeletionDatabaseTests.file
    def movie(self):
        paths = deletion_tests.CatalogueDeletionDatabaseTests.movie(self)
        self.db.execute("UPDATE movie_files SET kind='subtitle' WHERE path=%s", (paths[1],))
        return paths

    def editor(self):
        client = Mock()
        client.movie.return_value = corrected_movie()
        return EditCatalogueMovie(CatalogueEditDb(self.db), CatalogueEditFiles(), client, Mock())

    def test_correction_preserves_history_and_import_date_and_removes_old_records(self):
        paths = self.movie()
        self.db.execute("UPDATE movies SET added_at='2020-01-02 03:04:05' WHERE tmdb_id=42")
        with patch('r3el.interface.CatalogueFiles.CatalogueFiles._download_image', side_effect=download):
            self.editor().run(42, 43)
        self.assertIsNone(CatalogueDb(self.db).get(42))
        movie = CatalogueDb(self.db).get(43)
        self.assertEqual(movie['title'], 'Correct Movie')
        self.assertEqual(str(movie['added_at']), '2020-01-02 03:04:05')
        self.assertEqual(self.db.query('SELECT movie_id FROM watched'), [{'movie_id': 43}])
        self.assertTrue(all(not Path(path).exists() for path in paths))
        self.assertEqual(len(movie['files']), 2)
        self.assertTrue(all(Path(row['path']).exists() for row in movie['files']))
        self.assertEqual(len(movie['artwork']), 2)

    def test_database_failure_rolls_back_records_and_files(self):
        paths = self.movie()
        real_transaction = self.db.transaction
        @contextmanager
        def failed_commit():
            with real_transaction():
                yield
                raise RuntimeError('commit failed')
        with patch.object(self.db, 'transaction', failed_commit), \
                patch('r3el.interface.CatalogueFiles.CatalogueFiles._download_image', side_effect=download):
            with self.assertRaisesRegex(RuntimeError, 'commit failed'):
                self.editor().run(42, 43)
        self.assertIsNotNone(CatalogueDb(self.db).get(42))
        self.assertIsNone(CatalogueDb(self.db).get(43))
        self.assertTrue(all(Path(path).exists() for path in paths))
        self.assertEqual(list(self.root.rglob('.r3el-*')), [])

    def test_existing_id_and_same_id_leave_originals_intact(self):
        paths = self.movie()
        self.db.execute("INSERT INTO movies (tmdb_id,title,fetched_at) VALUES (43,'Existing',NOW())")
        for new_id in (42, 43):
            with self.assertRaises(ValueError):
                self.editor().run(42, new_id)
        self.assertTrue(all(Path(path).exists() for path in paths))

    def test_shared_old_artwork_is_preserved(self):
        paths = self.movie()
        self.db.execute("INSERT INTO tv_series (tmdb_id,title,added_at,fetched_at) VALUES (44,'Show',NOW(),NOW())")
        self.db.execute("INSERT INTO tv_artwork VALUES (%s,%s,44,NULL,NULL,'poster')",
                        (sha256(paths[2].encode()).digest(), paths[2]))
        with patch('r3el.interface.CatalogueFiles.CatalogueFiles._download_image', side_effect=download):
            self.editor().run(42, 43)
        self.assertTrue(Path(paths[2]).exists())
