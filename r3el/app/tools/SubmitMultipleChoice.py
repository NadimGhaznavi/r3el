"""Forward the numbered choice to R3el over ZeroMQ."""

import asyncio
import json

from r3el.constants.DMessage import DMessage
from r3el.zmq.ZMQClient import ZMQClient
from r3el.zmq.ZMQMsg import ZMQMsg


class SubmitMultipleChoice:
    def __init__(self, endpoint: str, attempt_id: str) -> None:
        self._client = ZMQClient(endpoint)
        self._attempt_id = attempt_id

    async def submit(self, number) -> str:
        response = await asyncio.to_thread(self._client.request, ZMQMsg(
            sender=DMessage.MCP_MULTIPLE_CHOICE, target=DMessage.MULTIPLE_CHOICE,
            method=DMessage.SUBMIT_MULTIPLE_CHOICE,
            payload={'attempt_id': self._attempt_id, 'submission': {'number': number}},
        ))
        return json.dumps(response.payload, ensure_ascii=False, allow_nan=False)
