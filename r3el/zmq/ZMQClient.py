"""Bounded, synchronous JSON request/reply transport with no application policy."""

import math
from typing import Any

import zmq

from r3el.constants.DZMQ import DZMQ
from r3el.zmq.ZMQMsg import ZMQMsg


class ZMQClient:
    def __init__(self, endpoint: str, timeout: float = DZMQ.TIMEOUT_SECONDS):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be a positive, finite number of seconds")
        self.endpoint = endpoint
        self._timeout_ms = math.ceil(timeout * 1000)

    def request_json(self, message: dict[str, Any]) -> Any:
        """Use a fresh socket per call; propagate transport failures without retrying."""
        with zmq.Context() as context:
            with context.socket(zmq.REQ) as socket:
                socket.setsockopt(zmq.LINGER, 0)
                socket.setsockopt(zmq.SNDTIMEO, self._timeout_ms)
                socket.setsockopt(zmq.RCVTIMEO, self._timeout_ms)
                socket.connect(self.endpoint)
                socket.send_json(message, allow_nan=False)
                return socket.recv_json()

    def request(self, message: ZMQMsg) -> ZMQMsg:
        """Return R3el's envelope, including rejection/error replies, unchanged."""
        return ZMQMsg.from_dict(self.request_json(message.to_dict()))
