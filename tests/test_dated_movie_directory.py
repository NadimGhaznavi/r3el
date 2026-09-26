"""Separate dialogues for dated directory movies, grouped limits, and final cleanup."""

from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, Mock, patch

from r3el.activity.DirectoryDiscovery import DirectoryDiscovery
from r3el.activity.EventWriter import EventWriter
from r3el.app.BatchIdentification import BatchIdentification
from r3el.app.BatchMatching import BatchMatching
from r3el.entity.MediaAttachment import MediaAttachment
from r3el.entity.MediaFile import MediaFile
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.interface.DirectoryFiles import DirectoryFiles
from r3el.interface.FileMgr import FileMgr
from r3el.interface.TMDBCatalogue import TMDBCatalogue
from test_catalogue import movie_payload


class DatedDirectoryTests(unittest.TestCase):
    def test_three_movies_require_all_years_and_same_year_pair_stays_two_parts(self):
        for names, expected in ((('A-2000.avi', 'B-2001.avi', 'C-2002.avi'), 3),
                                (('A-2000.avi', 'B-2001.avi', 'C.avi'), 0),
                                (('A-2000.avi', 'B-2000.avi'), 1)):
            with self.subTest(names=names), TemporaryDirectory() as root:
                directory = Path(root, 'movies')
                directory.mkdir()
                for name in names:
                    with (directory / name).open('wb') as stream:
                        stream.truncate(100 * 1024 * 1024 + 1)
                batch = MediaFileBatch('batch', 1, root)
                workspace = Mock()
                def append(batch, items, event):
                    batch.files.extend(items)
                workspace.append_directories.side_effect = append
                DirectoryDiscovery().run(batch, workspace, EventWriter(Mock(return_value=1), {'batch_id': 'batch'}))
                self.assertEqual(len(batch.files), expected)
                if expected == 3:
                    self.assertTrue(all(item.source_directory == str(directory) and item.find_ls is None
                                        for item in batch.files))
                if expected == 1:
                    self.assertIsNotNone(batch.files[0].find_ls)

    def test_moves_separately_and_removes_directory_only_after_last_media(self):
        with TemporaryDirectory() as root:
            directory = Path(root, 'Alice')
            directory.mkdir()
            paths = [directory / 'Alice-2010.avi', directory / 'Looking-Glass-2016.avi']
            for path in paths:
                path.write_bytes(path.name.encode())
                path.with_suffix('.srt').write_text(path.stem)
            (directory / 'notes.txt').write_text('notes')
            items = [MediaFile(str(index), str(path), source_directory=str(directory), attachments=[
                MediaAttachment(str(path)), MediaAttachment(str(path.with_suffix('.srt')), 'subtitle',
                                                           media_path=str(path))]) for index, path in enumerate(paths)]
            batch = MediaFileBatch('batch', 1, root, files=items, destination_directory=str(Path(root, 'out')))
            workspace = Mock()
            workspace.catalogue_paths.return_value = []
            matcher = BatchMatching(workspace, Mock(return_value=1))
            log = EventWriter(Mock(return_value=1), {'batch_id': 'batch'})
            for index, item in enumerate(items):
                movie = replace(TMDBCatalogue.from_details(movie_payload(), 42), tmdb_id=42 + index,
                                title=f'Movie {index}', poster_path=None, backdrop_path=None)
                result = TMDBMatch(movie.title, 2020, response={'total_results': 1, 'results': [{'id': movie.tmdb_id}]})
                matcher._catalogue(batch, item, result, log, movie=movie)
                self.assertFalse(paths[index].exists())
                self.assertEqual(directory.exists(), index == 0)
                target = Path(root, 'out', f'Movie {index} (2020)', f'Movie {index} (2020).srt')
                self.assertEqual(target.read_text(), paths[index].stem)
            self.assertEqual(workspace.save_catalogue.call_count, 2)

    def test_cleanup_preserves_any_remaining_media_including_small_files(self):
        with TemporaryDirectory() as root:
            directory = Path(root, 'movies')
            directory.mkdir()
            sample = directory / 'sample.avi'
            sample.write_bytes(b'small')
            self.assertFalse(DirectoryFiles().remove_without_media(str(directory)))
            sample.unlink()
            (directory / 'notes.nfo').write_text('notes')
            self.assertTrue(DirectoryFiles().remove_without_media(str(directory)))
            self.assertFalse(directory.exists())


class DatedDialogueTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_single_file_dialogue_for_every_movie(self):
        items = [MediaFile('one', '/source/Alice/Alice-2010.avi', source_directory='/source/Alice'),
                 MediaFile('two', '/source/Alice/Looking-Glass-2016.avi', source_directory='/source/Alice')]
        batch = MediaFileBatch('batch', 1, '/source', files=items)
        workspace = Mock()
        workspace.processing.side_effect = nullcontext
        workspace.load.return_value = batch
        with patch('r3el.app.BatchIdentification.ToolConversation') as conversation:
            conversation.return_value.run = AsyncMock(return_value={'status': 'identified', 'attempts': 1,
                'identification': {'title': 'Movie', 'year': 2010, 'confidence': 10}})
            identify = BatchIdentification(FileMgr('/source'), Mock(), 'endpoint', Mock(), Mock(return_value=1), workspace)
            await identify.run(1, limit=2, completion_state=MediaFileBatchState.MATCHING)
        self.assertEqual(conversation.call_count, 2)
        self.assertTrue(all('directory' not in call.kwargs for call in conversation.call_args_list))
        self.assertEqual([call.args[3].context['filename'] for call in conversation.call_args_list],
                         ['Alice-2010.avi', 'Looking-Glass-2016.avi'])
