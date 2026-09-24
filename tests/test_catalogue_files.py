"""Same-filesystem moves, local artwork, and interruption recovery."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import httpx

from r3el.activity.MovieNaming import MovieNaming
from r3el.interface.CatalogueFiles import CatalogueFiles
from r3el.interface.TMDBCatalogue import TMDBCatalogue
from test_catalogue import movie_payload


class CatalogueFilesTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'original.mkv'
        self.source.write_bytes(b'video bytes')
        self.output = self.root / 'batch-output'
        client = Mock()
        client.details.return_value = movie_payload()
        self.movie = replace(TMDBCatalogue(client).movie(42), poster_path=None, backdrop_path=None)
        self.files = CatalogueFiles()

    def prepare(self):
        return self.files.prepare(self.movie, str(self.source), str(self.output), 'file-id')

    def test_move_uses_same_inode_and_survives_retry_before_and_after_commit(self):
        files = self.prepare()
        self.assertEqual(files.video, str(self.output / 'Movie (2020)' / 'Movie (2020).mkv'))
        self.assertTrue(self.source.samefile(files.video))
        self.assertEqual(self.prepare(), files)
        self.files.finish(str(self.source), files.video, 'file-id')
        self.assertFalse(self.source.exists())
        self.assertEqual(Path(files.video).read_bytes(), b'video bytes')
        self.assertFalse((Path(files.video).parent / '.r3el-file-id.video').exists())
        self.files.finish(str(self.source), files.video, 'file-id')

    def test_existing_video_is_never_overwritten(self):
        folder = self.output / 'Movie (2020)'
        folder.mkdir(parents=True)
        target = folder / 'Movie (2020).mkv'
        target.write_bytes(b'existing movie')
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(target.read_bytes(), b'existing movie')
        self.assertTrue(self.source.exists())

    def test_source_replacement_is_not_deleted(self):
        files = self.prepare()
        self.source.unlink()
        self.source.write_bytes(b'new source')
        with self.assertRaisesRegex(ValueError, 'source video changed'):
            self.files.finish(str(self.source), files.video, 'file-id')
        self.assertEqual(self.source.read_bytes(), b'new source')

    def test_wrong_movie_directory_and_missing_year_are_rejected(self):
        self.prepare()
        self.movie = replace(self.movie, tmdb_id=99)
        with self.assertRaisesRegex(ValueError, 'different TMDB movie'):
            self.prepare()
        self.movie = replace(self.movie, release_date=None)
        with self.assertRaisesRegex(ValueError, 'release date'):
            self.prepare()

    @patch('r3el.interface.CatalogueFiles.httpx.stream')
    def test_artwork_download_is_cached_and_recorded_as_local_paths(self, stream):
        self.movie = replace(self.movie, poster_path='/poster.jpg', backdrop_path='/backdrop.jpg')
        stream.return_value.__enter__.side_effect = lambda: httpx.Response(
            200, content=b'image bytes', headers={'content-type': 'image/jpeg'},
            request=httpx.Request('GET', 'https://image.tmdb.org'))
        files = self.prepare()
        self.assertEqual(Path(files.poster).read_bytes(), b'image bytes')
        self.assertEqual(Path(files.backdrop).read_bytes(), b'image bytes')
        self.assertEqual(self.prepare(), files)
        self.assertEqual(stream.call_count, 2)

    @patch('r3el.interface.CatalogueFiles.httpx.stream', side_effect=httpx.ConnectError('Offline'))
    def test_download_failure_leaves_original_video(self, stream):
        self.movie = replace(self.movie, poster_path='/poster.jpg')
        with self.assertRaises(httpx.ConnectError):
            self.prepare()
        self.assertEqual(self.source.read_bytes(), b'video bytes')
        self.assertEqual(list(self.output.rglob('*.mkv')), [])

    def test_naming_rules(self):
        self.assertEqual(MovieNaming.stem('  Ａ: “B”/C\\D #1 50%?  ', 2020),
                         'A - B - C - D 1 50 percent (2020)')
        self.assertEqual(MovieNaming.stem('Spider-Man: No Way Home', 2021),
                         'Spider - Man - No Way Home (2021)')
        with self.assertRaises(ValueError):
            MovieNaming.stem('???', 2020)
