"""Forward a pair proposal to Ax3l for validation and submission."""

import asyncio
import json

from ax3l.constants.DAx3l import DAx3l
from ax3l.zmq.ZMQClient import ZMQClient
from ax3l.zmq.ZMQMsg import ZMQMsg


class SubmitPairValues:
    def __init__(self, endpoint: str = DAx3l.ZMQ_ENDPOINT):
        self._client = ZMQClient(endpoint)

    async def submit(self, pair: str, value_1: int | float, value_2: int | float) -> str:
        response = await asyncio.to_thread(
            self._client.request,
            ZMQMsg(sender="mcp-snakelab", target="snakelab", method="submit_pair_values",
                   payload={"pair": pair, "value_1": value_1, "value_2": value_2}),
        )
        return json.dumps(response.payload, ensure_ascii=False, allow_nan=False)
