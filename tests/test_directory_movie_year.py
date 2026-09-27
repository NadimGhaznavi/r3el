"""Directory movie discovery, optional year submissions, and staged TMDB selection."""

from contextlib import nullcontext
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, Mock, patch

from r3el.activity.DirectoryDiscovery import DirectoryDiscovery
from r3el.activity.EventWriter import EventWriter
from r3el.app.BatchIdentification import BatchIdentification
from r3el.app.BatchMatching import BatchMatching
from r3el.app.MovieSelection import MovieSelection
from r3el.app.SubmissionHandler import SubmissionHandler
from r3el.app.ToolConversation import ToolConversation
from r3el.app.ValidateIdentification import ValidateIdentification
from r3el.entity.Identification import Identification
from r3el.entity.MediaFile import MediaFile, MediaFileState
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.entity.TMDBReference import TMDBReference
from r3el.interface.FileMgr import FileMgr
from r3el.interface.TMDB import TMDB
from r3el.server.MatchResults import MatchResults
from r3el.zmq.ZMQServer import ZMQServer


def reply(name, arguments):
    return json.dumps({'choices': [{'message': {'tool_calls': [
        {'id': 'answer', 'type': 'function', 'function': {
            'name': name, 'arguments': json.dumps(arguments)}}]}}]})


class DirectoryMovieDiscoveryTests(unittest.TestCase):
    def test_single_movie_with_or_without_year_keeps_subtitles_and_listing(self):
        for filename in ('Creed-2015.mkv', 'Creed.mkv'):
            with self.subTest(filename=filename), TemporaryDirectory() as root:
                directory = Path(root, 'Creed')
                directory.mkdir()
                video = directory / filename
                with video.open('wb') as stream:
                    stream.truncate(101 * 1024 * 1024)
                subtitle = video.with_suffix('.srt')
                subtitle.write_text('subtitle')
                (directory / 'Creed-2015.nfo').write_text('metadata')
                events = []
                workspace = Mock()
                DirectoryDiscovery().run(MediaFileBatch('batch', 1, root), workspace,
                    EventWriter(lambda event: events.append(event) or len(events), {'batch_id': 'batch'}))
                items = workspace.append_directories.call_args.args[1]
                self.assertEqual(len(items), 1)
                item = items[0]
                self.assertEqual(item.path, str(video))
                self.assertEqual(item.source_directory, str(directory))
                self.assertEqual([a.path for a in item.attachments], [str(video), str(subtitle)])
                self.assertEqual(item.attachments[1].media_path, str(video))
                self.assertFalse(item.is_two_part)
                self.assertEqual(item.needs_year_inference, filename == 'Creed.mkv')
                if item.needs_year_inference:
                    self.assertIn('Creed-2015.nfo', item.directory_context['find-ls'])
                    self.assertEqual(item.directory_context['filename'], filename)
                    scan = next(json.loads(e.message)['data'] for e in events if e.name == 'directory_scan_completed')
                    self.assertEqual(scan['reason'], 'missing_years')
                self.assertTrue(video.exists())

    def test_collection_missing_years_selects_movies_but_leaves_featurettes(self):
        directory = Path('/source/Movies')
        filesystem = Mock()
        filesystem.directories.return_value = [directory]
        paths = [str(directory / name) for name in ('A-2000.mkv', 'B.mkv', 'C.mkv', 'Featurettes/Making.mkv')]
        filesystem.scan.return_value = ('full listing', [(p, 101 * 1024 * 1024) for p in paths])
        workspace = Mock()
        with patch('r3el.activity.DirectoryDiscovery.DirectoryFiles', return_value=filesystem):
            DirectoryDiscovery().run(MediaFileBatch('batch', 1, '/source'), workspace,
                                     EventWriter(Mock(return_value=1), {'batch_id': 'batch'}))
        items = workspace.append_directories.call_args.args[1]
        self.assertEqual([item.path for item in items], paths[:3])
        self.assertEqual([item.needs_year_inference for item in items], [False, True, True])


class DirectoryYearConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_guessed_year_and_no_year_cross_real_mcp_and_zmq(self):
        for year in (2015, None):
            with self.subTest(year=year):
                record = Mock(return_value=1)
                handler = SubmissionHandler(record)
                submission = dict(title='Creed', year=year, confidence=9)
                llm = Mock(complete=AsyncMock(return_value=reply('submit_identification', submission)))
                directory = {'filename': 'Creed.mkv', 'find-ls': 'listing containing Creed-2015.nfo'}
                with ZMQServer('tcp://127.0.0.1:*', handler.handle) as listener:
                    result = await ToolConversation(llm, listener.endpoint, handler,
                        EventWriter(record, {'batch_id': 'batch', 'filename': 'Creed.mkv'}), directory=directory).run()
                self.assertEqual(result['identification'], submission)
                self.assertEqual(result['attempts'], 1)
                payload = llm.complete.call_args.args[0]
                self.assertEqual(llm.complete.call_count, 1)
                self.assertEqual(payload['tools'][0]['function']['parameters']['properties']['year']['type'],
                                 ['integer', 'null'])
                prompts = [json.loads(m['content']) for m in payload['messages'] if m.get('content', '').startswith('{')]
                year_prompt = next(p for p in prompts if p.get('data') == directory)
                self.assertIn('No year', year_prompt['instructions'])
                self.assertIn('Filesystem timestamps are not release years', year_prompt['instructions'])

    async def test_batch_identification_does_not_assign_parts_for_year_inference(self):
        item = MediaFile('file', '/source/Creed/Creed.mkv', source_directory='/source/Creed', find_ls='listing')
        batch = MediaFileBatch('batch', 1, '/source', files=[item])
        workspace = Mock()
        workspace.processing.side_effect = nullcontext
        workspace.load.return_value = batch
        with patch('r3el.app.BatchIdentification.ToolConversation') as conversation:
            conversation.return_value.run = AsyncMock(return_value=dict(status='identified', attempts=1,
                identification=dict(title='Creed', year=None, confidence=9)))
            await BatchIdentification(FileMgr('/source'), Mock(), 'endpoint', Mock(), Mock(return_value=1),
                                      workspace).run(1)
        self.assertIsNone(item.identification.year)
        self.assertEqual(conversation.call_args.kwargs['directory'], item.directory_context)

    def test_no_year_is_restricted_to_the_new_flow(self):
        data = dict(title='Creed', year=None, confidence=9)
        with self.assertRaises(ValueError):
            ValidateIdentification().run(data)
        self.assertIsNone(ValidateIdentification().run(data, allow_no_year=True).year)
        for invalid in ('No year', True, 0, 2015.5):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                ValidateIdentification().run(dict(data, year=invalid), allow_no_year=True)


class DirectoryYearMatchingTests(unittest.TestCase):
    def test_search_then_selection_for_no_year_and_unconfirmed_year(self):
        for year, count, select in ((None, 0, True), (None, 1, True), (None, 2, True),
                                    (2015, 0, True), (2015, 1, False), (2015, 2, True)):
            with self.subTest(year=year, count=count):
                item = MediaFile('file', '/source/Creed/Creed.mkv', MediaFileState.IDENTIFIED,
                    Identification('Creed', year, 9), source_directory='/source/Creed', find_ls='listing')
                workspace = Mock()
                workspace.processing.side_effect = nullcontext
                workspace.matching.side_effect = nullcontext
                workspace.load.return_value = MediaFileBatch('batch', 1, '/source', files=[item],
                    state=MediaFileBatchState.IDENTIFICATION_COMPLETED)
                workspace.save_match.side_effect = lambda b, f, result, e: setattr(item, 'tmdb_match', result)
                response = dict(total_results=count, results=[dict(id=n+1, title='Creed') for n in range(count)])
                order = []
                with patch('r3el.app.BatchMatching.TMDB.from_environment') as tmdb, \
                     patch('r3el.app.BatchMatching.MovieSelection') as selection, \
                     patch('r3el.app.BatchMatching.RetryIdentification') as retry, \
                     patch.object(BatchMatching, '_catalogue'):
                    tmdb.return_value.search.side_effect = lambda *args: order.append('search') or response
                    selection.return_value.run.side_effect = lambda match, log, **kwargs: (
                        order.append('select') or replace(match, selected_number=0))
                    runner = BatchMatching(workspace, Mock(return_value=1), Mock())
                    runner.run('batch')
                    runner.run('batch')  # Resume must reuse both the search and selection.
                    tmdb.return_value.search.assert_called_once_with('Creed', year)
                    self.assertEqual(order, ['search', 'select'] if select else ['search'])
                    self.assertEqual(selection.return_value.run.call_count, int(select))
                    if select:
                        self.assertEqual(selection.return_value.run.call_args.kwargs['directory'], item.directory_context)
                    retry.assert_not_called()
                self.assertEqual(TMDB.search_parameters('Creed', year),
                                 {'query': 'Creed', 'page': 1, **({} if year is None else {'primary_release_year': year})})

    def test_declined_single_candidate_cannot_be_catalogued_and_stays_unresolved(self):
        result = TMDBMatch('Creed', None, response=dict(total_results=1, results=[dict(id=42)]), selected_number=0)
        workspace = Mock()
        BatchMatching(workspace, Mock())._catalogue(Mock(), Mock(media_type='movie'), result, Mock())
        workspace.save_catalogue.assert_not_called()
        self.assertTrue(result.needs_manual_match)
        self.assertEqual(result.label, 'No match selected')
        self.assertEqual(MatchResults(TMDBReference([], [])).prepare(result)['tone'], 'unresolved')

    def test_selection_receives_listing_and_candidate_release_dates(self):
        llm = Mock(complete=AsyncMock(return_value=reply('submit_multiple_choice', {'number': 1})))
        match = TMDBMatch('Creed', None, response=dict(total_results=1, results=[
            dict(id=42, title='Creed', release_date='2015-11-25')]))
        directory = {'filename': 'Creed.mkv', 'find-ls': 'Creed-2015.nfo'}
        result = MovieSelection(llm).run(match, EventWriter(Mock(return_value=1),
            {'batch_id': 'batch', 'filename': 'Creed.mkv'}), directory=directory)
        self.assertEqual(result.selected_number, 1)
        messages = llm.complete.call_args.args[0]['messages']
        data = [json.loads(m['content'])['data'] for m in messages]
        self.assertIn(directory, data)
        self.assertEqual(data[-1]['candidates'][0]['release_date'], '2015-11-25')
