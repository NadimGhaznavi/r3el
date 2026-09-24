"""Run one control-requested batch at a time on the application loop."""

import asyncio
from collections.abc import Awaitable, Callable
import logging
from threading import Lock

import httpx
import pymysql

from r3el.entity.BatchRequest import BatchRequest
from r3el.interface.WorkspaceDb import WorkspaceBusy, WorkspaceOccupied


class BatchProcessor:
    def __init__(self, execute: Callable[[BatchRequest], Awaitable[None]],
                 *, startup: Callable[[], Awaitable[None]] | None = None) -> None:
        self._execute = execute
        self._startup = startup
        self._loop = asyncio.get_running_loop()
        self._queue: asyncio.Queue[BatchRequest] = asyncio.Queue(maxsize=1)
        self._lock = Lock()
        self._busy = startup is not None
        self._closed = False

    def submit(self, request: BatchRequest) -> bool:
        """Reserve the processor from the listener thread; never queue extra work."""
        with self._lock:
            if self._busy or self._closed:
                return False
            self._busy = True
            self._loop.call_soon_threadsafe(self._queue.put_nowait, request)
        return True

    async def run(self) -> None:
        try:
            if self._startup is not None:
                try:
                    await self._startup()
                finally:
                    with self._lock:
                        self._busy = False
            while True:
                request = await self._queue.get()
                try:
                    await self._execute(request)
                except (OSError, httpx.HTTPError, pymysql.OperationalError, pymysql.InterfaceError,
                        WorkspaceOccupied, WorkspaceBusy):
                    logging.exception('Batch failed; returning to idle')
                finally:
                    with self._lock:
                        self._busy = False
                    self._queue.task_done()
        finally:
            with self._lock:
                self._closed = True
