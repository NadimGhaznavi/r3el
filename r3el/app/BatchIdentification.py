"""Retrieve and identify a single batch, then return to the caller."""

import asyncio
from uuid import uuid4

from r3el.activity.EventWriter import EventWriter
from r3el.app.ToolConversation import ToolConversation
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names


class BatchIdentification:
    def __init__(self, files, llm, endpoint, handler, record) -> None:
        self._files, self._llm = files, llm
        self._endpoint, self._handler, self._record = endpoint, handler, record

    async def run(self, batch_size: int) -> list[dict]:
        batch_id = str(uuid4())
        log = EventWriter(self._record, {'batch_id': batch_id})
        log.parent_event_id = log.write(Categories.Batch.LIFECYCLE, Names.BATCH_STARTED,
                                       {'batch_size': batch_size}, source='BatchIdentification')
        try:
            filenames = self._files.filenames(batch_size)
            log.write(Categories.Batch.DISCOVERY, Names.FILES_RETRIEVED,
                      filenames, source='FileMgr')
            results = []
            for filename in filenames:
                context = {'batch_id': batch_id, 'item_id': str(uuid4()), 'filename': filename}
                item_log = EventWriter(self._record, context, log.parent_event_id)
                item_log.parent_event_id = item_log.write(Categories.Identification.CONVERSATION,
                    Names.ITEM_STARTED, {}, source='BatchIdentification')
                if self._files.is_hidden(filename):
                    result = {'status': 'unresolved_hidden_file', 'attempts': 0}
                else:
                    result = await ToolConversation(self._llm, self._endpoint, self._handler, item_log).run()
                item_log.write(Categories.Identification.RESULT, Names.ITEM_COMPLETED,
                               result, source='BatchIdentification')
                results.append({'filename': filename, **result})
            log.write(Categories.Batch.LIFECYCLE, Names.BATCH_COMPLETED,
                      {'count': len(results),
                       'unresolved_llm': sum(r['status'] == 'unresolved_llm' for r in results),
                       'unresolved_hidden_file': sum(r['status'] == 'unresolved_hidden_file' for r in results)},
                      source='BatchIdentification')
            return results
        except asyncio.CancelledError:
            log.write(Categories.Batch.LIFECYCLE, Names.BATCH_CANCELLED, {},
                      source='BatchIdentification', level='WARNING')
            raise
        except Exception as error:
            log.write(Categories.Batch.LIFECYCLE, Names.BATCH_FAILED, {'error': str(error)},
                      source='BatchIdentification', level='ERROR')
            raise
