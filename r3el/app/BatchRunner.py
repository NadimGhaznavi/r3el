"""Run identification and matching for each explicitly requested new batch."""

import asyncio

from r3el.activity.EventWriter import EventWriter
from r3el.app.BatchIdentification import BatchIdentification
from r3el.app.BatchMatching import BatchMatching
from r3el.app.SubmissionHandler import SubmissionHandler
from r3el.constants.DR3el import DR3el
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.entity.BatchRequest import BatchRequest
from r3el.entity.BatchStopped import BatchStopped
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
        try:
            await self._run(request)
        except BatchStopped:
            # The stage that observed the request already checkpointed cancellation.
            return

    async def resume(self) -> None:
        db = DbMgr()
        try:
            workspace = WorkspaceDb(db)
            with workspace.processing():
                batch = workspace.load()
                if batch is None or not batch.in_progress:
                    return
                request = BatchRequest(batch.source_directory, batch.destination_directory, batch.requested_size)
        finally:
            db.close()
        try:
            await self._run(request, resume_id=batch.id)
        except BatchStopped:
            return

    async def _run(self, request: BatchRequest, *, resume_id: str | None = None) -> None:
        offset = 0
        while True:
            db = DbMgr()
            try:
                workspace = WorkspaceDb(db)
                await BatchIdentification(
                    FileMgr(request.input_directory), LLM(self._llm_url), self.endpoint,
                    self._submissions, EventLogDb(db).record, workspace,
                ).run(request.batch_size, destination_directory=request.output_directory,
                      new_batch=offset == 0 and resume_id is None, offset=offset,
                      expected_batch_id=resume_id, limit=DR3el.PROCESSING_GROUP_SIZE,
                      completion_state=MediaFileBatchState.MATCHING)
                batch = workspace.load()
                group = batch.files[offset:offset + DR3el.PROCESSING_GROUP_SIZE]
                finished = offset + DR3el.PROCESSING_GROUP_SIZE >= len(batch.files)
            finally:
                db.close()
            # The matching thread owns its connection and async MCP conversations.
            # Await the whole group, including selection and retries, before advancing.
            matching = asyncio.create_task(asyncio.to_thread(self._match, batch.id, [item.id for item in group], finished))
            try:
                await asyncio.shield(matching)
            except asyncio.CancelledError:
                # Keep the listener available until the matching thread checkpoints.
                try:
                    await matching
                finally:
                    raise
            if finished:
                return
            offset += DR3el.PROCESSING_GROUP_SIZE

    def _match(self, batch_id: str, file_ids: list[str], finished: bool) -> None:
        db = DbMgr()
        try:
            workspace = WorkspaceDb(db)
            batch = workspace.load()
            log = EventWriter(EventLogDb(db).record, {'batch_id': batch_id}, batch.started_event_id)
            try:
                if file_ids:
                    BatchMatching(workspace, log.record, LLM(self._llm_url)).run(batch_id, file_ids=file_ids)
            except BatchStopped:
                raise
            except BaseException as error:
                workspace.save_batch_state(batch_id, MediaFileBatchState.MATCHING_FAILED,
                    log.prepare(Categories.Batch.LIFECYCLE, Names.BATCH_FAILED,
                                {'stage': 'matching', 'error': str(error)}, source='BatchRunner', level='ERROR'))
                raise
            if not finished:
                return
            workspace.save_batch_state(batch_id, MediaFileBatchState.MATCHING_COMPLETED,
                log.prepare(Categories.Batch.LIFECYCLE, Names.BATCH_COMPLETED,
                            {'stage': 'matching', 'count': len(batch.files),
                             'unresolved_llm': sum(item.state == MediaFileState.UNRESOLVED_LLM
                                                   for item in workspace.load().files)}, source='BatchRunner'))
        finally:
            db.close()
