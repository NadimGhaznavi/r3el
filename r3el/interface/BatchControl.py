"""Send batch commands from the HTTP control server to R3el."""

from dataclasses import asdict

from r3el.constants.DMessage import DMessage
from r3el.entity.BatchRequest import BatchRequest
from r3el.zmq.ZMQClient import ZMQClient
from r3el.zmq.ZMQMsg import ZMQMsg


class BatchControl:
    def __init__(self, endpoint: str) -> None:
        self._client = ZMQClient(endpoint)

    def new_batch(self, request: BatchRequest) -> dict:
        return self._client.request(ZMQMsg(
            sender=DMessage.CONTROL, target=DMessage.BATCH, method=DMessage.NEW_BATCH,
            payload=asdict(request),
        )).payload
