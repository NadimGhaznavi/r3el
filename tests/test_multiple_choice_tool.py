"""Validate the multiple-choice form through MCP and real ZeroMQ."""

import unittest

from r3el.app.MultipleChoiceHandler import MultipleChoiceHandler
from r3el.constants.DMessage import DMessage
from r3el.interface.MCPTools import MCPTools
from r3el.zmq.ZMQMsg import ZMQMsg
from r3el.zmq.ZMQServer import ZMQServer


class MultipleChoiceHandlerTests(unittest.TestCase):
    def test_validation_stale_attempt_and_duplicate_submission(self):
        handler = MultipleChoiceHandler('active', 2)

        def submit(data, attempt='active', target=DMessage.MULTIPLE_CHOICE):
            return handler.handle(ZMQMsg(sender='test', target=target, method=DMessage.SUBMIT_MULTIPLE_CHOICE,
                payload={'attempt_id': attempt, 'submission': data}))

        self.assertEqual(submit({'number': 1}, 'stale')['status'], 'error')
        self.assertEqual(submit({'number': 1}, target='wrong')['status'], 'error')
        for data in (None, {}, {'number': 1, 'candidate_count': 99}, {'number': True},
                     {'number': '1'}, {'number': 1.0}, {'number': -1}, {'number': 3}):
            self.assertEqual(submit(data)['status'], 'rejected')
        self.assertEqual(submit({'number': 0}), {'status': 'ok', 'selected_number': 0})
        self.assertEqual(submit({'number': 2})['status'], 'error')


class MultipleChoiceToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_discovery_and_submission_reaches_zmq_handler(self):
        handler = MultipleChoiceHandler('active', 2)
        with ZMQServer('tcp://127.0.0.1:*', handler.handle) as listener:
            async with MCPTools(listener.endpoint, 'active', DMessage.SUBMIT_MULTIPLE_CHOICE) as tools:
                function = tools.definition['function']
                self.assertEqual(function['name'], 'submit_multiple_choice')
                self.assertEqual(set(function['parameters']['properties']), {'number'})
                self.assertEqual(function['parameters']['properties']['number']['type'], 'integer')
                self.assertEqual((await tools.submit({'number': '2'}))['status'], 'rejected')
                self.assertEqual((await tools.submit({'number': 3}))['status'], 'rejected')
                self.assertEqual(await tools.submit({'number': 2}), {'status': 'ok', 'selected_number': 2})
                self.assertEqual((await tools.submit({'number': 1}))['status'], 'error')

    async def test_shared_mcp_client_preserves_identification_tool(self):
        from unittest.mock import Mock
        from r3el.app.SubmissionHandler import SubmissionHandler
        from r3el.interface.IdentificationTools import IdentificationTools

        handler = SubmissionHandler(Mock(return_value=1))
        handler.register({'batch_id': 'batch', 'item_id': 'file', 'attempt_id': 'identify'}, 1)
        with ZMQServer('tcp://127.0.0.1:*', handler.handle) as listener:
            async with IdentificationTools(listener.endpoint, 'identify') as tools:
                self.assertEqual(tools.definition['function']['name'], 'submit_identification')
                result = await tools.submit({'title': 'Movie', 'year': 2020, 'confidence': 10})
                self.assertEqual(result['status'], 'ok')
        handler.unregister('identify')


class MovieSelectionIntegrationTests(unittest.TestCase):
    def test_tool_call_is_forwarded_and_validated_end_to_end(self):
        import json
        from unittest.mock import AsyncMock, Mock
        from r3el.activity.EventWriter import EventWriter
        from r3el.app.MovieSelection import MovieSelection
        from r3el.entity.TMDBMatch import TMDBMatch

        llm = Mock()
        llm.complete = AsyncMock(return_value=json.dumps({'choices': [{'message': {'tool_calls': [
            {'id': 'choice', 'type': 'function', 'function': {
                'name': 'submit_multiple_choice', 'arguments': '{"number": 2}'}}]}}]}))
        match = TMDBMatch('Movie', 2020, response={'total_results': 2, 'results': [
            {'id': 7, 'title': 'Other Movie'}, {'id': 8, 'title': 'Movie'}]})
        record = Mock(return_value=1)
        result = MovieSelection(llm).run(match, EventWriter(record, {'batch_id': 'batch', 'item_id': 'file'}))
        self.assertEqual(result.selected_number, 2)
        payload = llm.complete.call_args.args[0]
        self.assertEqual(payload['tool_choice'], 'required')
        self.assertEqual([tool['function']['name'] for tool in payload['tools']], ['submit_multiple_choice'])
        self.assertIn('submission_accepted', [call.args[0].name for call in record.call_args_list])

    def test_plain_text_and_wrong_tool_calls_are_rejected(self):
        import json
        from r3el.app.MovieSelection import MovieSelection

        messages = [{'content': '2'}, {'tool_calls': []}, {'tool_calls': [{
            'id': 'wrong', 'function': {'name': 'submit_identification', 'arguments': '{"number": 2}'}}]}]
        for message in messages:
            with self.assertRaises(ValueError):
                MovieSelection._tool_call(json.dumps({'choices': [{'message': message}]}))
