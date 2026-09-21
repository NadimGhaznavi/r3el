"""Verify message presentation selection and its template contract."""

from datetime import datetime
import json
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

    def test_default_preserves_plain_text_and_limits_preview(self):
        self.event['name'] = 'default_test_event'
        for length in (1200, 1201):
            with self.subTest(length=length):
                self.event['content'] = 'x' * length
                body = self.render()
                ending = '…' if length > 1200 else ''
                self.assertIn('<a href="/events/42"><pre>' + 'x' * 1200 + ending + '</pre></a>', body)
                self.assertNotIn('Full event</a>', body)

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
