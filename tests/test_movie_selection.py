"""Multiple-choice payload, response validation, and saved selection behavior."""

from contextlib import nullcontext
from dataclasses import asdict
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx

from r3el.activity.EventWriter import EventWriter
from r3el.app.BatchMatching import BatchMatching
from r3el.app.MovieSelection import MovieSelection
from r3el.app.MultipleChoiceHandler import MultipleChoiceHandler
from r3el.zmq.ZMQMsg import ZMQMsg
from r3el.constants.DMessage import DMessage
from r3el.entity.Identification import Identification
from r3el.entity.MediaFile import MediaFile, MediaFileState
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.entity.TMDBReference import TMDBReference
from r3el.server.MatchResults import MatchResults


class MovieSelectionTests(unittest.TestCase):
    def setUp(self):
        catalogue = patch('r3el.app.BatchMatching.BatchMatching._catalogue')
        catalogue.start()
        self.addCleanup(catalogue.stop)
        self.listener_patch = patch('r3el.app.MovieSelection.ZMQServer')
        self.listener = self.listener_patch.start()
        self.addCleanup(self.listener_patch.stop)
        self.tools_patch = patch('r3el.app.MovieSelection.MCPTools')
        self.tools = self.tools_patch.start().return_value
        self.addCleanup(self.tools_patch.stop)
        self.tools.__aenter__.return_value = self.tools
        self.tools.definition = {'type': 'function', 'function': {'name': 'submit_multiple_choice'}}

        async def submit(arguments):
            handler = self.listener.call_args.args[1]
            return handler(ZMQMsg(sender='test', target=DMessage.MULTIPLE_CHOICE, method=DMessage.SUBMIT_MULTIPLE_CHOICE,
                payload={'attempt_id': handler.__self__._attempt_id, 'submission': arguments}))

        self.tools.submit = AsyncMock(side_effect=submit)
        self.match = TMDBMatch('Movie', 2020, response={'total_results': 2, 'results': [
            {'id': 71, 'title': 'Movie Extra', 'overview': 'A traveler returns home.', 'release_date': '2020-02-03', 'vote_count': 1234},
            {'id': 99, 'title': 'Movie'}]})
        self.llm = Mock()
        self.llm.complete = AsyncMock()
        self.record = Mock(return_value=1)
        self.log = EventWriter(self.record, {'batch_id': 'batch', 'item_id': 'file', 'filename': 'x.mkv'})

    def reply(self, content):
        self.llm.complete.return_value = json.dumps({'choices': [{'message': {'tool_calls': [{'id': 'choice-1', 'type': 'function', 'function': {'name': 'submit_multiple_choice', 'arguments': json.dumps({'number': content})}}]}}]})

    def test_candidate_payload_contains_titles_overviews_and_votes_and_logs_prompt(self):
        self.reply(2)
        result = MovieSelection(self.llm).run(self.match, self.log)
        self.assertEqual(result.selected_number, 2)
        self.assertEqual(result.response['total_results'], 1)
        self.assertEqual(result.response['results'], [self.match.response['results'][1]])
        messages = self.llm.complete.call_args.args[0]['messages']
        self.assertIn('current_date', json.loads(messages[0]['content'])['data'])
        example = json.loads(messages[1]['content'])
        self.assertEqual(example['instructions'], 'Here is an example.')
        self.assertEqual(example['data']['examples'], [{
            'query': {'title': 'Batman', 'year': 2022},
            'candidates': [
                {'number': 1, 'title': 'Batman: The Audio Adventures'},
                {'number': 2, 'title': 'The Batman', 'overview': 'Two years of stalking the streets...'}],
            'output': {'name': 'submit_multiple_choice', 'arguments': {'number': 2}},
        }])
        prompt = messages[2]['content']
        data = json.loads(prompt)['data']
        self.assertEqual(data['query'], {'title': 'Movie', 'year': 2020})
        self.assertEqual(data['candidates'], [
            {'number': 1, 'title': 'Movie Extra', 'overview': 'A traveler returns home.', 'vote_count': 1234},
            {'number': 2, 'title': 'Movie', 'overview': '', 'vote_count': None}])
        self.assertIn('A traveler returns home.', prompt)
        self.assertNotIn('2020-02-03', prompt)
        events = [call.args[0] for call in self.record.call_args_list]
        self.assertEqual(events[1].source_name, 'example')
        self.assertEqual(events[1].classification.subcategory, 'LLMPrompt')
        self.assertEqual(events[2].source_name, 'multiple_choice')
        self.assertEqual(events[3].name, 'reply_received')
        restored = TMDBMatch(**json.loads(json.dumps(asdict(result))))
        prepared = MatchResults(TMDBReference([], [])).prepare(restored)
        self.assertEqual(prepared['status'], 'Resolved')
        self.assertEqual([movie['selected'] for movie in prepared['movies']], [True])
        self.assertEqual(prepared['movies'][0]['id'], 99)

    def test_no_choice_and_invalid_replies_remain_ambiguous(self):
        for content in (0, 3, -1, 2.0, '2', 'Movie', '2 because it matches', None, True):
            with self.subTest(content=content):
                self.reply(content)
                result = MovieSelection(self.llm).run(self.match, self.log)
                self.assertFalse(result.selected_number)
                self.assertEqual(bool(result.selection_error), content != 0)
                self.assertEqual(MatchResults(TMDBReference([], [])).prepare(result)['status'], 'Ambiguous')
        self.llm.complete.return_value = 'not json'
        self.assertIsNotNone(MovieSelection(self.llm).run(self.match, self.log).selection_error)
        self.llm.complete.side_effect = httpx.ConnectError('unavailable')
        self.assertIsNotNone(MovieSelection(self.llm).run(self.match, self.log).selection_error)

    @patch('r3el.app.BatchMatching.TMDB.from_environment')
    @patch('r3el.app.BatchMatching.LLM.from_environment')
    def test_saved_ambiguous_search_is_selected_and_reused_with_failed_selection_retry(self, llm, tmdb):
        llm.return_value = self.llm
        item = MediaFile('file', '/tmp/x.mkv', MediaFileState.IDENTIFIED,
                         Identification('Movie', 2020, 5), tmdb_match=self.match)
        workspace = Mock()
        workspace.processing.side_effect = nullcontext
        workspace.matching.side_effect = nullcontext
        workspace.load.return_value = MediaFileBatch('batch', 1, '/tmp', files=[item],
            state=MediaFileBatchState.IDENTIFICATION_COMPLETED)
        workspace.save_match.side_effect = lambda batch, file, result, event: setattr(item, 'tmdb_match', result)
        runner = BatchMatching(workspace, self.record)
        self.reply('invalid')
        runner.run('batch')
        self.assertIsNotNone(item.tmdb_match.selection_error)
        self.reply(2)
        runner.run('batch')
        runner.run('batch')
        self.assertEqual(item.tmdb_match.selected_number, 2)
        self.assertEqual(self.llm.complete.call_count, 2)
        tmdb.return_value.search.assert_not_called()

        # A fresh search is checkpointed before selection and uses the same flow.
        item.tmdb_match = None
        tmdb.return_value.search.return_value = self.match.response
        runner.run('batch')
        self.assertEqual(item.tmdb_match.selected_number, 2)
        tmdb.return_value.search.assert_called_once_with('Movie', 2020)
        checkpoints = workspace.save_match.call_args_list[-2:]
        self.assertIsNone(checkpoints[0].args[2].selected_number)
        self.assertTrue(checkpoints[0].args[2].selection_pending)
        self.assertFalse(checkpoints[1].args[2].selection_pending)
        self.assertEqual(checkpoints[1].args[2].selected_number, 2)

        # Exhausted zero results and single results need no further selection call.
        for candidates in ([], [{'id': 99, 'title': 'Movie'}]):
            item.state = MediaFileState.IDENTIFIED
            item.retries = 3
            item.tmdb_match = None
            tmdb.return_value.search.return_value = {'total_results': len(candidates), 'results': candidates}
            runner.run('batch')
        self.assertEqual(self.llm.complete.call_count, 3)


