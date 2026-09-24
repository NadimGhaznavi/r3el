"""Result presentation and shared catalog refresh contracts."""

import json
import unittest
from unittest.mock import Mock, patch

import httpx

from r3el.activity.TMDBReferenceRefresh import TMDBReferenceRefresh
from r3el.entity.MediaFile import MediaFile
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.entity.TMDBReference import TMDBGenre, TMDBLanguage, TMDBReference
from r3el.interface.TMDB import TMDB, TMDBError
from r3el.server.EventPages import EventPages


class MatchResultTests(unittest.TestCase):
    def setUp(self):
        self.reference = TMDBReference([TMDBGenre(53, 'Thriller'), TMDBGenre(878, 'Science Fiction')],
                                      [TMDBLanguage('en', 'English', 'English')])
        self.movie = dict(id=333371, title='10 Cloverfield Lane', original_title='10 Cloverfield Lane',
                          release_date='2016-03-10', original_language='en', genre_ids=[53, 878],
                          overview='After a catastrophic car crash...', vote_average=7.01, vote_count=8935,
                          poster_path='/example.jpg')

    def render(self, results, total=None, error=None):
        match = TMDBMatch('10 Cloverfield Lane', 2016,
                          response={'total_results': len(results) if total is None else total, 'results': results},
                          error=error)
        return EventPages().render('match.html', file=MediaFile('file', '/tmp/movie.mkv'), match=match,
            reference=self.reference, response_json=json.dumps(match.response, indent=2), refresh=0).decode()

    def test_resolved_movie_card_formats_saved_metadata(self):
        body = self.render([self.movie])
        for expected in ('Resolved', '7.01', '8,935 votes', 'March 10, 2016',
                         'Thriller · Science Fiction', '2016 · Movie · English', 'TMDB #333371',
                         'https://image.tmdb.org/t/p/w500/example.jpg', '<details class="match-json">'):
            self.assertIn(expected, body)
        self.assertNotIn('<details class="match-json" open', body)

    def test_ambiguous_partial_page_does_not_mark_candidate_resolved(self):
        body = self.render([self.movie], total=21)
        self.assertIn('Ambiguous', body)
        self.assertIn('No movie has been selected.', body)
        self.assertIn('Showing 1 of 21 results', body)
        self.assertNotIn('✓', body)

    def test_selected_match_shows_only_chosen_movie_in_cards_and_json(self):
        from dataclasses import replace
        from r3el.server.MatchResults import MatchResults

        match = TMDBMatch('Movie', 2016, response={'total_results': 11, 'total_pages': 1,
            'results': [{'id': 123, 'title': 'Discarded candidate'}, self.movie]}, selected_number=2)
        for saved in (match, replace(match, response=match.resolved_response)):
            with self.subTest(total=saved.response['total_results']):
                result = MatchResults(self.reference).prepare(saved)
                self.assertEqual(result['total'], 1)
                self.assertEqual([movie['id'] for movie in result['movies']], [333371])
                body = EventPages().render('match.html', file=MediaFile('file', '/tmp/movie.mkv'),
                    match=saved, reference=self.reference, refresh=0).decode()
                self.assertEqual(body.count('class="movie-card"'), 1)
                self.assertIn('10 Cloverfield Lane', body)
                self.assertNotIn('Discarded candidate', body)
                self.assertNotIn('Showing 1 of', body)
                self.assertIn('Selected by LLM', body)

    def test_missing_metadata_empty_results_and_failures(self):
        body = self.render([{'id': 1}])
        for text in ('No poster available', 'No overview available.', 'Year unknown', 'Not rated'):
            self.assertIn(text, body)
        self.assertIn('No matches', self.render([]))
        self.assertIn('Match failed', self.render([], error='TMDB returned HTTP 429.'))
        self.assertNotIn('Resolved', self.render([], error='TMDB returned HTTP 429.'))

    def test_external_text_is_escaped_and_poster_paths_are_restricted(self):
        self.movie.update(title='<script>bad</script>', overview='<img src=x onerror=alert(1)>',
                          poster_path='//evil.invalid/p.jpg', release_date='bad-date')
        body = self.render([self.movie])
        self.assertNotIn('<script>', body.split('<main>', 1)[1].split('</main>', 1)[0])
        self.assertIn('&lt;script&gt;', body)
        self.assertNotIn('src="//evil.invalid', body)
        self.assertIn('No poster available', body)


class ReferenceTests(unittest.TestCase):
    @patch('r3el.interface.TMDB.httpx.get')
    def test_catalog_download_preserves_ids_codes_and_native_names(self, get):
        get.side_effect = [httpx.Response(200, json=value, request=httpx.Request('GET', TMDB.URL)) for value in (
            {'genres': [{'id': 53, 'name': 'Thriller'}]},
            [{'iso_639_1': 'fr', 'english_name': 'French', 'name': 'Français'}])]
        reference = TMDB('secret').reference()
        self.assertEqual(reference.languages, [TMDBLanguage('fr', 'French', 'Français')])
        self.assertEqual(reference.genres, [TMDBGenre(53, 'Thriller')])

    @patch('r3el.interface.TMDB.httpx.get')
    def test_bad_catalog_does_not_replace_saved_labels(self, get):
        get.side_effect = [httpx.Response(200, json=value, request=httpx.Request('GET', TMDB.URL)) for value in (
            {'genres': [{'id': 53, 'name': 'Thriller'}]}, [{'iso_639_1': 'invalid'}])]
        references = Mock()
        with self.assertRaises(TMDBError):
            TMDBReferenceRefresh(TMDB('secret'), references).run()
        references.save.assert_not_called()
