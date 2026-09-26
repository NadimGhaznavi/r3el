"""Verify message presentation selection and its template contract."""

from datetime import datetime
import json
import html
import re
import unittest

from jinja2 import ChoiceLoader, DictLoader, TemplateSyntaxError, UndefinedError

from r3el.server.EventPages import EventPages


class EventPagesTests(unittest.TestCase):
    def setUp(self):
        self.pages = EventPages()
        self.event = dict(event_id=42, occurred_at=datetime(2026, 9, 20),
                          log_level='INFO', category='Batch', subcategory='Lifecycle',
                          name='batch_completed', source_name='BatchIdentification',
                          content='Batch finished.')

    def render(self):
        return self.pages.render('events.html', events=[self.event], category=None,
                                 subcategory=None, name=None, refresh=0).decode()

    def add_template(self, source):
        self.pages._templates.loader = ChoiceLoader([
            DictLoader({'messages/batch_completed.html': source}),
            self.pages._templates.loader,
        ])

    def test_control_shows_latest_batch_event_using_event_log_template(self):
        from r3el.entity.MediaFileBatch import MediaFileBatch
        batch = MediaFileBatch('batch', 1, '/source')
        self.event.update(name='file_copy', content=json.dumps({
            'context': {'batch_id': 'batch'},
            'data': {'outcome': 'verifying', 'verified_bytes': 10, 'total_bytes': 20,
                     'source_path': '/source/<movie>.avi'}}))
        body = self.pages.render('control.html', workspace=batch, refresh=0,
                                 latest_event=self.event).decode()
        status = body.split('<p id="batch-processing"', 1)[1].split('</p>', 1)[0]
        self.assertIn('Verifying copied media: 10 / 20 bytes', status)
        self.assertIn('&lt;movie&gt;.avi', status)
        self.assertIn('href="/events/42"', status)
        self.assertLess(body.index('Clear Current Batch'), body.index('<p id="batch-processing"'))
        self.assertLess(body.index('<p id="batch-processing"'), body.index('Current Batch</h2>'))
        batch.stop_requested = True
        body = self.pages.render('control.html', workspace=batch, refresh=0,
                                 latest_event=self.event).decode()
        self.assertIn('Stopping after the current operation...', body)
        self.assertIn('Verifying copied media: 10 / 20 bytes', body)

    def test_default_preserves_plain_text_and_limits_preview(self):
        self.event['name'] = 'default_test_event'
        for length in (1200, 1201):
            with self.subTest(length=length):
                self.event['content'] = 'x' * length
                body = self.render()
                ending = '…' if length > 1200 else ''
                self.assertIn('<a href="/events/42"><pre>' + 'x' * 1200 + ending + '</pre></a>', body)
                self.assertNotIn('Full event</a>', body)

    def test_tmdb_search_and_result_summaries_link_to_escaped_details(self):
        self.event.update(category='TMDB', subcategory='Search', name='tmdb_search', source_name='TMDB',
            content=json.dumps({'context': {'filename': '<movie>.mkv'}, 'data': {
                'parameters': {'query': '<Superman>', 'primary_release_year': 2025, 'page': 1}}}))
        body = self.render()
        self.assertIn('<a href="/events/42">TMDB search.', body)
        self.assertIn('Title: &lt;Superman&gt;, Primary release year: 2025.', body)
        self.assertIn('Filename: &lt;movie&gt;.mkv', body)
        self.event.update(subcategory='Result', name='tmdb_result')
        for outcome, error in (('1 match', None), ('No matches', None), ('7 matches', None),
                               ('Match failed', '<connection error>')):
            self.event['content'] = json.dumps({'context': {'filename': '<movie>.mkv'},
                                                'data': {'outcome': outcome, 'error': error}})
            body = self.render()
            self.assertIn('<a href="/events/42">TMDB result.', body)
            self.assertIn(outcome, body)
            if error:
                self.assertIn('&lt;connection error&gt;', body)

    def test_catalogue_event_templates_link_to_escaped_details(self):
        cases = [
            ('file_delete', {'outcome': 'deleted', 'paths': ['/in/<movie>.mpg'],
                             'preferred_path': '/out/movie.mkv', 'error': None}, 'Duplicate files deleted.'),
            ('file_delete', {'outcome': 'failed', 'paths': ['/in/<movie>.mpg'],
                             'preferred_path': '/out/movie.mkv', 'error': '<denied>'}, 'Duplicate files deletion failed.'),
            ('file_move', {'outcome': 'moved', 'source_path': '/in/<movie>.mkv',
                           'destination_path': '/out/movie.mkv', 'error': None}, 'File moved.'),
            ('file_move', {'outcome': 'failed', 'source_path': '/in/<movie>.mkv',
                           'destination_path': '/out/movie.mkv', 'error': '<denied>'}, 'File move failed.'),
            ('db_create_record', {'outcome': 'saved', 'title': '<Movie>', 'movie_id': 123,
                                  'path': '/out/movie.mkv'}, 'Catalogue record saved.'),
        ]
        for outcome in ('downloaded', 'reused', 'failed'):
            cases.append(('artifact_download', {'outcome': outcome, 'kind': 'poster',
                'url': 'https://image.tmdb.org/t/p/original/poster.jpg',
                'path': None if outcome == 'failed' else '/out/poster.jpg',
                'error': '<denied>' if outcome == 'failed' else None},
                'Artifact download failed.' if outcome == 'failed' else f'Artifact {outcome}.'))
        for name, data, expected in cases:
            with self.subTest(name=name, outcome=data['outcome']):
                self.event.update(name=name, content=json.dumps({
                    'context': {'filename': '<movie>.mkv'}, 'data': data}))
                body = self.render()
                self.assertIn(f'<a href="/events/42">{expected}', body)
                self.assertIn('Filename: &lt;movie&gt;.mkv', body)
                self.assertNotIn('<movie>', body)
                if data.get('error'):
                    self.assertIn('Error: &lt;denied&gt;', body)
                if name == 'db_create_record':
                    self.assertIn('Title: &lt;Movie&gt;, TMDB ID: 123', body)

    def test_multiple_choice_events_render_without_identification_fields(self):
        cases = (
            ('submission_accepted', 'MultipleChoiceHandler', {'status': 'ok', 'selected_number': 2}, 'Selected number: 2'),
            ('submission_accepted', 'MultipleChoiceHandler', {'status': 'ok', 'selected_number': 0}, 'no confident choice'),
            ('submission_rejected', 'MultipleChoiceHandler', {'status': 'rejected', 'reason': '<invalid>'}, 'Reason: &lt;invalid&gt;'),
            ('submission_rejected', 'MovieSelection', {'reason': '<bad call>'}, 'Reason: &lt;bad call&gt;'),
            ('tool_received', 'MultipleChoiceHandler', {'number': 2}, 'Tool received. Number: 2'),
            ('tool_received', 'MultipleChoiceHandler', {}, 'Tool received. Number: —'),
            ('tool_started', 'MovieSelection', {'function': {'arguments': '{"number": 2}'}}, 'Tool started. Number: 2'),
            ('tool_completed', 'MovieSelection', {'status': 'ok', 'selected_number': 2}, 'Tool completed. Status: ok'),
        )
        for name, source, data, expected in cases:
            with self.subTest(name=name, data=data):
                self.event.update(name=name, source_name=source, category='Prompt',
                    subcategory='SubmissionHandler', content=json.dumps({
                        'context': {'filename': '<movie>.mkv', 'attempt_id': 'selection-id'}, 'data': data}))
                body = self.render()
                self.assertIn(expected, body)
                self.assertIn('Filename: &lt;movie&gt;.mkv', body)
                self.assertNotIn('Attempts:', body)

    def test_identification_submission_summary_still_renders(self):
        self.event.update(name='submission_accepted', source_name='SubmissionHandler',
            content=json.dumps({'context': {'filename': 'Movie.mkv', 'attempt': 1},
                               'data': {'identification': {'title': 'Movie', 'year': 2020, 'confidence': 10}}}))
        body = self.render()
        self.assertIn('Attempts: 1', body)
        self.assertIn('Title: Movie, Year: 2020, Confidence: 10', body)

    def test_structured_prompt_summaries_show_fields_and_link_to_details(self):
        from r3el.app.prompts.CurrentDate import CurrentDate
        from r3el.app.prompts.MultipleChoice import MultipleChoice
        from datetime import date

        for prompt, expected in (
            (CurrentDate(), f'Current date: {date.today().isoformat()}.'),
            (MultipleChoice('<Superman>', 2025, [('Superman', 'A hero.'), ('Other', '')]),
             'Title: &lt;Superman&gt;, Year: 2025, Candidates: 2.'),
        ):
            with self.subTest(source=prompt.source_name):
                self.event.update(name='prompt_sent', source_name=prompt.source_name,
                    content=json.dumps({'context': {'filename': '<movie>.mkv'},
                                        'data': json.loads(prompt.to_json())}))
                body = self.render()
                self.assertIn('<a href="/events/42">', body)
                self.assertIn(expected, body)
                self.assertIn('Filename: &lt;movie&gt;.mkv', body)
                self.assertNotIn('&#34;instructions&#34;', body)
                self.assertNotIn('<Superman>', body)

    def test_legacy_prompt_summaries_remain_readable(self):
        for source, content, expected in (
            ('current_date', 'Current date: 2026-09-23. Your internal training knowledge may be older than this date.',
             'Current date: 2026-09-23.'),
            ('multiple_choice', 'We are searching The Movie Database with a title, Superman, and a year, 2025.',
             'Multiple choice prompt.'),
        ):
            self.event.update(name='prompt_sent', source_name=source,
                content=json.dumps({'context': {'filename': 'Movie.mkv'},
                                    'data': {'role': 'user', 'content': content}}))
            self.assertIn(expected, self.render())

    def test_default_indents_json_and_escapes_values(self):
        self.event['name'] = 'default_test_event'
        self.event['content'] = json.dumps({'title': '<b>Film 🎬</b>'})
        body = self.render()
        self.assertIn('{\n  &#34;title&#34;: &#34;&lt;b&gt;Film 🎬&lt;/b&gt;&#34;\n}', body)
        self.assertNotIn('<b>Film', body)

    def test_custom_template_receives_payload_and_event(self):
        self.event['content'] = json.dumps({
            'context': {'batch_id': 'batch-1'}, 'data': {'result': '<done>'},
        })
        original = self.event.copy()
        self.add_template('<p>{{ event.name }}: {{ message.payload.context.batch_id }}'
                          ' / {{ message.payload.data.result }}</p>')
        body = self.render()
        self.assertIn('<p>batch_completed: batch-1 / &lt;done&gt;</p>', body)
        self.assertNotIn('<pre>', body)
        self.assertNotIn('Full event</a>', body)
        self.assertEqual(self.event, original)

    def test_broken_custom_template_does_not_use_default(self):
        for source, error in (('{% invalid %}', TemplateSyntaxError),
                              ('{{ message.missing }}', UndefinedError)):
            with self.subTest(source=source):
                self.add_template(source)
                with self.assertRaises(error):
                    self.render()

    def test_reply_preview_decodes_reasoning_before_truncating_and_escaping(self):
        self.event['name'] = 'reply_received'
        for reasoning, expected in (
            ('12345678901234567890extra', '12345678901234567890...'),
            ('First line\nSecond line', 'First line...'),
            ('First line\r\nSecond line', 'First line...'),
            ('Brief', 'Brief...'),
            ('<b>Film 🎬</b>\nMore', '&lt;b&gt;Film 🎬&lt;/b&gt;...'),
        ):
            with self.subTest(reasoning=reasoning):
                self.event['content'] = json.dumps({
                    'context': {'filename': 'foobar.foo'},
                    'data': json.dumps({'choices': [{'message': {'reasoning_content': reasoning}}]}),
                })
                body = self.render()
                self.assertIn(f'<a href="/events/42">Filename: foobar.foo, Reasoning: {expected}</a>', body)
                self.assertNotIn('Full event</a>', body)

    def test_reply_preview_handles_unvalidated_model_responses(self):
        for response in ('not JSON', '{}', '{"choices": []}',
                         '{"choices": [{"message": {"reasoning_content": null}}]}'):
            with self.subTest(response=response):
                self.assertEqual(self.pages.reasoning_preview(response), '...')

    def reply_detail(self, data):
        event = dict(self.event, name='reply_received', process_id='item-1',
                     parent_event_id=None, app_version='test',
                     content=json.dumps({'context': {'filename': 'Film.mkv'}, 'data': data}))
        return self.pages.render('event.html', event=event, refresh=0).decode(), event['content']

    def test_reply_detail_renders_decoded_formatting_before_complete_json(self):
        reasoning = ('## Identification\n\n**Film** and *year* 🎬\nNext line\n\n'
                     '- First reason\n- Second reason\n\n```text\nLiteral <tag>\n```\n\n'
                     '| Field | Value |\n| --- | --- |\n| Year | 2020 |')
        reply = json.dumps({'choices': [{'message': {'reasoning_content': reasoning}}]})
        body, original = self.reply_detail(reply)
        message = body.split('<h2>Message</h2>', 1)[1].split('<h2>JSON</h2>', 1)[0]
        for formatted in ('<h2>Identification</h2>', '<strong>Film</strong>', '<em>year</em>',
                          '<br />', '<li>First reason</li>', '<pre><code', 'Literal &lt;tag&gt;',
                          '<table>', '🎬'):
            self.assertIn(formatted, message)
        self.assertNotIn('\\n', message)
        raw = re.search(r'<h2>JSON</h2>\s*<pre class="message">(.*?)</pre>', body, re.S).group(1)
        self.assertEqual(json.loads(html.unescape(raw)), json.loads(original))

    def test_reply_reasoning_cannot_inject_html_or_script_links(self):
        reasoning = ('<script>alert(1)</script>\n\n<img src=x onerror=alert(2)>\n\n'
                     '[click](javascript:alert%281%29)\n\n'
                     '[safe](https://example.com)')
        body, _ = self.reply_detail(json.dumps({'choices': [{'message': {'reasoning_content': reasoning}}]}))
        self.assertNotIn('<script>', body.split('<main>', 1)[1].split('</main>', 1)[0])
        self.assertNotIn('<img src=x', body)
        self.assertNotIn('href="javascript:', body)
        self.assertIn('href="https://example.com"', body)

    def test_reply_detail_missing_or_malformed_reasoning_keeps_raw_data(self):
        for reply in ('not JSON', '{}', '{"choices": []}',
                      json.dumps({'choices': [{'message': {'reasoning_content': None}}]}),
                      json.dumps({'choices': [{'message': {'reasoning_content': 42}}]}),
                      json.dumps({'choices': [{'message': {'reasoning_content': ''}}]})):
            with self.subTest(reply=reply):
                body, _ = self.reply_detail(reply)
                self.assertIn('No reasoning was included in this reply.', body)
                self.assertIn('<h2>JSON</h2>', body)

    def test_other_event_detail_keeps_original_message_layout(self):
        event = dict(self.event, process_id=None, parent_event_id=None, app_version='test')
        body = self.pages.render('event.html', event=event, refresh=0).decode()
        self.assertIn('<pre class="message">Batch finished.</pre>', body)
        self.assertNotIn('<h2>JSON</h2>', body)
