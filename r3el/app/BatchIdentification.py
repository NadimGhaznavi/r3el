"""Identify the pending files in a persistent batch workspace."""

import asyncio
from dataclasses import asdict
from uuid import uuid4

from r3el.activity.EventWriter import EventWriter
from r3el.app.ToolConversation import ToolConversation
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.entity.Identification import Identification
from r3el.entity.BatchStopped import BatchStopped
from r3el.constants.DR3el import DR3el
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.entity.MediaFile import MediaFile, MediaFileIssue, MediaFileState
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState
from r3el.interface.WorkspaceDb import WorkspaceDb, WorkspaceOccupied


class BatchIdentification:
    def __init__(self, files, llm, endpoint, handler, record, workspace: WorkspaceDb) -> None:
        self._files, self._llm = files, llm
        self._endpoint, self._handler, self._record = endpoint, handler, record
        self._workspace = workspace

    async def run(self, batch_size: int, *, destination_directory: str | None = None,
                  new_batch: bool = False, offset: int = 0, limit: int | None = None,
                  expected_batch_id: str | None = None, ordinary_only: bool = False,
                  completion_state: MediaFileBatchState = MediaFileBatchState.IDENTIFICATION_COMPLETED) -> list[dict]:
        with self._workspace.processing():
            batch = self._workspace.load()
            if expected_batch_id is not None and (batch is None or batch.id != expected_batch_id):
                raise WorkspaceOccupied('The batch to resume is no longer in the workspace.')
            if new_batch and batch is not None:
                if batch.in_progress:
                    raise WorkspaceOccupied('The current batch is still running.')
                batch = None
            if batch is None:
                batch = self._create(batch_size, destination_directory, new_batch)
            elif batch.state == MediaFileBatchState.IDENTIFICATION_COMPLETED:
                return self._results(batch)
            else:
                self._set_state(batch, MediaFileBatchState.PROCESSING, Names.BATCH_RESUMED,
                                {'pending': sum(item.state == MediaFileState.PENDING for item in batch.files)})
            try:
                candidates = ([item for item in batch.files
                               if item.find_ls is None and item.source_directory is None]
                              if ordinary_only else batch.files)
                files = candidates[offset:] if limit is None else candidates[offset:offset + limit]
                for item in files:
                    self._workspace.check_stop(batch.id)
                    if item.state != MediaFileState.PENDING:
                        continue
                    await self._identify(batch, item)
                self._workspace.check_stop(batch.id)
                event_name = (Names.IDENTIFICATION_GROUP_COMPLETED if completion_state == MediaFileBatchState.MATCHING
                              else Names.BATCH_COMPLETED)
                self._set_state(batch, completion_state, event_name,
                                {'count': len(files),
                                 'unresolved_llm': sum(item.state == MediaFileState.UNRESOLVED_LLM
                                                       for item in files),
                                 'unresolved_hidden_file': sum(item.state == MediaFileState.UNRESOLVED_HIDDEN_FILE
                                                               for item in files)})
                return self._results(batch)
            except asyncio.CancelledError:
                # Service shutdown leaves the processing checkpoint resumable.
                raise
            except BatchStopped:
                self._set_state(batch, MediaFileBatchState.CANCELLED, Names.BATCH_CANCELLED, {}, 'WARNING')
                raise
            except Exception as error:
                self._set_state(batch, MediaFileBatchState.FAILED, Names.BATCH_FAILED,
                                {'error': str(error)}, 'ERROR')
                raise

    def _create(self, batch_size: int, destination_directory: str | None, new_batch: bool) -> MediaFileBatch:
        filenames = self._files.filenames(batch_size)
        batch = MediaFileBatch(
            id=str(uuid4()), requested_size=batch_size, source_directory=str(self._files.directory),
            destination_directory=destination_directory,
            files=[MediaFile(str(uuid4()), str(self._files.directory / name)) for name in filenames],
        )
        log = EventWriter(self._record, {'batch_id': batch.id})
        batch.started_event_id = self._workspace.create(
            batch,
            log.prepare(Categories.Batch.LIFECYCLE, Names.BATCH_STARTED,
                        {'batch_size': batch_size}, source='BatchIdentification'),
            log.prepare(Categories.Batch.DISCOVERY, Names.FILES_RETRIEVED, filenames, source='FileMgr'),
            replace_existing=new_batch,
        )
        return batch

    async def _identify(self, batch: MediaFileBatch, item: MediaFile) -> None:
        context = {'batch_id': batch.id, 'item_id': item.id, 'filename': item.filename}
        log = EventWriter(self._record, context, batch.started_event_id)
        log.parent_event_id = log.write(Categories.Batch.BATCH_IDENTIFICATION,
                                       Names.ITEM_STARTED, {}, source='BatchIdentification')
        if item.find_ls is None and self._files.is_hidden(item.filename):
            item.state = MediaFileState.UNRESOLVED_HIDDEN_FILE
            item.issues = [MediaFileIssue('hidden_file', 'Hidden filename; identification skipped.')]
        else:
            options = {'directory': item.directory_context} if item.find_ls is not None else {}
            result = await ToolConversation(self._llm, self._endpoint, self._handler, log, **options).run()
            item.state = MediaFileState(result['status'])
            item.attempts = result['attempts']
            if item.state == MediaFileState.IDENTIFIED:
                item.identification = Identification(**result['identification'])
                if item.find_ls is not None:
                    item.assign_parts(**result['parts'])
                item.issues = [issue for issue in item.issues if issue.code == 'unresolved_srt']
            else:
                item.issues = ([issue for issue in item.issues if issue.code == 'unresolved_srt']
                               + [MediaFileIssue('unresolved_llm', result['reason'])])
        item.action = (MediaFileAction.APPROVE if item.identification is not None
                       and item.identification.confidence == DR3el.AUTO_APPROVE_CONFIDENCE
                       else MediaFileAction.PENDING)
        event = log.prepare(Categories.Batch.BATCH_IDENTIFICATION, Names.ITEM_COMPLETED,
                            self._result(item), source='BatchIdentification')
        self._workspace.save_file(batch.id, item, event)

    def _set_state(self, batch: MediaFileBatch, state: MediaFileBatchState,
                   name: str, data: dict, level: str = 'INFO') -> None:
        log = EventWriter(self._record, {'batch_id': batch.id}, batch.started_event_id)
        category = (Categories.Batch.BATCH_IDENTIFICATION if name == Names.IDENTIFICATION_GROUP_COMPLETED
                    else Categories.Batch.LIFECYCLE)
        event = log.prepare(category, name, data,
                            source='BatchIdentification', level=level)
        self._workspace.save_batch_state(batch.id, state, event)
        batch.state = state

    @staticmethod
    def _result(item: MediaFile) -> dict:
        result = {'filename': item.filename, 'status': item.state, 'attempts': item.attempts,
                  'issues': [asdict(issue) for issue in item.issues]}
        if item.identification is not None:
            result['identification'] = asdict(item.identification)
        return result

    @classmethod
    def _results(cls, batch: MediaFileBatch) -> list[dict]:
        return [cls._result(item) for item in batch.files]
