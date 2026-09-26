"""A clean directory run removes sources only after copying and catalogue commit."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from r3el.activity.EventWriter import EventWriter
from r3el.app.BatchMatching import BatchMatching
from r3el.entity.MediaAttachment import MediaAttachment
from r3el.entity.MediaFile import MediaFile, MediaFileIssue
from r3el.entity.MediaFileBatch import MediaFileBatch
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.interface.SourceDirectoryCleanup import SourceDirectoryCleanup
from r3el.interface.TMDBCatalogue import TMDBCatalogue
from test_catalogue import movie_payload


class SourceCleanupTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        attachments = []
        for part in (1, 2):
            video = self.source / f'part{part}.avi'
            srt = self.source / f'part{part}.srt'
            video.write_bytes(f'video {part}'.encode())
            srt.write_bytes(f'subtitle {part}'.encode())
            attachments.extend([MediaAttachment(str(video), part=part),
                                MediaAttachment(str(srt), 'subtitle', part, str(video))])
        (self.source / 'movie.nfo').write_text('release information')
        self.item = MediaFile('item', str(self.source), find_ls='listing', attachments=attachments)
        self.batch = MediaFileBatch('batch', 1, str(self.root), files=[self.item],
                                    destination_directory=str(self.root / 'output'))
        self.result = TMDBMatch('Movie', 2020, response={'total_results': 1, 'results': [{'id': 42}]})
        self.movie = replace(TMDBCatalogue.from_details(movie_payload(), 42), poster_path=None, backdrop_path=None)
        self.workspace = Mock()
        self.matcher = BatchMatching(self.workspace, Mock(return_value=1))
        self.log = EventWriter(Mock(return_value=1), {'batch_id': 'batch', 'item_id': 'item'})

    def run_catalogue(self):
        self.matcher._catalogue(self.batch, self.item, self.result, self.log, movie=self.movie)

    def test_commits_then_removes_sources_and_directory_including_release_notes(self):
        def committed(*args):
            self.assertTrue(self.source.is_dir())
            self.assertTrue(all(Path(file.path).exists() for file in self.item.attachments))
        self.workspace.save_catalogue.side_effect = committed
        self.run_catalogue()
        self.assertFalse(self.source.exists())
        target = self.root / 'output/Movie (2020)'
        self.assertEqual((target / 'Movie (2020) Part 1.srt').read_bytes(), b'subtitle 1')
        self.assertEqual((target / 'Movie (2020) Part 2.avi').read_bytes(), b'video 2')
        self.assertTrue(self.workspace.save_match.call_args.args[2].file_moved)

    def test_catalogue_failure_preserves_all_sources(self):
        self.workspace.save_catalogue.side_effect = RuntimeError('commit failed')
        with self.assertRaisesRegex(RuntimeError, 'commit failed'):
            self.run_catalogue()
        self.assertTrue(all(Path(file.path).exists() for file in self.item.attachments))
        self.assertTrue((self.source / 'movie.nfo').exists())

    def test_unresolved_subtitle_and_directory_remain_but_copied_sources_are_removed(self):
        unresolved = self.source / 'unknown.srt'
        unresolved.write_bytes(b'unresolved')
        self.item.attachments.append(MediaAttachment(str(unresolved), 'subtitle'))
        self.item.issues.append(MediaFileIssue('unresolved_srt', str(unresolved)))
        self.run_catalogue()
        self.assertEqual(unresolved.read_bytes(), b'unresolved')
        self.assertFalse((self.source / 'part1.avi').exists())
        self.assertFalse((self.source / 'part1.srt').exists())
        self.assertTrue(self.source.is_dir())

    def test_missing_or_changed_destination_prevents_any_source_deletion(self):
        a = self.source / 'part1.avi'
        b = self.source / 'part2.avi'
        good = self.root / 'good.avi'
        bad = self.root / 'bad.avi'
        good.write_bytes(a.read_bytes())
        copies = [{'source': str(a), 'destination': str(good)}, {'source': str(b), 'destination': str(bad)}]
        for exists in (False, True):
            if exists:
                bad.write_bytes(b'wrong bytes')
            with self.assertRaises(ValueError):
                SourceDirectoryCleanup().finish(str(self.source), copies, preserve_directory=False)
            self.assertTrue(a.exists())
            self.assertTrue(b.exists())

    def test_destination_inside_source_is_never_deleted(self):
        origin = self.source / 'part1.avi'
        target = self.source / 'copy.avi'
        target.write_bytes(origin.read_bytes())
        with self.assertRaises(ValueError):
            SourceDirectoryCleanup().finish(str(self.source),
                [{'source': str(origin), 'destination': str(target)}], preserve_directory=False)
        self.assertTrue(origin.exists())
        self.assertTrue(target.exists())
