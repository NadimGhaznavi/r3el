"""Start a fresh filename conversation after a zero-result TMDB search."""

import asyncio
from dataclasses import asdict, replace

from r3el.activity.EventWriter import EventWriter
from r3el.app.SubmissionHandler import SubmissionHandler
from r3el.app.ToolConversation import ToolConversation
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.constants.DR3el import DR3el
from r3el.entity.Identification import Identification
from r3el.entity.MediaFile import MediaFile, MediaFileIssue, MediaFileState
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.interface.DbMgr import DbMgr
from r3el.interface.EventLogDb import EventLogDb
from r3el.interface.LLM import LLM
from r3el.interface.WorkspaceDb import WorkspaceDb
from r3el.zmq.ZMQServer import ZMQServer


class RetryIdentification:
    def __init__(self, workspace: WorkspaceDb, llm: LLM | None = None) -> None:
        self._workspace = workspace
        self._llm = llm

    @staticmethod
    def _record_submission(event) -> int:
        # The ZeroMQ listener owns a separate connection from the matching worker.
        db = DbMgr()
        try:
            return EventLogDb(db).record(event)
        finally:
            db.close()

    def run(self, item: MediaFile, log: EventWriter) -> None:
        item.retries += 1
        log = EventWriter(log.record, {**log.context, 'retries': item.retries}, log.parent_event_id)
        item.tmdb_match = replace(item.tmdb_match, selection_pending=True)
        self._save(item, log, Names.ITEM_STARTED)
        handler = SubmissionHandler(self._record_submission)
        try:
            with ZMQServer('tcp://127.0.0.1:*', handler.handle) as listener:
                result = asyncio.run(ToolConversation(self._llm or LLM.from_environment(),
                    listener.endpoint, handler, log).run())
        except BaseException:
            item.tmdb_match = replace(item.tmdb_match, selection_pending=False)
            self._save(item, log, Names.ITEM_COMPLETED)
            raise
        item.attempts += result['attempts']
        item.state = MediaFileState(result['status'])
        if item.state == MediaFileState.IDENTIFIED:
            item.identification = Identification(**result['identification'])
            item.issues = []
            item.tmdb_match = None
            item.action = (MediaFileAction.APPROVE if item.identification.confidence == DR3el.AUTO_APPROVE_CONFIDENCE
                           else MediaFileAction.PENDING)
        else:
            item.issues = [MediaFileIssue('unresolved_llm', result['reason'])]
            item.action = MediaFileAction.PENDING
            item.tmdb_match = replace(item.tmdb_match, selection_pending=False)
        self._save(item, log, Names.ITEM_COMPLETED)

    def exhausted(self, item: MediaFile, log: EventWriter) -> None:
        item.state = MediaFileState.UNRESOLVED_LLM
        item.action = MediaFileAction.PENDING
        item.issues = [MediaFileIssue('unresolved_llm', 'No TMDB matches after three identification retries.')]
        item.tmdb_match = replace(item.tmdb_match, selection_pending=False)
        self._save(item, log, Names.ITEM_COMPLETED)

    def _save(self, item: MediaFile, log: EventWriter, name: str) -> None:
        event = log.prepare(Categories.Batch.BATCH_IDENTIFICATION, name,
                            {'status': item.state, 'retries': item.retries, 'attempts': item.attempts,
                             'issues': [asdict(issue) for issue in item.issues]}, source='RetryIdentification')
        self._workspace.save_file(log.context['batch_id'], item, event)
