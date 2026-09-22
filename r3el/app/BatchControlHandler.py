"""Validate control messages and submit work without blocking the listener."""

from collections.abc import Callable

from r3el.constants.DMessage import DMessage
from r3el.entity.BatchRequest import BatchRequest
from r3el.interface.BatchConfiguration import BatchConfiguration
from r3el.zmq.ZMQMsg import ZMQMsg


class BatchControlHandler:
    def __init__(self, submit: Callable[[BatchRequest], bool], configured: bool) -> None:
        self._submit = submit
        self._configured = configured

    def handle(self, request: ZMQMsg) -> dict:
        if (request.sender != DMessage.CONTROL or request.target != DMessage.BATCH
                or request.method != DMessage.NEW_BATCH):
            return {'status': DMessage.ERROR, 'error': {'code': DMessage.UNKNOWN_REQUEST}}
        try:
            parameters = BatchConfiguration.resolve(request.payload)
        except ValueError as error:
            return {'status': DMessage.ERROR, 'error': {
                'code': DMessage.INVALID_PARAMETERS, 'message': str(error),
            }}
        if not self._configured:
            return {'status': DMessage.ERROR, 'error': {'code': DMessage.NOT_CONFIGURED}}
        if not self._submit(parameters):
            return {'status': DMessage.BUSY}
        return {'status': DMessage.ACCEPTED}
