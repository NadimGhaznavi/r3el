"""Validate MCP submissions inside R3el and return corrective feedback."""

from dataclasses import asdict
import json
from threading import Lock

from r3el.constants.DMessage import DMessage
from r3el.activity.EventWriter import EventWriter
from r3el.app.ValidateIdentification import ValidateIdentification
from r3el.app.prompts.InvalidIdentification import InvalidIdentification
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.zmq.ZMQMsg import ZMQMsg


class SubmissionHandler:
    def __init__(self, record) -> None:
        self._record = record
        self._attempts = {}
        self._lock = Lock()

    def register(self, context: dict, parent_event_id: int) -> None:
        with self._lock:
            self._attempts[context['attempt_id']] = EventWriter(self._record, context, parent_event_id)

    def unregister(self, attempt_id: str) -> None:
        with self._lock:
            del self._attempts[attempt_id]

    def handle(self, request: ZMQMsg) -> dict:
        if request.target != DMessage.IDENTIFICATION or request.method != DMessage.SUBMIT_IDENTIFICATION:
            return {'status': 'error', 'reason': 'Unknown target or method.'}
        attempt_id = request.payload.get('attempt_id')
        if not isinstance(attempt_id, str):
            return {'status': 'error', 'reason': 'Missing attempt identifier.'}
        with self._lock:
            log = self._attempts.get(attempt_id)
        if log is None:
            return {'status': 'error', 'reason': 'No active identification attempt.'}
        data = request.payload.get('submission')
        log.write(Categories.Prompt.SUBMISSION_HANDLER, Names.TOOL_RECEIVED, data, source='SubmissionHandler')
        try:
            identification = ValidateIdentification().run(data)
        except ValueError as error:
            prompt = InvalidIdentification(str(error))
            result = {'status': 'rejected', 'reason': str(error),
                      'prompt': json.loads(prompt.to_json()), 'source_name': prompt.source_name}
            log.write(Categories.Prompt.SUBMISSION_HANDLER, Names.SUBMISSION_REJECTED,
                      result, source='SubmissionHandler')
            return result
        result = {'status': 'ok', 'identification': asdict(identification)}
        log.write(Categories.Prompt.SUBMISSION_HANDLER, Names.SUBMISSION_ACCEPTED,
                  result, source='SubmissionHandler')
        return result
