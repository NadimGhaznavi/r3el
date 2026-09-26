"""Exercise the one-time repair with real directories and a mocked database."""
from contextlib import nullcontext
from hashlib import sha256
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location(
    'movie_repair', Path(__file__).resolve().parents[1] / 'scripts/relocate-imported-movies.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ImportedMovieRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'movies').mkdir()
        (self.root / 'music').mkdir()
        self.source = self.root / 'Movie (2020)'
        self.source.mkdir()
        (self.source / '.tmdb-id').write_text('42')
        for name in ('Movie.avi', 'Movie.srt', 'poster.jpg'):
            (self.source / name).write_text(name)
        self.db = Mock()
        self.db.transaction.side_effect = nullcontext
        self.db.query.side_effect = lambda sql: [
            dict(path=str(self.source / name), path_hash=sha256(name.encode()).digest(), movie_id=42)
            for name in (('Movie.avi', 'Movie.srt') if 'movie_files' in sql else ('poster.jpg',))]
        self.repair = module.ImportedMovieRepair(self.db)

    def test_preview_then_move_updates_files_subtitles_and_artwork(self):
        self.repair.run(self.root)
        self.assertTrue(self.source.exists())
        self.db.execute.assert_not_called()
        self.repair.run(self.root, True)
        self.assertFalse(self.source.exists())
        target = self.root / 'movies' / self.source.name
        self.assertEqual((target / 'Movie.srt').read_text(), 'Movie.srt')
        self.assertTrue((self.root / 'music').is_dir())
        self.assertEqual(self.db.execute.call_count, 3)
        for call in self.db.execute.call_args_list:
            path, digest, _ = call.args[1]
            self.assertTrue(Path(path).is_relative_to(target))
            self.assertEqual(digest, sha256(path.encode()).digest())

    def test_existing_destination_preserves_source(self):
        (self.root / 'movies' / self.source.name).mkdir()
        with self.assertRaisesRegex(ValueError, 'Destination already exists'):
            self.repair.run(self.root, True)
        self.assertTrue((self.source / 'Movie.avi').exists())
        self.db.execute.assert_not_called()

    def test_database_failure_restores_directory(self):
        self.db.execute.side_effect = RuntimeError('database failure')
        with self.assertRaisesRegex(RuntimeError, 'database failure'):
            self.repair.run(self.root, True)
        self.assertTrue((self.source / 'Movie.avi').exists())
        self.assertFalse((self.root / 'movies' / self.source.name).exists())
