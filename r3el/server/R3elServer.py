"""Run the MCP/ZeroMQ listener, idle until work is requested."""

import argparse
import asyncio
import json
import os
import signal

from r3el.activity.ServerLifecycle import ServerLifecycle
from r3el.app.BatchIdentification import BatchIdentification
from r3el.app.BatchControlHandler import BatchControlHandler
from r3el.app.BatchProcessor import BatchProcessor
from r3el.app.BatchRunner import BatchRunner
from r3el.app.MessageHandler import MessageHandler
from r3el.app.SubmissionHandler import SubmissionHandler
from r3el.constants.DR3el import DR3el
from r3el.interface.DbMgr import DbMgr
from r3el.interface.EventLogDb import EventLogDb
from r3el.interface.FileMgr import FileMgr
from r3el.interface.LLM import LLM
from r3el.interface.WorkspaceDb import WorkspaceDb
from r3el.zmq.ZMQServer import ZMQServer


def record_event(event) -> int:
    # Lifecycle and listener events own fresh connections, including after long idle periods.
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
    lifecycle = ServerLifecycle(record_event)
    try:
        lifecycle.started()
        print('R3el server started.', flush=True)
        try:
            submissions = SubmissionHandler(record_event)
            runner = BatchRunner(args.llm_url, args.zmq_endpoint, submissions)
            processor = BatchProcessor(runner.run, startup=runner.resume if args.llm_url and not args.run_batch else None)
            control = BatchControlHandler(processor.submit, bool(args.llm_url) and not args.run_batch)
            messages = MessageHandler(submissions.handle, control.handle)
            with ZMQServer(args.zmq_endpoint, messages.handle) as listener:
                runner.endpoint = listener.endpoint
                if args.run_batch:
                    db = DbMgr()
                    try:
                        results = await BatchIdentification(
                            FileMgr(args.film_dir), LLM(args.llm_url), listener.endpoint,
                            submissions, EventLogDb(db).record, WorkspaceDb(db),
                        ).run(args.batch_size)
                        print(json.dumps(results, ensure_ascii=False), flush=True)
                    finally:
                        db.close()
                else:
                    await processor.run()
        finally:
            lifecycle.stopped()
            print('R3el server stopped.', flush=True)
    finally:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-batch', action='store_true',
                        help='Explicitly run one batch and exit (manual diagnostics).')
    parser.add_argument('--llm-url', default=os.environ.get('R3EL_LLM_URL'))
    parser.add_argument('--film-dir', default=DR3el.FILM_DIR)
    parser.add_argument('--batch-size', type=int, default=DR3el.BATCH_SIZE)
    parser.add_argument('--zmq-endpoint', default=DR3el.ZMQ_ENDPOINT)
    args = parser.parse_args()
    if args.run_batch and not args.llm_url:
        parser.error('Supply --llm-url or R3EL_LLM_URL.')
    if args.batch_size < 1:
        parser.error('--batch-size must be positive.')
    try:
        asyncio.run(run(args))
    except asyncio.CancelledError:
        pass


if __name__ == '__main__':
    main()
