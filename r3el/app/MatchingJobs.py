"""Run one matching job at a time and expose its completion status."""

from collections.abc import Callable
import logging
from threading import Lock, Thread
from uuid import uuid4

import pymysql

from r3el.interface.WorkspaceDb import WorkspaceActionConflict, WorkspaceBusy
from r3el.entity.BatchStopped import BatchStopped


class MatchingJobs:
    def __init__(self, execute: Callable[[str], None]) -> None:
        self._execute = execute
        self._lock = Lock()
        self._job = None
        self._thread = None
        self._closed = False

    def submit(self, batch_id: str) -> dict | None:
        with self._lock:
            if self._closed:
                return None
            if self._job is not None and self._job['status'] == 'running':
                return dict(self._job) if self._job['batch_id'] == batch_id else None
            self._job = {'id': str(uuid4()), 'batch_id': batch_id, 'status': 'running'}
            self._thread = Thread(target=self._run, args=(batch_id,), name='r3el-matching')
            self._thread.start()
            return dict(self._job)

    def current(self) -> dict | None:
        with self._lock:
            return dict(self._job) if self._job is not None else None

    def _run(self, batch_id: str) -> None:
        status = 'failed'
        try:
            self._execute(batch_id)
            status = 'completed'
        except BatchStopped:
            status = 'cancelled'
        except (WorkspaceActionConflict, WorkspaceBusy, pymysql.MySQLError):
            logging.exception('Background matching failed')
        finally:
            # Unexpected errors still reach the thread exception hook and journal.
            with self._lock:
                self._job['status'] = status

    def close(self) -> None:
        with self._lock:
            self._closed = True
            thread = self._thread
        if thread is not None:
            thread.join()
