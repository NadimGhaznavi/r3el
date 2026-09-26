"""Explicit destination replacement, conflict classification, and retry checkpoints."""

from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from r3el.activity.EventWriter import EventWriter
from r3el.activity.TwoPartCopy import TwoPartCopy
from r3el.app.BatchMatching import BatchMatching
from r3el.entity.MediaAttachment import MediaAttachment
from r3el.entity.MediaFile import MediaFile
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.interface.CatalogueFiles import CatalogueFiles
from r3el.interface.TMDBCatalogue import TMDBCatalogue
from r3el.interface.WorkspaceDb import WorkspaceActionConflict
from test_catalogue import movie_payload


class ReplacementTests(unittest.TestCase):
    def test_replaces_only_item_paths_and_can_resume_before_and_after_catalogue_commit(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'out'
            folder = output / 'Movie (2020)'
            folder.mkdir(parents=True)
            untouched = folder / 'unrelated.srt'
            untouched.write_bytes(b'leave alone')
            attachments = []
            for part in (1, 2):
                video = str(root / f'original-{part}.avi')
                for extension in ('avi', 'srt'):
                    source = root / f'original-{part}.{extension}'
                    source.write_bytes(f'new {part} {extension}'.encode())
                    (folder / f'Movie (2020) Part {part}.{extension}').write_bytes(b'old content')
                    attachments.append(MediaAttachment(str(source), 'video' if extension == 'avi' else 'subtitle',
                                                       part, video if extension == 'srt' else None))
            item = MediaFile('item', str(root), find_ls='listing', attachments=attachments)
            movie = replace(TMDBCatalogue.from_details(movie_payload(), 42), poster_path=None, backdrop_path=None)
            log = EventWriter(Mock(return_value=1), {'batch_id': 'batch'})
            with self.assertRaisesRegex(FileExistsError, 'destination video already exists'):
                TwoPartCopy().prepare(movie, item, str(output), log)
            self.assertEqual((folder / 'Movie (2020) Part 1.avi').read_bytes(), b'old content')
            files, copies = TwoPartCopy().prepare(movie, item, str(output), log, replace_existing=True)
            self.assertEqual(TwoPartCopy().prepare(movie, item, str(output), log, replace_existing=True), (files, copies))
            for copy in copies:
                self.assertEqual(Path(copy['destination']).read_bytes(), Path(copy['source']).read_bytes())
                CatalogueFiles().finish(copy['source'], copy['destination'], copy['stage_id'], preserve_source=True)
                CatalogueFiles().finish(copy['source'], copy['destination'], copy['stage_id'], preserve_source=True)
            self.assertEqual(untouched.read_bytes(), b'leave alone')
            self.assertFalse(list(folder.glob('.r3el-*')))

    def test_conflict_label_includes_saved_results_and_other_failures_stay_distinct(self):
        conflict = TMDBMatch('Movie', 2020, catalogue_error='The destination video already exists: /out/movie.avi')
        self.assertTrue(conflict.entry_exists)
        self.assertEqual(conflict.label, 'Entry exists')
        self.assertEqual(replace(conflict, catalogue_error='Permission denied').label, 'Catalogue failed')

    def test_action_checks_current_workspace_and_checkpoints_authorization_before_copy(self):
        workspace = Mock()
        workspace.processing.side_effect = nullcontext
        workspace.matching.side_effect = nullcontext
        result = TMDBMatch('Movie', 2020, response={'total_results': 1, 'results': [{'id': 42}]},
                           catalogue_error='The destination video already exists: /out/movie.avi')
        item = MediaFile('item', '/source', tmdb_match=result)
        batch = MediaFileBatch('batch', 1, '/source', files=[item], state=MediaFileBatchState.MATCHING_COMPLETED)
        workspace.load.return_value = batch
        matcher = BatchMatching(workspace, Mock(return_value=1))
        def copy(batch, item, match, log):
            self.assertTrue(match.replace_local_media)
            self.assertEqual(workspace.save_match.call_args.args[2], match)
        with patch.object(matcher, '_catalogue', side_effect=copy) as catalogue:
            matcher.replace_media('batch', 'item')
            catalogue.assert_called_once()
            batch.state = MediaFileBatchState.PROCESSING
            with self.assertRaises(WorkspaceActionConflict):
                matcher.replace_media('batch', 'item')
            batch.state = MediaFileBatchState.MATCHING_COMPLETED
            item.tmdb_match = replace(result, catalogue_error=None)
            with self.assertRaises(WorkspaceActionConflict):
                matcher.replace_media('batch', 'item')
            with self.assertRaises(WorkspaceActionConflict):
                matcher.replace_media('old-batch', 'item')
