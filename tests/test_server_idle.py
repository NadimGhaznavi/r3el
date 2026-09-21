"""Default startup keeps the listener alive without processing the workspace."""

import argparse
import asyncio
import unittest
from unittest.mock import patch

from r3el.server.R3elServer import run


class IdleServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_idle_until_cancelled_and_cleans_up(self):
        with (patch('r3el.server.R3elServer.DbMgr') as database,
              patch('r3el.server.R3elServer.ServerLifecycle') as lifecycle,
              patch('r3el.server.R3elServer.ZMQServer') as listener,
              patch('r3el.server.R3elServer.BatchIdentification') as batch):
            task = asyncio.create_task(run(argparse.Namespace(
                zmq_endpoint='tcp://127.0.0.1:*', run_batch=False)))
            try:
                await asyncio.sleep(0)
                self.assertFalse(task.done())
                listener.return_value.__enter__.assert_called_once()
                batch.assert_not_called()
                lifecycle.return_value.started.assert_called_once()
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            listener.return_value.__exit__.assert_called_once()
            lifecycle.return_value.stopped.assert_called_once()
            database.return_value.close.assert_called_once()
