"""Serial request/reply transport; application handlers own validation and actions."""

from collections.abc import Callable
from threading import Event, Thread
import traceback

import zmq

from r3el.constants.DZMQ import DZMQ
from r3el.zmq.ZMQMsg import ZMQMsg


class ZMQServer:
    def __init__(self, endpoint: str, handler: Callable[[ZMQMsg], dict]):
        self.endpoint = endpoint
        self._handler = handler
        self._ready = Event()
        self._stop = Event()
        self._error: BaseException | None = None
        self._thread = Thread(target=self._serve, name="r3el-zmq", daemon=True)

    def __enter__(self):
        self._thread.start()
        self._ready.wait()
        if self._error is not None:
            self._thread.join()
            raise self._error
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()
        if self._error is not None:
            raise self._error

    def _serve(self) -> None:
        # The listener thread creates, uses, and closes its own socket/context.
        try:
            with zmq.Context() as context:
                with context.socket(zmq.REP) as socket:
                    socket.setsockopt(zmq.LINGER, 0)
                    socket.setsockopt(zmq.SNDTIMEO, int(DZMQ.TIMEOUT_SECONDS * 1000))
                    socket.bind(self.endpoint)
                    self.endpoint = socket.getsockopt_string(zmq.LAST_ENDPOINT)
                    self._ready.set()
                    while not self._stop.is_set():
                        if not socket.poll(DZMQ.POLL_MS):
                            continue
                        frames = socket.recv_multipart()
                        request = None
                        try:
                            if len(frames) != 1:
                                raise ValueError("Expected one JSON message frame")
                            request = ZMQMsg.from_json(frames[0])
                        except (ValueError, TypeError, KeyError) as error:
                            payload = {"status": "error", "error": {
                                "code": "invalid_request", "message": str(error),
                            }}
                        else:
                            try:
                                payload = self._handler(request)
                            except Exception:
                                traceback.print_exc()
                                payload = {"status": "error", "error": {
                                    "code": "handler_error",
                                    "message": "R3el could not complete the request. Do not automatically retry; submission may have occurred.",
                                }}
                        reply = ZMQMsg(sender="r3el", target=request.sender if request else None,
                                       method=request.method if request else "error", payload=payload)
                        socket.send(reply.to_json())
        except BaseException as error:
            self._error = error
        finally:
            self._ready.set()
