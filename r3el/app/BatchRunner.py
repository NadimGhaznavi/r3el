"""Compose identification resources for each new control-requested batch."""

from r3el.app.BatchIdentification import BatchIdentification
from r3el.app.SubmissionHandler import SubmissionHandler
from r3el.entity.BatchRequest import BatchRequest
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
        # Each batch gets a fresh connection after potentially long idle periods.
        db = DbMgr()
        try:
            await BatchIdentification(
                FileMgr(request.input_directory), LLM(self._llm_url), self.endpoint,
                self._submissions, EventLogDb(db).record, WorkspaceDb(db),
            ).run(request.batch_size, destination_directory=request.output_directory, new_batch=True)
        finally:
            db.close()
