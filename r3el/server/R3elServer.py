"""An idle service to establish the R3el deployment lifecycle."""

import signal
import time
from threading import Event

from r3el.activity.ServerLifecycle import ServerLifecycle
from r3el.interface.DbMgr import DbMgr
from r3el.interface.EventLogDb import EventLogDb


def main() -> None:
    stopped = Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    db = DbMgr()
    try:
        lifecycle = ServerLifecycle(EventLogDb(db))
        lifecycle.started()
        print("R3el server started (idle).", flush=True)
        while not stopped.is_set():
            time.sleep(1)
        lifecycle.stopped()
        print("R3el server stopped.", flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
