"""Coordinate one filename's prompts, tool calls, and bounded corrections."""

import asyncio
import json
import math
from uuid import uuid4

from r3el.activity.EventWriter import EventWriter
from r3el.app.prompts.CurrentDate import CurrentDate
from r3el.app.prompts.FileContext import FileContext
from r3el.app.prompts.SubmitIdentificationPrompt import SubmitIdentificationPrompt
from r3el.app.prompts.InvalidIdentification import InvalidIdentification
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.constants.DR3el import DR3el
from r3el.interface.IdentificationTools import IdentificationTools


def finite_number(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('Use finite JSON numbers.')
    return number


class ToolConversation:
    def __init__(self, llm, endpoint: str, handler, log: EventWriter) -> None:
        self._llm, self._endpoint, self._handler, self._log = llm, endpoint, handler, log

    @staticmethod
    def _tool_call(body: str) -> tuple[dict, dict, dict]:
        try:
            response = json.loads(body)
            message = response['choices'][0]['message']
            calls = message['tool_calls']
            if not isinstance(calls, list) or len(calls) != 1:
                raise ValueError('Return exactly one tool call.')
            call = calls[0]
            if call['function']['name'] != 'submit_identification':
                raise ValueError('Call submit_identification.')
            if not isinstance(call['id'], str) or not call['id']:
                raise ValueError('Tool call must have an identifier.')
            arguments = json.loads(call['function']['arguments'],
                                   parse_constant=finite_number, parse_float=finite_number)
            if not isinstance(arguments, dict) or set(arguments) != {'title', 'year', 'confidence'}:
                raise ValueError('Supply exactly title, year, and confidence.')
            return message, call, arguments
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError('Return a tool call containing title, year, and confidence.') from error

    async def run(self) -> dict:
        messages = []
        for prompt in (CurrentDate(), FileContext(self._log.context['filename']),
                       SubmitIdentificationPrompt()):
            message = json.loads(prompt.to_json())
            messages.append(message)
            self._log.write(Categories.Prompt.LLM_PROMPT, Names.PROMPT_SENT,
                            message, source=prompt.source_name)
        reason = ''
        for attempt in range(1, DR3el.MAX_LLM_RETRIES + 2):
            context = {**self._log.context, 'attempt': attempt, 'attempt_id': str(uuid4())}
            attempt_log = EventWriter(self._log.record, context, self._log.parent_event_id)
            parent = attempt_log.write(Categories.Prompt.TOOL_CONVERSATION,
                                       Names.ATTEMPT_STARTED, {}, source='ToolConversation')
            attempt_log.parent_event_id = parent
            self._handler.register(context, parent)
            try:
                async with IdentificationTools(self._endpoint, context['attempt_id']) as tools:
                    body = await self._llm.complete({
                        'messages': messages, 'tools': [tools.definition],
                        'tool_choice': 'required', 'parallel_tool_calls': False, 'stream': False,
                    })
                    attempt_log.write(Categories.Prompt.TOOL_CONVERSATION, Names.REPLY_RECEIVED,
                                      body, source='LLM')
                    try:
                        message, call, arguments = self._tool_call(body)
                    except ValueError as error:
                        reason = str(error)
                        attempt_log.write(Categories.Prompt.SUBMISSION_HANDLER, Names.SUBMISSION_REJECTED,
                                          {'reason': reason}, source='ToolConversation')
                    else:
                        messages.append(message)
                        attempt_log.write(Categories.Prompt.TOOL_CONVERSATION, Names.TOOL_STARTED,
                                          call, source='ToolConversation')
                        result = await tools.submit(arguments)
                        attempt_log.write(Categories.Prompt.TOOL_CONVERSATION, Names.TOOL_COMPLETED,
                                          result, source='ToolConversation')
                        if result['status'] == 'ok':
                            return {'status': 'identified', 'attempts': attempt,
                                    'identification': result['identification']}
                        if result['status'] != 'rejected':
                            raise RuntimeError(f'Server could not process the submission: {result}')
                        messages.append({'role': 'tool', 'tool_call_id': call['id'],
                                         'content': json.dumps(result, ensure_ascii=False)})
                        reason = result['reason']
                    if attempt <= DR3el.MAX_LLM_RETRIES:
                        prompt = InvalidIdentification(reason)
                        feedback = json.loads(prompt.to_json())
                        messages.append(feedback)
                        attempt_log.write(Categories.Prompt.LLM_PROMPT, Names.PROMPT_SENT,
                                          feedback, source=prompt.source_name)
            except asyncio.CancelledError:
                attempt_log.write(Categories.Prompt.TOOL_CONVERSATION, Names.ATTEMPT_CANCELLED,
                                  {}, source='ToolConversation', level='WARNING')
                raise
            except Exception as error:
                attempt_log.write(Categories.Prompt.TOOL_CONVERSATION, Names.ATTEMPT_FAILED,
                                  {'error': str(error)}, source='ToolConversation', level='ERROR')
                raise
            finally:
                self._handler.unregister(context['attempt_id'])
        return {'status': 'unresolved_llm', 'attempts': DR3el.MAX_LLM_RETRIES + 1, 'reason': reason}
