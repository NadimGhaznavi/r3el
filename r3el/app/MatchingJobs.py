"""Run one matching job at a time and expose its completion status."""

from collections.abc import Callable
import logging
from threading import Lock, Thread
from uuid import uuid4

import pymysql

from r3el.interface.WorkspaceDb import WorkspaceActionConflict, WorkspaceBusy
from r3el.entity.BatchStopped import BatchStopped


class MatchingJobs:
    def __init__(self, execute: Callable[..., None]) -> None:
        self._execute = execute
        self._lock = Lock()
        self._job = None
        self._thread = None
        self._closed = False

    def submit(self, batch_id: str, *, file_id: str | None = None, movie_id: int | None = None,
               replace_media: bool = False) -> dict | None:
        with self._lock:
            if self._closed:
                return None
            if self._job is not None and self._job['status'] == 'running':
                return (dict(self._job) if self._job['batch_id'] == batch_id
                        and self._job.get('file_id') == file_id and self._job.get('movie_id') == movie_id
                        and self._job.get('replace_media', False) == replace_media else None)
            self._job = {'id': str(uuid4()), 'batch_id': batch_id, 'status': 'running'}
            if file_id is not None:
                self._job.update(file_id=file_id, movie_id=movie_id)
            if replace_media:
                self._job['replace_media'] = True
            self._thread = Thread(target=self._run, args=(batch_id, file_id, movie_id, replace_media), name='r3el-matching')
            self._thread.start()
            return dict(self._job)

    def current(self) -> dict | None:
        with self._lock:
            return dict(self._job) if self._job is not None else None

    def _run(self, batch_id: str, file_id: str | None, movie_id: int | None, replace_media: bool) -> None:
        status = 'failed'
        try:
            if replace_media:
                self._execute(batch_id, file_id=file_id, replace_media=True)
            elif file_id is None:
                self._execute(batch_id)
            else:
                self._execute(batch_id, file_id=file_id, movie_id=movie_id)
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
