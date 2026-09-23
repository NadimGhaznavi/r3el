"""Validate a choice against the server-owned selection attempt."""

from r3el.constants.DMessage import DMessage
from r3el.zmq.ZMQMsg import ZMQMsg


class MultipleChoiceHandler:
    def __init__(self, attempt_id: str, candidate_count: int) -> None:
        self._attempt_id = attempt_id
        self._candidate_count = candidate_count
        self._accepted = False

    def handle(self, request: ZMQMsg) -> dict:
        if (request.target != DMessage.MULTIPLE_CHOICE
                or request.method != DMessage.SUBMIT_MULTIPLE_CHOICE):
            return {'status': 'error', 'reason': 'Unknown target or method.'}
        if request.payload.get('attempt_id') != self._attempt_id or self._accepted:
            return {'status': 'error', 'reason': 'No active multiple-choice attempt.'}
        submission = request.payload.get('submission')
        if not isinstance(submission, dict) or set(submission) != {'number'}:
            return {'status': 'rejected', 'reason': 'Supply exactly number.'}
        number = submission['number']
        if type(number) is not int or not 0 <= number <= self._candidate_count:
            return {'status': 'rejected',
                    'reason': f'Number must be an integer from 0 to {self._candidate_count}.'}
        self._accepted = True
        return {'status': 'ok', 'selected_number': number}
