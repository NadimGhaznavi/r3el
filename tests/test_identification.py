import unittest

from r3el.app.ValidateIdentification import ValidateIdentification
from r3el.app.ToolConversation import ToolConversation
from r3el.app.SubmissionHandler import SubmissionHandler
from r3el.app.prompts.FileContext import FileContext
from r3el.app.prompts.SubmitIdentificationPrompt import SubmitIdentificationPrompt
from r3el.zmq.ZMQMsg import ZMQMsg


class IdentificationTests(unittest.TestCase):
    def test_form_validation_preserves_unicode_and_punctuation(self):
        result = ValidateIdentification().run({'title': '  Amélie: A Film!  ', 'year': 2001, 'confidence': 8})
        self.assertEqual(result.title, 'Amélie: A Film!')

    def test_confidence_integer_range_is_preserved(self):
        for confidence in (0, 1, 8, 10):
            with self.subTest(confidence=confidence):
                result = ValidateIdentification().run({'title': 'Film', 'year': 2001, 'confidence': confidence})
                self.assertEqual(result.confidence, confidence)
                self.assertIs(type(result.confidence), int)

    def test_prompts_request_integer_confidence(self):
        for prompt in (FileContext('Film.mkv'), SubmitIdentificationPrompt()):
            self.assertIn('integer from 0 to 10', prompt.to_json())

    def test_basic_invalid_fields(self):
        good = {'title': 'Example', 'year': 2001, 'confidence': 8}
        invalid = [('title', ''), ('title', ' '), ('title', 'x' * 256), ('title', ' ' * 256 + 'x'),
                   ('title', 'text\x00'), ('title', 'text\u202e'), ('title', []),
                   ('year', True), ('year', '2001'), ('year', 0), ('year', 10000),
                   ('confidence', True), ('confidence', 10 ** 400), ('confidence', float('nan')),
                   ('confidence', float('inf')), ('confidence', -1), ('confidence', 11),
                   ('confidence', 0.9), ('confidence', 9.0), ('confidence', '9'), ('confidence', None)]
        for key, value in invalid:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                ValidateIdentification().run({**good, key: value})
        with self.assertRaises(ValueError):
            ValidateIdentification().run({**good, 'extra': 1})

    def test_malformed_model_reply_is_rejected(self):
        for body in ('not json', '{}', '{"choices": []}', '{"choices": [{"message": null}]}'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                ToolConversation._tool_call(body)

    def test_stale_attempt_cannot_submit(self):
        handler = SubmissionHandler(lambda event: self.fail('Should not log an unassigned request'))
        result = handler.handle(ZMQMsg(sender='test', target='identification',
            method='submit_identification', payload={'attempt_id': 'expired'}))
        self.assertEqual(result['status'], 'error')
