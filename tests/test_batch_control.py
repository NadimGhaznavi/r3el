"""Exercise control routing and processing alongside real ZMQ submissions."""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from r3el.app.BatchControlHandler import BatchControlHandler
from r3el.app.BatchProcessor import BatchProcessor
from r3el.app.MessageHandler import MessageHandler
from r3el.app.SubmissionHandler import SubmissionHandler
from r3el.constants.DMessage import DMessage
from r3el.entity.BatchRequest import BatchRequest
from r3el.interface.BatchControl import BatchControl
from r3el.zmq.ZMQClient import ZMQClient
from r3el.zmq.ZMQMsg import ZMQMsg
from r3el.zmq.ZMQServer import ZMQServer


def command(**changes):
    payload = dict(input_directory='/tmp/input', output_directory='/tmp/output', batch_size=5)
    payload.update(changes)
    return ZMQMsg(sender=DMessage.CONTROL, target=DMessage.BATCH,
                  method=DMessage.NEW_BATCH, payload=payload)


class BatchMessageTests(unittest.TestCase):
    def test_invalid_external_parameters_never_schedule_work(self):
        submit = Mock()
        handler = BatchControlHandler(submit, True)
        for changes in ({'batch_size': True}, {'batch_size': '5'}, {'batch_size': 0},
                        {'batch_size': 6}, {'input_directory': '../films'},
                        {'output_directory': None}, {'input_directory': '/tmp/\x00'},
                        {'extra': 'field'}):
            with self.subTest(changes=changes):
                result = handler.handle(command(**changes))
                self.assertEqual(result['error']['code'], DMessage.INVALID_PARAMETERS)
        submit.assert_not_called()

    def test_sender_and_model_configuration_are_checked(self):
        submit = Mock()
        request = command()
        request.sender = DMessage.MCP_IDENTIFICATION
        self.assertEqual(BatchControlHandler(submit, True).handle(request)['error']['code'],
                         DMessage.UNKNOWN_REQUEST)
        self.assertEqual(BatchControlHandler(submit, False).handle(command())['error']['code'],
                         DMessage.NOT_CONFIGURED)
        submit.assert_not_called()

    def test_unknown_route_is_rejected(self):
        submission, batch = Mock(), Mock()
        request = command()
        request.method = 'unknown'
        self.assertEqual(MessageHandler(submission, batch).handle(request)['error']['code'],
                         DMessage.UNKNOWN_REQUEST)
        submission.assert_not_called()
        batch.assert_not_called()


class BatchProcessorTests(unittest.IsolatedAsyncioTestCase):
    async def test_listener_accepts_submissions_during_batch_and_returns_to_idle(self):
        started, finish = asyncio.Event(), asyncio.Event()
        requests = []

        async def execute(request):
            requests.append(request)
            started.set()
            await finish.wait()

        processor = BatchProcessor(execute)
        submissions = SubmissionHandler(Mock(return_value=1))
        submissions.register({'attempt_id': 'active-attempt', 'batch_id': 'batch-1', 'item_id': 'item-1'}, 1)
        handler = MessageHandler(submissions.handle, BatchControlHandler(processor.submit, True).handle)
        worker = asyncio.create_task(processor.run())
        try:
            with ZMQServer('tcp://127.0.0.1:*', handler.handle) as listener:
                control = BatchControl(listener.endpoint)
                parameters = BatchRequest('/tmp/input', '/tmp/output', 5)
                reply = await asyncio.to_thread(control.new_batch, parameters)
                self.assertEqual(reply['status'], DMessage.ACCEPTED)
                await asyncio.wait_for(started.wait(), 2)
                reply = await asyncio.to_thread(control.new_batch, parameters)
                self.assertEqual(reply['status'], DMessage.BUSY)
                submission = ZMQMsg(
                    sender=DMessage.MCP_IDENTIFICATION, target=DMessage.IDENTIFICATION,
                    method=DMessage.SUBMIT_IDENTIFICATION,
                    payload={'attempt_id': 'active-attempt',
                             'submission': {'title': 'Example Film', 'year': 2020, 'confidence': 8}},
                )
                reply = await asyncio.to_thread(ZMQClient(listener.endpoint).request, submission)
                self.assertEqual(reply.payload['status'], 'ok')
                finish.set()
                # Let the worker finish and return to its queue wait.
                await asyncio.sleep(0)
                started.clear()
                reply = await asyncio.to_thread(control.new_batch, parameters)
                self.assertEqual(reply['status'], DMessage.ACCEPTED)
                await asyncio.wait_for(started.wait(), 2)
                self.assertEqual(requests, [parameters, parameters])
        finally:
            worker.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await worker
        self.assertFalse(processor.submit(parameters))

    async def test_external_failure_returns_to_idle_without_retry(self):
        execute = AsyncMock(side_effect=[OSError('input unavailable'), None])
        processor = BatchProcessor(execute)
        parameters = BatchRequest('/tmp/input', '/tmp/output', 5)
        self.assertTrue(processor.submit(parameters))
        self.assertFalse(processor.submit(parameters))
        with self.assertLogs(level='ERROR'):
            worker = asyncio.create_task(processor.run())
            await asyncio.sleep(0)
        self.assertTrue(processor.submit(parameters))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertEqual(execute.await_count, 2)
        worker.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await worker

    async def test_programming_errors_surface_and_close_processor(self):
        processor = BatchProcessor(AsyncMock(side_effect=TypeError('bug')))
        parameters = BatchRequest('/tmp/input', '/tmp/output', 5)
        self.assertTrue(processor.submit(parameters))
        with self.assertRaisesRegex(TypeError, 'bug'):
            await processor.run()
        self.assertFalse(processor.submit(parameters))
