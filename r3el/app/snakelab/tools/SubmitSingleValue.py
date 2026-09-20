"""Forward a single-parameter proposal to Ax3l for validation and submission."""

import asyncio
import json

from ax3l.constants.DAx3l import DAx3l
from ax3l.zmq.ZMQClient import ZMQClient
from ax3l.zmq.ZMQMsg import ZMQMsg


class SubmitSingleValue:
    def __init__(self, endpoint: str = DAx3l.ZMQ_ENDPOINT):
        self._client = ZMQClient(endpoint)

    async def submit(self, parameter: str, value: int | float) -> str:
        response = await asyncio.to_thread(
            self._client.request,
            ZMQMsg(sender="mcp-snakelab", target="snakelab", method="submit_single_value",
                   payload={"parameter": parameter, "value": value}),
        )
        return json.dumps(response.payload, ensure_ascii=False, allow_nan=False)
