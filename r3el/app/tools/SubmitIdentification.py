"""Forward the submission to R3el over ZeroMQ."""

import asyncio
import json

from r3el.zmq.ZMQClient import ZMQClient
from r3el.zmq.ZMQMsg import ZMQMsg


class SubmitIdentification:
    def __init__(self, endpoint: str, attempt_id: str) -> None:
        self._client = ZMQClient(endpoint)
        self._attempt_id = attempt_id

    async def submit(self, title, year, confidence) -> str:
        response = await asyncio.to_thread(self._client.request, ZMQMsg(
            sender='mcp-identification', target='identification', method='submit_identification',
            payload={'attempt_id': self._attempt_id,
                     'submission': {'title': title, 'year': year, 'confidence': confidence}},
        ))
        return json.dumps(response.payload, ensure_ascii=False, allow_nan=False)
