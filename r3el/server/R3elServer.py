"""Run one identification batch with an MCP/ZeroMQ listener, then stop."""

import argparse
import asyncio
import json
import os
import signal

from r3el.activity.ServerLifecycle import ServerLifecycle
from r3el.app.BatchIdentification import BatchIdentification
from r3el.app.SubmissionHandler import SubmissionHandler
from r3el.constants.DR3el import DR3el
from r3el.interface.DbMgr import DbMgr
from r3el.interface.EventLogDb import EventLogDb
from r3el.interface.FileMgr import FileMgr
from r3el.interface.LLM import LLM
from r3el.interface.WorkspaceDb import WorkspaceDb
from r3el.zmq.ZMQServer import ZMQServer


def record_tool_event(event) -> int:
    # The listener thread owns its connections; never share the batch connection.
    db = DbMgr()
    try:
        return EventLogDb(db).record(event)
    finally:
        db.close()


async def run(args) -> None:
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, task.cancel)
    db = DbMgr()
    try:
        events = EventLogDb(db)
        lifecycle = ServerLifecycle(events)
        lifecycle.started()
        print('R3el server started (one batch).', flush=True)
        try:
            handler = SubmissionHandler(record_tool_event)
            with ZMQServer(args.zmq_endpoint, handler.handle) as listener:
                results = await BatchIdentification(
                    FileMgr(args.film_dir), LLM(args.llm_url), listener.endpoint, handler, events.record,
                    WorkspaceDb(db),
                ).run(args.batch_size)
                print(json.dumps(results, ensure_ascii=False), flush=True)
        finally:
            lifecycle.stopped()
            print('R3el server stopped.', flush=True)
    finally:
        db.close()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llm-url', default=os.environ.get('R3EL_LLM_URL'))
    parser.add_argument('--film-dir', default=DR3el.FILM_DIR)
    parser.add_argument('--batch-size', type=int, default=DR3el.BATCH_SIZE)
    parser.add_argument('--zmq-endpoint', default=DR3el.ZMQ_ENDPOINT)
    args = parser.parse_args()
    if not args.llm_url:
        parser.error('Supply --llm-url or R3EL_LLM_URL.')
    if args.batch_size < 1:
        parser.error('--batch-size must be positive.')
    try:
        asyncio.run(run(args))
    except asyncio.CancelledError:
        pass


if __name__ == '__main__':
    main()
