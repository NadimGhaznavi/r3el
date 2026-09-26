"""Select a numbered TMDB candidate while retaining ambiguous failures."""

import asyncio
from dataclasses import replace
import json
from uuid import uuid4

import httpx

from r3el.activity.EventWriter import EventWriter
from r3el.app.MultipleChoiceHandler import MultipleChoiceHandler
from r3el.app.prompts.CurrentDate import CurrentDate
from r3el.app.prompts.Example import Example
from r3el.app.prompts.MultipleChoice import MultipleChoice
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.interface.LLM import LLM
from r3el.interface.MCPTools import MCPTools
from r3el.constants.DMessage import DMessage
from r3el.zmq.ZMQServer import ZMQServer


class MovieSelection:
    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    def run(self, match: TMDBMatch, log: EventWriter) -> TMDBMatch:
        attempt_id = str(uuid4())
        log = EventWriter(log.record, {**log.context, 'attempt_id': attempt_id}, log.parent_event_id)
        candidates = [(movie.get('title') or movie.get('name') or movie.get('original_title') or movie.get('original_name') or '',
                       movie.get('overview') or '', movie.get('vote_count')) for movie in match.response['results']]
        messages = []
        for prompt in (CurrentDate(), *([] if match.media_type == 'tv' else [Example()]), MultipleChoice(match.title, match.year, candidates, media_type=match.media_type)):
            message = json.loads(prompt.to_json())
            messages.append(message)
            log.write(Categories.Prompt.LLM_PROMPT, Names.PROMPT_SENT,
                      message, source=prompt.source_name)
        handler = MultipleChoiceHandler(attempt_id, len(candidates))
        with ZMQServer('tcp://127.0.0.1:*', handler.handle) as listener:
            return asyncio.run(self._select(match, messages, log, listener.endpoint, attempt_id))

    async def _select(self, match: TMDBMatch, messages: list[dict], log: EventWriter,
                      endpoint: str, attempt_id: str) -> TMDBMatch:
        async with MCPTools(endpoint, attempt_id, DMessage.SUBMIT_MULTIPLE_CHOICE) as tools:
            try:
                body = await self._llm.complete({
                    'messages': messages, 'tools': [tools.definition], 'tool_choice': 'required',
                    'parallel_tool_calls': False, 'stream': False,
                })
            except httpx.HTTPError:
                return replace(match, selection_error='Unable to complete the LLM movie selection.')
            log.write(Categories.Prompt.TOOL_CONVERSATION, Names.REPLY_RECEIVED,
                      body, source='MovieSelection')
            try:
                call, arguments = self._tool_call(body)
            except ValueError as error:
                log.write(Categories.Prompt.SUBMISSION_HANDLER, Names.SUBMISSION_REJECTED,
                          {'reason': str(error)}, source='MovieSelection')
                return replace(match, selection_error=str(error))
            log.write(Categories.Prompt.TOOL_CONVERSATION, Names.TOOL_STARTED,
                      call, source='MovieSelection')
            result = await tools.submit(arguments)
            log.write(Categories.Prompt.TOOL_CONVERSATION, Names.TOOL_COMPLETED,
                      result, source='MovieSelection')
            # Record on the caller's thread, which owns the workspace DB connection.
            log.write(Categories.Prompt.SUBMISSION_HANDLER, Names.TOOL_RECEIVED,
                      arguments, source='MultipleChoiceHandler')
            if result['status'] != 'ok':
                log.write(Categories.Prompt.SUBMISSION_HANDLER, Names.SUBMISSION_REJECTED,
                          result, source='MultipleChoiceHandler')
                return replace(match, selection_error=result.get('reason', 'Movie selection submission failed.'))
            log.write(Categories.Prompt.SUBMISSION_HANDLER, Names.SUBMISSION_ACCEPTED,
                      result, source='MultipleChoiceHandler')
            selected = replace(match, selected_number=result['selected_number'], selection_error=None)
            return replace(selected, response=selected.resolved_response)

    @staticmethod
    def _tool_call(body: str) -> tuple[dict, dict]:
        try:
            calls = json.loads(body)['choices'][0]['message']['tool_calls']
            if not isinstance(calls, list) or len(calls) != 1:
                raise ValueError('Return exactly one submit_multiple_choice tool call.')
            call = calls[0]
            if (call['function']['name'] != DMessage.SUBMIT_MULTIPLE_CHOICE
                    or not isinstance(call['id'], str) or not call['id']):
                raise ValueError('Return a submit_multiple_choice tool call with an identifier.')
            arguments = json.loads(call['function']['arguments'])
            if not isinstance(arguments, dict):
                raise ValueError('Supply the choice as a number field.')
            return call, arguments
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ValueError('The LLM did not return a valid submit_multiple_choice tool call.') from error