class OverviewExcerptTests(unittest.TestCase):
    def test_overview_ends_at_sentence_boundary_after_roughly_two_lines(self):
        from r3el.app.prompts.MultipleChoice import MultipleChoice

        first = 'A traveler returns home. '
        second = 'She ' + 'searches the town ' * 9 + 'for her family.'
        overview = first + second + ' This later sentence should not be included.'
        self.assertEqual(MultipleChoice._excerpt(overview), first + second)
        self.assertEqual(MultipleChoice._excerpt('Short story! Another event?'), 'Short story! Another event?')
        self.assertEqual(MultipleChoice._excerpt('A complete sentence. An unfinished fragment'),
                         'A complete sentence. An unfinished fragment.')
        self.assertEqual(MultipleChoice._excerpt('  A story\nwith spaces.  '), 'A story with spaces.')
        self.assertEqual(MultipleChoice._excerpt(''), '')
        self.assertEqual(MultipleChoice._excerpt('No punctuation'), 'No punctuation.')
        quoted = 'A ' + 'very long story ' * 12 + 'ends with “Goodbye.”'
        self.assertEqual(MultipleChoice._excerpt(quoted + ' Omitted.'), quoted)


class PendingSelectionTests(unittest.TestCase):
    def test_pending_selection_status_and_matches_link(self):
        from dataclasses import replace
        from r3el.server.EventPages import EventPages

        match = TMDBMatch('Movie', 2020, response={'total_results': 11, 'results': [{'id': 1}]},
                          selection_pending=True)
        item = MediaFile('file', '/tmp/movie.mkv', MediaFileState.IDENTIFIED,
                         Identification('Movie', 2020, 10), tmdb_match=match)
        batch = MediaFileBatch('batch', 1, '/tmp', files=[item],
                              state=MediaFileBatchState.IDENTIFICATION_COMPLETED)
        for pending, number, label in ((True, None, '11 matches'), (False, 1, '1 match'),
                                       (False, 0, '11 matches')):
            item.tmdb_match = replace(match, selection_pending=pending, selected_number=number)
            body = EventPages().render('control.html', workspace=batch, refresh=0).decode()
            self.assertNotIn('class="file-action"', body)
            self.assertIn('<td>Pending</td>' if pending else '<td>Imported</td>', body)
            self.assertIn(f'href="/matches/batch/file">{label}</a>', body)

    @patch('r3el.app.BatchMatching.MovieSelection.run', side_effect=RuntimeError('bug'))
    def test_unexpected_selection_failure_clears_pending_and_surfaces(self, select):
        item = MediaFile('file', '/tmp/movie.mkv', MediaFileState.IDENTIFIED,
                         Identification('Movie', 2020, 10), tmdb_match=TMDBMatch(
                             'Movie', 2020, response={'total_results': 2, 'results': [{'id': 1}]}))
        workspace = Mock()
        workspace.processing.side_effect = nullcontext
        workspace.matching.side_effect = nullcontext
        workspace.load.return_value = MediaFileBatch('batch', 1, '/tmp', files=[item],
            state=MediaFileBatchState.IDENTIFICATION_COMPLETED)
        with self.assertRaisesRegex(RuntimeError, 'bug'):
            BatchMatching(workspace, Mock(return_value=1)).run('batch')
        checkpoints = workspace.save_match.call_args_list
        self.assertTrue(checkpoints[0].args[2].selection_pending)
        self.assertFalse(checkpoints[-1].args[2].selection_pending)
        self.assertEqual(checkpoints[-1].args[2].label, '2 matches')
