"""Run identification and matching for each explicitly requested new batch."""

import asyncio

from r3el.activity.EventWriter import EventWriter
from r3el.app.BatchIdentification import BatchIdentification
from r3el.app.BatchMatching import BatchMatching
from r3el.app.SubmissionHandler import SubmissionHandler
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.entity.BatchRequest import BatchRequest
from r3el.entity.MediaFileBatch import MediaFileBatchState
from r3el.entity.MediaFile import MediaFileState
from r3el.interface.DbMgr import DbMgr
from r3el.interface.EventLogDb import EventLogDb
from r3el.interface.FileMgr import FileMgr
from r3el.interface.LLM import LLM
from r3el.interface.WorkspaceDb import WorkspaceDb


class BatchRunner:
    def __init__(self, llm_url: str, endpoint: str, submissions: SubmissionHandler) -> None:
        self._llm_url = llm_url
        self.endpoint = endpoint
        self._submissions = submissions

    async def run(self, request: BatchRequest) -> None:
        db = DbMgr()
        try:
            workspace = WorkspaceDb(db)
            await BatchIdentification(
                FileMgr(request.input_directory), LLM(self._llm_url), self.endpoint,
                self._submissions, EventLogDb(db).record, workspace,
            ).run(request.batch_size, destination_directory=request.output_directory, new_batch=True,
                  completion_state=MediaFileBatchState.MATCHING)
            batch_id = workspace.load().id
        finally:
            db.close()
        # Matching uses synchronous TMDB and its own async MCP conversations.
        # Its thread owns a fresh connection, while the server listener stays responsive.
        await asyncio.to_thread(self._match, batch_id)

    def _match(self, batch_id: str) -> None:
        db = DbMgr()
        try:
            workspace = WorkspaceDb(db)
            batch = workspace.load()
            log = EventWriter(EventLogDb(db).record, {'batch_id': batch_id}, batch.started_event_id)
            try:
                if batch.files:
                    BatchMatching(workspace, log.record, LLM(self._llm_url)).run(batch_id)
            except BaseException as error:
                workspace.save_batch_state(batch_id, MediaFileBatchState.MATCHING_FAILED,
                    log.prepare(Categories.Batch.LIFECYCLE, Names.BATCH_FAILED,
                                {'stage': 'matching', 'error': str(error)}, source='BatchRunner', level='ERROR'))
                raise
            workspace.save_batch_state(batch_id, MediaFileBatchState.MATCHING_COMPLETED,
                log.prepare(Categories.Batch.LIFECYCLE, Names.BATCH_COMPLETED,
                            {'stage': 'matching', 'count': len(batch.files),
                             'unresolved_llm': sum(item.state == MediaFileState.UNRESOLVED_LLM
                                                   for item in workspace.load().files)}, source='BatchRunner'))
        finally:
            db.close()
