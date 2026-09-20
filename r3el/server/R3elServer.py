"""An idle service to establish the R3el deployment lifecycle."""

import signal
from threading import Event


def main():
    stopped = Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    print("R3el server started (idle).", flush=True)
    stopped.wait()
    print("R3el server stopped.", flush=True)


if __name__ == "__main__":
    main()
