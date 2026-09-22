"""Route application requests without coupling transport to workflows."""

from collections.abc import Callable

from r3el.constants.DMessage import DMessage
from r3el.zmq.ZMQMsg import ZMQMsg


class MessageHandler:
    def __init__(self, submission: Callable[[ZMQMsg], dict], batch: Callable[[ZMQMsg], dict]) -> None:
        self._routes = {
            (DMessage.IDENTIFICATION, DMessage.SUBMIT_IDENTIFICATION): submission,
            (DMessage.BATCH, DMessage.NEW_BATCH): batch,
        }

    def handle(self, request: ZMQMsg) -> dict:
        handler = self._routes.get((request.target, request.method))
        if handler is None:
            return {'status': DMessage.ERROR, 'error': {'code': DMessage.UNKNOWN_REQUEST}}
        return handler(request)
