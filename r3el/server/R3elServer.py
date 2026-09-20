"""An idle service to establish the R3el deployment lifecycle."""

import signal
import time
from threading import Event


def main() -> None:
    stopped = Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    print("R3el server started (idle).", flush=True)
    while not stopped.is_set():
        time.sleep(1)
    print("R3el server stopped.", flush=True)


if __name__ == "__main__":
    main()
